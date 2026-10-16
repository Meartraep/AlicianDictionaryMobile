# -*- coding: utf-8 -*-
"""Tests for verifying a database the phone published as a new version."""
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
import verify_published_database as verify  # noqa: E402


class PublicationTests(unittest.TestCase):
    """A publication is the base ledger plus one entry the phone stamped."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix='verifypublish'))
        self.base_ledger = self.tmp / 'base-ledger.json'
        self.db = self.tmp / 'translated.db'
        self.ledger = self.tmp / 'database-versions.json'
        self.manifest = self.tmp / 'database-manifest.json'
        self.saved = (dv.DB, dv.MANIFEST, dv.LEDGER)
        dv.DB, dv.MANIFEST, dv.LEDGER = self.db, self.manifest, self.ledger
        shutil.copy2(dv.LEDGER if dv.LEDGER.is_file() else REPO / 'database-versions.json',
                     self.base_ledger)
        self.base = json.loads(self.base_ledger.read_text(encoding='utf-8'))
        self.base_version = int(self.base[-1]['db_version'])
        self.publish()

    def tearDown(self) -> None:
        dv.DB, dv.MANIFEST, dv.LEDGER = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- fixtures -------------------------------------------------------
    def change_content(self, text: str = ' 手机端修改 ') -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                "UPDATE songs SET lyric = lyric || ? WHERE id = (SELECT MIN(id) FROM songs)",
                (text,))
            connection.commit()
        finally:
            connection.close()

    def publish(self, version: int | None = None, notes: str = '手机端发布',
                stamp: bool = True, manifest_ok: bool = True,
                ledger_sha1: str | None = None, ledger_size: int | None = None) -> dict:
        """Materialise a publishing pull request in the temp directory."""
        shutil.copy2(REPO / 'app/src/main/assets/translated.db', self.db)
        self.change_content()
        new_version = version if version is not None else self.base_version + 1
        if stamp:
            dv.write_database_marker(self.db, {
                'db_version': str(new_version),
                'published_at': '2026-10-16',
                'notes': notes,
                'format': dv.FORMAT,
            })
        size, digest = dv.file_identity(self.db)
        entry = {
            'db_version': new_version,
            'sha1': ledger_sha1 or digest,
            'size': ledger_size if ledger_size is not None else size,
            'published_at': '2026-10-16',
            'app_tag': '',
            'notes': notes,
        }
        entries = list(self.base) + [entry]
        self.ledger.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
        manifest = dv.build_manifest(entry) if manifest_ok else dict(dv.build_manifest(entry), size=1)
        self.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                 encoding='utf-8')
        return entry

    def problems(self):
        return verify.verify_published_database(
            self.db, self.ledger, self.manifest, self.base_ledger)

    # ---- accepted -------------------------------------------------------
    def test_valid_publication_is_accepted(self) -> None:
        self.assertEqual(self.problems(), [])

    def test_second_publication_from_a_newer_base_is_accepted(self) -> None:
        first = self.publish()
        base_two = self.tmp / 'base-two.json'
        base_two.write_text(self.ledger.read_text(encoding='utf-8'), encoding='utf-8')
        self.base_ledger = base_two
        self.base = json.loads(base_two.read_text(encoding='utf-8'))
        self.base_version = int(first['db_version'])
        self.publish()
        self.assertEqual(self.problems(), [])

    # ---- refused --------------------------------------------------------
    def test_publication_without_a_new_entry_is_refused(self) -> None:
        self.ledger.write_text(json.dumps(self.base, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
        self.assertIn('exactly one entry', ' '.join(self.problems()))

    def test_two_new_entries_are_refused(self) -> None:
        entries = json.loads(self.ledger.read_text(encoding='utf-8'))
        entries.append(dict(entries[-1], db_version=self.base_version + 2))
        self.ledger.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
        self.assertIn('exactly one entry', ' '.join(self.problems()))

    def test_modified_history_is_refused(self) -> None:
        entries = json.loads(self.ledger.read_text(encoding='utf-8'))
        entries[0] = dict(entries[0], notes='被改写的旧记录')
        self.ledger.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
        self.assertIn('already published', ' '.join(self.problems()))

    def test_version_must_be_exactly_the_next_one(self) -> None:
        self.publish(version=self.base_version + 3)
        self.assertIn('must be v%d' % (self.base_version + 1), ' '.join(self.problems()))

    def test_unstamped_database_is_refused_with_a_hint(self) -> None:
        self.publish(stamp=False)
        problems = ' '.join(self.problems())
        self.assertIn('marker', problems)
        self.assertIn('older app', problems)

    def test_ledger_sha1_must_describe_the_bytes(self) -> None:
        self.publish(ledger_sha1='a' * 40)
        self.assertIn('does not describe the uploaded database', ' '.join(self.problems()))

    def test_ledger_size_must_describe_the_bytes(self) -> None:
        self.publish(ledger_size=1)
        self.assertIn('does not describe the uploaded database', ' '.join(self.problems()))

    def test_unchanged_content_is_refused(self) -> None:
        # Re-upload the bytes that are already published, claiming the next version:
        # the entry is internally consistent, but there is nothing new to publish.
        shutil.copy2(REPO / 'app/src/main/assets/translated.db', self.db)
        size, digest = dv.file_identity(self.db)
        self.assertEqual(digest, str(self.base[-1]['sha1']).lower(),
                         'the fixture must upload the already published bytes')
        entries = json.loads(self.ledger.read_text(encoding='utf-8'))
        entries[-1] = dict(entries[-1], db_version=self.base_version + 1, sha1=digest, size=size)
        self.ledger.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
        self.manifest.write_text(
            json.dumps(dv.build_manifest(entries[-1]), ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8')
        self.assertIn('nothing to publish', ' '.join(self.problems()))

    def test_manifest_must_be_the_projection(self) -> None:
        self.publish(manifest_ok=False)
        self.assertIn('not the projection', ' '.join(self.problems()))

    def test_empty_note_is_refused(self) -> None:
        self.publish(notes='')
        self.assertIn('no release note', ' '.join(self.problems()))

    def test_too_long_note_is_refused(self) -> None:
        self.publish(notes='x' * (verify.MAX_NOTES_LENGTH + 1))
        self.assertIn('longer than', ' '.join(self.problems()))

    # ---- allowlist ------------------------------------------------------
    def test_allowlist_accepts_the_publishing_paths(self) -> None:
        self.assertEqual(verify.check_allowlist([
            'app/src/main/assets/translated.db',
            'database-versions.json',
            'database-manifest.json',
        ]), [])

    def test_allowlist_rejects_code_and_workflows(self) -> None:
        violations = verify.check_allowlist([
            'app/src/main/assets/translated.db',
            'app/src/main/java/com/meartraep/alician/mobile/MainActivity.kt',
            '.github/workflows/release-slsa.yml',
        ])
        self.assertEqual(len(violations), 2)


if __name__ == '__main__':
    unittest.main()
