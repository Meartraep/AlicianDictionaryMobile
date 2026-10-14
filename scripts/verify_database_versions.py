# -*- coding: utf-8 -*-
"""Verify that every published database version stays unique and traceable.

Checks the append-only ledger, the bundled database, the manifest the app reads,
and optionally the bytes actually served by GitHub:

    python scripts/verify_database_versions.py
    python scripts/verify_database_versions.py --remote --retries 5
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')

from database_versioning import (  # noqa: E402
    DB,
    MANIFEST,
    RAW_MANIFEST_URL,
    check_asset_matches_ledger,
    load_ledger,
    read_database_version,
    validate_ledger,
)


def _fetch(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={
        'User-Agent': 'AlicianDictionaryMobile/verify-database',
        'Cache-Control': 'no-cache',
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def check_remote(retries: int, delay: float) -> list:
    problems = []
    entries = load_ledger()
    last = entries[-1]
    attempt = 0
    while True:
        attempt += 1
        try:
            payload = json.loads(_fetch(RAW_MANIFEST_URL).decode('utf-8'))
            url = payload.get('url') or ''
            if not url:
                return ['published manifest has no url field']
            database = _fetch(url)
            break
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as error:
            if attempt > retries:
                return ['could not fetch the published database metadata: %s' % error]
            print('  retry %d/%d after %s' % (attempt, retries, error))
            time.sleep(delay)

    size = len(database)
    digest = hashlib.sha1(database).hexdigest()
    print('published manifest : v%s %s' % (payload.get('db_version'), payload.get('sha1')))
    print('published database : %d bytes %s' % (size, digest))
    if int(payload.get('db_version', -1)) != int(last['db_version']):
        problems.append('published manifest db_version=%s does not match ledger v%s'
                        % (payload.get('db_version'), last['db_version']))
    if str(payload.get('sha1', '')).lower() != str(last['sha1']).lower():
        problems.append('published manifest sha1 does not match ledger v%s' % last['db_version'])
    if size != int(last['size']) or digest != str(last['sha1']).lower():
        problems.append('published database bytes do not match ledger v%s '
                        '(size=%d sha1=%s)' % (last['db_version'], size, digest))
    handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    try:
        handle.write(database)
        handle.close()
        version = read_database_version(Path(handle.name))
        if version != int(last['db_version']):
            problems.append('published database marker v%d does not match ledger v%s'
                            % (version, last['db_version']))
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--remote', action='store_true',
                        help='also verify the bytes served by GitHub')
    parser.add_argument('--retries', type=int, default=3,
                        help='retries for the remote check (CDN may lag after a push)')
    parser.add_argument('--delay', type=float, default=15.0,
                        help='seconds between remote retries')
    args = parser.parse_args()

    problems = []
    entries = load_ledger()
    print('ledger entries: %d' % len(entries))
    for entry in entries:
        print('  v%-3s %s %8s bytes  %s  %s'
              % (entry.get('db_version'), str(entry.get('sha1'))[:12],
                 entry.get('size'), entry.get('published_at'), entry.get('app_tag') or ''))
    problems.extend(validate_ledger(entries))
    if not problems:
        problems.extend(check_asset_matches_ledger())
        size, digest = (DB.stat().st_size, hashlib.sha1(DB.read_bytes()).hexdigest())
        print('bundled database: marker v%s, %d bytes %s'
              % (read_database_version(DB), size, digest))
        print('manifest        : %s' % MANIFEST.name)
    if args.remote and not problems:
        problems.extend(check_remote(max(0, args.retries), max(0.0, args.delay)))

    if problems:
        for problem in problems:
            print('FAIL: %s' % problem, file=sys.stderr)
        return 1
    print('OK: database versions are unique, monotonic and traceable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
