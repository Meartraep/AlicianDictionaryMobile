# -*- coding: utf-8 -*-
"""P2 acceptance tests for the guarded data-write layer and curated word editing.

Spec: ``.luna-review/p2-tests-spec.md`` (19 numbered checks).  Three layers:

* ``DataCoreEditingTests``      — ``form_meta`` / ``delete_preview`` / ``reference_options``
  and the declarative-reference + write-guard regressions (checks 1-8);
* ``CuratedWordEditingTests``   — ``DictionaryService`` create/add/delete word & sense
  (checks 9-13);
* ``BridgeEditingTests``        — the same capabilities through ``mobile_bridge.invoke``
  plus recovery-point lifecycle and the restore round trip (checks 14-19).

Every test copies the *shipped* database ``app/src/main/assets/translated.db`` into its
own ``tempfile.mkdtemp()``; the shipped asset is never opened for writing (its SHA-256 is
asserted before each test and again at the end of the run).  Real data facts used here:
``dictionary_headwords`` id 1 is ``a`` with 5 senses and no semantic aliases, song id 1 is
``Alice Music`` with 27 sentence alignments / 18 official translations, headword ``Jay``
(id 590) has 2 senses and real semantic aliases.

Run::

    cd app/src/test/python
    $env:PYTHONPATH = '<repo>/app/src/main/python'
    python -m unittest test_data_editing -v
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
from webui_backend.data_core import DataCore, DataError  # noqa: E402
from webui_backend.dictionary_core import DictionaryConfig, HistoryManager  # noqa: E402
from webui_backend.dictionary_service import DictionaryService  # noqa: E402

import mobile_bridge  # noqa: E402


ASSET_SHA256 = hashlib.sha256(ASSET_DB.read_bytes()).hexdigest()


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_sql(path, statement: str, args=()):
    connection = sqlite3.connect(str(path))
    try:
        return [tuple(row) for row in connection.execute(statement, args).fetchall()]
    finally:
        connection.close()


class ResultMixin:
    """Small helpers shared by the three layers."""

    def scalar(self, statement: str, args=()):
        rows = read_sql(self.db_path, statement, args)
        return rows[0][0] if rows else None

    def fields_by_name(self, form):
        return {field["name"]: field for field in form.get("fields") or []}


# ---------------------------------------------------------------------------
# A. DataCore layer (spec checks 1-8)
# ---------------------------------------------------------------------------
class DataCoreEditingTests(ResultMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="p2-data-editing-"))
        self.db_path = str(self.tmpdir / "translated.db")
        self.backups_dir = str(self.tmpdir / "backups")
        shutil.copyfile(ASSET_DB, self.db_path)
        self.assertEqual(sha256_file(self.db_path), ASSET_SHA256)
        self.core = DataCore(self.db_path, backups_dir=self.backups_dir)
        self.assertTrue(self.core.connect(), "DataCore.connect() failed on a real DB copy")
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        try:
            self.core.close()
        except Exception:  # pragma: no cover
            pass
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def assert_asset_unmodified(self) -> None:
        self.assertEqual(
            hashlib.sha256(ASSET_DB.read_bytes()).hexdigest(),
            ASSET_SHA256,
            "the shipped database asset must never be modified by the tests",
        )

    # -- check 1 ---------------------------------------------------------
    def test_form_meta_for_headwords(self):
        form = self.core.form_meta("dictionary_headwords")
        self.assertTrue(form["ok"])
        self.assertEqual(form["table"], "dictionary_headwords")
        self.assertEqual(form["label"], "词头")
        self.assertEqual(form["group"], data_schema.GROUP_CORE)
        self.assertIs(form["editable"], True)
        self.assertEqual(form["key_column"], "id")
        self.assertEqual(form["display"], ["words", "display_explanation"])
        self.assertIn({"table": "dictionary", "label": "义项", "column": "headword_id"}, form["cascade"])
        self.assertTrue(any(item["table"] == "dictionary" for item in form["cascade"]))

        fields = self.fields_by_name(form)
        words = fields["words"]
        self.assertIs(words["required"], True)
        self.assertEqual(words["max_length"], 64)
        self.assertEqual(words["label"], "词形")
        identifier = fields["id"]
        self.assertIs(identifier["primary_key"], True)
        self.assertIs(identifier["required"], False)
        self.assertEqual(fields["display_explanation"]["max_length"], 500)
        self.assertIs(fields["display_explanation"]["multiline"], True)

    # -- check 2 ---------------------------------------------------------
    def test_form_meta_for_sentence_alignments_references(self):
        form = self.core.form_meta("sentence_alignments")
        self.assertTrue(form["ok"])
        self.assertEqual(form["editable"], True)
        fields = self.fields_by_name(form)
        for column in ("song_id", "song_title"):
            reference = fields[column]["reference"]
            self.assertIsNotNone(reference, "%s must expose a reference" % column)
            self.assertEqual(reference["table"], "songs", column)
        self.assertEqual(fields["song_id"]["reference"]["column"], "id")
        self.assertEqual(fields["song_title"]["reference"]["column"], "title")
        self.assertIs(fields["alician_sentence"]["multiline"], True)
        self.assertIs(fields["chinese_translation"]["multiline"], True)
        self.assertIs(fields["song_id"]["required"], True)

    # -- check 3 ---------------------------------------------------------
    def test_form_meta_readonly_and_unknown(self):
        readonly = self.core.form_meta("database_metadata")
        self.assertTrue(readonly["ok"])
        self.assertIs(readonly["editable"], False)
        self.assertEqual(readonly["group"], data_schema.GROUP_SYSTEM)

        with self.assertRaises(DataError) as caught:
            self.core.form_meta("no_such_table")
        self.assertIn("未知数据表", str(caught.exception))

    # -- check 4 ---------------------------------------------------------
    def test_delete_preview_for_headword_is_exact_and_does_not_write(self):
        headword_id = 1  # real headword "a": 5 senses, no semantic aliases
        sense_count = self.scalar(
            "SELECT COUNT(*) FROM dictionary WHERE headword_id = ?", (headword_id,)
        )
        self.assertEqual(sense_count, 5)
        sha_before = sha256_file(self.db_path)
        counts_before = {
            table: self.scalar('SELECT COUNT(*) FROM "%s"' % table)
            for table in ("dictionary_headwords", "dictionary", "dictionary_semantic_aliases")
        }

        preview = self.core.delete_preview("dictionary_headwords", headword_id)

        self.assertTrue(preview["ok"])
        self.assertEqual(preview["table"], "dictionary_headwords")
        self.assertEqual(preview["key"], headword_id)
        self.assertEqual(preview["deleted_self"], 1)
        children = {item["table"]: item["count"] for item in preview["children"]}
        self.assertEqual(children.get("dictionary"), sense_count)
        self.assertEqual(preview["total_removed"], 1 + sense_count)
        for child in preview["children"]:
            self.assertIn("label", child)
            self.assertIn("group", child)
        self.assertTrue(str(preview["summary"]).strip())

        # The preview must be completely side-effect free.
        self.assertEqual(sha256_file(self.db_path), sha_before, "delete preview wrote to the DB")
        counts_after = {
            table: self.scalar('SELECT COUNT(*) FROM "%s"' % table)
            for table in ("dictionary_headwords", "dictionary", "dictionary_semantic_aliases")
        }
        self.assertEqual(counts_after, counts_before)

    # -- check 5 ---------------------------------------------------------
    def test_delete_preview_for_song_lists_alignment_and_translation_children(self):
        song_id = 1  # "Alice Music"
        expected = {
            "sentence_alignments": self.scalar(
                "SELECT COUNT(*) FROM sentence_alignments WHERE song_id = ?", (song_id,)
            ),
            "song_translations": self.scalar(
                "SELECT COUNT(*) FROM song_translations WHERE song_title = "
                "(SELECT title FROM songs WHERE id = ?)",
                (song_id,),
            ),
        }
        self.assertEqual(expected["sentence_alignments"], 27)
        self.assertEqual(expected["song_translations"], 18)

        preview = self.core.delete_preview("songs", song_id)
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["deleted_self"], 1)
        children = {item["table"]: item["count"] for item in preview["children"]}
        for table, count in expected.items():
            self.assertEqual(children.get(table), count, table)
        self.assertEqual(preview["total_removed"], 1 + sum(expected.values()))

    # -- check 6 ---------------------------------------------------------
    def test_reference_options_for_song_id(self):
        result = self.core.reference_options("sentence_alignments", "song_id", keyword="Alice")
        self.assertTrue(result["ok"])
        self.assertEqual(result["parent"], "songs")
        self.assertGreaterEqual(len(result["options"]), 1)
        real_ids = {
            int(row[0]) for row in read_sql(self.db_path, "SELECT id FROM songs WHERE id IS NOT NULL")
        }
        for option in result["options"]:
            self.assertIn("value", option)
            self.assertIn("label", option)
            self.assertIn(int(option["value"]), real_ids)
        self.assertTrue(
            any("Alice" in option["label"] for option in result["options"]),
            "the real song 'Alice Music' must be an option: %r" % (result["options"],),
        )

        with self.assertRaises(DataError) as caught:
            self.core.reference_options("sentence_alignments", "chinese_translation")
        self.assertIn("关联字段", str(caught.exception))

    # -- check 7 ---------------------------------------------------------
    def test_declarative_reference_rejects_orphan(self):
        before = self.scalar("SELECT COUNT(*) FROM song_translations")
        with self.assertRaises(DataError) as caught:
            self.core.create(
                "song_translations", {"song_title": "不存在的歌", "sentence": "x"}
            )
        self.assertIn("不存在", str(caught.exception))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM song_translations"), before)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM song_translations WHERE song_title = '不存在的歌'"),
            0,
        )

    # -- check 8 ---------------------------------------------------------
    def test_write_guard_regressions(self):
        # read-only table
        with self.assertRaises(DataError) as caught:
            self.core.create("database_metadata", {"key": "p2", "value": "1"})
        self.assertIn("只读", str(caught.exception))

        # duplicate (case-insensitive) phrase
        existing = read_sql(self.db_path, "SELECT PHRASE FROM phrase ORDER BY id LIMIT 1")[0][0]
        before = self.scalar("SELECT COUNT(*) FROM phrase")
        with self.assertRaises(DataError) as caught:
            self.core.create("phrase", {"PHRASE": str(existing).upper()})
        self.assertIn("已存在", str(caught.exception))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM phrase"), before)

        # form meta and delete preview both reflect the read-only rule
        self.assertIs(self.core.form_meta("database_metadata")["editable"], False)
        with self.assertRaises(DataError) as caught:
            self.core.delete_preview("database_metadata", 1)
        self.assertIn("只读", str(caught.exception))


# ---------------------------------------------------------------------------
# B. DictionaryService layer (spec checks 9-13)
# ---------------------------------------------------------------------------
class CuratedWordEditingTests(ResultMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="p2-curated-"))
        self.db_path = str(self.tmpdir / "translated.db")
        shutil.copyfile(ASSET_DB, self.db_path)
        self.assertEqual(sha256_file(self.db_path), ASSET_SHA256)
        self._saved_config = (DictionaryConfig.DB_NAME, DictionaryConfig.CURRENT_DB)
        self._saved_env = {
            name: os.environ.get(name) for name in ("ALICIAN_DB_PATH", "ALICIAN_LITE_BUILD")
        }
        os.environ["ALICIAN_DB_PATH"] = self.db_path
        os.environ["ALICIAN_LITE_BUILD"] = "1"
        DictionaryConfig.DB_NAME = self.db_path
        DictionaryConfig.CURRENT_DB = self.db_path
        self.service = DictionaryService(enable_semantic=False)
        self.service.history_manager = HistoryManager(str(self.tmpdir / "search_history.json"))
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        try:
            self.service.close()
        except Exception:  # pragma: no cover
            pass
        DictionaryConfig.DB_NAME, DictionaryConfig.CURRENT_DB = self._saved_config
        for name, value in self._saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_word(self, word="P2Word", senses=None, display="测试词展示释义", word_class="n."):
        if senses is None:
            senses = [
                {"explanation": "第一个义项", "class": "n.", "english": "first", "japanese": "一番"},
                {"explanation": "第二个义项", "class": "v.", "english": "second", "japanese": "二番"},
            ]
        return self.service.create_word_entry(word, display, word_class, senses)

    # -- check 9 ---------------------------------------------------------
    def test_create_word_entry_with_two_senses(self):
        result = self._create_word("P2CreatedWord")
        self.assertTrue(result["ok"], result.get("message"))
        headword_id = result["headword_id"]
        self.assertIsInstance(headword_id, int)
        self.assertGreater(headword_id, 0)
        self.assertEqual(result["word"], "P2CreatedWord")

        entry = self.service.get_headword_entry(headword_id)
        self.assertTrue(entry["ok"], entry.get("message"))
        payload = entry["entry"]
        for key in ("word", "explanation", "kind", "headword_id", "senses"):
            self.assertIn(key, payload)
        self.assertEqual(payload["word"], "P2CreatedWord")
        self.assertEqual(payload["kind"], "alice")
        self.assertEqual(payload["headword_id"], headword_id)
        self.assertEqual(payload["explanation"], "测试词展示释义")
        self.assertEqual(len(payload["senses"]), 2)
        self.assertEqual(
            [sense["explanation"] for sense in payload["senses"]],
            ["第一个义项", "第二个义项"],
            "senses must be ordered by sense_order",
        )
        orders = [
            row[0]
            for row in read_sql(
                self.db_path,
                "SELECT sense_order FROM dictionary WHERE headword_id = ? ORDER BY id",
                (headword_id,),
            )
        ]
        self.assertEqual(orders, [1, 2])

    def test_create_word_entry_rejects_duplicates_and_partial_data(self):
        self.assertTrue(self._create_word("P2DupWord")["ok"])

        duplicate = self._create_word("P2DupWord")
        self.assertFalse(duplicate["ok"], duplicate)
        self.assertIn("已存在", duplicate["message"])

        empty = self._create_word("P2EmptySenses", senses=[])
        self.assertFalse(empty["ok"], empty)
        self.assertIn("至少", empty["message"])

        heads_before = self.scalar("SELECT COUNT(*) FROM dictionary_headwords")
        senses_before = self.scalar("SELECT COUNT(*) FROM dictionary")
        partial = self._create_word(
            "P2HalfWord",
            senses=[{"explanation": "合法义项"}, {"explanation": "   "}],
        )
        self.assertFalse(partial["ok"], partial)
        self.assertIn("不能为空", partial["message"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM dictionary_headwords"), heads_before)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM dictionary"), senses_before)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary_headwords WHERE words = 'P2HalfWord'"), 0
        )

    # -- check 10 --------------------------------------------------------
    def test_add_sense_appends_at_end(self):
        created = self._create_word("P2AddSenseWord")
        headword_id = created["headword_id"]
        max_order_before = self.scalar(
            "SELECT MAX(sense_order) FROM dictionary WHERE headword_id = ?", (headword_id,)
        )
        self.assertEqual(max_order_before, 2)

        added = self.service.add_sense_entry(
            headword_id, "追加的义项", "adj.", "third-english", "三番目"
        )
        self.assertTrue(added["ok"], added.get("message"))
        sense_id = added["sense_id"]
        new_order = self.scalar("SELECT sense_order FROM dictionary WHERE id = ?", (sense_id,))
        self.assertEqual(new_order, max_order_before + 1, "sense_order must increment")
        self.assertEqual(
            self.scalar("SELECT explanation FROM dictionary WHERE id = ?", (sense_id,)),
            "追加的义项",
        )
        entry = self.service.get_headword_entry(headword_id)["entry"]
        self.assertEqual(len(entry["senses"]), 3)
        self.assertEqual(entry["senses"][-1]["id"], sense_id)

        blank = self.service.add_sense_entry(headword_id, "   ", "n.", "", "")
        self.assertFalse(blank["ok"], blank)
        self.assertIn("不能为空", blank["message"])
        self.assertEqual(
            len(self.service.get_headword_entry(headword_id)["entry"]["senses"]), 3
        )

    # -- check 11 --------------------------------------------------------
    def test_delete_sense(self):
        created = self._create_word("P2DeleteSenseWord")
        headword_id = created["headword_id"]
        entry = self.service.get_headword_entry(headword_id)["entry"]
        sense_id = entry["senses"][0]["id"]

        removed = self.service.delete_sense_entry(sense_id)
        self.assertTrue(removed["ok"], removed.get("message"))
        entry_after = self.service.get_headword_entry(headword_id)["entry"]
        self.assertEqual(len(entry_after["senses"]), 1)
        self.assertNotIn(sense_id, [sense["id"] for sense in entry_after["senses"]])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM dictionary WHERE id = ?", (sense_id,)), 0)

        missing = self.service.delete_sense_entry(999_999)
        self.assertFalse(missing["ok"], missing)
        self.assertIn("未找到", missing["message"])

    # -- last-sense guard ------------------------------------------------
    def test_cannot_delete_the_last_sense_of_a_headword(self):
        created = self._create_word("P2LastSenseWord")
        headword_id = created["headword_id"]
        entry = self.service.get_headword_entry(headword_id)["entry"]
        self.assertEqual(len(entry["senses"]), 2)

        first = self.service.delete_sense_entry(entry["senses"][0]["id"])
        self.assertTrue(first["ok"], first.get("message"))
        last = self.service.get_headword_entry(headword_id)["entry"]["senses"][0]

        rejected = self.service.delete_sense_entry(last["id"])
        self.assertFalse(rejected["ok"], rejected)
        self.assertIn("至少保留一个义项", rejected["message"])

        # Nothing was removed and the headword is still usable.
        remaining = self.service.get_headword_entry(headword_id)["entry"]["senses"]
        self.assertEqual([sense["id"] for sense in remaining], [last["id"]])
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary WHERE headword_id = ?", (headword_id,)),
            1,
        )

    # -- check 12 --------------------------------------------------------
    def test_delete_headword_removes_senses_and_aliases(self):
        created = self._create_word("P2DeleteWord")
        headword_id = created["headword_id"]
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM dictionary WHERE headword_id = ?", (headword_id,)), 2)

        removed = self.service.delete_headword_entry(headword_id)
        self.assertTrue(removed["ok"], removed.get("message"))
        self.assertGreaterEqual(int(removed["deleted"]), 3, "headword + 2 senses must be reported")
        self.assertFalse(self.service.get_headword_entry(headword_id)["ok"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM dictionary WHERE headword_id = ?", (headword_id,)), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM dictionary_headwords WHERE id = ?", (headword_id,)), 0)

        # Real headword with real semantic aliases: deleting it must clear them.
        jay = read_sql(self.db_path, "SELECT id FROM dictionary_headwords WHERE words = 'Jay'")
        self.assertTrue(jay, "real data changed: headword 'Jay' is missing")
        jay_id = int(jay[0][0])
        sense_ids = [
            int(row[0])
            for row in read_sql(self.db_path, "SELECT id FROM dictionary WHERE headword_id = ?", (jay_id,))
        ]
        placeholders = ",".join("?" for _ in sense_ids)
        aliases_before = self.scalar(
            "SELECT COUNT(*) FROM dictionary_semantic_aliases WHERE sense_id IN (%s)" % placeholders,
            tuple(sense_ids),
        )
        self.assertGreater(aliases_before, 0, "real data changed: 'Jay' has no semantic aliases")

        result = self.service.delete_headword_entry(jay_id)
        self.assertTrue(result["ok"], result.get("message"))
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM dictionary_semantic_aliases WHERE sense_id IN (%s)" % placeholders,
                tuple(sense_ids),
            ),
            0,
            "semantic aliases of the deleted senses must be cleared",
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary_headwords WHERE id = ?", (jay_id,)), 0
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM dictionary WHERE headword_id = ?", (jay_id,)), 0
        )

    # -- check 13 --------------------------------------------------------
    def test_failed_curated_write_leaves_connection_usable(self):
        created = self._create_word("P2TxWord")
        headword_id = created["headword_id"]

        failed = self.service.add_sense_entry(headword_id, "   ", "n.", "", "")
        self.assertFalse(failed["ok"], failed)
        self.assertIn("不能为空", failed["message"])
        self.assertFalse(
            self.service.db_handler.conn.in_transaction,
            "a failed curated write must not leave the connection in a transaction",
        )

        recovered = self.service.add_sense_entry(headword_id, "恢复后的义项", "n.", "", "")
        self.assertTrue(recovered["ok"], recovered.get("message"))
        entry = self.service.get_headword_entry(headword_id)["entry"]
        self.assertEqual(len(entry["senses"]), 3)
        self.assertEqual(entry["senses"][-1]["explanation"], "恢复后的义项")


# ---------------------------------------------------------------------------
# C. Bridge layer (spec checks 14-19)
# ---------------------------------------------------------------------------
class BridgeEditingTests(ResultMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="p2-bridge-"))
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
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def call(self, method: str, **payload):
        return json.loads(
            mobile_bridge.invoke(method, json.dumps(payload, ensure_ascii=False))
        )

    def backup_count(self) -> int:
        directory = self.data_dir / "backups"
        return len(list(directory.glob("*.db"))) if directory.is_dir() else 0

    def alice_entries(self, word: str):
        search = self.call("dictionary_search", query=word, exact=True, position="any")
        self.assertTrue(search.get("ok"), search.get("message"))
        return [
            entry
            for section in search.get("sections") or []
            for entry in section.get("entries") or []
            if entry.get("kind") == "alice" and entry.get("word") == word
        ]

    # -- check 14 --------------------------------------------------------
    def test_bridge_metadata_endpoints_match_datacore(self):
        form = self.call("data_form", table="dictionary_headwords")
        self.assertTrue(form["ok"], form.get("message"))
        self.assertIs(form["editable"], True)
        self.assertEqual(form["label"], "词头")
        self.assertEqual(form["group"], "core")
        self.assertEqual(form["key_column"], "id")
        self.assertEqual(form["display"], ["words", "display_explanation"])
        fields = self.fields_by_name(form)
        self.assertIs(fields["words"]["required"], True)
        self.assertEqual(fields["words"]["max_length"], 64)
        self.assertIs(fields["id"]["primary_key"], True)
        self.assertIs(fields["id"]["required"], False)
        self.assertTrue(any(item["table"] == "dictionary" for item in form["cascade"]))
        # Same structure as the DataCore call behind the bridge.
        core_form = self.core.form_meta("dictionary_headwords")
        for key in ("label", "group", "editable", "key_column", "display", "fields", "cascade"):
            self.assertEqual(form[key], core_form[key], key)

        preview = self.call("data_delete_preview", table="dictionary_headwords", key=1)
        self.assertTrue(preview["ok"], preview.get("message"))
        core_preview = self.core.delete_preview("dictionary_headwords", 1)
        for key in ("table", "label", "key", "deleted_self", "children", "total_removed", "summary"):
            self.assertEqual(preview[key], core_preview[key], key)
        self.assertEqual(preview["deleted_self"], 1)
        children = {item["table"]: item["count"] for item in preview["children"]}
        self.assertEqual(children.get("dictionary"), 5)
        self.assertEqual(preview["total_removed"], 6)

        options = self.call(
            "data_reference_options", table="sentence_alignments", column="song_id", keyword="Alice"
        )
        self.assertTrue(options["ok"], options.get("message"))
        self.assertGreaterEqual(len(options["options"]), 1)
        self.assertTrue(any("Alice" in option["label"] for option in options["options"]))
        bad = self.call(
            "data_reference_options", table="sentence_alignments", column="chinese_translation"
        )
        self.assertFalse(bad["ok"], bad)
        self.assertIn("关联字段", bad["message"])

        unknown = self.call("data_form", table="no_such_table")
        self.assertFalse(unknown["ok"], unknown)
        self.assertIn("未知数据表", unknown["message"])
        readonly = self.call("data_form", table="database_metadata")
        self.assertTrue(readonly["ok"], readonly.get("message"))
        self.assertIs(readonly["editable"], False)

    # -- check 15 --------------------------------------------------------
    def test_bridge_generic_row_write_cycle_with_backup(self):
        phrase = "P2BridgePhrase"
        backups_before = self.backup_count()

        created = self.call(
            "data_create", table="phrase", values={"PHRASE": phrase, "explanation": "before"}
        )
        self.assertTrue(created["ok"], created.get("message"))
        self.assertTrue(str(created.get("message")).strip())
        key = created["key"]

        duplicate = self.call(
            "data_create", table="phrase", values={"PHRASE": phrase.upper(), "explanation": "dup"}
        )
        self.assertFalse(duplicate["ok"], duplicate)
        self.assertIn("已存在", duplicate["message"])

        readonly = self.call(
            "data_create", table="database_metadata", values={"key": "p2", "value": "1"}
        )
        self.assertFalse(readonly["ok"], readonly)
        self.assertIn("只读", readonly["message"])

        updated = self.call(
            "data_update", table="phrase", key=key, values={"explanation": "after"}
        )
        self.assertTrue(updated["ok"], updated.get("message"))
        page = self.call("data_page", table="phrase", keyword=phrase)
        self.assertTrue(page["ok"], page.get("message"))
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["rows"][0]["explanation"], "after")

        removed = self.call("data_delete", table="phrase", key=key)
        self.assertTrue(removed["ok"], removed.get("message"))
        backup = str(removed.get("backup") or "")
        self.assertTrue(backup, "data_delete must return a recovery point path (spec 15)")
        self.assertTrue(Path(backup).is_file(), backup)
        self.assertEqual(self.backup_count(), backups_before + 1)
        self.assertEqual(self.call("data_page", table="phrase", keyword=phrase)["total"], 0)

    # -- check 16 --------------------------------------------------------
    def test_bridge_create_word_reloads_translator_and_is_searchable(self):
        word = "P2BridgeWord"
        translator_before = id(mobile_bridge._translator)
        ledger_before = self.core.local_edits_count()

        created = self.call(
            "dictionary_create_word",
            word=word,
            display_explanation="桥接测试词",
            display_class="n.",
            senses=[
                {"explanation": "桥接义项一", "class": "n.", "english": "first", "japanese": "一番"},
                {"explanation": "桥接义项二", "class": "v.", "english": "second", "japanese": "二番"},
            ],
        )
        self.assertTrue(created["ok"], created.get("message"))
        headword_id = created["headword_id"]
        self.assertIsInstance(headword_id, int)
        self.assertGreater(headword_id, 0)

        self.assertNotEqual(
            id(mobile_bridge._translator),
            translator_before,
            "creating a word must invalidate the translator cache (spec 16)",
        )
        self.assertEqual(
            self.core.local_edits_count(),
            ledger_before + 1,
            "the curated create must append one local-edit ledger row",
        )

        entries = self.alice_entries(word)
        self.assertEqual(len(entries), 1, "created word must be searchable via dictionary_search")
        self.assertEqual(entries[0]["headword_id"], headword_id)
        self.assertEqual(len(entries[0]["senses"]), 2)
        self.assertEqual(
            [sense["explanation"] for sense in entries[0]["senses"]],
            ["桥接义项一", "桥接义项二"],
        )

        entry = self.call("dictionary_entry", headword_id=headword_id)
        self.assertTrue(entry["ok"], entry.get("message"))
        self.assertEqual(entry["entry"]["word"], word)
        self.assertEqual(entry["entry"]["headword_id"], headword_id)
        self.assertEqual(len(entry["entry"]["senses"]), 2)

        # Invalid creates leave no partial headword behind.
        heads_before = self.call("data_page", table="dictionary_headwords", limit=1)["total"]
        partial = self.call(
            "dictionary_create_word",
            word="P2HalfWord",
            display_explanation="展示",
            display_class="",
            senses=[{"explanation": "合法"}, {"explanation": "   "}],
        )
        self.assertFalse(partial["ok"], partial)
        self.assertIn("不能为空", partial["message"])
        self.assertEqual(
            self.call("data_page", table="dictionary_headwords", limit=1)["total"], heads_before
        )

        duplicate = self.call(
            "dictionary_create_word",
            word=word,
            display_explanation="重复",
            display_class="",
            senses=[{"explanation": "x"}],
        )
        self.assertFalse(duplicate["ok"], duplicate)
        self.assertIn("已存在", duplicate["message"])

        empty = self.call(
            "dictionary_create_word",
            word="P2NoSensesWord",
            display_explanation="展示",
            display_class="",
            senses=[],
        )
        self.assertFalse(empty["ok"], empty)
        self.assertIn("至少", empty["message"])

    # -- check 17 --------------------------------------------------------
    def test_bridge_curated_delete_paths(self):
        word = "P2BridgeCurated"
        created = self.call(
            "dictionary_create_word",
            word=word,
            display_explanation="策展删除测试",
            display_class="n.",
            senses=[{"explanation": "初始义项", "class": "n.", "english": "one", "japanese": "一"}],
        )
        self.assertTrue(created["ok"], created.get("message"))
        headword_id = created["headword_id"]

        added = self.call(
            "dictionary_add_sense",
            **{
                "headword_id": headword_id,
                "explanation": "追加义项",
                "class": "adj.",
                "english": "extra",
                "japanese": "追加",
            },
        )
        self.assertTrue(added["ok"], added.get("message"))
        sense_id = added["sense_id"]
        entry = self.call("dictionary_entry", headword_id=headword_id)["entry"]
        self.assertEqual(len(entry["senses"]), 2)
        self.assertEqual(entry["senses"][-1]["explanation"], "追加义项")

        blank = self.call(
            "dictionary_add_sense",
            **{"headword_id": headword_id, "explanation": "   ", "class": "n."},
        )
        self.assertFalse(blank["ok"], blank)
        self.assertIn("不能为空", blank["message"])

        deleted_sense = self.call("dictionary_delete_sense", sense_id=sense_id)
        self.assertTrue(deleted_sense["ok"], deleted_sense.get("message"))
        backup = str(deleted_sense.get("backup") or "")
        self.assertTrue(backup, "delete_sense must return a recovery point path")
        self.assertTrue(Path(backup).is_file(), backup)
        entry = self.call("dictionary_entry", headword_id=headword_id)["entry"]
        self.assertEqual(len(entry["senses"]), 1)

        missing_sense = self.call("dictionary_delete_sense", sense_id=999_999)
        self.assertFalse(missing_sense["ok"], missing_sense)
        self.assertIn("未找到", missing_sense["message"])

        missing_headword = self.call("dictionary_delete_headword", headword_id=999_999, word="x")
        self.assertFalse(missing_headword["ok"], missing_headword)
        self.assertIn("未找到", missing_headword["message"])

        deleted_word = self.call("dictionary_delete_headword", headword_id=headword_id, word=word)
        self.assertTrue(deleted_word["ok"], deleted_word.get("message"))
        word_backup = str(deleted_word.get("backup") or "")
        self.assertTrue(word_backup, "delete_headword must return a recovery point path")
        self.assertTrue(Path(word_backup).is_file(), word_backup)
        self.assertFalse(self.call("dictionary_entry", headword_id=headword_id)["ok"])
        self.assertEqual(self.alice_entries(word), [])
        self.assertEqual(self.backup_count() >= 2, True, "each delete keeps a recovery point")

    # -- check 18 --------------------------------------------------------
    def test_bridge_delete_with_missing_key_fails_cleanly(self):
        before_page = self.call("data_page", table="phrase", limit=200)
        self.assertTrue(before_page["ok"])
        before_rows = before_page["rows"]
        before_total = before_page["total"]

        result = self.call("data_delete", table="phrase", key=999_999)
        self.assertFalse(result["ok"], result)
        self.assertIn("未找到", result["message"])

        after_page = self.call("data_page", table="phrase", limit=200)
        self.assertEqual(after_page["total"], before_total, "a failed delete must not change data")
        self.assertEqual(after_page["rows"], before_rows)

    # -- check 19 --------------------------------------------------------
    def test_bridge_restore_roundtrip(self):
        backup = self.call("gov_backup_create", reason="p2_restore")
        self.assertTrue(backup["ok"], backup.get("message"))
        backup_path = str(backup["path"])
        self.assertTrue(Path(backup_path).is_file(), backup_path)

        word = "P2RestoreWord"
        created = self.call(
            "dictionary_create_word",
            word=word,
            display_explanation="恢复点测试",
            display_class="n.",
            senses=[{"explanation": "恢复点义项"}],
        )
        self.assertTrue(created["ok"], created.get("message"))
        self.assertEqual(len(self.alice_entries(word)), 1)

        restored = self.call("gov_backup_restore", path=backup_path)
        self.assertTrue(restored["ok"], restored.get("message"))
        self.assertIn("恢复", str(restored.get("message") or ""))

        # The restored database must be the pre-create snapshot: word gone, marker intact.
        self.assertEqual(self.alice_entries(word), [], "restore must remove the created word")
        metadata = self.call("database_metadata")
        self.assertTrue(metadata["ok"], metadata.get("message"))
        self.assertEqual(metadata["database_version"], 2, "version marker must stay 2 after restore")

        # Services keep working after the atomic replace + reconnect.
        self.assertIsNotNone(mobile_bridge._data_core)
        self.assertTrue(self.call("data_form", table="phrase")["ok"])
        self.assertEqual(
            self.call("data_page", table="dictionary_headwords", limit=5)["total"], 1339
        )
        self.assertEqual(self.call("data_page", table="songs", limit=5)["total"], 53)


# ---------------------------------------------------------------------------
# Shipped asset guard (spec "硬性要求")
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
