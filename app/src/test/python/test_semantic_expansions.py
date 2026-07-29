from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from webui_backend.translation_service import TranslationService


class SemanticExpansionTests(unittest.TestCase):
    def _create_database(self, path: Path, include_expansion: bool) -> None:
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
                    (1, 1, 'Abelu', '升起', 'v.', 1, 8, 3);
                """
            )
            if include_expansion:
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

    def test_expansions_are_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(database, include_expansion=True)
            service = TranslationService(
                str(database),
                enable_fallback_matching=False,
            )
            service._jieba = None
            try:
                disabled = service.translate(
                    "龘靐齉",
                    "zh_to_alician",
                    use_semantic_expansions=False,
                )
                enabled = service.translate(
                    "龘靐齉",
                    "zh_to_alician",
                    use_semantic_expansions=True,
                )
            finally:
                service.close()

            self.assertEqual(disabled["stats"]["unknown"], 1)
            self.assertEqual(enabled["tokens"][0]["target"], "Abelu")
            self.assertEqual(enabled["tokens"][0]["method"], "semantic_expansion")
            self.assertTrue(enabled["semantic_expansions_enabled"])
            self.assertTrue(enabled["semantic_expansions_available"])
            self.assertEqual(enabled["semantic_expansion_count"], 1)

    def test_missing_expansion_table_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "translated.db"
            self._create_database(database, include_expansion=False)
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
