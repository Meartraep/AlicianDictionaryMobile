# -*- coding: utf-8 -*-
"""P3b acceptance tests — maintenance actions and whitelisted global replace.

Spec: ``.luna-review/p3b-spec.md`` (section 测试侧, 6 checks).  Coverage:

1. ``DataCoreEditing`` — ``DataCore.rebuild_no_class``: rebuilt ``no_class`` equals the
   distinct words of class-less ``dictionary`` senses, row count == distinct count,
   idempotent, no other table changes;
2. bridge ``maintenance_no_class`` — ok/inserted/source_rows, recovery point file, one
   extra ``backups/`` file, translator cache reloaded, integrity ok;
3. bridge ``update_word_count`` — recovery point exists and a sampled word's
   ``count``/``variety`` equals an independent recomputation from ``songs.lyric``;
4. bridge ``data_replace_preview`` / ``data_replace_apply`` — editable tables only,
   ``replaced == len(matches)``, recovery point exists, a real headword renamed,
   read-only ``raw`` untouched, the new value still matches the old keyword (substring
   semantics — the test does **not** assert "0 matches");
5. bridge ``data_diagnose`` — integrity ok, four orphan checks with
   ``song_translations == 1``, ``foreign_keys == 1``;
6. the shipped asset's SHA-256 never changes + CI wiring.

Every test copies the *shipped* database ``app/src/main/assets/translated.db`` into its
own ``tempfile.mkdtemp()``.  No fake schema, no production edits.

Run::

    cd app/src/test/python
    $env:PYTHONPATH = '<repo>/app/src/main/python'
    python -m unittest test_maintenance -v
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MAIN_PYTHON = REPO / "app" / "src" / "main" / "python"
ASSET_DB = REPO / "app" / "src" / "main" / "assets" / "translated.db"

if str(MAIN_PYTHON) not in sys.path:
    sys.path.insert(0, str(MAIN_PYTHON))

try:  # Windows console is GBK; Chinese assertion messages must not crash.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

from webui_backend import data_schema  # noqa: E402
from webui_backend.data_core import DataCore  # noqa: E402
from webui_backend.dictionary_core import DictionaryConfig  # noqa: E402

import mobile_bridge  # noqa: E402


ASSET_SHA256 = hashlib.sha256(ASSET_DB.read_bytes()).hexdigest()

#: Real-data expectations on the shipped database (re-derived in every test that uses
#: them; these constants only document the probe-verified values).
CLASS_LESS_SENSES = 36
CLASS_LESS_DISTINCT_WORDS = 29
SHIPPED_NO_CLASS_ROWS = 30
NO_CLASS_REPLACE_PREVIEW_MATCHES = 470
NO_CLASS_REPLACE_TABLES = {
    "dictionary",
    "dictionary_headwords",
    "sentence_alignments",
    "song_translations",
    "songs",
}
REPLACE_SAMPLE_WORDS = ("Xia", "Finz", "a", "end")


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_sql(path, statement: str, args=()):
    connection = sqlite3.connect(str(path))
    try:
        return [tuple(row) for row in connection.execute(statement, args).fetchall()]
    finally:
        connection.close()


def count_occurrences(lyric_lower: str, word_lower: str) -> int:
    """Whole-word occurrence count, same boundary rule as ``update_word_count.py``."""
    count = 0
    start = 0
    word_len = len(word_lower)
    lyric_len = len(lyric_lower)
    while start <= lyric_len - word_len:
        position = lyric_lower.find(word_lower, start)
        if position == -1:
            break
        left_ok = position == 0 or not lyric_lower[position - 1].isalnum()
        right_ok = (position + word_len) == lyric_len or not lyric_lower[position + word_len].isalnum()
        if left_ok and right_ok:
            count += 1
        start = position + 1
    return count


def independent_word_stats(db_path, word: str):
    """Recompute ``(count, variety)`` from ``songs.lyric`` without using the app code."""
    lyrics = [
        row[0]
        for row in read_sql(
            db_path, "SELECT lyric FROM songs WHERE lyric IS NOT NULL AND lyric != ''"
        )
    ]
    word_lower = word.lower()
    total = 0
    variety = 0
    for lyric in lyrics:
        occurrences = count_occurrences(lyric.lower(), word_lower)
        if occurrences > 0:
            total += occurrences
            variety += 1
    return total, variety


class RealDatabaseTestCase(unittest.TestCase):
    """One private copy of the shipped database per test."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="p3b-maintenance-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.db_path = str(self.tmpdir / "translated.db")
        shutil.copyfile(ASSET_DB, self.db_path)
        self.assertEqual(
            sha256_file(self.db_path),
            ASSET_SHA256,
            "the database under test must be a byte-for-byte copy of the shipped asset",
        )

    def scalar(self, statement: str, args=(), db_path=None):
        rows = read_sql(db_path or self.db_path, statement, args)
        return rows[0][0] if rows else None

    def table_counts(self) -> dict:
        counts = {}
        for (table,) in read_sql(
            self.db_path,
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
        ):
            counts[str(table)] = self.scalar('SELECT COUNT(*) FROM "%s"' % table)
        return counts

    def assert_asset_unmodified(self) -> None:
        self.assertEqual(
            hashlib.sha256(ASSET_DB.read_bytes()).hexdigest(),
            ASSET_SHA256,
            "the shipped database asset must never be modified by the tests",
        )


# ---------------------------------------------------------------------------
# Check 1 — DataCore.rebuild_no_class
# ---------------------------------------------------------------------------
class NoClassRebuildDataCoreTests(RealDatabaseTestCase):
    def test_rebuild_no_class_matches_dictionary_and_is_idempotent(self):
        self.core = DataCore(self.db_path, backups_dir=str(self.tmpdir / "backups"))
        self.assertTrue(self.core.connect(), "DataCore.connect() failed on a real DB copy")
        self.addCleanup(self.core.close)

        source_rows = self.scalar(
            "SELECT COUNT(*) FROM dictionary WHERE class IS NULL OR class = ''"
        )
        expected_words = {
            str(row[0])
            for row in read_sql(
                self.db_path,
                "SELECT DISTINCT words FROM dictionary WHERE class IS NULL OR class = ''",
            )
        }
        self.assertEqual(source_rows, CLASS_LESS_SENSES, "real data changed")
        self.assertEqual(len(expected_words), CLASS_LESS_DISTINCT_WORDS, "real data changed")
        shipped_rows = self.scalar("SELECT COUNT(*) FROM no_class")
        self.assertEqual(shipped_rows, SHIPPED_NO_CLASS_ROWS, "real data changed")
        counts_before = self.table_counts()
        dictionary_rows_before = self.scalar("SELECT COUNT(*) FROM dictionary")
        headword_rows_before = self.scalar("SELECT COUNT(*) FROM dictionary_headwords")

        result = self.core.rebuild_no_class()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["inserted"], CLASS_LESS_DISTINCT_WORDS, result)
        self.assertEqual(result["source_rows"], CLASS_LESS_SENSES, result)

        rebuilt_rows = self.scalar("SELECT COUNT(*) FROM no_class")
        rebuilt_words = {
            str(row[0]) for row in read_sql(self.db_path, "SELECT words FROM no_class")
        }
        self.assertEqual(rebuilt_rows, len(expected_words), "no_class row count != distinct words")
        self.assertEqual(rebuilt_rows, CLASS_LESS_DISTINCT_WORDS)
        self.assertEqual(rebuilt_words, expected_words, "no_class words != class-less dictionary words")

        # Nothing but no_class may change.
        counts_after = self.table_counts()
        for table, before in counts_before.items():
            if table == "no_class":
                continue
            self.assertEqual(counts_after.get(table), before, "table %r changed" % table)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM dictionary"), dictionary_rows_before)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary_headwords"), headword_rows_before
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary WHERE class IS NULL OR class = ''"),
            CLASS_LESS_SENSES,
            "the class-less senses themselves must be untouched",
        )

        # Idempotent: a second rebuild produces the same table.
        again = self.core.rebuild_no_class()
        self.assertTrue(again["ok"], again)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM no_class"), rebuilt_rows)
        self.assertEqual(
            {str(row[0]) for row in read_sql(self.db_path, "SELECT words FROM no_class")},
            expected_words,
        )
        self.assert_asset_unmodified()


# ---------------------------------------------------------------------------
# Checks 2-5 — bridge maintenance actions
# ---------------------------------------------------------------------------
class BridgeMaintenanceTests(RealDatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data_dir = self.tmpdir / "data"
        self.data_dir.mkdir()
        self.db_path = str(self.data_dir / "translated.db")
        shutil.copyfile(ASSET_DB, self.db_path)
        self.assertEqual(sha256_file(self.db_path), ASSET_SHA256)

        self._saved_cwd = os.getcwd()
        self._saved_env = {
            name: os.environ.get(name) for name in ("ALICIAN_DB_PATH", "ALICIAN_LITE_BUILD")
        }
        self._saved_config = (DictionaryConfig.DB_NAME, DictionaryConfig.CURRENT_DB)
        self.addCleanup(self._cleanup)

        init = json.loads(mobile_bridge.initialize(self.db_path, str(self.data_dir)))
        self.assertTrue(init.get("ok"), init.get("message"))
        self.core = mobile_bridge._data_core
        self.assertIsNotNone(self.core)

    def _cleanup(self) -> None:
        try:
            mobile_bridge._close_services()
        except Exception:  # pragma: no cover
            pass
        try:
            os.chdir(self._saved_cwd)
        except Exception:  # pragma: no cover
            pass
        for name, value in self._saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        DictionaryConfig.DB_NAME, DictionaryConfig.CURRENT_DB = self._saved_config

    def call(self, method: str, **payload):
        return json.loads(
            mobile_bridge.invoke(method, json.dumps(payload, ensure_ascii=False))
        )

    def backup_count(self) -> int:
        directory = self.data_dir / "backups"
        return len(list(directory.glob("*.db"))) if directory.is_dir() else 0

    # -- check 2 ---------------------------------------------------------
    def test_maintenance_no_class_via_bridge(self):
        source_rows = self.scalar(
            "SELECT COUNT(*) FROM dictionary WHERE class IS NULL OR class = ''"
        )
        expected_words = {
            str(row[0])
            for row in read_sql(
                self.db_path,
                "SELECT DISTINCT words FROM dictionary WHERE class IS NULL OR class = ''",
            )
        }
        self.assertEqual(source_rows, CLASS_LESS_SENSES)
        self.assertEqual(len(expected_words), CLASS_LESS_DISTINCT_WORDS)
        backups_before = self.backup_count()
        translator_before = id(mobile_bridge._translator)

        result = self.call("maintenance_no_class")
        self.assertTrue(result["ok"], result.get("message"))
        self.assertIn("no_class", str(result.get("message") or ""))
        self.assertEqual(result["inserted"], len(expected_words), result)
        self.assertEqual(result["source_rows"], source_rows, result)

        backup = str(result.get("backup") or "")
        self.assertTrue(backup, "maintenance_no_class must return a recovery point path")
        self.assertTrue(Path(backup).is_file(), backup)
        self.assertEqual(self.backup_count(), backups_before + 1)

        self.assertNotEqual(
            id(mobile_bridge._translator),
            translator_before,
            "no_class rebuild must reload the translator cache (event sink) ",
        )

        actual_rows = self.scalar("SELECT COUNT(*) FROM no_class")
        actual_words = {
            str(row[0]) for row in read_sql(self.db_path, "SELECT words FROM no_class")
        }
        self.assertEqual(actual_rows, len(expected_words))
        self.assertEqual(actual_words, expected_words)
        self.assertEqual(
            self.scalar("PRAGMA integrity_check"), "ok", "database integrity must stay ok"
        )

        # Idempotent through the bridge too, and one more recovery point.
        backups_after_first = self.backup_count()
        again = self.call("maintenance_no_class")
        self.assertTrue(again["ok"], again.get("message"))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM no_class"), actual_rows)
        self.assertEqual(self.backup_count(), backups_after_first + 1)
        self.assert_asset_unmodified()

    # -- check 3 ---------------------------------------------------------
    def test_update_word_count_recomputes_from_songs_lyric(self):
        # Corrupt a few sampled statistics first, so a no-op implementation cannot pass.
        sample_ids = {}
        for word in REPLACE_SAMPLE_WORDS:
            row = read_sql(
                self.db_path, "SELECT id FROM dictionary_headwords WHERE words = ?", (word,)
            )
            self.assertTrue(row, "real data changed: headword %r is missing" % word)
            sample_ids[word] = int(row[0][0])
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executemany(
                "UPDATE dictionary_headwords SET count = -1, variety = -1 WHERE id = ?",
                [(sample_id,) for sample_id in sample_ids.values()],
            )
            connection.commit()
        finally:
            connection.close()

        backups_before = self.backup_count()
        result = self.call("update_word_count")
        self.assertTrue(result["ok"], result.get("message"))
        backup = str(result.get("backup") or "")
        self.assertTrue(backup, "update_word_count must return a recovery point path")
        self.assertTrue(Path(backup).is_file(), backup)
        self.assertEqual(self.backup_count(), backups_before + 1)

        for word, headword_id in sample_ids.items():
            expected_count, expected_variety = independent_word_stats(self.db_path, word)
            actual = read_sql(
                self.db_path,
                "SELECT count, variety FROM dictionary_headwords WHERE id = ?",
                (headword_id,),
            )[0]
            self.assertEqual(
                (int(actual[0]), int(actual[1])),
                (expected_count, expected_variety),
                "recount mismatch for %r (songs.lyric source)" % word,
            )
            self.assertGreater(expected_count, 0, "sample word %r should occur in lyrics" % word)
            # dictionary rows mirror the headword statistics.
            mirrored = read_sql(
                self.db_path,
                "SELECT COUNT(*) FROM dictionary WHERE headword_id = ? AND "
                "(count != ? OR variety != ?)",
                (headword_id, expected_count, expected_variety),
            )[0][0]
            self.assertEqual(mirrored, 0, "dictionary statistics not synced for %r" % word)
        self.assertEqual(self.scalar("PRAGMA integrity_check"), "ok")
        self.assert_asset_unmodified()

    # -- check 4 ---------------------------------------------------------
    def test_global_replace_preview_and_apply(self):
        editable = set(data_schema.editable_table_names())
        raw_rows_before = read_sql(
            self.db_path, "SELECT * FROM raw ORDER BY rowid"
        )
        backups_before = self.backup_count()

        preview = self.call("data_replace_preview", keyword="Xia", replacement="XiaX")
        self.assertTrue(preview["ok"], preview.get("message"))
        matches = preview.get("matches") or []
        self.assertEqual(len(matches), NO_CLASS_REPLACE_PREVIEW_MATCHES,
                         "real data changed: expected 470 'Xia' matches")
        preview_tables = {str(match["table"]) for match in matches}
        self.assertEqual(preview_tables, NO_CLASS_REPLACE_TABLES)
        self.assertLessEqual(preview_tables, editable, "preview must only scan editable tables")
        self.assertNotIn("raw", preview_tables)
        for match in matches:
            self.assertIn("new_value", match)
            self.assertIn("Xia", str(match["value"]))
            self.assertIn("XiaX", str(match["new_value"]))

        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary_headwords WHERE words = 'Xia'"), 1
        )

        applied = self.call(
            "data_replace_apply", keyword="Xia", replacement="XiaX", matches=matches
        )
        self.assertTrue(applied["ok"], applied.get("message"))
        self.assertEqual(applied["replaced"], len(matches), applied)
        replaced_backup = str(applied.get("backup") or "")
        self.assertTrue(replaced_backup, "data_replace_apply must return a recovery point path")
        self.assertTrue(Path(replaced_backup).is_file(), replaced_backup)
        self.assertEqual(self.backup_count(), backups_before + 1)

        # A real headword was renamed; the renamed spelling exists in both tables.
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary_headwords WHERE words = 'Xia'"), 0
        )
        self.assertGreaterEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary_headwords WHERE words = 'XiaX'"), 1
        )
        self.assertGreaterEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary WHERE words = 'XiaX'"), 1
        )

        # Read-only tables were never touched.
        self.assertEqual(
            read_sql(self.db_path, "SELECT * FROM raw ORDER BY rowid"),
            raw_rows_before,
            "the read-only 'raw' table must not be touched by global replace",
        )

        # The trap: after replacing, a preview for the OLD keyword still matches because
        # the new value contains the old substring — assert content, not "0 matches".
        again = self.call("data_replace_preview", keyword="Xia", replacement="XiaX")
        self.assertTrue(again["ok"], again.get("message"))
        again_matches = again.get("matches") or []
        self.assertGreater(len(again_matches), 0, "substring semantics keep matching after replace")
        self.assertTrue(
            any("XiaX" in str(match["value"]) for match in again_matches),
            "post-replace preview must show the replacement substring",
        )
        self.assertEqual(self.scalar("PRAGMA integrity_check"), "ok")
        self.assert_asset_unmodified()

    # -- check 5 ---------------------------------------------------------
    def test_data_diagnose(self):
        report = self.call("data_diagnose")
        self.assertTrue(report["ok"], report.get("message"))
        self.assertEqual(report["integrity"], "ok")
        self.assertEqual(report["foreign_key_violations"], 0)

        orphans = report.get("orphans") or []
        self.assertEqual(len(orphans), 4, "diagnose must report the four known orphan checks")
        counts = {}
        for entry in orphans:
            for key in ("table", "label", "count"):
                self.assertIn(key, entry)
            counts[str(entry["table"])] = int(entry["count"])
        self.assertEqual(counts.get("song_translations"), 1,
                         "real data has one orphaned song_translations.song_title")
        for table in ("dictionary", "sentence_alignments", "dictionary_semantic_aliases"):
            self.assertEqual(counts.get(table), 0, table)

        self.assertEqual(report["pragmas"]["foreign_keys"], 1)
        self.assertEqual(report["pragmas"]["busy_timeout"], 5000)
        self.assertEqual(report["pragmas"]["journal_mode"], "delete")

        tables = {entry["name"]: entry for entry in report["tables"]}
        self.assertEqual(tables["dictionary"]["rows"], 1515)
        self.assertEqual(tables["dictionary_headwords"]["rows"], 1339)
        self.assertEqual(tables["songs"]["rows"], 53)
        self.assertIn("local_edits", report)
        self.assert_asset_unmodified()


# ---------------------------------------------------------------------------
# Check 6 — shipped asset guard
# ---------------------------------------------------------------------------
class ShippedAssetTests(unittest.TestCase):
    def test_shipped_database_asset_is_unmodified(self):
        self.assertEqual(
            hashlib.sha256(ASSET_DB.read_bytes()).hexdigest(),
            ASSET_SHA256,
            "tests must never open the shipped database for writing",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
