# -*- coding: utf-8 -*-
"""Validate a signed, ABI-specific release APK before it is published.

The release workflow (`.github/workflows/release-slsa.yml`) builds one APK per
ABI and publishes both, because AGP 9 cannot combine `splits.abi` with the
`ndk.abiFilters` setting that Chaquopy 17 requires. This guard fails the release
if the split silently regresses to a multi-ABI APK, if the jieba trimming in
`app/build.gradle.kts` stops working, if the download size grows past its
budget, or if the release tag does not match the APK's `versionName`:

    python scripts/verify_release_apk.py \\
        --check-gradle app/build.gradle.kts --expected-version v1.12.2

    python scripts/verify_release_apk.py \\
        dist/AlicianDictionary-v1.12.2-arm64-v8a.apk --abi arm64-v8a \\
        --expected-version v1.12.2 --aapt2 /path/to/aapt2
"""
from __future__ import annotations

import argparse
import io
import re
import shutil
import subprocess
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

_GRADLE_VERSION_NAME_RE = re.compile(r'^\s*versionName\s*=\s*"([^"]+)"', re.MULTILINE)
_GRADLE_VERSION_CODE_RE = re.compile(r"^\s*versionCode\s*=\s*(\d+)", re.MULTILINE)
_BADGING_VERSION_NAME_RE = re.compile(r"versionName='([^']*)'")
_BADGING_VERSION_CODE_RE = re.compile(r"versionCode='(\d+)'")


def normalize_release_version(tag_or_version: str) -> str:
    """Strip an optional leading 'v'/'V' from a release tag or version string."""
    cleaned = tag_or_version.strip()
    if len(cleaned) >= 2 and cleaned[0] in ("v", "V") and cleaned[1].isdigit():
        return cleaned[1:]
    return cleaned


def parse_gradle_version(gradle_text: str) -> tuple[str | None, int | None]:
    """Extract (versionName, versionCode) from app/build.gradle.kts text."""
    name_match = _GRADLE_VERSION_NAME_RE.search(gradle_text)
    code_match = _GRADLE_VERSION_CODE_RE.search(gradle_text)
    version_name = name_match.group(1).strip() if name_match else None
    version_code = int(code_match.group(1)) if code_match else None
    return version_name, version_code


def check_gradle_version(gradle_path: Path, expected_version: str) -> list[str]:
    """Verify app/build.gradle.kts declares a versionName matching the release tag."""
    if not gradle_path.is_file():
        return ["missing Gradle file: %s" % gradle_path]

    expected = normalize_release_version(expected_version)
    if not expected:
        return ["expected release version is empty"]

    version_name, version_code = parse_gradle_version(
        gradle_path.read_text(encoding="utf-8")
    )
    problems: list[str] = []
    if not version_name:
        problems.append("could not find versionName in %s" % gradle_path)
    elif version_name != expected:
        problems.append(
            "%s has versionName=%r, but release tag expects %r "
            "(bump versionName and versionCode before tagging)"
            % (gradle_path, version_name, expected)
        )
    if version_code is None or version_code <= 0:
        problems.append("could not find a positive versionCode in %s" % gradle_path)

    if not problems:
        print(
            "%s: versionName=%s versionCode=%d (matches %s)"
            % (gradle_path, version_name, version_code, expected_version)
        )
    return problems


def parse_aapt2_badging_version(badging_output: str) -> tuple[str | None, int | None]:
    """Extract (versionName, versionCode) from `aapt2 dump badging` output."""
    for line in badging_output.splitlines():
        if line.startswith("package:"):
            name_match = _BADGING_VERSION_NAME_RE.search(line)
            code_match = _BADGING_VERSION_CODE_RE.search(line)
            version_name = name_match.group(1).strip() if name_match else None
            version_code = int(code_match.group(1)) if code_match else None
            return version_name, version_code
    return None, None


def _resolve_aapt2(aapt2: Path | None) -> str | None:
    if aapt2 is not None:
        return str(aapt2) if aapt2.is_file() else None
    return shutil.which("aapt2")


def check_apk_version(
    path: Path,
    expected_version: str,
    aapt2: Path | None = None,
) -> list[str]:
    """Verify the built APK's manifest versionName matches the release tag."""
    expected = normalize_release_version(expected_version)
    if not expected:
        return ["expected release version is empty"]

    aapt2_bin = _resolve_aapt2(aapt2)
    if not aapt2_bin:
        return [
            "aapt2 is required to verify APK versionName against %r (pass --aapt2)"
            % expected_version
        ]

    result = subprocess.run(
        [aapt2_bin, "dump", "badging", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return ["aapt2 dump badging failed for %s: %s" % (path.name, detail)]

    version_name, version_code = parse_aapt2_badging_version(result.stdout)
    problems: list[str] = []
    if not version_name:
        problems.append("could not read versionName from %s via aapt2" % path.name)
    elif version_name != expected:
        problems.append(
            "%s declares versionName=%r (versionCode=%s), but release tag expects %r"
            % (path.name, version_name, version_code, expected)
        )
    if version_code is None or version_code <= 0:
        problems.append("could not read a positive versionCode from %s" % path.name)
    return problems


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
    expected_version: str | None = None,
    aapt2: Path | None = None,
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

    if expected_version is not None:
        problems.extend(check_apk_version(path, expected_version, aapt2=aapt2))

    if problems:
        return problems
    version_note = (
        " version=%s" % normalize_release_version(expected_version)
        if expected_version is not None
        else ""
    )
    print(
        "%s: ABI=%s%s size=%d bytes jieba=%d bytes"
        % (path.name, abi, version_note, size, jieba_size)
    )
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", nargs="?", type=Path, help="APK to validate")
    parser.add_argument(
        "--abi",
        choices=SUPPORTED_ABIS,
        help="ABI the APK must contain exclusively",
    )
    parser.add_argument(
        "--check-gradle",
        type=Path,
        help="validate versionName/versionCode in app/build.gradle.kts before building",
    )
    parser.add_argument(
        "--expected-version",
        help="release tag or versionName the build must match (e.g. v1.12.2 or 1.12.2)",
    )
    parser.add_argument(
        "--aapt2",
        type=Path,
        help="path to the Android SDK aapt2 binary used to inspect APK versionName",
    )
    parser.add_argument("--max-apk-bytes", type=int, default=DEFAULT_MAX_APK_BYTES)
    parser.add_argument("--max-jieba-bytes", type=int, default=DEFAULT_MAX_JIEBA_BYTES)
    args = parser.parse_args(argv)

    if args.check_gradle is not None:
        if not args.expected_version:
            parser.error("--check-gradle requires --expected-version")
        problems = check_gradle_version(args.check_gradle, args.expected_version)
    else:
        if args.apk is None or args.abi is None:
            parser.error("apk and --abi are required unless --check-gradle is given")
        problems = check_apk(
            args.apk,
            args.abi,
            args.max_apk_bytes,
            args.max_jieba_bytes,
            expected_version=args.expected_version,
            aapt2=args.aapt2,
        )

    if problems:
        for problem in problems:
            print("FAIL: %s" % problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
