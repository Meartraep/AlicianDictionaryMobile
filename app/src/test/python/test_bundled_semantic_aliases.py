from __future__ import annotations

import re
import sqlite3
import unittest
from pathlib import Path

from webui_backend.translation_service import TranslationService


DATABASE = Path(__file__).resolve().parents[2] / "main" / "assets" / "translated.db"


class BundledSemanticAliasTests(unittest.TestCase):
    def test_bundled_alias_dataset_adds_new_expressions(self) -> None:
        with sqlite3.connect(DATABASE) as connection:
            alias_count = connection.execute(
                "SELECT COUNT(DISTINCT alias) FROM dictionary_semantic_aliases"
            ).fetchone()[0]
            copied_explanation_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM dictionary_semantic_aliases AS alias
                WHERE EXISTS (
                    SELECT 1
                    FROM dictionary AS entry
                    WHERE TRIM(entry.explanation) = alias.alias
                )
                """
            ).fetchone()[0]
            metadata = dict(
                connection.execute(
                    "SELECT key, value FROM semantic_alias_metadata"
                ).fetchall()
            )

        self.assertGreaterEqual(alias_count, 100)
        self.assertEqual(copied_explanation_count, 0)
        self.assertEqual(metadata.get("dataset_kind"), "semantic_alias")
        self.assertEqual(int(metadata.get("alias_count", "0")), alias_count)

    def test_alias_dataset_excludes_reviewed_relation_errors(self) -> None:
        with sqlite3.connect(DATABASE) as connection:
            rows = connection.execute(
                """
                SELECT alias.alias, entry.explanation
                FROM dictionary_semantic_aliases AS alias
                JOIN dictionary AS entry ON entry.id = alias.sense_id
                """
            ).fetchall()
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

        unsafe_aliases = {"牙口", "睡着", "笑脸", "身形"}
        self.assertTrue(unsafe_aliases.isdisjoint(alias for alias, _ in rows))
        self.assertFalse(
            any(
                re.search(r"[（(][^()（）]*[\u3400-\u9fff][^()（）]*[）)]", explanation)
                for _, explanation in rows
            )
        )
        self.assertNotIn("dictionary_sense_expansions", tables)
        self.assertNotIn("semantic_expansion_metadata", tables)

    def test_natural_synonyms_have_a_visible_opt_in_effect(self) -> None:
        queries = [
            "飞起",
            "哀愁",
            "瞧见",
            "协助",
            "援助",
            "奔跑",
            "终止",
            "快速",
            "难过",
            "喜爱",
            "行走",
        ]
        service = TranslationService(
            str(DATABASE),
            enable_fallback_matching=False,
        )
        changed = 0
        semantic_hits = 0
        disabled_unknown = 0
        enabled_unknown = 0
        try:
            for query in queries:
                disabled = service.translate(
                    query,
                    "zh_to_alician",
                    use_semantic_expansions=False,
                )
                enabled = service.translate(
                    query,
                    "zh_to_alician",
                    use_semantic_expansions=True,
                )
                disabled_unknown += disabled["stats"]["unknown"]
                enabled_unknown += enabled["stats"]["unknown"]
                if disabled["result_text"] != enabled["result_text"]:
                    changed += 1
                if any(
                    token["method"] == "semantic_expansion"
                    for token in enabled["tokens"]
                ):
                    semantic_hits += 1
        finally:
            service.close()

        self.assertGreaterEqual(changed, 8)
        self.assertGreaterEqual(semantic_hits, 8)
        self.assertLess(enabled_unknown, disabled_unknown)

    def test_previous_false_positive_no_longer_maps_disgust_to_eating(self) -> None:
        service = TranslationService(
            str(DATABASE),
            enable_fallback_matching=False,
        )
        try:
            result = service.translate(
                "厌恶",
                "zh_to_alician",
                use_semantic_expansions=True,
            )
        finally:
            service.close()

        translated_targets = {
            token["target"]
            for token in result["tokens"]
            if token["status"] not in {"space", "punct", "unknown"}
        }
        self.assertNotIn("Gardis", translated_targets)


if __name__ == "__main__":
    unittest.main()
