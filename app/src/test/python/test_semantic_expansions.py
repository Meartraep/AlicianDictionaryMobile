from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from webui_backend.translation_service import TranslationService


class StubTokenizer:
    def __init__(self, parts: list[str]) -> None:
        self.parts = parts

    def cut(self, _text: str, **_kwargs: object) -> list[str]:
        return list(self.parts)


class SemanticExpansionTests(unittest.TestCase):
    def _create_database(
        self,
        path: Path,
        *,
        include_alias: bool = False,
        include_legacy_expansion: bool = False,
        include_direct_alias_term: bool = False,
        include_strong_exact_cover: bool = False,
    ) -> None:
        with sqlite3.connect(path) as connection:
            connection.executescript(
                """
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
                    PHRASE TEXT,
                    explanation TEXT,
                    count INTEGER DEFAULT 0,
                    variety INTEGER DEFAULT 0
                );
                INSERT INTO dictionary
                    (id, headword_id, words, explanation, class, sense_order, count, variety)
                VALUES
                    (1, 1, 'Abelu', '升起', 'v.', 1, 8, 3),
                    (2, 2, 'Tai', '起', 'v.', 1, 2, 1),
                    (6, 6, 'Voi', '真', 'adj.', 1, 3, 1),
                    (7, 7, 'Study', '学习', 'v.', 1, 3, 1);
                """
            )
            if include_direct_alias_term:
                connection.execute(
                    """
                    INSERT INTO dictionary
                        (id, headword_id, words, explanation, class, sense_order, count, variety)
                    VALUES (3, 3, 'Fly', '飞起', 'v.', 1, 4, 2)
                    """
                )
            if include_strong_exact_cover:
                connection.executescript(
                    """
                    INSERT INTO dictionary
                        (id, headword_id, words, explanation, class, sense_order, count, variety)
                    VALUES
                        (4, 4, 'Sun', '太阳', 'n.', 1, 4, 2),
                        (5, 5, 'Rise', '升起', 'v.', 1, 4, 2);
                    """
                )
            if include_alias:
                connection.executescript(
                    """
                    CREATE TABLE dictionary_semantic_aliases (
                        id INTEGER PRIMARY KEY,
                        sense_id INTEGER NOT NULL,
                        alias TEXT NOT NULL,
                        similarity REAL NOT NULL,
                        rank INTEGER NOT NULL
                    );
                    INSERT INTO dictionary_semantic_aliases
                    VALUES (1, 1, '飞起', 0.90, 1);
                    """
                )
                if include_strong_exact_cover:
                    connection.execute(
                        """
                        INSERT INTO dictionary_semantic_aliases
                        VALUES (2, 1, '太阳升起', 0.91, 1)
                        """
                    )
            if include_legacy_expansion:
                connection.executescript(
                    """
                    CREATE TABLE dictionary_sense_expansions (
                        id INTEGER PRIMARY KEY,
                        sense_id INTEGER NOT NULL,
                        related_sense_id INTEGER NOT NULL,
                        expansion TEXT NOT NULL,
                        similarity REAL NOT NULL,
                        rank INTEGER NOT NULL,
                        model_name TEXT NOT NULL,
                        model_revision TEXT NOT NULL,
                        generated_at TEXT NOT NULL
                    );
                    INSERT INTO dictionary_sense_expansions
                    VALUES (1, 1, 1, '龘靐齉', 0.94, 1, 'fake', 'fake', 'now');
                    """
                )

    def test_aliases_are_opt_in_and_beat_shorter_exact_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(database, include_alias=True)
            service = TranslationService(
                str(database),
                enable_fallback_matching=False,
            )
            service._jieba = None
            try:
                disabled = service.translate(
                    "飞起",
                    "zh_to_alician",
                    use_semantic_expansions=False,
                )
                enabled = service.translate(
                    "飞起",
                    "zh_to_alician",
                    use_semantic_expansions=True,
                )
            finally:
                service.close()

            self.assertEqual(disabled["stats"]["unknown"], 1)
            self.assertEqual([token["source"] for token in disabled["tokens"]], ["飞起"])
            self.assertEqual(len(enabled["tokens"]), 1)
            self.assertEqual(enabled["tokens"][0]["source"], "飞起")
            self.assertEqual(enabled["tokens"][0]["target"], "Abelu")
            self.assertEqual(enabled["tokens"][0]["method"], "semantic_expansion")
            self.assertEqual(enabled["stats"]["unknown"], 0)
            self.assertTrue(enabled["semantic_expansions_enabled"])
            self.assertTrue(enabled["semantic_expansions_available"])
            self.assertEqual(enabled["semantic_expansion_count"], 1)

    def test_sentence_segmentation_precedes_dictionary_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(database)
            service = TranslationService(
                str(database),
                enable_fallback_matching=False,
            )
            service._jieba = StubTokenizer(
                ["今天", "早上", "我", "在", "学校", "认真学习"]
            )
            try:
                tokens = service._translate_chinese_run(
                    "今天早上我在学校认真学习"
                )
            finally:
                service.close()

            self.assertEqual(
                [token["source"] for token in tokens],
                ["今天", "早上", "我", "在", "学校", "认真学习"],
            )
            self.assertEqual(tokens[-1]["status"], "unknown")
            self.assertEqual(tokens[-1]["target"], "〔认真学习〕")

    def test_equal_length_dictionary_term_wins_over_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(
                database,
                include_alias=True,
                include_direct_alias_term=True,
            )
            service = TranslationService(
                str(database),
                enable_fallback_matching=False,
            )
            service._jieba = None
            try:
                result = service.translate(
                    "飞起",
                    "zh_to_alician",
                    use_semantic_expansions=True,
                )
            finally:
                service.close()

            self.assertEqual(len(result["tokens"]), 1)
            self.assertEqual(result["tokens"][0]["target"], "Fly")
            self.assertEqual(result["tokens"][0]["method"], "dictionary_term")
            self.assertFalse(result["semantic_expansions_available"])

    def test_alias_start_ends_the_preceding_unknown_segment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(database, include_alias=True)
            service = TranslationService(
                str(database),
                enable_fallback_matching=False,
            )
            service._jieba = None
            try:
                result = service.translate(
                    "陌飞起",
                    "zh_to_alician",
                    use_semantic_expansions=True,
                )
            finally:
                service.close()

            self.assertEqual(result["tokens"][0]["source"], "陌")
            semantic = next(
                token for token in result["tokens"]
                if token["method"] == "semantic_expansion"
            )
            self.assertEqual(semantic["source"], "飞起")
            self.assertEqual(semantic["target"], "Abelu")

    def test_alias_does_not_swallow_two_complete_multicharacter_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(
                database,
                include_alias=True,
                include_strong_exact_cover=True,
            )
            service = TranslationService(
                str(database),
                enable_fallback_matching=False,
            )
            service._jieba = None
            try:
                result = service.translate(
                    "太阳升起",
                    "zh_to_alician",
                    use_semantic_expansions=True,
                )
            finally:
                service.close()

            self.assertEqual(
                [token["source"] for token in result["tokens"]],
                ["太阳", "升起"],
            )
            self.assertTrue(
                all(
                    token["method"] == "dictionary_term"
                    for token in result["tokens"]
                )
            )

    def test_legacy_nearest_explanations_are_not_presented_as_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(database, include_legacy_expansion=True)
            service = TranslationService(
                str(database),
                enable_fallback_matching=False,
            )
            service._jieba = None
            try:
                result = service.translate(
                    "龘靐齉",
                    "zh_to_alician",
                    use_semantic_expansions=True,
                )
            finally:
                service.close()

            self.assertEqual(result["stats"]["unknown"], 1)
            self.assertFalse(result["semantic_expansions_available"])
            self.assertEqual(result["semantic_expansion_count"], 0)

    def test_missing_expansion_table_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(database)
            service = TranslationService(
                str(database),
                enable_fallback_matching=False,
            )
            service._jieba = None
            try:
                result = service.translate(
                    "龘靐齉",
                    "zh_to_alician",
                    use_semantic_expansions=True,
                )
            finally:
                service.close()

            self.assertEqual(result["stats"]["unknown"], 1)
            self.assertTrue(result["semantic_expansions_enabled"])
            self.assertFalse(result["semantic_expansions_available"])
            self.assertEqual(result["semantic_expansion_count"], 0)


if __name__ == "__main__":
    unittest.main()
