# -*- coding: utf-8 -*-
"""Publish the bundled database under a unique version number.

One command owns the whole release step:

    python scripts/update_database_manifest.py --bump --tag v1.9.1

It stamps the marker inside translated.db, appends database-versions.json and
rewrites database-manifest.json. Without --bump it only re-projects the manifest
from the ledger and refuses to touch anything when the database content changed
but the version number did not - that is exactly the situation the version
uniqueness invariant forbids.

Exit codes: 0 healthy, 1 invariant violation, 2 the database needs a --bump.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')

from database_versioning import (  # noqa: E402
    DB,
    FORMAT,
    MANIFEST,
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


def _report(problems) -> int:
    if not problems:
        return 0
    for problem in problems:
        print('FAIL: %s' % problem, file=sys.stderr)
    return 1


def _marker_version() -> int:
    marker = read_database_metadata(DB)
    try:
        return int(marker.get('db_version', '0') or 0)
    except (TypeError, ValueError):
        return 0


def run(args: argparse.Namespace) -> int:
    entries = load_ledger()
    problems = validate_ledger(entries)
    if problems:
        return _report(problems)

    published_at = args.published_at or datetime.date.today().isoformat()

    if args.status:
        last = entries[-1]
        size, digest = file_identity(DB)
        print('ledger entries      : %d' % len(entries))
        print('newest published    : v%d (%s) %d bytes %s'
              % (last['db_version'], last['published_at'], last['size'], last['sha1']))
        print('bundled database    : marker v%d, %d bytes %s'
              % (_marker_version(), size, digest))
        print('manifest            : %s' % MANIFEST)
        remaining = check_asset_matches_ledger()
        if remaining:
            print('state               : OUT OF SYNC')
            for problem in remaining:
                print('  - %s' % problem)
            return 1
        print('state               : in sync')
        return 0

    if not args.bump:
        # Only re-project the manifest; never let changed content keep an old number.
        last = entries[-1]
        size, digest = file_identity(DB)
        if size != int(last['size']) or digest != str(last['sha1']).lower():
            print('FAIL: translated.db changed but db_version is still v%d.'
                  % last['db_version'], file=sys.stderr)
            print('      A version number identifies one exact content. Run:', file=sys.stderr)
            print('      python scripts/update_database_manifest.py --bump --tag vX.Y.Z',
                  file=sys.stderr)
            return 2
        if _marker_version() != int(last['db_version']):
            return _report(['database marker db_version=%d does not match ledger v%d'
                            % (_marker_version(), last['db_version'])])
        save_manifest(last)
        print('content unchanged: database-manifest.json re-projected from v%d'
              % last['db_version'])
        return _report(check_asset_matches_ledger())

    last = entries[-1]
    if _marker_version() > int(last['db_version']):
        return _report([
            'the database marker is already v%d while the ledger ends at v%d; '
            'record that version in the ledger or restore the marker before bumping'
            % (_marker_version(), last['db_version'])])

    size, digest = file_identity(DB)
    if digest == str(last['sha1']).lower():
        return _report([
            'the database content is identical to v%d, so bumping would map two versions '
            'to one content; nothing to publish' % last['db_version']])

    version = int(last['db_version']) + 1
    notes = args.notes
    if notes is None:
        notes = last.get('notes', '')
    write_database_marker(DB, {
        'db_version': str(version),
        'published_at': published_at,
        'notes': notes,
        'format': FORMAT,
    })

    # The marker lives inside the file, so the published identity is the one after stamping.
    size, digest = file_identity(DB)
    entry = {
        'db_version': version,
        'sha1': digest,
        'size': size,
        'published_at': published_at,
        'app_tag': args.tag or '',
        'notes': notes,
    }
    entries.append(entry)
    problems = validate_ledger(entries)
    if problems:
        return _report(problems)
    save_ledger(entries)
    save_manifest(entry)

    print('published db_version=%d (%s) size=%d sha1=%s'
          % (version, published_at, size, digest))
    if args.tag:
        print('app tag recorded    : %s' % args.tag)
    remaining = check_asset_matches_ledger()
    if remaining:
        return _report(remaining)
    print('ledger, manifest and database are consistent')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bump', action='store_true',
                        help='publish the current database content as a new version')
    parser.add_argument('--status', action='store_true', help='print the version state')
    parser.add_argument('--notes', default=None, help='release note stored with the version')
    parser.add_argument('--tag', default=None, help='app release tag that ships this version')
    parser.add_argument('--published-at', default=None, help='publication date (YYYY-MM-DD)')
    return run(parser.parse_args())


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except VersioningError as error:
        print('FAIL: %s' % error, file=sys.stderr)
        raise SystemExit(1)
