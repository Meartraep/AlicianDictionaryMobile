# -*- coding: utf-8 -*-
"""Tests for the branch-side stamping of a database published from the phone."""
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
sys.stdout.reconfigure(encoding='utf-8')

import database_versioning as dv  # noqa: E402
import publish_database_from_branch as publish  # noqa: E402

ASSET = REPO / 'app/src/main/assets/translated.db'


class StampingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix='dbpublish'))
        self.db = self.tmp / 'translated.db'
        self.manifest = self.tmp / 'database-manifest.json'
        self.ledger = self.tmp / 'database-versions.json'
        shutil.copy2(ASSET, self.db)
        shutil.copy2(dv.MANIFEST, self.manifest)
        shutil.copy2(dv.LEDGER, self.ledger)
        self.saved = (dv.DB, dv.MANIFEST, dv.LEDGER)
        dv.DB, dv.MANIFEST, dv.LEDGER = self.db, self.manifest, self.ledger

    def tearDown(self) -> None:
        dv.DB, dv.MANIFEST, dv.LEDGER = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def entries(self):
        return json.loads(self.ledger.read_text(encoding='utf-8'))

    def change(self, text: str = ' 手机端修改 ') -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                "UPDATE songs SET lyric = lyric || ? WHERE id = (SELECT MIN(id) FROM songs)",
                (text,))
            connection.commit()
        finally:
            connection.close()

    # ---- allowlist ------------------------------------------------------
    def test_allowlist_accepts_the_publishing_paths(self) -> None:
        self.assertEqual(publish.check_allowlist([
            'app/src/main/assets/translated.db',
            'database-versions.json',
            'database-manifest.json',
        ]), [])

    def test_allowlist_rejects_code_and_workflows(self) -> None:
        violations = publish.check_allowlist([
            'app/src/main/assets/translated.db',
            'app/src/main/java/com/meartraep/alician/mobile/MainActivity.kt',
            '.github/workflows/release-slsa.yml',
        ])
        self.assertEqual(len(violations), 2)

    # ---- notes ----------------------------------------------------------
    def test_notes_are_collapsed_and_capped(self) -> None:
        self.assertEqual(publish.normalise_notes('  第一行\n第二行  '), '第一行 第二行')
        self.assertEqual(publish.normalise_notes('   '), publish.DEFAULT_NOTES)
        self.assertEqual(publish.normalise_notes(None), publish.DEFAULT_NOTES)
        long_note = 'x' * (publish.MAX_NOTES_LENGTH + 100)
        self.assertEqual(len(publish.normalise_notes(long_note)), publish.MAX_NOTES_LENGTH)

    # ---- happy path -----------------------------------------------------
    def test_stamping_assigns_the_next_version(self) -> None:
        self.change()
        result = publish.stamp_database(self.db, notes='手机端发布测试', published_at='2026-10-20')
        self.assertTrue(result.needs_commit)
        self.assertEqual(result.version, 2)
        self.assertEqual([entry['db_version'] for entry in self.entries()], [1, 2])
        self.assertEqual(self.entries()[-1]['notes'], '手机端发布测试')
        self.assertEqual(dv.read_database_version(self.db), 2)
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        self.assertEqual(manifest['db_version'], 2)
        self.assertEqual(manifest['sha1'], result.sha1)
        self.assertEqual(dv.check_asset_matches_ledger(), [])

    def test_stamping_is_idempotent_for_a_rerun(self) -> None:
        self.change()
        publish.stamp_database(self.db, notes='第一次')
        second = publish.stamp_database(self.db, notes='第二次')
        self.assertFalse(second.needs_commit)
        self.assertEqual(second.version, 2)
        self.assertEqual([entry['db_version'] for entry in self.entries()], [1, 2],
                         'a rerun must not append a second entry')
        self.assertEqual(self.entries()[-1]['notes'], '第一次')

    def test_check_only_does_not_write(self) -> None:
        self.change()
        before = self.ledger.read_text(encoding='utf-8')
        result = publish.stamp_database(self.db, check_only=True)
        self.assertTrue(result.needs_commit)
        self.assertEqual(result.version, 2)
        self.assertEqual(self.ledger.read_text(encoding='utf-8'), before)
        self.assertEqual(dv.read_database_version(self.db), 1)

    # ---- refusals -------------------------------------------------------
    def test_identical_content_is_a_no_op(self) -> None:
        # Either a re-run of this pipeline or a database that is already published:
        # there is nothing to stamp, and no new ledger entry may appear.
        result = publish.stamp_database(self.db)
        self.assertFalse(result.needs_commit)
        self.assertEqual(result.version, 1)
        self.assertIn('already published', result.reason)
        self.assertEqual([entry['db_version'] for entry in self.entries()], [1])

    def test_marker_ahead_of_the_ledger_is_refused(self) -> None:
        self.change()
        dv.write_database_marker(self.db, {'db_version': '9'})
        with self.assertRaises(dv.VersioningError) as context:
            publish.stamp_database(self.db)
        self.assertIn('fix the marker', str(context.exception))

    def test_marker_that_the_ledger_never_assigned_is_refused(self) -> None:
        # A file stamped v2 while the ledger still ends at v1 was produced against a
        # different ledger state, so the pipeline refuses it instead of guessing.
        self.change()
        dv.write_database_marker(self.db, {
            'db_version': '2',
            'published_at': '2026-10-20',
            'notes': '手工戳的版本号',
        })
        with self.assertRaises(dv.VersioningError) as context:
            publish.stamp_database(self.db)
        self.assertIn('the ledger does not contain', str(context.exception))

    def test_second_edit_after_publishing_gets_the_next_version(self) -> None:
        self.change(' 第一次修改 ')
        publish.stamp_database(self.db, notes='v2')
        self.change(' 第二次修改 ')
        result = publish.stamp_database(self.db, notes='v3')
        self.assertTrue(result.needs_commit)
        self.assertEqual(result.version, 3)
        self.assertEqual(dv.read_database_version(self.db), 3)
        self.assertEqual(dv.check_asset_matches_ledger(), [])

    def test_publishing_twice_in_a_row_produces_unique_versions(self) -> None:
        self.change(' 第一次修改 ')
        first = publish.stamp_database(self.db, notes='v2')
        self.change(' 第二次修改 ')
        second = publish.stamp_database(self.db, notes='v3')
        self.assertEqual((first.version, second.version), (2, 3))
        self.assertEqual([entry['db_version'] for entry in self.entries()], [1, 2, 3])
        self.assertEqual(dv.validate_ledger(self.entries()), [])
        self.assertEqual(dv.check_asset_matches_ledger(), [])


if __name__ == '__main__':
    unittest.main()
