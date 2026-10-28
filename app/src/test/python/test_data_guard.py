# -*- coding: utf-8 -*-
"""P0 acceptance tests for the unified data layer: schema registry + ``DataCore``.

Contract: ``.luna-review/p0-interface.md`` (authoritative).  Coverage maps to its
11-item acceptance list, items 1-9 and 11 (recovery points live in
``test_backup_restore.py``).

Every test copies the *shipped* database ``app/src/main/assets/translated.db``
into a fresh ``tempfile.mkdtemp()`` and constructs
``DataCore(<copy>, backups_dir=<tmp>/backups)``.  No fake schema is built and the
shipped asset is never opened for writing (its SHA-256 is asserted before every
test and again at the end of the run).

Run::

    cd app/src/test/python
    $env:PYTHONPATH = '<repo>/app/src/main/python'
    python -m unittest test_data_guard -v
"""

from __future__ import annotations

import hashlib
import json
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
from webui_backend.data_core import DataCore, DataError  # noqa: E402


ASSET_SHA256 = hashlib.sha256(ASSET_DB.read_bytes()).hexdigest()


def _shipped_business_tables() -> list:
    connection = sqlite3.connect("file:" + ASSET_DB.as_posix() + "?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        connection.close()
    return [str(row[0]) for row in rows]


SHIPPED_TABLES = _shipped_business_tables()
EDITABLE_TABLES = [
    "dictionary_headwords",
    "dictionary",
    "phrase",
    "songs",
    "sentence_alignments",
    "song_translations",
]

#: Tables whose DDL must not change when ``DataCore.connect()`` ensures the ledger.
_ALL_TABLES = list(SHIPPED_TABLES)


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def field_names(fields) -> list:
    """``table_fields``/``page.fields`` entry names (dicts or plain strings)."""
    names = []
    for field in fields or ():
        if isinstance(field, dict):
            names.append(str(field.get("name")))
        else:
            names.append(str(field))
    return names


class RealDatabaseTestCase(unittest.TestCase):
    """One private copy of the shipped database + one connected ``DataCore`` per test."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="p0-data-guard-"))
        self.addCleanup(self._cleanup_tmpdir)
        self.db_path = str(self.tmpdir / "translated.db")
        self.backups_dir = str(self.tmpdir / "backups")
        self._copy_module()
        self.core = DataCore(self.db_path, backups_dir=self.backups_dir)
        self.assertTrue(self.core.connect(), "DataCore.connect() failed on a real DB copy")

    def _cleanup_tmpdir(self) -> None:
        try:
            self.core.close()
        except Exception:  # pragma: no cover - never mask a test failure
            pass
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _copy_module(self) -> None:
        import shutil

        shutil.copyfile(ASSET_DB, self.db_path)
        self.assertEqual(
            sha256_file(self.db_path),
            ASSET_SHA256,
            "the database under test must be a byte-for-byte copy of the shipped asset",
        )

    # ------------------------------------------------------------- sql helpers

    def sql(self, statement: str, args=()):
        connection = sqlite3.connect(self.db_path)
        try:
            return [tuple(row) for row in connection.execute(statement, args).fetchall()]
        finally:
            connection.close()

    def scalar(self, statement: str, args=()):
        rows = self.sql(statement, args)
        return rows[0][0] if rows else None

    def content_snapshot(self, tables=None):
        snapshot = {}
        for table in tables or _ALL_TABLES:
            if table in ("local_edits",):
                continue
            snapshot[table] = self.sql('SELECT * FROM "%s" ORDER BY rowid' % table)
        return snapshot

    # ----------------------------------------------------------- assertions

    def assert_rejected(self, message_part: str, callable_, tables=None):
        """A write must raise DataError, not change the data and not leak a transaction."""
        before = self.content_snapshot(tables)
        ledger_before = self.core.local_edits_count()
        with self.assertRaises(DataError) as caught:
            callable_()
        message = str(caught.exception)
        self.assertTrue(message.strip(), "DataError must carry a user-visible message")
        self.assertIn(message_part, message)
        self.assertEqual(
            self.content_snapshot(tables), before, "a rejected write must not change the data"
        )
        self.assertEqual(
            self.core.local_edits_count(), ledger_before, "a rejected write must not be audited"
        )
        if self.core.conn is not None:
            self.assertFalse(
                self.core.conn.in_transaction,
                "a rejected write must not leave the connection inside a transaction",
            )

    def assert_asset_unmodified(self) -> None:
        self.assertEqual(
            hashlib.sha256(ASSET_DB.read_bytes()).hexdigest(),
            ASSET_SHA256,
            "the shipped database asset must never be modified by the tests",
        )


# ---------------------------------------------------------------------------
# data_schema.py — declarative registry (CONTRACT "data_schema.py")
# ---------------------------------------------------------------------------
class SchemaRegistryTests(RealDatabaseTestCase):
    def test_spec_is_a_frozen_dataclass(self):
        spec = data_schema.spec_for("dictionary_headwords")
        self.assertIsInstance(spec, data_schema.TableSpec)
        self.assertEqual(spec.name, "dictionary_headwords")
        with self.assertRaises(Exception):
            spec.name = "changed"  # frozen dataclass must reject mutation

    def test_group_constants_and_titles(self):
        self.assertEqual(data_schema.GROUP_CORE, "core")
        self.assertEqual(data_schema.GROUP_LYRIC, "lyric")
        self.assertEqual(data_schema.GROUP_SEMANTIC, "semantic")
        self.assertEqual(data_schema.GROUP_SYSTEM, "system")
        self.assertEqual(data_schema.GROUP_LEGACY, "legacy")
        expected = {
            data_schema.GROUP_CORE: "核心词典",
            data_schema.GROUP_LYRIC: "歌词与译文",
            data_schema.GROUP_SEMANTIC: "语义（只读）",
            data_schema.GROUP_SYSTEM: "系统（只读）",
            data_schema.GROUP_LEGACY: "遗留表（只读）",
        }
        for group, title in expected.items():
            self.assertIn(group, data_schema.GROUPS)
            self.assertEqual(data_schema.GROUPS[group]["title"], title)

    def test_editable_table_names_are_exactly_the_contract_six(self):
        self.assertEqual(set(data_schema.editable_table_names()), set(EDITABLE_TABLES))
        self.assertEqual(len(data_schema.editable_table_names()), len(EDITABLE_TABLES))

    def test_registry_covers_every_shipped_business_table(self):
        registered = set(data_schema.TABLES)
        missing = [table for table in SHIPPED_TABLES if table not in registered]
        self.assertEqual(missing, [], "every shipped business table must be registered")
        extra = sorted(registered - set(SHIPPED_TABLES))
        self.assertEqual(
            extra,
            ["local_edits"],
            "only the auto-created local_edits table may be registered without being shipped",
        )
        self.assertEqual(len(SHIPPED_TABLES), 32, "real database has 32 business tables")

    def test_named_tables_have_contract_group_and_editability(self):
        expected = {
            "dictionary_headwords": (data_schema.GROUP_CORE, True),
            "dictionary": (data_schema.GROUP_CORE, True),
            "phrase": (data_schema.GROUP_CORE, True),
            "songs": (data_schema.GROUP_LYRIC, True),
            "sentence_alignments": (data_schema.GROUP_LYRIC, True),
            "song_translations": (data_schema.GROUP_LYRIC, True),
            "dictionary_semantic_aliases": (data_schema.GROUP_SEMANTIC, False),
            "semantic_alias_metadata": (data_schema.GROUP_SEMANTIC, False),
            "adverb_position_stats": (data_schema.GROUP_SEMANTIC, False),
            "database_metadata": (data_schema.GROUP_SYSTEM, False),
            "Signature": (data_schema.GROUP_SYSTEM, False),
            "local_edits": (data_schema.GROUP_SYSTEM, False),
            "raw": (data_schema.GROUP_LEGACY, False),
            "Album1": (data_schema.GROUP_LEGACY, False),
            "Album2": (data_schema.GROUP_LEGACY, False),
            "Album3": (data_schema.GROUP_LEGACY, False),
            "Single": (data_schema.GROUP_LEGACY, False),
            "All_words": (data_schema.GROUP_LEGACY, False),
            "Unknown": (data_schema.GROUP_LEGACY, False),
            "test": (data_schema.GROUP_LEGACY, False),
            "no_class": (data_schema.GROUP_LEGACY, False),
        }
        for table, (group, editable) in expected.items():
            self.assertIn(table, data_schema.TABLES, "missing registry entry for %r" % table)
            spec = data_schema.TABLES[table]
            self.assertEqual(spec.group, group, table)
            self.assertEqual(spec.editable, editable, table)
            self.assertTrue(str(spec.label).strip(), "table %r needs a UI label" % table)

        pos_tables = [table for table in SHIPPED_TABLES if table.endswith(".")]
        self.assertGreaterEqual(len(pos_tables), 12)
        for table in pos_tables:
            spec = data_schema.TABLES[table]
            self.assertEqual(spec.group, data_schema.GROUP_LEGACY, table)
            self.assertFalse(spec.editable, table)

    def test_spec_for_unregistered_table_is_readonly_legacy(self):
        spec = data_schema.spec_for("future_table_not_in_db")
        self.assertFalse(spec.editable)
        self.assertEqual(spec.group, data_schema.GROUP_LEGACY)
        self.assertEqual(spec.name, "future_table_not_in_db")
        # unknown/None-ish names must not raise
        self.assertFalse(data_schema.spec_for("").editable)

    def test_write_rules_cover_contract_minimum(self):
        headwords = data_schema.TABLES["dictionary_headwords"]
        self.assertIn("words", headwords.required)
        self.assertIn(("words",), tuple(tuple(group) for group in headwords.unique))
        self.assertIn(("words", 64), tuple(headwords.max_length))
        self.assertIn(("display_explanation", 500), tuple(headwords.max_length))

        phrase = data_schema.TABLES["phrase"]
        self.assertIn("PHRASE", phrase.required)
        self.assertIn(("PHRASE",), tuple(tuple(group) for group in phrase.unique))

        songs = data_schema.TABLES["songs"]
        self.assertIn("title", songs.required)
        self.assertIn(("title",), tuple(tuple(group) for group in songs.unique))

        translations = data_schema.TABLES["song_translations"]
        self.assertIn("song_title", translations.required)
        self.assertIn("sentence", translations.required)
        self.assertIn(("song_title", "sentence"), tuple(tuple(g) for g in translations.unique))

        senses = data_schema.TABLES["dictionary"]
        for column in ("headword_id", "words", "explanation", "sense_order"):
            self.assertIn(column, senses.required)

        alignments = data_schema.TABLES["sentence_alignments"]
        for column in ("song_id", "song_title", "alician_sentence"):
            self.assertIn(column, alignments.required)

    def test_cascade_rules(self):
        headword_pairs = [tuple(entry[:2]) for entry in data_schema.TABLES["dictionary_headwords"].cascade]
        self.assertIn(("dictionary", "headword_id"), headword_pairs)
        song_pairs = [tuple(entry[:2]) for entry in data_schema.TABLES["songs"].cascade]
        self.assertIn(("sentence_alignments", "song_id"), song_pairs)
        self.assertIn(("song_translations", "song_title"), song_pairs)

    def test_grouped_tables(self):
        grouped = data_schema.grouped_tables()
        self.assertIsInstance(grouped, list)
        self.assertEqual(
            [entry["group"] for entry in grouped],
            [
                data_schema.GROUP_CORE,
                data_schema.GROUP_LYRIC,
                data_schema.GROUP_SEMANTIC,
                data_schema.GROUP_SYSTEM,
                data_schema.GROUP_LEGACY,
            ],
        )
        listed = []
        for entry in grouped:
            self.assertTrue(entry["title"])
            self.assertIn("tables", entry)
            for table in entry["tables"]:
                self.assertIn("name", table)
                self.assertIn("label", table)
                self.assertIn("editable", table)
                listed.append(table["name"])
        self.assertEqual(sorted(listed), sorted(data_schema.TABLES))


# ---------------------------------------------------------------------------
# Acceptance 1 — connection policy (contract "连接行为")
# ---------------------------------------------------------------------------
class ConnectionTests(RealDatabaseTestCase):
    def test_connect_is_idempotent_and_reopens_after_close(self):
        self.assertTrue(self.core.connect(), "repeated connect() must be safe")
        self.assertTrue(self.core.connect())
        self.assertIsNotNone(self.core.conn)
        self.core.close()
        self.core.close()  # close() is idempotent
        self.assertIsNone(self.core.conn)
        self.assertTrue(self.core.connect(), "connect() must work again after close()")
        self.assertIsNotNone(self.core.conn)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM dictionary"), 1515)

    def test_missing_database_file_is_reported_not_raised(self):
        missing = DataCore(str(self.tmpdir / "does-not-exist.db"))
        self.assertFalse(missing.connect())
        self.assertTrue(str(missing.last_error).strip())

    def test_connection_pragmas_match_contract(self):
        pragmas = self.core.diagnose()["pragmas"]
        self.assertEqual(pragmas["foreign_keys"], 1)
        self.assertEqual(pragmas["busy_timeout"], 5000)
        self.assertEqual(pragmas["synchronous"], 2)  # FULL
        self.assertEqual(pragmas["journal_mode"], "delete")  # TODO contract: no WAL

    def test_local_edits_table_is_created_lazily_on_first_write(self):
        # CONTRACT/interface detail: the ledger is created on demand, NOT in connect(),
        # so a fresh install's database bytes are untouched until the first edit.
        self.assertNotIn("local_edits", self.core.table_names())
        self.assertEqual(self.core.local_edits_count(), 0)
        self.assertEqual(self.core.local_edits(), [])

        connection = sqlite3.connect("file:" + ASSET_DB.as_posix() + "?mode=ro", uri=True)
        try:
            original = {
                row[0]: row[1]
                for row in connection.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
        finally:
            connection.close()
        current = {
            row[0]: row[1]
            for row in self.sql("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        }
        self.assertEqual(current, original, "connect() must not change the shipped schema")

        created = self.core.create("phrase", {"PHRASE": "P0 ledger materialiser"})
        self.assertTrue(created["ok"])
        self.assertIn("local_edits", self.core.table_names())
        self.assertEqual(self.core.local_edits_count(), 1)

        columns = {
            str(row[1]): row
            for row in self.sql("PRAGMA table_info(local_edits)")
        }
        for column in ("id", "table_name", "row_key", "op", "summary", "changed_at"):
            self.assertIn(column, columns)
        self.assertEqual(columns["id"][5], 1, "local_edits.id must be the primary key")
        for column in ("table_name", "row_key", "op", "summary", "changed_at"):
            self.assertEqual(columns[column][3], 1, "local_edits.%s must be NOT NULL" % column)

        # The rest of the shipped schema must stay untouched (contract: 其余 schema 不改动).
        connection = sqlite3.connect("file:" + ASSET_DB.as_posix() + "?mode=ro", uri=True)
        try:
            original = {
                row[0]: row[1]
                for row in connection.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
        finally:
            connection.close()
        current = {
            row[0]: row[1]
            for row in self.sql("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        }
        self.assertEqual(set(current) - set(original), {"local_edits"})
        for table in original:
            self.assertEqual(current[table], original[table], "schema of %r changed" % table)

    def test_table_names_is_shipped_tables_plus_ledger(self):
        # Lazy ledger: no local_edits before the first write ...
        self.assertEqual(set(self.core.table_names()), set(SHIPPED_TABLES))
        self.assertEqual(len(self.core.table_names()), len(SHIPPED_TABLES))
        # ... and exactly one extra table once something has been written.
        self.core.create("phrase", {"PHRASE": "P0 table names"})
        names = self.core.table_names()
        self.assertEqual(len(names), len(SHIPPED_TABLES) + 1)
        self.assertEqual(set(names), set(SHIPPED_TABLES) | {"local_edits"})

    def test_table_fields_contract_keys(self):
        fields = self.core.table_fields("dictionary")
        self.assertIsInstance(fields, list)
        for field in fields:
            self.assertIsInstance(field, dict)
            for key in ("name", "type", "notnull", "pk", "default"):
                self.assertIn(key, field)
        by_name = {str(field["name"]): field for field in fields}
        self.assertEqual(by_name["id"]["pk"], 1)
        self.assertEqual(by_name["explanation"]["notnull"], True)
        self.assertIn("INTEGER", str(by_name["sense_order"]["type"]).upper())


# ---------------------------------------------------------------------------
# Acceptance 2 — paging (contract "page")
# ---------------------------------------------------------------------------
class PageTests(RealDatabaseTestCase):
    def test_dictionary_page_is_server_side_and_complete(self):
        page = self.core.page("dictionary", limit=10)
        self.assertTrue(page["ok"])
        self.assertEqual(page["table"], "dictionary")
        self.assertEqual(page["total"], 1515)
        self.assertEqual(page["offset"], 0)
        self.assertEqual(page["limit"], 10)
        self.assertEqual(len(page["rows"]), 10)
        self.assertIsInstance(page["rows"][0], dict)
        self.assertIn("id", page["rows"][0])
        # Real data has a few deleted ids (6, 168, 1114, 1495), so compare with the
        # database's own first ten keys instead of assuming contiguous numbering.
        expected_ids = [row[0] for row in self.sql("SELECT id FROM dictionary ORDER BY id LIMIT 10")]
        self.assertEqual([row["id"] for row in page["rows"]], expected_ids)
        payload = json.dumps(page, ensure_ascii=False, default=str)
        self.assertLess(len(payload.encode("utf-8")), 50_000, "a 10-row page must stay small")

    def test_keyword_filter_matches_rows(self):
        page = self.core.page("dictionary", keyword="Finz", limit=50)
        self.assertGreaterEqual(page["total"], 1, "keyword must hit real rows")
        self.assertLessEqual(len(page["rows"]), 50)
        for row in page["rows"]:
            values = [str(value) for value in row.values() if value is not None]
            self.assertTrue(
                any("finz" in value.lower() for value in values),
                "row %r does not contain the keyword" % (row,),
            )
        empty = self.core.page("dictionary", keyword="P0NoSuchTokenZzz")
        self.assertEqual(empty["total"], 0)
        self.assertEqual(empty["rows"], [])

    def test_exact_keyword_filter(self):
        page = self.core.page("dictionary", keyword="Finz", exact=True)
        self.assertGreaterEqual(page["total"], 1)
        for row in page["rows"]:
            values = [str(value).lower() for value in row.values() if value is not None]
            self.assertIn("finz", values, "exact search must match whole field values only")

    def test_limit_is_clamped_to_the_contract_range(self):
        # CONTRACT page: limit is clamped to 1..200.  Zero/None fall back to the
        # default page size; the response always reports the effective limit.
        zero = self.core.page("dictionary", limit=0)
        self.assertGreaterEqual(zero["limit"], 1)
        self.assertLessEqual(zero["limit"], 200)
        self.assertEqual(len(zero["rows"]), zero["limit"])
        clamped = self.core.page("dictionary", limit=5000)
        self.assertEqual(clamped["limit"], 200)
        self.assertEqual(len(clamped["rows"]), 200)
        bounded = self.core.page("dictionary", limit=500)
        self.assertEqual(bounded["limit"], 200)
        self.assertEqual(len(bounded["rows"]), 200)

    def test_offset_walks_the_table(self):
        expected_ids = [
            row[0] for row in self.sql("SELECT id FROM dictionary ORDER BY id LIMIT 50 OFFSET 1500")
        ]
        page = self.core.page("dictionary", offset=1500, limit=50)
        self.assertEqual(page["offset"], 1500)
        self.assertEqual(page["total"], 1515)
        self.assertEqual(len(page["rows"]), len(expected_ids))
        self.assertEqual(len(page["rows"]), 15)
        self.assertEqual([row["id"] for row in page["rows"]], expected_ids)

    def test_table_without_id_column_uses_rowid(self):
        page = self.core.page("Album1", limit=5)
        self.assertEqual(page["total"], 247)
        self.assertEqual(len(page["rows"]), 5)
        names = field_names(page["fields"])
        self.assertEqual(names[0], "rowid", "tables without id must key on rowid (CONTRACT page)")
        self.assertIn("rowid", page["rows"][0])
        row = self.core.row("Album1", 1)
        self.assertIsNotNone(row)
        self.assertEqual(row["rowid"], 1)

    def test_large_table_page_stays_bounded(self):
        page = self.core.page("sentence_alignments", limit=200)
        self.assertEqual(page["total"], 1286)
        self.assertEqual(page["limit"], 200)
        self.assertEqual(len(page["rows"]), 200)
        # Server-side paging is the point: one request is capped at 200 rows no matter
        # how large the table is.  (Measured today: ~244 KiB of UTF-8 for this page;
        # see .luna-review/p0-tests/report.md for the plan §4.8 payload note.)
        payload = json.dumps(page, ensure_ascii=False, default=str).encode("utf-8")
        self.assertLess(len(payload), 1024 * 1024, "one page must stay bounded")
        small = self.core.page("sentence_alignments", limit=50)
        self.assertEqual(len(small["rows"]), 50)
        self.assertLess(
            len(json.dumps(small, ensure_ascii=False, default=str).encode("utf-8")),
            len(payload),
            "payload must grow with the page size, not with the table size",
        )

    def test_unknown_table_is_rejected(self):
        with self.assertRaises(DataError) as caught:
            self.core.page("no_such_table")
        self.assertIn("未知数据表", str(caught.exception))

    def test_table_name_injection_is_rejected_and_database_survives(self):
        before = self.core.page("songs", limit=1)["total"]
        for injected in (
            'dictionary"; DROP TABLE songs; --',
            "dictionary' OR 1=1 --",
            'dictionary" UNION SELECT 1 --',
        ):
            with self.assertRaises(DataError) as caught:
                self.core.page(injected)
            self.assertIn("未知数据表", str(caught.exception))
        self.assertEqual(self.core.page("songs", limit=1)["total"], before)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM songs"), 53)

    def test_row_lookup(self):
        row = self.core.row("dictionary", 1)
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], 1)
        self.assertEqual(row["words"], "a")
        self.assertIsNone(self.core.row("dictionary", 10_000_000))


# ---------------------------------------------------------------------------
# Acceptance 3 — read-only tables (contract: 只读表永远不可写)
# ---------------------------------------------------------------------------
class ReadonlyTests(RealDatabaseTestCase):
    def test_database_metadata_is_readonly(self):
        before = self.core.page("database_metadata", limit=50)["rows"]
        self.assert_rejected(
            "只读",
            lambda: self.core.create("database_metadata", {"key": "x", "value": "y"}),
        )
        self.assert_rejected(
            "只读", lambda: self.core.update("database_metadata", 1, {"value": "99"})
        )
        self.assert_rejected("只读", lambda: self.core.delete("database_metadata", [1]))
        self.assertEqual(self.core.page("database_metadata", limit=50)["rows"], before)

    def test_semantic_and_legacy_tables_are_readonly(self):
        for table in (
            "dictionary_semantic_aliases",
            "semantic_alias_metadata",
            "adverb_position_stats",
            "raw",
            "Album1",
            "n.",
        ):
            spec = data_schema.spec_for(table)
            self.assertFalse(spec.editable, table)
            self.assert_rejected(
                "只读",
                lambda table=table: self.core.create(table, {"whatever": "x"}),
            )

    def test_local_edits_ledger_is_readonly_after_creation(self):
        # The ledger is created lazily by the first successful write; from then on it
        # is a system table and must never be editable through the guard.
        self.core.create("phrase", {"PHRASE": "P0 ledger readonly"})
        self.assertIn("local_edits", self.core.table_names())
        self.assertFalse(data_schema.spec_for("local_edits").editable)
        self.assert_rejected(
            "只读", lambda: self.core.create("local_edits", {"whatever": "x"})
        )


# ---------------------------------------------------------------------------
# Acceptance 4 — write validation (contract "create/update/delete/batch_update")
# ---------------------------------------------------------------------------
class ValidationTests(RealDatabaseTestCase):
    def test_unknown_field_is_rejected(self):
        self.assert_rejected(
            "字段",
            lambda: self.core.create(
                "phrase", {"PHRASE": "P0 new phrase", "no_such_column": "x"}
            ),
        )
        self.assert_rejected(
            "字段",
            lambda: self.core.update("phrase", 1, {"no_such_column": "x"}),
        )

    def test_missing_required_value_is_rejected(self):
        self.assert_rejected(
            "不能为空",
            lambda: self.core.create("phrase", {"explanation": "no phrase key"}),
        )
        self.assert_rejected(
            "不能为空",
            lambda: self.core.create("dictionary_headwords", {"display_explanation": "x"}),
        )

    def test_blank_required_value_is_rejected(self):
        self.assert_rejected(
            "不能为空", lambda: self.core.create("phrase", {"PHRASE": "   "})
        )
        self.assert_rejected(
            "不能为空",
            lambda: self.core.create(
                "dictionary",
                {
                    "headword_id": 1,
                    "words": "a",
                    "explanation": "   ",
                    "sense_order": 9,
                },
            ),
        )

    def test_overlong_value_is_rejected(self):
        self.assert_rejected(
            "过长",
            lambda: self.core.create(
                "dictionary_headwords", {"words": "x" * 65, "display_explanation": "y"}
            ),
        )
        self.assert_rejected(
            "过长", lambda: self.core.update("phrase", 1, {"explanation": "y" * 501})
        )

    def test_type_mismatch_is_rejected(self):
        self.assert_rejected(
            "整数",
            lambda: self.core.create(
                "dictionary",
                {
                    "headword_id": 1,
                    "words": "a",
                    "explanation": "type test",
                    "sense_order": "not-an-int",
                },
            ),
        )
        self.assert_rejected(
            "整数",
            lambda: self.core.update("dictionary", 1, {"sense_order": "1.5"}),
        )

    def test_case_insensitive_duplicate_is_rejected(self):
        existing = self.sql("SELECT PHRASE FROM phrase WHERE id = 1")[0][0]
        before = self.content_snapshot(["phrase"])
        self.assert_rejected(
            "已存在",
            lambda: self.core.create("phrase", {"PHRASE": str(existing).upper()}),
            tables=["phrase"],
        )
        self.assert_rejected(
            "已存在",
            lambda: self.core.update("phrase", 2, {"PHRASE": str(existing).upper()}),
            tables=["phrase"],
        )
        self.assertEqual(self.content_snapshot(["phrase"]), before)

    def test_self_update_does_not_count_as_duplicate(self):
        existing = self.sql("SELECT PHRASE FROM phrase WHERE id = 1")[0][0]
        result = self.core.update("phrase", 1, {"PHRASE": str(existing).upper()})
        self.assertTrue(result["ok"])
        self.assertEqual(
            self.sql("SELECT PHRASE FROM phrase WHERE id = 1")[0][0], str(existing).upper()
        )
        self.assertEqual(self.core.local_edits_count(), 1)

    def test_missing_foreign_key_is_rejected(self):
        self.assert_rejected(
            "不存在",
            lambda: self.core.create(
                "dictionary",
                {
                    "headword_id": 999_999,
                    "words": "ghost",
                    "explanation": "ghost",
                    "sense_order": 1,
                },
            ),
        )

    def test_update_and_delete_of_missing_row_are_rejected(self):
        self.assert_rejected(
            "未找到", lambda: self.core.update("phrase", 999_999, {"explanation": "x"})
        )
        self.assert_rejected("未找到", lambda: self.core.delete("phrase", [999_999]))

    def test_empty_delete_selection_is_rejected(self):
        self.assert_rejected("请选择", lambda: self.core.delete("phrase", []))

    def test_unknown_table_create_is_rejected(self):
        with self.assertRaises(DataError) as caught:
            self.core.create("no_such_table", {"foo": "bar"})
        self.assertTrue(str(caught.exception).strip())

    def test_all_failed_writes_leave_the_database_unchanged(self):
        before = self.content_snapshot()
        failures = [
            lambda: self.core.create("database_metadata", {"key": "x"}),
            lambda: self.core.create("phrase", {"PHRASE": "   "}),
            lambda: self.core.create("phrase", {"PHRASE": "x" * 5000}),
            lambda: self.core.create("dictionary", {"headword_id": 999_999, "words": "g",
                                                   "explanation": "g", "sense_order": 1}),
            lambda: self.core.update("phrase", 999_999, {"explanation": "x"}),
            lambda: self.core.delete("raw", [1]),
            lambda: self.core.batch_update(
                "phrase", [{"id": 1, "values": {"PHRASE": "Kulu Nai"}}]
            ),
        ]
        for failure in failures:
            with self.assertRaises(DataError):
                failure()
        self.assertEqual(self.content_snapshot(), before)
        self.assertEqual(self.core.local_edits_count(), 0)


# ---------------------------------------------------------------------------
# Acceptance 5 — transaction hygiene (contract "batch_update")
# ---------------------------------------------------------------------------
class TransactionTests(RealDatabaseTestCase):
    def test_batch_update_failure_rolls_back_everything_and_connection_recovers(self):
        original = self.sql("SELECT explanation FROM phrase WHERE id = 1")[0][0]
        existing_phrase = self.sql("SELECT PHRASE FROM phrase WHERE id = 3")[0][0]
        before = self.content_snapshot(["phrase"])
        ledger_before = self.core.local_edits_count()

        with self.assertRaises(DataError) as caught:
            self.core.batch_update(
                "phrase",
                [
                    {"id": 1, "values": {"explanation": "P0 must be rolled back"}},
                    {"id": 2, "values": {"PHRASE": str(existing_phrase)}},
                ],
            )
        self.assertIn("已存在", str(caught.exception))

        self.assertEqual(
            self.content_snapshot(["phrase"]), before, "nothing from a failed batch may persist"
        )
        self.assertEqual(self.core.local_edits_count(), ledger_before)
        self.assertFalse(self.core.conn.in_transaction, "failed batch must roll back")
        self.assertEqual(
            self.sql("SELECT explanation FROM phrase WHERE id = 1")[0][0], original
        )

        # The connection must be usable again: the very next write succeeds.
        result = self.core.update("phrase", 1, {"explanation": "P0 after rollback"})
        self.assertTrue(result["ok"])
        self.assertEqual(
            self.sql("SELECT explanation FROM phrase WHERE id = 1")[0][0], "P0 after rollback"
        )
        self.assertEqual(self.core.local_edits_count(), ledger_before + 1)

    def test_missing_row_in_batch_is_rejected_atomically(self):
        before = self.content_snapshot(["phrase"])
        with self.assertRaises(DataError) as caught:
            self.core.batch_update(
                "phrase",
                [
                    {"id": 1, "values": {"explanation": "P0 first edit"}},
                    {"id": 999_999, "values": {"explanation": "P0 missing row"}},
                ],
            )
        self.assertIn("未找到", str(caught.exception))
        self.assertEqual(self.content_snapshot(["phrase"]), before)
        self.assertFalse(self.core.conn.in_transaction)

    def test_successful_batch_commits_all_edits_in_one_transaction(self):
        ledger_before = self.core.local_edits_count()
        result = self.core.batch_update(
            "phrase",
            [
                {"id": 1, "values": {"explanation": "P0 batch one"}},
                {"id": 3, "values": {"explanation": "P0 batch three"}},
            ],
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["committed"], 2)
        self.assertEqual(self.sql("SELECT explanation FROM phrase WHERE id = 1")[0][0], "P0 batch one")
        self.assertEqual(self.sql("SELECT explanation FROM phrase WHERE id = 3")[0][0], "P0 batch three")
        self.assertGreaterEqual(
            self.core.local_edits_count() - ledger_before,
            1,
            "a successful batch must be audited at least once",
        )


# ---------------------------------------------------------------------------
# Acceptance 6 — cascade delete (contract "cascade")
# ---------------------------------------------------------------------------
class CascadeTests(RealDatabaseTestCase):
    def test_deleting_a_headword_removes_its_senses(self):
        headword_id = self.sql("SELECT id FROM dictionary_headwords WHERE words = 'a'")[0][0]
        data = {
            "senses_before": self.scalar(
                "SELECT COUNT(*) FROM dictionary WHERE headword_id = ?", (headword_id,)
            ),
            "headwords_before": self.scalar("SELECT COUNT(*) FROM dictionary_headwords"),
            "senses_total_before": self.scalar("SELECT COUNT(*) FROM dictionary"),
        }
        self.assertEqual(data["senses_before"], 5)
        ledger_before = self.core.local_edits_count()

        result = self.core.delete("dictionary_headwords", [headword_id])
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], 1)

        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary WHERE headword_id = ?", (headword_id,)), 0
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary_headwords WHERE id = ?", (headword_id,)), 0
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary_headwords"), data["headwords_before"] - 1
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary"),
            data["senses_total_before"] - data["senses_before"],
        )
        self.assertEqual(self.core.local_edits_count(), ledger_before + 1)

    def test_deleting_a_song_removes_alignments_and_translations(self):
        song = self.sql("SELECT id, title FROM songs WHERE id = 1")[0]
        song_id, title = song[0], song[1]
        alignments = self.scalar(
            "SELECT COUNT(*) FROM sentence_alignments WHERE song_id = ?", (song_id,)
        )
        translations = self.scalar(
            "SELECT COUNT(*) FROM song_translations WHERE song_title = ?", (title,)
        )
        self.assertGreater(alignments, 0)
        self.assertGreater(translations, 0)
        totals = (
            self.scalar("SELECT COUNT(*) FROM songs"),
            self.scalar("SELECT COUNT(*) FROM sentence_alignments"),
            self.scalar("SELECT COUNT(*) FROM song_translations"),
        )

        result = self.core.delete("songs", [song_id])
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], 1)

        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM sentence_alignments WHERE song_id = ?", (song_id,)), 0
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM song_translations WHERE song_title = ?", (title,)), 0
        )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM songs"), totals[0] - 1)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM sentence_alignments"), totals[1] - alignments
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM song_translations"), totals[2] - translations
        )


# ---------------------------------------------------------------------------
# Acceptance 7 — local-edit ledger (contract "本地修改台账")
# ---------------------------------------------------------------------------
class LedgerTests(RealDatabaseTestCase):
    def _ledger_entry_for(self, table: str, op: str):
        for entry in self.core.local_edits(limit=100):
            self.assertIsInstance(entry, dict)
            name = entry.get("table", entry.get("table_name"))
            if str(name) == table and str(entry.get("op")) == op:
                return entry
        return None

    def test_successful_create_update_delete_are_audited(self):
        self.assertEqual(self.core.local_edits_count(), 0)

        created = self.core.create("phrase", {"PHRASE": "P0 ledger phrase", "explanation": "audit"})
        self.assertTrue(created["ok"])
        self.assertEqual(self.core.local_edits_count(), 1)
        insert_entry = self._ledger_entry_for("phrase", "insert")
        self.assertIsNotNone(insert_entry, "create() must append an insert ledger row")
        self.assertEqual(str(insert_entry["row_key"]), str(created["key"]))
        self.assertTrue(str(insert_entry["summary"]).strip())
        self.assertTrue(str(insert_entry["changed_at"]).strip())

        key = created["key"]
        updated = self.core.update("phrase", key, {"explanation": "audited update"})
        self.assertTrue(updated["ok"])
        self.assertEqual(self.core.local_edits_count(), 2)

        deleted = self.core.delete("phrase", [key])
        self.assertTrue(deleted["ok"])
        self.assertEqual(self.core.local_edits_count(), 3)
        self.assertEqual(len(self.core.local_edits(limit=10)), 3)
        ops = {str(entry["op"]) for entry in self.core.local_edits(limit=10)}
        self.assertEqual(ops, {"insert", "update", "delete"})

    def test_failed_writes_are_not_audited(self):
        self.core.create("phrase", {"PHRASE": "P0 audit baseline"})
        baseline = self.core.local_edits_count()
        self.assertEqual(baseline, 1)
        for failure in (
            lambda: self.core.create("database_metadata", {"key": "x"}),
            lambda: self.core.create("phrase", {"PHRASE": "P0 audit baseline"}),
            lambda: self.core.update("phrase", 999_999, {"explanation": "x"}),
            lambda: self.core.delete("phrase", [999_999]),
        ):
            with self.assertRaises(DataError):
                failure()
        self.assertEqual(self.core.local_edits_count(), baseline)

    def test_delete_ledger_rows_are_visible_and_bounded(self):
        for index in range(3):
            self.core.create("phrase", {"PHRASE": "P0 bounded %d" % index})
        self.assertEqual(self.core.local_edits_count(), 3)
        limited = self.core.local_edits(limit=2)
        self.assertEqual(len(limited), 2)
        self.assertGreaterEqual(int(self.core.local_edits(limit=1)[0]["id"]),
                                int(limited[-1]["id"]))


# ---------------------------------------------------------------------------
# Acceptance 8 — global search / replace (contract "global_search / replace_*")
# ---------------------------------------------------------------------------
class GlobalReplaceTests(RealDatabaseTestCase):
    def test_global_search_only_scans_editable_tables(self):
        # "Finz" exists in editable *and* readonly/legacy tables in the real data,
        # so the exclusion below is meaningful, not vacuous.
        readonly_hits = 0
        for table in SHIPPED_TABLES:
            if table in EDITABLE_TABLES:
                continue
            columns = [str(row[1]) for row in self.sql('PRAGMA table_info("%s")' % table)]
            if not columns:
                continue
            where = " OR ".join('CAST("%s" AS TEXT) LIKE ?' % column for column in columns)
            count = self.scalar(
                'SELECT COUNT(*) FROM "%s" WHERE %s' % (table, where),
                tuple("%Finz%" for _ in columns),
            )
            readonly_hits += int(count or 0)
        self.assertGreater(readonly_hits, 0, "real data must contain 'Finz' outside editable tables")

        results = self.core.global_search("Finz")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        editable = set(data_schema.editable_table_names())
        for result in results:
            self.assertIsInstance(result, dict)
            self.assertIn("table", result)
            self.assertIn(
                result["table"], editable, "global search must never return %r" % (result["table"],)
            )

    def test_global_search_excludes_readonly_only_keyword(self):
        self.assertEqual(
            self.core.global_search("db_version"),
            [],
            "database_metadata is read-only and must never appear in global search",
        )

    def test_replace_preview_and_apply(self):
        token = "P0GUARD_TOKEN_XYZ"
        replacement = "P0REPLACED_TOKEN_XYZ"
        created = self.core.create(
            "phrase",
            {"PHRASE": token, "explanation": "sentinel %s explanation" % token},
        )
        self.assertTrue(created["ok"])

        preview = self.core.replace_preview(token, replacement)
        self.assertGreaterEqual(len(preview), 1, "replace preview must find the sentinel")
        for match in preview:
            self.assertIn("table", match)
            self.assertIn(match["table"], set(data_schema.editable_table_names()))
            self.assertIn("new_value", match)
            self.assertNotIn(token, str(match["new_value"]))

        applied = self.core.replace_apply(token, replacement, preview)
        self.assertTrue(applied["ok"])
        self.assertGreaterEqual(applied["replaced"], 1)

        row = self.core.row("phrase", created["key"])
        self.assertIsNotNone(row)
        self.assertIn(replacement, str(row.get("PHRASE")))
        self.assertIn(replacement, str(row.get("explanation")))
        self.assertNotIn(token, json.dumps(row, ensure_ascii=False))

        self.assertEqual(
            self.core.replace_preview(token, replacement),
            [],
            "after a successful replace the same preview must return zero matches (CONTRACT 8)",
        )
        self.assertEqual(self.core.page("phrase", keyword=token)["total"], 0)


# ---------------------------------------------------------------------------
# Acceptance 9 — diagnose (contract "diagnose")
# ---------------------------------------------------------------------------
class DiagnoseTests(RealDatabaseTestCase):
    def test_diagnose_contract_shape_and_values(self):
        report = self.core.diagnose()
        self.assertTrue(report["ok"])
        self.assertEqual(report["integrity"], "ok")
        self.assertEqual(report["foreign_key_violations"], 0)
        self.assertEqual(report["local_edits"], self.core.local_edits_count())

        self.assertEqual(
            report["pragmas"],
            {"foreign_keys": 1, "busy_timeout": 5000, "synchronous": 2, "journal_mode": "delete"},
        )

        tables = {entry["name"]: entry for entry in report["tables"]}
        expected_rows = {
            "dictionary": 1515,
            "dictionary_headwords": 1339,
            "songs": 53,
            "sentence_alignments": 1286,
            "song_translations": 929,
        }
        for table, rows in expected_rows.items():
            self.assertIn(table, tables, "diagnose() tables must include %r" % table)
            self.assertEqual(tables[table]["rows"], rows, table)
            self.assertIn("group", tables[table])
        self.assertEqual(tables["dictionary"]["group"], data_schema.GROUP_CORE)
        self.assertEqual(tables["songs"]["group"], data_schema.GROUP_LYRIC)
        self.assertEqual(tables["database_metadata"]["group"], data_schema.GROUP_SYSTEM)

    def test_diagnose_orphan_checks_follow_contract(self):
        orphans = self.core.diagnose()["orphans"]
        self.assertIsInstance(orphans, list)
        self.assertEqual(len(orphans), 4, "contract lists four known orphan checks")
        counts = {}
        for entry in orphans:
            for key in ("table", "label", "count"):
                self.assertIn(key, entry, "orphan entry must expose %r (CONTRACT diagnose)" % key)
            self.assertTrue(str(entry["label"]).strip())
            counts[str(entry["table"])] = int(entry["count"])
        self.assertEqual(counts.get("song_translations"), 1,
                         "real data has exactly one orphaned song_translations.song_title")
        for table in ("dictionary", "sentence_alignments", "dictionary_semantic_aliases"):
            self.assertEqual(counts.get(table), 0, table)

    def test_validation_order_constant(self):
        try:
            from webui_backend.data_core import VALIDATION_ORDER
        except ImportError:
            self.fail(
                "data_core.VALIDATION_ORDER is missing (p0-interface.md §data_core, "
                "needed by error-classification tests)"
            )
        self.assertEqual(
            tuple(VALIDATION_ORDER),
            (
                "table",
                "readonly",
                "payload",
                "required",
                "type",
                "length",
                "unique",
                "fk",
                "transaction",
            ),
        )


# ---------------------------------------------------------------------------
# Acceptance 11 — the shipped asset is never written
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
