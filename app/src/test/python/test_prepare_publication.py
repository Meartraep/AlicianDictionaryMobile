# -*- coding: utf-8 -*-
"""The phone stamps the version it publishes; these tests pin that behaviour.

The bridge output must match the repository tooling exactly, because CI verifies
the pull request with scripts/database_versioning.py.
"""
from __future__ import annotations

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
import mobile_bridge  # noqa: E402

DATABASE_URL = ('https://raw.githubusercontent.com/Meartraep/AlicianDictionaryMobile/'
                'main/app/src/main/assets/translated.db')


class PreparePublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix='publication'))
        self.source = self.tmp / 'translated.db'
        shutil.copy2(REPO / 'app/src/main/assets/translated.db', self.source)
        connection = sqlite3.connect(self.source)
        connection.execute(
            "UPDATE songs SET lyric = lyric || ' ' WHERE id = (SELECT MIN(id) FROM songs)")
        connection.commit()
        connection.close()
        self.target = self.tmp / 'publication.db'
        mobile_bridge.initialize(str(self.source), str(self.tmp))
        self.ledger_text = (REPO / 'database-versions.json').read_text(encoding='utf-8')
        self.entries = json.loads(self.ledger_text)
        self.published_version = int(self.entries[-1]['db_version'])

    def tearDown(self) -> None:
        mobile_bridge._close_services()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def prepare(self, **overrides):
        payload = {
            'source': str(self.source),
            'target': str(self.target),
            'ledger_json': self.ledger_text,
            'notes': '手机端发布测试',
            'published_at': '2026-10-17',
            'database_url': DATABASE_URL,
        }
        payload.update(overrides)
        return json.loads(mobile_bridge.invoke('prepare_database_publication', json.dumps(payload)))

    # ---- happy path -----------------------------------------------------
    def test_stamps_the_next_version_into_a_copy(self) -> None:
        result = self.prepare()
        self.assertTrue(result.get('ok'), result.get('message'))
        self.assertEqual(result['version'], self.published_version + 1)
        self.assertEqual(result['previous_version'], self.published_version)
        # The user's own database must not be modified.
        with sqlite3.connect(self.source) as connection:
            source_marker = connection.execute(
                "SELECT value FROM database_metadata WHERE key='db_version'").fetchone()
        self.assertEqual(int(source_marker[0]), self.published_version)
        self.assertEqual(dv.read_database_version(self.target), self.published_version + 1)

    def test_ledger_and_manifest_match_the_repository_tools(self) -> None:
        result = self.prepare()
        entries = json.loads(result['ledger_json'])
        self.assertEqual(len(entries), len(self.entries) + 1)
        self.assertEqual(entries[:-1], self.entries, 'published history must be untouched')
        entry = entries[-1]
        self.assertEqual(entry['db_version'], self.published_version + 1)
        self.assertEqual(entry['sha1'], result['sha1'])
        self.assertEqual(entry['size'], result['size'])
        self.assertEqual(entry['notes'], '手机端发布测试')
        # Identical to what scripts/database_versioning.py would write.
        self.assertEqual(entry['sha1'], dv.file_identity(self.target)[1])
        self.assertEqual(result['manifest_json'],
                         json.dumps(dv.build_manifest(entry), ensure_ascii=False, indent=2) + '\n')

    def test_stamped_file_satisfies_the_repository_invariants(self) -> None:
        result = self.prepare()
        work = self.tmp / 'repo'
        work.mkdir()
        (work / 'app/src/main/assets').mkdir(parents=True)
        shutil.copy2(self.target, work / 'app/src/main/assets/translated.db')
        (work / 'database-versions.json').write_text(result['ledger_json'], encoding='utf-8')
        (work / 'database-manifest.json').write_text(result['manifest_json'], encoding='utf-8')
        saved = (dv.DB, dv.MANIFEST, dv.LEDGER)
        dv.DB = work / 'app/src/main/assets/translated.db'
        dv.MANIFEST = work / 'database-manifest.json'
        dv.LEDGER = work / 'database-versions.json'
        try:
            self.assertEqual(dv.validate_ledger(dv.load_ledger()), [])
            self.assertEqual(dv.check_asset_matches_ledger(), [])
        finally:
            dv.DB, dv.MANIFEST, dv.LEDGER = saved

    # ---- refusals -------------------------------------------------------
    def test_stale_ledger_is_refused(self) -> None:
        result = self.prepare(version=self.published_version + 2)
        self.assertFalse(result.get('ok'))
        self.assertIn('台账已更新', result.get('message', ''))

    def test_missing_note_is_refused(self) -> None:
        result = self.prepare(notes='   ')
        self.assertFalse(result.get('ok'))
        self.assertIn('版本说明', result.get('message', ''))

    def test_missing_source_is_refused(self) -> None:
        result = self.prepare(source=str(self.tmp / 'nope.db'))
        self.assertFalse(result.get('ok'))
        self.assertIn('不存在', result.get('message', ''))

    def test_empty_ledger_is_refused(self) -> None:
        result = self.prepare(ledger_json='[]')
        self.assertFalse(result.get('ok'))
        self.assertIn('台账为空', result.get('message', ''))

    def test_notes_are_collapsed_and_capped(self) -> None:
        result = self.prepare(notes='  第一行\n第二行  ' + 'x' * 600)
        self.assertTrue(result.get('ok'), result.get('message'))
        note = json.loads(result['ledger_json'])[-1]['notes']
        self.assertEqual(len(note), 500)
        self.assertTrue(note.startswith('第一行 第二行'))

    def test_publishing_twice_produces_two_unique_versions(self) -> None:
        first = self.prepare()
        second = self.prepare(ledger_json=first['ledger_json'], target=str(self.tmp / 'second.db'))
        self.assertEqual(second['version'], self.published_version + 2)
        entries = json.loads(second['ledger_json'])
        self.assertEqual(len(entries), len(self.entries) + 2)
        self.assertEqual(dv.validate_ledger(entries), [])
        self.assertNotEqual(entries[-1]['sha1'], entries[-2]['sha1'])


if __name__ == '__main__':
    unittest.main()
