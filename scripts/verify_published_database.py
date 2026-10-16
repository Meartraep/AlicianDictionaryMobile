# -*- coding: utf-8 -*-
"""Verify a database that the phone published as a new version.

The phone stamps the version itself (it appends the ledger entry and re-projects
the manifest in its own commit), so the pipeline no longer writes anything -- and
therefore never pushes a bot commit that GitHub would hold for approval. What the
phone *proposes* stays enforced here:

1. the pull request may only touch the database, the ledger and the manifest,
2. the ledger must be the base ledger plus exactly one appended entry,
3. that entry must be base_last + 1, a version nobody used before,
4. its sha1/size must be the bytes of the uploaded database,
5. the marker inside the database must be that same version,
6. the content must actually differ from the currently published version,
7. the manifest must be the projection of the new entry.

Usage (CI):
    python scripts/verify_published_database.py \
        --base-ledger base-ledger.json \
        --changed-files app/src/main/assets/translated.db database-versions.json

Exit codes: 0 verified, 1 rejected (reasons on stderr).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')

from database_versioning import (  # noqa: E402
    DB,
    LEDGER,
    MANIFEST,
    VersioningError,
    build_manifest,
    check_asset_matches_ledger,
    file_identity,
    load_ledger,
    read_database_version,
    validate_ledger,
)

# Only these paths may differ in a publishing pull request; everything else --
# code, workflows, scripts -- would turn a data update into a supply-chain change.
ALLOWED_PATHS = frozenset({
    'app/src/main/assets/translated.db',
    'database-versions.json',
    'database-manifest.json',
})

MAX_NOTES_LENGTH = 500


def check_allowlist(changed_files: List[str]) -> List[str]:
    """Paths a publishing pull request must not touch."""
    return sorted(
        path for path in {path.strip() for path in changed_files if path.strip()}
        if path not in ALLOWED_PATHS
    )


def verify_published_database(
    db_path: Path = DB,
    ledger_path: Path = LEDGER,
    manifest_path: Path = MANIFEST,
    base_ledger_path: Path | None = None,
) -> List[str]:
    """Returns every reason the publication must be refused (empty when fine)."""
    problems: List[str] = []

    base = json.loads(Path(base_ledger_path).read_text(encoding='utf-8')) if base_ledger_path else []
    entries = load_ledger(ledger_path)
    problems.extend(validate_ledger(entries))

    if not base:
        problems.append('the base ledger of the target branch is empty or missing')
        return problems
    if len(entries) != len(base) + 1:
        problems.append(
            'the ledger must gain exactly one entry: the target branch has %d, this pull '
            'request has %d' % (len(base), len(entries)))
        return problems
    if entries[:-1] != base:
        problems.append('the pull request modifies ledger entries that are already published')
        return problems

    previous = base[-1]
    entry = entries[-1]
    size, digest = file_identity(db_path)
    marker = read_database_version(db_path)

    expected_version = int(previous['db_version']) + 1
    if int(entry['db_version']) != expected_version:
        problems.append(
            'the new version must be v%d (the published one is v%s), not v%s; re-read the '
            'published ledger and stamp again'
            % (expected_version, previous['db_version'], entry['db_version']))

    if digest == str(previous['sha1']).lower():
        problems.append(
            'the uploaded database is identical to the published v%s; there is nothing to '
            'publish' % previous['db_version'])

    if str(entry['sha1']).lower() != digest:
        problems.append(
            'ledger sha1 %s does not describe the uploaded database (%s)'
            % (str(entry['sha1'])[:12], digest[:12]))
    if int(entry['size']) != size:
        problems.append(
            'ledger size %s does not describe the uploaded database (%d bytes)'
            % (entry['size'], size))

    if marker != int(entry['db_version']):
        problems.append(
            'the database carries marker v%d but the new ledger entry says v%s; the version '
            'must be stamped into the uploaded file (an older app publishes an unstamped '
            'database)' % (marker, entry['db_version']))

    notes = str(entry.get('notes', '')).strip()
    if not notes:
        problems.append('the new entry has no release note')
    elif len(notes) > MAX_NOTES_LENGTH:
        problems.append('the release note is longer than %d characters' % MAX_NOTES_LENGTH)

    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    if manifest != build_manifest(entry):
        problems.append(
            'database-manifest.json is not the projection of the newest ledger entry')

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=str(DB), help='database uploaded by the phone')
    parser.add_argument('--ledger', default=str(LEDGER), help='ledger in the pull request')
    parser.add_argument('--manifest', default=str(MANIFEST), help='manifest in the pull request')
    parser.add_argument('--base-ledger', default=None,
                        help='ledger of the target branch (fetched from main)')
    parser.add_argument('--changed-files', nargs='*', default=[],
                        help='paths changed by the pull request (allowlist check)')
    args = parser.parse_args()

    violations = check_allowlist(args.changed_files)
    if violations:
        print('FAIL: a publishing pull request may only change the database and its '
              'ledger/manifest; these paths are not allowed:', file=sys.stderr)
        for path in violations:
            print('  - %s' % path, file=sys.stderr)
        return 1

    try:
        problems = verify_published_database(
            Path(args.db), Path(args.ledger), Path(args.manifest),
            Path(args.base_ledger) if args.base_ledger else None)
        if not problems:
            problems = check_asset_matches_ledger(Path(args.db), Path(args.ledger), Path(args.manifest))
    except (OSError, ValueError, VersioningError, json.JSONDecodeError) as error:
        print('FAIL: %s' % error, file=sys.stderr)
        return 1

    if problems:
        for problem in problems:
            print('FAIL: %s' % problem, file=sys.stderr)
        return 1

    entry = load_ledger(Path(args.ledger))[-1]
    print('OK: v%s verified (%d bytes, sha1 %s)'
          % (entry['db_version'], entry['size'], str(entry['sha1'])[:12]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
