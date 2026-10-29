from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from webui_backend.writing_database import DatabaseManager
from webui_backend.writing_service import WritingAssistantService

ASSET_DB = Path(__file__).resolve().parents[2] / "main" / "assets" / "translated.db"

SCHEMA = """
CREATE TABLE dictionary_headwords (
    id INTEGER PRIMARY KEY,
    words TEXT NOT NULL,
    display_explanation TEXT,
    display_class TEXT,
    count INTEGER DEFAULT 0,
    variety INTEGER DEFAULT 0,
    time TEXT
);
CREATE TABLE dictionary (
    id INTEGER PRIMARY KEY,
    headword_id INTEGER NOT NULL,
    words TEXT NOT NULL,
    explanation TEXT NOT NULL,
    class TEXT,
    sense_order INTEGER NOT NULL,
    count INTEGER DEFAULT 0,
    variety INTEGER DEFAULT 0,
    time TEXT
);
CREATE TABLE phrase (
    id INTEGER PRIMARY KEY,
    PHRASE TEXT NOT NULL,
    explanation TEXT,
    count INTEGER DEFAULT 0,
    variety INTEGER DEFAULT 0
);
"""

# ``Certa`` 与 ``Poul ail`` 词频/泛度极低，但没有 (?) 标注：不应再标蓝。
# ``Dubia``/``Frequ``/``Nai Drue`` 带 (?) 标注；``Sensu`` 仅第二个义项带标注。
ROWS = """
INSERT INTO dictionary_headwords
    (id, words, display_explanation, display_class, count, variety)
VALUES
    (1, 'Certa', '确定的', 'adj.', 1, 0),
    (2, 'Dubia', '不确定(?)', 'adj.', 0, 0),
    (3, 'Frequ', '常见(?)', 'adj.', 99, 42),
    (4, 'Sensu', '稳定', 'adj.', 5, 2);

INSERT INTO dictionary
    (id, headword_id, words, explanation, class, sense_order, count, variety)
VALUES
    (1, 1, 'Certa', '确定的', 'adj.', 1, 1, 0),
    (2, 2, 'Dubia', '不确定(?)', 'adj.', 1, 0, 0),
    (3, 3, 'Frequ', '常见(?)', 'adj.', 1, 99, 42),
    (4, 4, 'Sensu', '稳定', 'adj.', 1, 5, 2),
    (5, 4, 'Sensu', '另一个(?)', 'adj.', 2, 5, 2);

INSERT INTO phrase (id, PHRASE, explanation, count, variety)
VALUES
    (1, 'Poul ail', '确定的', 4, 3),
    (2, 'Nai Drue', '待定（?）', 0, 0);
"""


class WritingAssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "translated.db"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(SCHEMA)
            connection.executescript(ROWS)

        self._previous_db_env = os.environ.get("ALICIAN_DB_PATH")
        os.environ["ALICIAN_DB_PATH"] = str(self.db_path)
        DatabaseManager().close_connection()
        self.service = WritingAssistantService()
        self.service.config_manager.set("strict_case", True)
        self.service.reload_known_words()

    def tearDown(self) -> None:
        self.service.close()
        DatabaseManager().close_connection()
        if self._previous_db_env is None:
            os.environ.pop("ALICIAN_DB_PATH", None)
        else:
            os.environ["ALICIAN_DB_PATH"] = self._previous_db_env
        self.tmp.cleanup()

    def _span(self, text: str, word: str) -> tuple[int, int]:
        start = text.index(word)
        return start, start + len(word)

    def test_blue_marks_only_senses_with_uncertain_marker(self) -> None:
        text = "Certa Dubia Frequ Sensu Missin. Poul ail. Nai Drue."
        result = self.service.check_text(text)

        expected_uncertain = {
            self._span(text, "Dubia"),
            self._span(text, "Frequ"),
            self._span(text, "Sensu"),
            self._span(text, "Nai Drue"),
        }
        self.assertEqual(set(result["uncertain_ranges"]), expected_uncertain)
        self.assertEqual(set(result["unknown_ranges"]), {self._span(text, "Missin")})
        self.assertEqual(result["uncertain_count"], len(expected_uncertain))

        # 词频/泛度很低但没有 (?) 的词（Certa、Poul ail）不能被标蓝。
        self.assertNotIn(self._span(text, "Certa"), result["uncertain_ranges"])
        self.assertNotIn(self._span(text, "Poul ail"), result["uncertain_ranges"])

        items = {item["display"]: item for item in result["sidebar_items"]}
        self.assertEqual(
            {word for word, item in items.items() if item["type"] == "uncertain"},
            {"Dubia", "Frequ", "Sensu", "Nai Drue"},
        )
        self.assertEqual(items["Missin"]["type"], "unknown")
        self.assertIn("词义不确定词 4 个", result["status"])

    def test_sidebar_items_no_longer_expose_frequency_or_variety(self) -> None:
        result = self.service.check_text("Certa Dubia. Frequ.")
        self.assertTrue(result["sidebar_items"])
        for item in result["sidebar_items"]:
            self.assertNotIn("count", item)
            self.assertNotIn("variety", item)
            self.assertNotIn("reasons", item)

    def test_case_insensitive_mode_uses_lowercase_keys(self) -> None:
        self.service.config_manager.set("strict_case", False)
        self.service.reload_known_words()

        text = "dubia frequ certa"
        result = self.service.check_text(text)

        self.assertEqual(
            set(result["uncertain_ranges"]),
            {self._span(text, "dubia"), self._span(text, "frequ")},
        )
        uncertain_keys = {
            item["key"] for item in result["sidebar_items"] if item["type"] == "uncertain"
        }
        self.assertEqual(uncertain_keys, {"dubia", "frequ"})

    def test_reload_picks_up_dictionary_sense_edits(self) -> None:
        # 给 Certa 的义项加上 (?)：词头展示释义没有标注，也应通过义项判定为不确定。
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "UPDATE dictionary SET explanation = '确定的(?)' WHERE id = 1"
            )
            # 移除 Dubia 词头与义项上的 (?) 标注。
            connection.execute(
                "UPDATE dictionary_headwords SET display_explanation = '确定' WHERE id = 2"
            )
            connection.execute(
                "UPDATE dictionary SET explanation = '确定' WHERE id = 2"
            )
            connection.commit()

        self.service.reload_known_words()
        result = self.service.check_text("Certa Dubia")

        self.assertEqual(set(result["uncertain_ranges"]), {self._span("Certa Dubia", "Certa")})


class WritingCacheInvalidationTests(unittest.TestCase):
    def test_dictionary_edits_refresh_cached_uncertainty_markers(self) -> None:
        import mobile_bridge

        class FakeWriting:
            def __init__(self) -> None:
                self.reloads = 0

            def reload_known_words(self) -> None:
                self.reloads += 1

        fake = FakeWriting()
        previous = mobile_bridge._writing
        mobile_bridge._writing = fake
        try:
            for table in ("dictionary", "dictionary_headwords", "phrase"):
                mobile_bridge._reload_writing_if_needed({table})
            # Unrelated writes (lyrics, raw text) must not reload the writing cache.
            mobile_bridge._reload_writing_if_needed({"songs", "raw"})
            mobile_bridge._reload_writing_if_needed(None)
        finally:
            mobile_bridge._writing = previous

        self.assertEqual(fake.reloads, 3)


class PublishedDatabaseWritingTests(unittest.TestCase):
    """The shipped database must map to the same uncertain-word set as a direct recount."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._previous_db_env = os.environ.get("ALICIAN_DB_PATH")
        os.environ["ALICIAN_DB_PATH"] = str(ASSET_DB)
        DatabaseManager().close_connection()
        cls.service = WritingAssistantService()
        cls.service.config_manager.set("strict_case", True)
        cls.service.reload_known_words()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.service.close()
        DatabaseManager().close_connection()
        if cls._previous_db_env is None:
            os.environ.pop("ALICIAN_DB_PATH", None)
        else:
            os.environ["ALICIAN_DB_PATH"] = cls._previous_db_env

    def test_published_database_uncertain_words_match_independent_recount(self) -> None:
        expected = set()
        with closing(sqlite3.connect(ASSET_DB)) as connection:
            uncertain_ids = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT headword_id FROM dictionary "
                    "WHERE explanation LIKE '%(?)%'"
                )
            }
            for headword_id, word, display_explanation in connection.execute(
                "SELECT id, words, display_explanation FROM dictionary_headwords"
            ):
                if headword_id in uncertain_ids or "(?)" in str(display_explanation or ""):
                    expected.add(str(word))

        self.assertTrue(expected)
        self.assertEqual(self.service.highlight_manager.uncertain_words, expected)
        self.assertIn("Alan", self.service.highlight_manager.uncertain_words)

    def test_published_database_known_low_frequency_words_stay_black(self) -> None:
        # 低词频/低泛度本身不再产生蓝色高亮。
        uncertain = self.service.highlight_manager.uncertain_words
        with closing(sqlite3.connect(ASSET_DB)) as connection:
            low_stat_words = [
                str(row[0])
                for row in connection.execute(
                    "SELECT words FROM dictionary_headwords "
                    "WHERE count < 3 AND variety < 3"
                )
            ]
        candidates = [
            word
            for word in low_stat_words
            if word not in uncertain and word.isascii() and word.isalpha()
        ]
        self.assertTrue(candidates)
        word = candidates[0]
        result = self.service.check_text(word)
        self.assertNotIn((0, len(word)), result["uncertain_ranges"])
        self.assertNotIn((0, len(word)), result["unknown_ranges"])


class BridgeCuratedWriteRefreshTests(unittest.TestCase):
    """Dictionary-editor writes bypass the DataCore sink; the writing cache must still refresh."""

    def setUp(self) -> None:
        import mobile_bridge

        self.bridge = mobile_bridge
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "translated.db"
        shutil.copy2(ASSET_DB, self.db_path)
        self.data_dir = Path(self.tmp.name) / "data"
        self._cwd = os.getcwd()
        self._env = {
            key: os.environ.get(key)
            for key in ("ALICIAN_DB_PATH", "ALICIAN_LITE_BUILD")
        }

        with closing(sqlite3.connect(self.db_path)) as connection:
            self.headword_id = int(
                connection.execute(
                    "SELECT id FROM dictionary_headwords WHERE words = 'Abelu'"
                ).fetchone()[0]
            )
            self.senses = [
                {
                    "id": row[0],
                    "explanation": row[1],
                    "class": row[2],
                    "english_gloss": row[3],
                    "japanese_gloss": row[4],
                }
                for row in connection.execute(
                    "SELECT id, explanation, class, english_gloss, japanese_gloss "
                    "FROM dictionary WHERE headword_id = ? ORDER BY id",
                    (self.headword_id,),
                )
            ]

        initialized = json.loads(
            self.bridge.initialize(str(self.db_path), str(self.data_dir))
        )
        self.assertTrue(initialized.get("ok"), initialized)
        self.assertFalse(
            self.bridge._writing.highlight_manager.is_uncertain_word("Abelu")
        )

    def tearDown(self) -> None:
        self.bridge._close_services()
        os.chdir(self._cwd)
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def _update_word(self, explanation: str) -> dict:
        senses = [dict(sense) for sense in self.senses]
        senses[0]["explanation"] = explanation
        return json.loads(
            self.bridge.invoke(
                "dictionary_update_word",
                json.dumps(
                    {
                        "headword_id": self.headword_id,
                        "original_word": "Abelu",
                        "word": "Abelu",
                        "display_explanation": explanation,
                        "senses": senses,
                    }
                ),
            )
        )

    def test_editor_edit_refreshes_writing_uncertainty(self) -> None:
        self.assertEqual(
            self.bridge._writing.check_text("Abelu")["uncertain_ranges"], []
        )

        result = self._update_word("升起(?)")
        self.assertTrue(result.get("ok"), result)
        self.assertTrue(
            self.bridge._writing.highlight_manager.is_uncertain_word("Abelu")
        )
        self.assertEqual(
            self.bridge._writing.check_text("Abelu")["uncertain_ranges"], [(0, 5)]
        )

        # Removing the marker must clear the blue highlight again.
        result = self._update_word("升起")
        self.assertTrue(result.get("ok"), result)
        self.assertFalse(
            self.bridge._writing.highlight_manager.is_uncertain_word("Abelu")
        )
        self.assertEqual(
            self.bridge._writing.check_text("Abelu")["uncertain_ranges"], []
        )
