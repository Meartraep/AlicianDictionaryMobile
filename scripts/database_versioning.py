# -*- coding: utf-8 -*-
"""Shared helpers for keeping the published database version unique.

Invariants enforced by the scripts that import this module:

* db_version is a strictly increasing positive integer that is never reused.
* One db_version maps to exactly one published byte content (one SHA-1).
* The database carries its own copy of the marker, so the installed revision
  travels with the file; database-versions.json is the append-only ledger of
  everything that was ever published.
* The manifest shown to the app is a projection of the ledger's last entry.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'app/src/main/assets/translated.db'
MANIFEST = ROOT / 'database-manifest.json'
LEDGER = ROOT / 'database-versions.json'
RAW_URL = ('https://raw.githubusercontent.com/Meartraep/AlicianDictionaryMobile/'
           'main/app/src/main/assets/translated.db')
RAW_MANIFEST_URL = ('https://raw.githubusercontent.com/Meartraep/AlicianDictionaryMobile/'
                    'main/database-manifest.json')
FORMAT = 'alician-lite'

HEX_DIGITS = set('0123456789abcdef')


class VersioningError(RuntimeError):
    """Raised when an invariant would be violated."""


def file_identity(path: Path) -> Tuple[int, str]:
    data = Path(path).read_bytes()
    return len(data), hashlib.sha1(data).hexdigest()


def read_database_metadata(path: Path) -> Dict[str, str]:
    """Marker stored inside a database; empty when it predates the marker."""
    values: Dict[str, str] = {}
    if not Path(path).is_file():
        return values
    # sqlite3's context manager commits but does not close, and a lingering
    # connection keeps the file locked on Windows.
    conn = sqlite3.connect(path)
    try:
        for key, value in conn.execute('SELECT key, value FROM database_metadata'):
            values[str(key)] = str(value)
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    return values


def read_database_version(path: Path) -> int:
    values = read_database_metadata(path)
    try:
        return int(values.get('db_version', '0'))
    except (TypeError, ValueError):
        return 0


def write_database_marker(path: Path, values: Dict[str, str]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS database_metadata '
                     '(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for key, value in values.items():
            conn.execute('INSERT INTO database_metadata(key, value) VALUES(?, ?) '
                         'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                         (str(key), str(value)))
        conn.commit()
    finally:
        conn.close()


def load_ledger() -> List[Dict[str, Any]]:
    if not LEDGER.is_file():
        return []
    entries = json.loads(LEDGER.read_text(encoding='utf-8'))
    if not isinstance(entries, list):
        raise VersioningError('database-versions.json must contain a JSON array')
    return entries


def save_ledger(entries: List[Dict[str, Any]]) -> None:
    LEDGER.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8')


def build_manifest(entry: Dict[str, Any]) -> Dict[str, Any]:
    """The manifest the app fetches is a projection of one ledger entry."""
    return {
        'db_version': int(entry['db_version']),
        'published_at': entry['published_at'],
        'notes': entry.get('notes', ''),
        'format': FORMAT,
        'size': int(entry['size']),
        'sha1': entry['sha1'],
        'url': RAW_URL,
    }


def save_manifest(entry: Dict[str, Any]) -> None:
    MANIFEST.write_text(json.dumps(build_manifest(entry), ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')


def validate_ledger(entries: List[Dict[str, Any]]) -> List[str]:
    """Return every invariant violation found in the ledger (empty = healthy)."""
    problems: List[str] = []
    if not entries:
        problems.append('ledger is empty: no database version was ever published')
        return problems
    seen_versions: Dict[int, str] = {}
    seen_hashes: Dict[str, int] = {}
    previous_version = 0
    for index, entry in enumerate(entries):
        label = 'entry %d' % index
        if not isinstance(entry, dict):
            problems.append('%s: not a JSON object' % label)
            continue
        missing = [key for key in ('db_version', 'sha1', 'size', 'published_at')
                   if key not in entry]
        if missing:
            problems.append('%s: missing keys %s' % (label, ', '.join(missing)))
            continue
        version = entry['db_version']
        if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
            problems.append('%s: db_version must be a positive integer' % label)
            continue
        digest = str(entry['sha1']).lower()
        if len(digest) != 40 or any(character not in HEX_DIGITS for character in digest):
            problems.append('%s: sha1 is not a 40 character hex digest' % label)
        size = entry['size']
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            problems.append('%s: size must be a positive integer' % label)
        if version <= previous_version:
            problems.append('%s: db_version %d is not greater than the previous %d'
                            % (label, version, previous_version))
        if version in seen_versions:
            problems.append('%s: db_version %d was already used' % (label, version))
        if digest in seen_hashes:
            problems.append('%s: sha1 %s was already published as v%d'
                            % (label, digest, seen_hashes[digest]))
        seen_versions[version] = digest
        seen_hashes[digest] = version
        previous_version = max(previous_version, version)
    return problems


def check_asset_matches_ledger() -> List[str]:
    """The bundled database must be exactly the ledger's newest entry."""
    problems: List[str] = []
    entries = load_ledger()
    ledger_problems = validate_ledger(entries)
    if ledger_problems:
        return ledger_problems
    last = entries[-1]
    size, digest = file_identity(DB)
    if size != int(last['size']) or digest != str(last['sha1']).lower():
        problems.append(
            'translated.db differs from the newest ledger entry (v%s): file size=%d sha1=%s, '
            'ledger size=%s sha1=%s. Publish it with '
            'python scripts/update_database_manifest.py --bump'
            % (last['db_version'], size, digest, last['size'], last['sha1']))
    marker = read_database_metadata(DB)
    if int(marker.get('db_version', '0') or 0) != int(last['db_version']):
        problems.append('database marker db_version=%s does not match ledger v%s'
                        % (marker.get('db_version', '0'), last['db_version']))
    if marker.get('published_at') and marker.get('published_at') != last['published_at']:
        problems.append('database marker published_at=%s does not match ledger %s'
                        % (marker.get('published_at'), last['published_at']))
    if MANIFEST.is_file():
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        expected = build_manifest(last)
        for key in ('db_version', 'sha1', 'size', 'published_at'):
            if manifest.get(key) != expected[key]:
                problems.append('database-manifest.json %s=%r does not match ledger %r'
                                % (key, manifest.get(key), expected[key]))
    else:
        problems.append('database-manifest.json is missing')
    return problems
