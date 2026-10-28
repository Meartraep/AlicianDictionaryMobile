# -*- coding: utf-8 -*-
"""Real-data regression tests for the dictionary search + per-sense edit contract.

Contract under test: ``docs/DICTIONARY_SEARCH_EDIT_CONTRACT.md`` (this module's
docstrings cite its section numbers, e.g. ``CONTRACT §3``).

Contract under test (the dictionary feature's public behaviour):

* ``dictionary_search`` keeps its top-level fields and adds the ``song`` /
  ``translation`` result sections plus ``headword_id`` + ``senses`` on curated
  entries; the section gates and result caps are part of the contract;
* ``dictionary_song_lyrics`` returns one whole song in the ``ExampleResult``
  shape; a missing song returns ``ok == False``;
* ``dictionary_update_word`` writes one headword and the *submitted* senses only,
  in a single transaction, with uniqueness / ownership / length validation.

Every test copies the *shipped* database ``app/src/main/assets/translated.db`` into a
fresh ``tempfile.mkdtemp()`` directory and talks to that copy through the production
classes (``webui_backend.dictionary_core.DatabaseHandler`` via
``webui_backend.dictionary_service.DictionaryService``).  No fake schema is built and
the shipped asset is never opened for writing; ``setUp`` asserts that the copy is a
byte-for-byte copy (SHA-256) of the asset before any test touches it.

The assertions are deliberately about *data preservation*:

* a multi-sense headword edit must only touch the submitted sense and must leave every
  other sense's explanation / glosses / class / order byte-identical;
* renaming onto an already existing word is rejected and creates no duplicate headword;
* invalid payloads are rejected without touching the database;
* a failed ``update_song_lyric`` must roll back so the next write can start its own
  transaction.

Run::

    cd app/src/test/python
    $env:PYTHONPATH = '<repo>/app/src/main/python'
    python -m unittest test_dictionary_search -v

The module also makes itself runnable from the repository root and as a plain script::

    python app/src/test/python/test_dictionary_search.py -v
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[4]
MAIN_PYTHON = REPO / "app" / "src" / "main" / "python"
ASSET_DB = REPO / "app" / "src" / "main" / "assets" / "translated.db"

if str(MAIN_PYTHON) not in sys.path:
    sys.path.insert(0, str(MAIN_PYTHON))

try:  # The Windows console is GBK; Chinese assertion messages must not crash.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - exotic stdout replacements
    pass

from webui_backend import dictionary_core  # noqa: E402
from webui_backend.dictionary_core import DictionaryConfig, HistoryManager  # noqa: E402
from webui_backend.dictionary_service import DictionaryService  # noqa: E402


ASSET_SHA256 = hashlib.sha256(ASSET_DB.read_bytes()).hexdigest()

#: Columns returned by the sense snapshot helper, in order.
SENSE_COLUMNS = (
    "id",
    "headword_id",
    "words",
    "explanation",
    "class",
    "sense_order",
    "count",
    "variety",
    "english_gloss",
    "japanese_gloss",
)

#: Fields CONTRACT §1 promises on every alice/chinese entry.
ALICE_ENTRY_FIELDS = (
    "word",
    "explanation",
    "word_class",
    "kind",
    "count",
    "variety",
    "english_gloss",
    "japanese_gloss",
    "headword_id",
    "senses",
)

#: Fields CONTRACT §1 promises on every kind="translation" entry.
TRANSLATION_ENTRY_FIELDS = (
    "word",
    "explanation",
    "word_class",
    "kind",
    "count",
    "variety",
    "english_gloss",
    "japanese_gloss",
    "song_title",
    "album",
)


def _quiet_close(service: "DictionaryService") -> None:
    try:
        service.close()
    except Exception:  # pragma: no cover - closing must never mask a test result
        pass


class RealDatabaseTestCase(unittest.TestCase):
    """Base class: one private copy of the real database per test."""

    # ------------------------------------------------------------------ setup

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="dict-search-realdata-"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        self.db_path = str(self.tmpdir / "translated.db")
        shutil.copyfile(ASSET_DB, self.db_path)
        self.assertEqual(
            hashlib.sha256(Path(self.db_path).read_bytes()).hexdigest(),
            ASSET_SHA256,
            "the database under test must be a byte-for-byte copy of the shipped asset",
        )

        # Construct the service exactly the way mobile_bridge._open_services() does:
        # point DictionaryConfig at the database, then let DictionaryService connect.
        saved_config = (DictionaryConfig.DB_NAME, DictionaryConfig.CURRENT_DB)
        saved_env = {
            name: os.environ.get(name) for name in ("ALICIAN_DB_PATH", "ALICIAN_LITE_BUILD")
        }
        os.environ["ALICIAN_DB_PATH"] = self.db_path
        os.environ["ALICIAN_LITE_BUILD"] = "1"
        DictionaryConfig.DB_NAME = self.db_path
        DictionaryConfig.CURRENT_DB = self.db_path
        self.addCleanup(self._restore_globals, saved_config, saved_env)

        self.history_path = str(self.tmpdir / "search_history.json")
        self.service = DictionaryService(enable_semantic=False)
        self.addCleanup(_quiet_close, self.service)
        # Keep query history out of the repository working tree.
        self.service.history_manager = HistoryManager(self.history_path)

    @staticmethod
    def _restore_globals(saved_config, saved_env) -> None:
        DictionaryConfig.DB_NAME, DictionaryConfig.CURRENT_DB = saved_config
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    # ------------------------------------------------------- raw sqlite helpers

    def _query(self, sql: str, args=()):
        """Run a read query against the private database copy."""
        connection = sqlite3.connect(self.db_path)
        try:
            return [tuple(row) for row in connection.execute(sql, args).fetchall()]
        finally:
            connection.close()

    def _query_one(self, sql: str, args=()):
        rows = self._query(sql, args)
        return rows[0] if rows else None

    # ------------------------------------------------------ production helpers

    def _search(self, query: str, exact: bool = False, position: str = "any", record_history=None):
        """Call DictionaryService.search, binding record_history only when needed."""
        args = [query, exact, position]
        if record_history is None:
            return self.service.search(*args)
        signature = inspect.signature(self.service.search)
        if "record_history" not in signature.parameters:
            self.fail(
                "DictionaryService.search() has no record_history parameter "
                "(CONTRACT §1); signature: %s" % (signature,)
            )
        return self.service.search(*args, record_history=record_history)

    def _update_word(self, **fields):
        """Call the contract-shaped sense-level update entry point.

        The JSON payload calls the renamed value ``word`` (CONTRACT §3); the Python
        implementation may call that parameter ``new_word``.  Everything else must be
        addressable by its contract name.
        """
        method = getattr(self.service, "update_word_entry", None)
        if method is None:
            self.fail("DictionaryService.update_word_entry() is missing (CONTRACT §3)")
        required = ("headword_id", "original_word", "display_explanation", "senses")
        signature = inspect.signature(method)
        missing = [name for name in required if name not in signature.parameters]
        if missing:
            self.fail(
                "DictionaryService.update_word_entry() does not expose the contract "
                "fields %s; signature: %s" % (missing, signature)
            )
        arguments = {name: value for name, value in fields.items() if name != "word"}
        if "word" in signature.parameters:
            arguments["word"] = fields["word"]
        elif "new_word" in signature.parameters:
            arguments["new_word"] = fields["word"]
        else:
            self.fail(
                "DictionaryService.update_word_entry() has no 'word'/'new_word' parameter "
                "for the renamed value (CONTRACT §3); signature: %s" % (signature,)
            )
        return method(**arguments)

    def _song_lyrics(self, title: str, album: str):
        method = getattr(self.service, "get_song_lyrics", None)
        if method is None:
            self.fail("DictionaryService.get_song_lyrics() is missing (CONTRACT §2)")
        return method(title, album)

    def _sections_by_kind(self, result: dict) -> dict:
        sections = result.get("sections")
        self.assertIsInstance(
            sections, list, "search() response must carry a 'sections' list (CONTRACT §1)"
        )
        by_kind = {}
        for section in sections:
            self.assertIn("title", section, "every section needs a title (CONTRACT §1)")
            self.assertIn("kind", section, "every section needs a kind (CONTRACT §1)")
            self.assertIn("entries", section, "every section needs entries (CONTRACT §1)")
            by_kind[section["kind"]] = section
        return by_kind

    # --------------------------------------------------------- data helpers

    def _headword_row(self, word: str):
        return self._query_one(
            "SELECT id, words, display_explanation, display_class, count, variety "
            "FROM dictionary_headwords WHERE LOWER(words) = LOWER(?)",
            (word,),
        )

    def _senses(self, headword_id: int):
        return self._query(
            "SELECT id, headword_id, words, explanation, class, sense_order, count, variety, "
            "english_gloss, japanese_gloss FROM dictionary "
            "WHERE headword_id = ? ORDER BY sense_order, id",
            (headword_id,),
        )

    def _snapshot(self, headword_id: int) -> dict:
        return {
            "headword": self._query_one(
                "SELECT id, words, display_explanation, display_class, count, variety "
                "FROM dictionary_headwords WHERE id = ?",
                (headword_id,),
            ),
            "senses": self._senses(headword_id),
            "headword_rows": self._query_one(
                "SELECT COUNT(*) FROM dictionary_headwords"
            )[0],
            "sense_rows": self._query_one("SELECT COUNT(*) FROM dictionary")[0],
        }

    def _multi_sense_headword(self):
        """Return ``(headword_row, senses)`` for the real headword ``a``."""
        headword = self._headword_row("a")
        self.assertIsNotNone(
            headword, "the shipped database is expected to contain the headword 'a'"
        )
        senses = self._senses(headword[0])
        self.assertGreaterEqual(
            len(senses),
            2,
            "CONTRACT §7.1.7 expects 'a' to be a real multi-sense headword",
        )
        return headword, senses

    def _unique_new_word(self, base: str = "aEditRegression") -> str:
        candidate = base
        suffix = 1
        while self._query_one(
            "SELECT id FROM dictionary_headwords WHERE LOWER(words) = LOWER(?)", (candidate,)
        ) is not None:
            suffix += 1
            candidate = "%s%d" % (base, suffix)
        return candidate


class SearchSectionTests(RealDatabaseTestCase):
    """CONTRACT §1: the new song / translation sections and their length gates."""

    def test_search_response_keeps_top_level_contract_fields(self):
        result = self._search("Alice")
        self.assertTrue(result.get("ok"), result)
        for field in (
            "ok",
            "query",
            "exact_match",
            "is_phrase",
            "sections",
            "history",
            "message",
            "suggestions",
            "context_examples",
            "features",
        ):
            self.assertIn(field, result, "search() must keep the existing top-level field %r" % field)

    def test_search_alice_hits_real_song_section_with_album(self):
        result = self._search("Alice")
        self.assertTrue(result.get("ok"), result)
        sections = self._sections_by_kind(result)
        self.assertIn(
            "song", sections, "search('Alice') must return the 歌曲标题 section (CONTRACT §7.1.1)"
        )
        section = sections["song"]
        self.assertEqual(section["title"], "歌曲标题", "song section title (CONTRACT §1)")

        entries = section["entries"]
        self.assertLessEqual(len(entries), 20, "song section must be capped at 20 (CONTRACT §1)")
        self.assertGreaterEqual(len(entries), 1)

        real_song = self._query_one(
            "SELECT title, Album FROM songs WHERE title = 'Alice Music'"
        )
        self.assertIsNotNone(real_song, "real data changed: song 'Alice Music' is missing")
        real_title, real_album = real_song

        for entry in entries:
            self.assertEqual(entry["kind"], "song", entry)
            self.assertEqual(entry["word_class"], "歌曲", entry)
            self.assertEqual(entry["count"], 0, entry)
            self.assertEqual(entry["variety"], 0, entry)
            self.assertTrue(entry["word"].strip(), entry)
            self.assertIn("alice", entry["word"].lower(), entry)
            self.assertIn("album", entry, "song entry must carry album (CONTRACT §1/§7.1.1)")
            self.assertTrue(entry["album"].strip(), entry)
            self.assertEqual(
                entry["explanation"], entry["album"], "song explanation is the album (CONTRACT §1)"
            )

        words = {entry["word"]: entry for entry in entries}
        self.assertIn(
            real_title,
            words,
            "the real song title 'Alice Music' must be part of search('Alice')",
        )
        self.assertEqual(
            words[real_title]["album"],
            real_album,
            "the real album of 'Alice Music' must be attached to its entry",
        )

    def test_search_world_hits_real_translation_section(self):
        result = self._search("world")
        self.assertTrue(result.get("ok"), result)
        sections = self._sections_by_kind(result)
        self.assertIn(
            "translation",
            sections,
            "search('world') must return the 歌词英/日译命中 section (CONTRACT §7.1.2)",
        )
        section = sections["translation"]
        self.assertEqual(section["title"], "歌词英/日译命中", "translation section title (CONTRACT §1)")

        entries = section["entries"]
        self.assertLessEqual(
            len(entries), 20, "translation section must be capped at 20 (CONTRACT §1)"
        )
        self.assertGreaterEqual(len(entries), 1, "search('world') must find real lyric lines")

        song_albums = {
            title: album
            for title, album in self._query("SELECT title, Album FROM songs")
        }
        for entry in entries:
            for field in TRANSLATION_ENTRY_FIELDS:
                self.assertIn(field, entry, "translation entry missing %r (CONTRACT §1)" % field)
            self.assertEqual(entry["kind"], "translation", entry)
            self.assertEqual(entry["word_class"], "歌词句子", entry)
            self.assertEqual(entry["count"], 0, entry)
            self.assertEqual(entry["variety"], 0, entry)
            self.assertTrue(entry["word"].strip(), entry)
            self.assertTrue(entry["explanation"].strip(), entry)
            self.assertTrue(
                entry["english_gloss"].strip() or entry["japanese_gloss"].strip(),
                "translation entry must carry the matching gloss",
            )
            self.assertTrue(entry["song_title"].strip(), entry)
            self.assertTrue(entry["album"].strip(), entry)
            self.assertIn(
                entry["song_title"],
                song_albums,
                "translation entry song_title must be a real song title",
            )
            self.assertEqual(
                entry["album"],
                song_albums[entry["song_title"]],
                "translation entry album must match the song's real album",
            )

        self.assertTrue(
            any("world" in entry["english_gloss"].lower() for entry in entries),
            "the real English translation containing 'world' must be represented",
        )

    def test_min_length_gate_hides_translation_and_song_sections_for_one_letter(self):
        # CONTRACT §1: translation needs len(query) >= 3, song needs len(query) >= 2.
        # The real database has far more than 20 lyric lines containing "a", so the
        # absence below can only come from the length gate.
        translation_rows = self._query_one(
            "SELECT COUNT(*) FROM song_translations "
            "WHERE LOWER(english) LIKE '%a%' OR LOWER(japanese) LIKE '%a%'"
        )[0]
        self.assertGreater(
            translation_rows,
            20,
            "real data changed: expected many lyric translations containing 'a'",
        )

        result = self._search("a")
        self.assertTrue(result.get("ok"), result)
        sections = self._sections_by_kind(result)
        self.assertNotIn(
            "translation",
            sections,
            "translation section must be gated for len(query) < 3 (CONTRACT §1/§7.1.3)",
        )
        self.assertNotIn(
            "song",
            sections,
            "song section must be gated for len(query) < 2 (CONTRACT §1)",
        )

    def test_translation_section_is_capped_at_twenty(self):
        translation_rows = self._query_one(
            "SELECT COUNT(*) FROM song_translations "
            "WHERE LOWER(english) LIKE '%the%' OR LOWER(japanese) LIKE '%the%'"
        )[0]
        self.assertGreater(
            translation_rows,
            20,
            "real data changed: expected more than 20 lyric translations containing 'the'",
        )

        result = self._search("the")
        sections = self._sections_by_kind(result)
        self.assertIn("translation", sections, "search('the') must hit the translation section")
        self.assertEqual(
            len(sections["translation"]["entries"]),
            20,
            "translation section must be limited to 20 entries (CONTRACT §1/§7.1.3)",
        )

    def test_alice_entry_exposes_headword_id_and_ordered_senses(self):
        # CONTRACT §1: alice/chinese entries gain headword_id + senses (ascending sense_order).
        result = self._search("a", exact=True)
        self.assertTrue(result.get("ok"), result)
        sections = self._sections_by_kind(result)
        self.assertIn("alice", sections, "exact search('a') must hit the alice section")

        entries = [
            entry for entry in sections["alice"]["entries"] if entry["word"].lower() == "a"
        ]
        self.assertEqual(
            len(entries), 1, "exact search('a') must return exactly one 'a' headword entry"
        )
        entry = entries[0]
        for field in ALICE_ENTRY_FIELDS:
            self.assertIn(field, entry, "alice entry missing %r (CONTRACT §1)" % field)

        headword, senses = self._multi_sense_headword()
        self.assertEqual(entry["headword_id"], headword[0], "headword_id must be dictionary_headwords.id")
        self.assertIsInstance(entry["senses"], list)
        self.assertEqual(
            [sense["id"] for sense in entry["senses"]],
            [sense[0] for sense in senses],
            "senses must be ordered by sense_order (CONTRACT §1)",
        )
        for got, expected in zip(entry["senses"], senses):
            self.assertEqual(got["explanation"], expected[3], got)
            self.assertEqual(got.get("class"), expected[4], got)
            self.assertEqual(got.get("english_gloss"), expected[8], got)
            self.assertEqual(got.get("japanese_gloss"), expected[9], got)


class HistoryTests(RealDatabaseTestCase):
    """CONTRACT §1 / §7.1.4: record_history=False never writes query history."""

    def test_record_history_false_does_not_write_history(self):
        with mock.patch.object(self.service.history_manager, "add_record") as add_record:
            result = self._search("Alice", record_history=False)
            add_record.assert_not_called()
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(
            self.service.get_history(), [], "record_history=False must leave history empty"
        )
        self.assertFalse(
            Path(self.history_path).exists(),
            "record_history=False must not create the history file",
        )

        with mock.patch.object(self.service.history_manager, "add_record") as add_record:
            default_result = self._search("Alice")
            add_record.assert_called_once_with("Alice")
        self.assertEqual(
            result["sections"],
            default_result["sections"],
            "record_history=False must not change anything but history (CONTRACT §1)",
        )


class SongLyricsTests(RealDatabaseTestCase):
    """CONTRACT §2 / §7.1.5-6: full-lyric payload identical in shape to examples."""

    def _pick_song_with_alignments(self):
        row = self._query_one(
            "SELECT s.title, s.Album, COUNT(*) AS aligned "
            "FROM sentence_alignments sa "
            "JOIN songs s ON s.title = sa.song_title "
            "GROUP BY s.title, s.Album "
            "ORDER BY aligned DESC, s.title LIMIT 1"
        )
        self.assertIsNotNone(row, "real data changed: no song with sentence alignments")
        title, album, aligned = row
        self.assertGreater(aligned, 0)
        return title, album

    def _expected_lyric_translations(self, title: str, album: str):
        rows = self._query(
            "SELECT sa.alician_sentence, COALESCE(sa.chinese_translation, ''), "
            "COALESCE(st.english, ''), COALESCE(st.japanese, ''), COALESCE(st.korean, '') "
            "FROM sentence_alignments sa "
            "LEFT JOIN song_translations st "
            "ON st.song_title = sa.song_title AND st.sentence = sa.alician_sentence "
            "WHERE sa.song_title = ? AND sa.album = ? "
            "AND TRIM(sa.alician_sentence) <> '' "
            "ORDER BY sa.song_sentence_order",
            (title, album),
        )
        return [
            {
                "line": line,
                "poetic": poetic,
                "english": english,
                "japanese": japanese,
                "korean": korean,
            }
            for line, poetic, english, japanese, korean in rows
        ]

    def test_get_song_lyrics_returns_one_full_song_with_real_translations(self):
        title, album = self._pick_song_with_alignments()
        expected_translations = self._expected_lyric_translations(title, album)
        self.assertGreater(
            len(expected_translations), 0, "real data changed: pick a song with aligned lines"
        )
        lyric = self._query_one(
            "SELECT lyric FROM songs WHERE title = ? AND Album = ?", (title, album)
        )[0]
        self.assertTrue(lyric and lyric.strip(), "real data changed: song lyric is empty")

        result = self._song_lyrics(title, album)
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result["word"], title)
        self.assertEqual(len(result["examples"]), 1, "a full song is exactly one example")

        example = result["examples"][0]
        for field in (
            "id",
            "paragraph",
            "title",
            "album",
            "lyric",
            "start",
            "end",
            "poetic_translation",
            "english_translation",
            "japanese_translation",
            "korean_translation",
            "lyric_translations",
        ):
            self.assertIn(field, example, "ExampleResult example missing %r (CONTRACT §2)" % field)
        self.assertEqual(example["id"], 0)
        self.assertEqual(example["title"], title)
        self.assertEqual(example["album"], album)
        self.assertEqual(example["paragraph"], lyric, "paragraph must be the complete lyric")
        self.assertEqual(example["lyric"], lyric, "lyric must be the complete lyric")
        self.assertEqual(example["start"], 0)
        self.assertEqual(example["end"], len(lyric))
        for field in (
            "poetic_translation",
            "english_translation",
            "japanese_translation",
            "korean_translation",
        ):
            self.assertEqual(
                example[field], "", "%s must be empty on the full-lyric example (CONTRACT §2)" % field
            )
        self.assertEqual(
            example["lyric_translations"],
            expected_translations,
            "lyric_translations must come from the real alignment tables (CONTRACT §2/§7.1.5)",
        )

        self.assertEqual(
            result["song_stats"],
            [{"album": album, "title": title, "before": 1, "after": 1}],
        )
        self.assertEqual(result["total_before"], 1)
        self.assertEqual(result["total_after"], 1)
        self.assertEqual(result["deduplication_rate"], 0)
        self.assertEqual(result.get("position_filter"), "any")
        self.assertEqual(result["message"], "")

    def test_get_song_lyrics_missing_song(self):
        result = self._song_lyrics("不存在的歌", "")
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("word"), "不存在的歌")
        self.assertEqual(result.get("examples"), [])
        self.assertEqual(result.get("song_stats"), [])
        self.assertEqual(result.get("total_before"), 0)
        self.assertEqual(result.get("total_after"), 0)
        self.assertEqual(result.get("deduplication_rate"), 0)
        self.assertEqual(result.get("message"), "未找到这首歌。")


class UpdateWordEntryTests(RealDatabaseTestCase):
    """CONTRACT §3 / §7.1.7-9: sense-level edit, rename uniqueness, validation."""

    def _valid_sense_payload(self, sense) -> dict:
        return {
            "id": sense[0],
            "explanation": sense[3],
            "english": sense[8],
            "japanese": sense[9],
        }

    def test_update_preserves_unsubmitted_senses_and_rename_syncs_words(self):
        headword, senses = self._multi_sense_headword()
        headword_id, word, display_explanation = headword[0], headword[1], headword[2]
        first_sense = senses[0]
        untouched_senses = senses[1:]
        headword_rows_before = self._query_one("SELECT COUNT(*) FROM dictionary_headwords")[0]
        sense_rows_before = self._query_one("SELECT COUNT(*) FROM dictionary")[0]

        new_display = "展示释义（回归测试）"
        new_explanation = "义项一释义（回归测试）"
        new_english = "regression english"
        new_japanese = "回帰テスト"

        result = self._update_word(
            headword_id=headword_id,
            original_word=word,
            word=word,
            display_explanation=new_display,
            senses=[
                {
                    "id": first_sense[0],
                    "explanation": new_explanation,
                    "english": new_english,
                    "japanese": new_japanese,
                }
            ],
        )
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(result.get("message"), "词条已保存。")
        self.assertEqual(result.get("headword_id"), headword_id)
        self.assertEqual(result.get("word"), word)

        headword_after = self._query_one(
            "SELECT id, words, display_explanation, display_class, count, variety "
            "FROM dictionary_headwords WHERE id = ?",
            (headword_id,),
        )
        self.assertEqual(headword_after[2], new_display, "display_explanation must be updated")
        self.assertEqual(headword_after[1], word, "the word itself was not renamed in this step")
        self.assertEqual(
            headword_after[3:],
            headword[3:],
            "display_class/count/variety must not change (CONTRACT §3)",
        )

        senses_after_first = self._senses(headword_id)
        self.assertEqual(len(senses_after_first), len(senses))
        first_after = senses_after_first[0]
        self.assertEqual(first_after[0], first_sense[0], "sense ids must not change")
        self.assertEqual(first_after[3], new_explanation)
        self.assertEqual(first_after[8], new_english)
        self.assertEqual(first_after[9], new_japanese)
        self.assertEqual(
            first_after[4:8],
            first_sense[4:8],
            "class/sense_order/count/variety must not change (CONTRACT §3)",
        )
        for before, after in zip(untouched_senses, senses_after_first[1:]):
            self.assertEqual(
                after,
                before,
                "unsubmitted sense must stay byte-identical (CONTRACT §0.1/§3): %r" % (before[0],),
            )

        # Rename: only words should follow; every sense keeps its own explanation/glosses.
        new_word = self._unique_new_word()
        rename_result = self._update_word(
            headword_id=headword_id,
            original_word=word,
            word=new_word,
            display_explanation=new_display,
            senses=[
                {
                    "id": first_sense[0],
                    "explanation": new_explanation,
                    "english": new_english,
                    "japanese": new_japanese,
                }
            ],
        )
        self.assertTrue(rename_result.get("ok"), rename_result)
        self.assertEqual(rename_result.get("word"), new_word)

        headword_renamed = self._query_one(
            "SELECT id, words, display_explanation FROM dictionary_headwords WHERE id = ?",
            (headword_id,),
        )
        self.assertEqual(headword_renamed[1], new_word, "headword must be renamed")
        self.assertEqual(headword_renamed[2], new_display)

        senses_renamed = self._senses(headword_id)
        self.assertEqual(len(senses_renamed), len(senses))
        self.assertEqual(
            [sense[0] for sense in senses_renamed],
            [sense[0] for sense in senses],
            "renaming must not create or delete senses",
        )
        for before, after in zip(senses_after_first, senses_renamed):
            self.assertEqual(after[1], headword_id, "headword_id must stay intact")
            self.assertEqual(after[2], new_word, "every sense's words must be renamed together")
            self.assertEqual(
                after[3:], before[3:], "renaming must not alter explanations/glosses/order"
            )

        # Delta check: only the edited rows changed; nothing was duplicated or deleted.
        self.assertEqual(
            self._query_one("SELECT COUNT(*) FROM dictionary_headwords")[0], headword_rows_before
        )
        self.assertEqual(self._query_one("SELECT COUNT(*) FROM dictionary")[0], sense_rows_before)

    def test_rename_onto_existing_word_is_rejected_without_new_headword(self):
        headword, senses = self._multi_sense_headword()
        headword_id, word, display_explanation = headword[0], headword[1], headword[2]

        # Pick a real other headword whose spelling has a different-case variant so the
        # uniqueness check is exercised case-insensitively (CONTRACT §3).
        candidates = self._query(
            "SELECT id, words FROM dictionary_headwords WHERE id <> ? AND LENGTH(words) >= 2 "
            "ORDER BY id",
            (headword_id,),
        )
        target = None
        for candidate_id, candidate_word in candidates:
            if candidate_word.lower() != candidate_word:
                variant = candidate_word.lower()
            elif candidate_word.upper() != candidate_word:
                variant = candidate_word.upper()
            else:
                continue
            if variant != candidate_word and variant.lower() == candidate_word.lower():
                target = (candidate_id, candidate_word, variant)
                break
        self.assertIsNotNone(target, "real data changed: no headword with a case variant")
        target_id, target_word, collision_word = target

        before = self._snapshot(headword_id)
        target_before = self._query_one(
            "SELECT id, words, display_explanation FROM dictionary_headwords WHERE id = ?",
            (target_id,),
        )

        result = self._update_word(
            headword_id=headword_id,
            original_word=word,
            word=collision_word,
            display_explanation=display_explanation,
            senses=[self._valid_sense_payload(senses[0])],
        )
        self.assertFalse(
            result.get("ok"),
            "renaming onto an existing word must be rejected (CONTRACT §3/§7.1.8): %r" % (result,),
        )
        self.assertEqual(result.get("message"), "已存在同名词条，请改用不同的原文。")

        self.assertEqual(
            self._snapshot(headword_id), before, "a rejected rename must not touch the database"
        )
        self.assertEqual(
            self._query_one(
                "SELECT id, words, display_explanation FROM dictionary_headwords WHERE id = ?",
                (target_id,),
            ),
            target_before,
            "a rejected rename must not touch the colliding headword",
        )
        self.assertEqual(
            self._query_one(
                "SELECT COUNT(*) FROM dictionary_headwords WHERE LOWER(words) = LOWER(?)",
                (collision_word,),
            )[0],
            1,
            "a rejected rename must not create a duplicate headword",
        )

    def test_invalid_payloads_are_rejected_and_leave_data_untouched(self):
        headword, senses = self._multi_sense_headword()
        headword_id, word, display_explanation = headword[0], headword[1], headword[2]
        first_sense = senses[0]
        valid_senses = [self._valid_sense_payload(first_sense)]

        other_sense = self._query_one(
            "SELECT id FROM dictionary WHERE headword_id <> ? ORDER BY id LIMIT 1",
            (headword_id,),
        )
        self.assertIsNotNone(other_sense, "real data changed: no second headword senses")
        missing_headword_id = headword_id + 100000

        cases = [
            (
                "missing headword",
                dict(
                    headword_id=missing_headword_id,
                    original_word=word,
                    word=word,
                    display_explanation=display_explanation,
                    senses=valid_senses,
                ),
                "未找到要修改的词条。",
            ),
            (
                "blank word",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word="   ",
                    display_explanation=display_explanation,
                    senses=valid_senses,
                ),
                "原文不能为空。",
            ),
            (
                "word too long",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word="x" * 65,
                    display_explanation=display_explanation,
                    senses=valid_senses,
                ),
                "原文过长。",
            ),
            (
                "word contains newline",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word="bad\nword",
                    display_explanation=display_explanation,
                    senses=valid_senses,
                ),
                "原文不能包含换行。",
            ),
            (
                "word contains carriage return",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word="bad\rword",
                    display_explanation=display_explanation,
                    senses=valid_senses,
                ),
                "原文不能包含换行。",
            ),
            (
                "blank display explanation",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word=word,
                    display_explanation="   ",
                    senses=valid_senses,
                ),
                "展示释义不能为空。",
            ),
            (
                "display explanation too long",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word=word,
                    display_explanation="x" * 501,
                    senses=valid_senses,
                ),
                "展示释义过长。",
            ),
            (
                "blank sense explanation",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word=word,
                    display_explanation=display_explanation,
                    senses=[
                        {
                            "id": first_sense[0],
                            "explanation": "   ",
                            "english": first_sense[8],
                            "japanese": first_sense[9],
                        }
                    ],
                ),
                "义项释义不能为空。",
            ),
            (
                "sense explanation too long",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word=word,
                    display_explanation=display_explanation,
                    senses=[
                        {
                            "id": first_sense[0],
                            "explanation": "x" * 501,
                            "english": first_sense[8],
                            "japanese": first_sense[9],
                        }
                    ],
                ),
                "义项释义过长。",
            ),
            (
                "sense id from another headword",
                dict(
                    headword_id=headword_id,
                    original_word=word,
                    word=word,
                    display_explanation=display_explanation,
                    senses=[
                        {
                            "id": other_sense[0],
                            "explanation": "不属于该词条的义项",
                            "english": "",
                            "japanese": "",
                        }
                    ],
                ),
                "义项数据不一致，请刷新后重试。",
            ),
        ]

        before = self._snapshot(headword_id)
        for name, fields, expected_message in cases:
            with self.subTest(case=name):
                result = self._update_word(**fields)
                self.assertFalse(
                    result.get("ok"),
                    "%s must be rejected (CONTRACT §3/§7.1.9): %r" % (name, result),
                )
                self.assertEqual(result.get("message"), expected_message)
                self.assertEqual(
                    self._snapshot(headword_id),
                    before,
                    "%s must leave the database untouched" % name,
                )
                connection = self.service.db_handler.conn
                if connection is not None:
                    self.assertFalse(
                        connection.in_transaction,
                        "%s must not leave the connection inside a transaction (CONTRACT §3)"
                        % name,
                    )


class TransactionRecoveryTests(RealDatabaseTestCase):
    """CONTRACT §0.3 / §4 / §7.1.10: a failed lyric save must not poison the connection."""

    def test_failed_lyric_update_rolls_back_and_next_word_update_succeeds(self):
        headword, senses = self._multi_sense_headword()
        headword_id, word, display_explanation = headword[0], headword[1], headword[2]
        first_sense = senses[0]

        failed = self.service.update_song_lyric("不存在的歌", "不存在的专辑", "随便写点什么")
        self.assertFalse(failed.get("ok"), failed)

        connection = self.service.db_handler.conn
        self.assertIsNotNone(connection)
        self.assertFalse(
            connection.in_transaction,
            "update_song_lyric() on a missing song must roll back (CONTRACT §4), "
            "otherwise the next write hits 'cannot start a transaction within a transaction'",
        )

        new_display = "事务恢复测试展示释义"
        new_explanation = "事务恢复测试义项"
        result = self._update_word(
            headword_id=headword_id,
            original_word=word,
            word=word,
            display_explanation=new_display,
            senses=[
                {
                    "id": first_sense[0],
                    "explanation": new_explanation,
                    "english": first_sense[8],
                    "japanese": first_sense[9],
                }
            ],
        )
        self.assertTrue(
            result.get("ok"),
            "after a failed lyric update the word update must still succeed "
            "(CONTRACT §7.1.10): %r" % (result,),
        )
        self.assertNotIn("cannot start a transaction within a transaction", result.get("message", ""))

        stored = self._query_one(
            "SELECT display_explanation FROM dictionary_headwords WHERE id = ?", (headword_id,)
        )
        self.assertEqual(stored[0], new_display)
        stored_sense = self._query_one(
            "SELECT explanation FROM dictionary WHERE id = ?", (first_sense[0],)
        )
        self.assertEqual(stored_sense[0], new_explanation)


class ShippedSchemaTests(RealDatabaseTestCase):
    """Guard: the tests really run against the shipped schema, never a fake one."""

    def test_private_copy_keeps_the_shipped_schema_constraints(self):
        self.assertEqual(
            hashlib.sha256(Path(self.db_path).read_bytes()).hexdigest(),
            ASSET_SHA256,
            "the working database must be the shipped asset, unmodified",
        )

        # songs.title must be UNIQUE (used by get_song_lyrics and the song section).
        unique_title_columns = []
        for index_row in self._query("PRAGMA index_list(songs)"):
            if not index_row[2]:  # not unique
                continue
            index_name = index_row[1]
            columns = [row[2] for row in self._query("PRAGMA index_info(%s)" % index_name)]
            if columns == ["title"]:
                unique_title_columns.append(index_name)
        self.assertTrue(unique_title_columns, "songs.title must be UNIQUE in the shipped schema")

        # dictionary must have the real NOT NULL columns, integer primary key and FK.
        table_info = {row[1]: row for row in self._query("PRAGMA table_info(dictionary)")}
        self.assertIn("id", table_info)
        self.assertEqual(table_info["id"][5], 1, "dictionary.id must be the primary key")
        self.assertEqual(table_info["headword_id"][3], 1, "dictionary.headword_id must be NOT NULL")
        self.assertEqual(table_info["explanation"][3], 1, "dictionary.explanation must be NOT NULL")
        self.assertEqual(table_info["sense_order"][3], 1, "dictionary.sense_order must be NOT NULL")
        foreign_tables = [row[2] for row in self._query("PRAGMA foreign_key_list(dictionary)")]
        self.assertIn(
            "dictionary_headwords",
            foreign_tables,
            "dictionary.headword_id must keep its foreign key in the shipped schema",
        )

        # Real data volume, so the tests above are genuinely data-driven.
        self.assertGreaterEqual(self._query_one("SELECT COUNT(*) FROM songs")[0], 50)
        self.assertGreaterEqual(self._query_one("SELECT COUNT(*) FROM song_translations")[0], 900)
        self.assertGreaterEqual(self._query_one("SELECT COUNT(*) FROM sentence_alignments")[0], 1200)
        self.assertGreaterEqual(self._query_one("SELECT COUNT(*) FROM dictionary")[0], 1500)
        self.assertGreaterEqual(self._query_one("SELECT COUNT(*) FROM dictionary_headwords")[0], 1300)
        multi_sense = self._query_one(
            "SELECT COUNT(*) FROM ("
            "SELECT headword_id FROM dictionary GROUP BY headword_id HAVING COUNT(*) > 1)"
        )[0]
        self.assertGreaterEqual(multi_sense, 100, "shipped data has 140 multi-sense headwords")


if __name__ == "__main__":
    unittest.main(verbosity=2)
