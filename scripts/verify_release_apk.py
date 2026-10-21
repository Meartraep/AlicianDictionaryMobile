# -*- coding: utf-8 -*-
"""Validate a signed, ABI-specific release APK before it is published.

The release workflow (`.github/workflows/release-slsa.yml`) builds one APK per
ABI and publishes both, because AGP 9 cannot combine `splits.abi` with the
`ndk.abiFilters` setting that Chaquopy 17 requires. This guard fails the release
if the split silently regresses to a multi-ABI APK, if the jieba trimming in
`app/build.gradle.kts` stops working, or if the download size grows past its
budget:

    python scripts/verify_release_apk.py \\
        dist/AlicianDictionary-v1.11.0-arm64-v8a.apk --abi arm64-v8a
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

JIEBA_ARCHIVE = "assets/chaquopy/requirements-common.imy"
UNUSED_JIEBA_PREFIXES = ("jieba/lac_small/", "jieba/posseg/", "jieba/analyse/")
REQUIRED_JIEBA_FILES = ("jieba/dict.txt", "jieba/finalseg/prob_emit.pyc")
SUPPORTED_ABIS = ("arm64-v8a", "x86_64")
DEFAULT_MAX_APK_BYTES = 28_000_000
DEFAULT_MAX_JIEBA_BYTES = 3 * 1024 * 1024


def _apk_abis(archive: zipfile.ZipFile) -> list[str]:
    return sorted(
        {name.split("/")[1] for name in archive.namelist() if name.startswith("lib/")}
    )


def _check_jieba_archive(
    archive: zipfile.ZipFile,
    max_bytes: int,
    problems: list[str],
) -> int:
    """Check the trimmed jieba archive inside the APK and return its size."""
    try:
        info = archive.getinfo(JIEBA_ARCHIVE)
    except KeyError:
        problems.append("missing %s (was jieba removed from the requirements?)" % JIEBA_ARCHIVE)
        return 0
    if info.file_size > max_bytes:
        problems.append(
            "%s is %d bytes, over the %d byte budget"
            % (JIEBA_ARCHIVE, info.file_size, max_bytes)
        )
    with archive.open(info) as packed:
        data = packed.read()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as jieba:
            names = jieba.namelist()
    except zipfile.BadZipFile:
        problems.append("%s is not a valid zip archive" % JIEBA_ARCHIVE)
        return info.file_size

    unused = [name for name in names if name.startswith(UNUSED_JIEBA_PREFIXES)]
    if unused:
        problems.append(
            "%s still contains %d unused entries (e.g. %s)"
            % (JIEBA_ARCHIVE, len(unused), unused[0])
        )
    missing = [name for name in REQUIRED_JIEBA_FILES if name not in names]
    if missing:
        problems.append("%s is missing runtime files: %r" % (JIEBA_ARCHIVE, missing))
    if not any(
        name.startswith("jieba-") and name.endswith(".dist-info/METADATA")
        for name in names
    ):
        problems.append(
            "%s is missing jieba dist-info metadata (pkg_resources needs it)"
            % JIEBA_ARCHIVE
        )
    return info.file_size


def check_apk(
    path: Path,
    abi: str,
    max_apk_bytes: int,
    max_jieba_bytes: int,
) -> list[str]:
    """Return the problems found in the APK; an empty list means it is publishable."""
    if abi not in SUPPORTED_ABIS:
        return ["unsupported ABI %r (expected one of %r)" % (abi, SUPPORTED_ABIS)]
    if not path.is_file():
        return ["missing APK: %s" % path]

    problems: list[str] = []
    size = path.stat().st_size
    if size > max_apk_bytes:
        problems.append(
            "%s is %d bytes, over the %d byte budget" % (path.name, size, max_apk_bytes)
        )
    try:
        with zipfile.ZipFile(path) as archive:
            abis = _apk_abis(archive)
            if abis != [abi]:
                problems.append(
                    "%s is published as %r but contains ABIs %r"
                    % (path.name, abi, abis)
                )
            jieba_size = _check_jieba_archive(archive, max_jieba_bytes, problems)
    except zipfile.BadZipFile:
        return problems + ["not a valid APK/zip file: %s" % path]

    if problems:
        return problems
    print(
        "%s: ABI=%s size=%d bytes jieba=%d bytes"
        % (path.name, abi, size, jieba_size)
    )
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path, help="APK to validate")
    parser.add_argument(
        "--abi",
        required=True,
        choices=SUPPORTED_ABIS,
        help="ABI the APK must contain exclusively",
    )
    parser.add_argument("--max-apk-bytes", type=int, default=DEFAULT_MAX_APK_BYTES)
    parser.add_argument("--max-jieba-bytes", type=int, default=DEFAULT_MAX_JIEBA_BYTES)
    args = parser.parse_args(argv)

    problems = check_apk(args.apk, args.abi, args.max_apk_bytes, args.max_jieba_bytes)
    if problems:
        for problem in problems:
            print("FAIL: %s" % problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
