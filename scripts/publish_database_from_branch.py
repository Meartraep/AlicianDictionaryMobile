# -*- coding: utf-8 -*-
"""Stamp a database published from the phone with the next unique version.

The phone only uploads app/src/main/assets/translated.db. This script owns
everything else, so the client can never pick a version number:

1. refuse anything outside the publishing allowlist,
2. refuse a database whose content is identical to the published one,
3. stamp db_version = ledger_last + 1 (plus published_at and the release note)
   into the database marker,
4. append database-versions.json and re-project database-manifest.json,
5. re-run the uniqueness invariants before anything is committed.

Usage (CI):
    python scripts/publish_database_from_branch.py --notes-file notes.txt \
        --changed-files app/src/main/assets/translated.db

Exit codes: 0 stamped or nothing to do, 2 refused (see stderr).
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')

from database_versioning import (  # noqa: E402
    DB,
    FORMAT,
    VersioningError,
    check_asset_matches_ledger,
    file_identity,
    load_ledger,
    read_database_metadata,
    save_ledger,
    save_manifest,
    validate_ledger,
    write_database_marker,
)

# Only these paths may differ in a publishing pull request; everything else --
# code, workflows, scripts -- would turn a data update into a supply-chain change.
ALLOWED_PATHS = frozenset({
    'app/src/main/assets/translated.db',
    'database-versions.json',
    'database-manifest.json',
})

MAX_NOTES_LENGTH = 500
DEFAULT_NOTES = '数据库内容更新'


class StampResult(NamedTuple):
    needs_commit: bool
    version: int
    sha1: str
    size: int
    reason: str


def check_allowlist(changed_files: List[str]) -> List[str]:
    """Paths a publishing pull request must not touch."""
    return sorted(
        path for path in {path.strip() for path in changed_files if path.strip()}
        if path not in ALLOWED_PATHS
    )


def normalise_notes(notes: Optional[str]) -> str:
    """Release notes become public text in the manifest, so keep them tame."""
    if notes is None:
        return DEFAULT_NOTES
    collapsed = ' '.join(str(notes).split())
    if not collapsed:
        return DEFAULT_NOTES
    return collapsed[:MAX_NOTES_LENGTH]


def stamp_database(
    db_path: Path,
    notes: Optional[str] = None,
    published_at: Optional[str] = None,
    check_only: bool = False,
) -> StampResult:
    """Assign the next version to the database at db_path. Raises VersioningError."""
    entries = load_ledger()
    problems = validate_ledger(entries)
    if problems:
        raise VersioningError('; '.join(problems))
    last = entries[-1]
    last_version = int(last['db_version'])

    marker = read_database_metadata(db_path)
    try:
        marker_version = int(marker.get('db_version', '0') or 0)
    except (TypeError, ValueError):
        marker_version = 0

    size, digest = file_identity(db_path)

    if marker_version > last_version + 1:
        raise VersioningError(
            'the uploaded database claims v%d while the ledger ends at v%d; '
            'fix the marker before publishing' % (marker_version, last_version))

    if marker_version == last_version + 1:
        # The ledger only ever holds versions this pipeline assigned, so a marker
        # one step ahead means the file was stamped against a different ledger state.
        raise VersioningError(
            'the uploaded database is stamped v%d, which the ledger does not contain; '
            're-upload the published database or restore its marker'
            % marker_version)

    # The digest covers the whole file, so an equal digest means the marker matches too.
    if digest == str(last['sha1']).lower():
        return StampResult(False, last_version, digest, size,
                           'content is already published as v%d' % last_version)

    version = last_version + 1
    release_notes = normalise_notes(notes)
    date = published_at or datetime.date.today().isoformat()

    if check_only:
        return StampResult(True, version, digest, size, 'would publish v%d' % version)

    write_database_marker(db_path, {
        'db_version': str(version),
        'published_at': date,
        'notes': release_notes,
        'format': FORMAT,
    })

    # The marker lives inside the file, so the identity is the one after stamping.
    size, digest = file_identity(db_path)
    entry = {
        'db_version': version,
        'sha1': digest,
        'size': size,
        'published_at': date,
        'app_tag': '',
        'notes': release_notes,
    }
    entries.append(entry)
    problems = validate_ledger(entries)
    if problems:
        raise VersioningError('; '.join(problems))
    save_ledger(entries)
    save_manifest(entry)

    remaining = check_asset_matches_ledger()
    if remaining:
        raise VersioningError('; '.join(remaining))
    return StampResult(True, version, digest, size, 'published v%d' % version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=str(DB), help='database uploaded by the phone')
    parser.add_argument('--notes', default=None, help='release note shown to users')
    parser.add_argument('--notes-file', default=None, help='file holding the release note')
    parser.add_argument('--published-at', default=None, help='publication date (YYYY-MM-DD)')
    parser.add_argument('--changed-files', nargs='*', default=[],
                        help='paths changed by the pull request (allowlist check)')
    parser.add_argument('--check-only', action='store_true',
                        help='report what would happen without writing anything')
    args = parser.parse_args()

    notes = args.notes
    if args.notes_file:
        notes = Path(args.notes_file).read_text(encoding='utf-8')

    violations = check_allowlist(args.changed_files)
    if violations:
        print('FAIL: a publishing pull request may only change the database and its '
              'ledger/manifest; these paths are not allowed:', file=sys.stderr)
        for path in violations:
            print('  - %s' % path, file=sys.stderr)
        return 2

    try:
        result = stamp_database(Path(args.db), notes, args.published_at, args.check_only)
    except VersioningError as error:
        print('FAIL: %s' % error, file=sys.stderr)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print('FAIL: %s' % error, file=sys.stderr)
        return 2

    print('needs_commit=%s' % ('true' if result.needs_commit else 'false'))
    print('db_version=%d' % result.version)
    print('sha1=%s' % result.sha1)
    print('size=%d' % result.size)
    print('reason=%s' % result.reason)
    github_output = Path(__import__('os').environ.get('GITHUB_OUTPUT', ''))
    if str(github_output) not in ('', '.'):
        try:
            with github_output.open('a', encoding='utf-8') as handle:
                handle.write('needs_commit=%s\n' % ('true' if result.needs_commit else 'false'))
                handle.write('db_version=%d\n' % result.version)
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
