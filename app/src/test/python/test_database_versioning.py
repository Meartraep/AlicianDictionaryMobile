# -*- coding: utf-8 -*-
"""Guards for database version uniqueness and the download-time version check.

The script tests run against throw-away copies of the shipped database, manifest
and ledger; the bridge test exercises the real replace_database entry point.
Expectations are relative to the ledger the repository currently ships, so they
keep holding after every published version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'app/src/main/python'))
sys.stdout.reconfigure(encoding='utf-8')

import database_versioning as dv  # noqa: E402
import update_database_manifest as bump  # noqa: E402
import mobile_bridge  # noqa: E402


def sha1_of(path: Path) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def make_args(**overrides) -> argparse.Namespace:
    base = dict(bump=False, status=False, notes=None, tag=None, published_at='2026-01-02')
    base.update(overrides)
    return argparse.Namespace(**base)


class ScriptInvariantTests(unittest.TestCase):
    """The ledger and the published database must never disagree."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix='dbver'))
        self.db = self.tmp / 'translated.db'
        self.manifest = self.tmp / 'database-manifest.json'
        self.ledger = self.tmp / 'database-versions.json'
        shutil.copy2(dv.DB, self.db)
        shutil.copy2(dv.MANIFEST, self.manifest)
        shutil.copy2(dv.LEDGER, self.ledger)
        self.saved = (dv.DB, dv.MANIFEST, dv.LEDGER, bump.DB, bump.MANIFEST)
        dv.DB, dv.MANIFEST, dv.LEDGER = self.db, self.manifest, self.ledger
        bump.DB, bump.MANIFEST = self.db, self.manifest
        self.base_version = int(self.entries()[-1]['db_version'])

    def tearDown(self) -> None:
        dv.DB, dv.MANIFEST, dv.LEDGER, bump.DB, bump.MANIFEST = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def entries(self):
        return json.loads(self.ledger.read_text(encoding='utf-8'))

    def versions(self):
        return [entry['db_version'] for entry in self.entries()]

    def mutate_content(self) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                "UPDATE songs SET lyric = lyric || ' ' WHERE id = (SELECT MIN(id) FROM songs)")
            connection.commit()
        finally:
            connection.close()

    def test_changed_content_without_bump_is_refused(self) -> None:
        self.mutate_content()
        problems = dv.check_asset_matches_ledger()
        self.assertTrue(problems, 'changed content must be reported')
        self.assertIn('differs from the newest ledger entry', problems[0])
        self.assertEqual(bump.run(make_args()), 2, 'refresh without --bump must fail')

    def test_bump_publishes_a_unique_version(self) -> None:
        before = self.versions()
        self.mutate_content()
        self.assertEqual(bump.run(make_args(bump=True, tag='v9.9.9')), 0)
        entries = self.entries()
        self.assertEqual(self.versions(), before + [self.base_version + 1])
        self.assertEqual(entries[-1]['app_tag'], 'v9.9.9')
        self.assertEqual(dv.validate_ledger(entries), [])
        self.assertEqual(dv.read_database_version(self.db), self.base_version + 1)
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        self.assertEqual(manifest['db_version'], self.base_version + 1)
        self.assertEqual(manifest, dv.build_manifest(entries[-1]))
        self.assertEqual(dv.check_asset_matches_ledger(), [])

    def test_bump_without_content_change_is_refused(self) -> None:
        before = self.versions()
        code = bump.run(make_args(bump=True))
        self.assertEqual(code, 1, 'two versions for one content must be impossible')
        self.assertEqual(self.versions(), before)

    def test_manifest_is_reprojected_from_the_ledger(self) -> None:
        self.manifest.write_text('{}', encoding='utf-8')
        self.assertEqual(bump.run(make_args()), 0)
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        self.assertEqual(manifest['db_version'], self.base_version)
        self.assertEqual(manifest['sha1'], sha1_of(self.db))

    def test_duplicate_version_and_hash_are_detected(self) -> None:
        entries = self.entries()
        entries.append(dict(entries[-1]))
        problems = dv.validate_ledger(entries)
        self.assertTrue(any('was already used' in problem for problem in problems), problems)
        self.assertTrue(any('was already published' in problem for problem in problems), problems)

    def test_non_monotonic_and_malformed_entries_are_detected(self) -> None:
        entries = self.entries()
        entries.append({'db_version': 0, 'sha1': 'x' * 40, 'size': 1, 'published_at': '2026-01-01'})
        problems = dv.validate_ledger(entries)
        self.assertTrue(any('positive integer' in problem for problem in problems), problems)
        broken = [dict(entries[-1], db_version=self.base_version + 1, sha1='not-a-hash')]
        problems = dv.validate_ledger(broken)
        self.assertTrue(any('sha1 is not' in problem for problem in problems), problems)
        missing = [dict(entries[-1])]
        missing[0].pop('sha1')
        problems = dv.validate_ledger(missing)
        self.assertTrue(any('missing keys' in problem for problem in problems), problems)


class ReplaceDatabaseGuardTests(unittest.TestCase):
    """replace_database must refuse a file whose marker contradicts the manifest."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix='dbguard'))
        self.installed = self.tmp / 'translated.db'
        shutil.copy2(dv.DB, self.installed)
        mobile_bridge.initialize(str(self.installed), str(self.tmp))
        self.source = self.tmp / 'downloaded.db'
        shutil.copy2(dv.DB, self.source)

    def tearDown(self) -> None:
        mobile_bridge._close_services()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_matching_version_is_accepted(self) -> None:
        installed_version = dv.read_database_version(self.installed)
        result = json.loads(mobile_bridge.invoke('replace_database', json.dumps({
            'path': str(self.source), 'expected_db_version': installed_version})))
        self.assertTrue(result.get('ok'), result.get('message'))
        self.assertEqual(dv.read_database_version(self.installed), installed_version)

    def test_mismatched_version_is_refused_and_installed_database_untouched(self) -> None:
        before = sha1_of(self.installed)
        installed_version = dv.read_database_version(self.installed)
        wrong = installed_version + 99
        result = json.loads(mobile_bridge.invoke('replace_database', json.dumps({
            'path': str(self.source), 'expected_db_version': wrong})))
        self.assertFalse(result.get('ok'))
        message = result.get('message', '')
        self.assertIn('v' + str(wrong), message)
        self.assertIn('v' + str(installed_version), message)
        self.assertEqual(sha1_of(self.installed), before,
                         'a rejected update must not touch the installed database')

    def test_import_without_expected_version_still_works(self) -> None:
        result = json.loads(mobile_bridge.invoke('replace_database', json.dumps({
            'path': str(self.source)})))
        self.assertTrue(result.get('ok'), result.get('message'))


class ShippedRepositoryStateTests(unittest.TestCase):
    """The repository as committed must satisfy the invariants."""

    def test_ledger_is_healthy(self) -> None:
        self.assertEqual(dv.validate_ledger(dv.load_ledger()), [])

    def test_database_manifest_and_ledger_agree(self) -> None:
        self.assertEqual(dv.check_asset_matches_ledger(), [])

    def test_newest_entry_matches_the_shipped_manifest(self) -> None:
        entries = dv.load_ledger()
        self.assertTrue(entries, 'at least one published version must be recorded')
        manifest = json.loads(dv.MANIFEST.read_text(encoding='utf-8'))
        self.assertEqual(manifest, dv.build_manifest(entries[-1]))
        for key in ('db_version', 'sha1', 'size', 'published_at'):
            self.assertIn(key, entries[-1])


if __name__ == '__main__':
    unittest.main()
