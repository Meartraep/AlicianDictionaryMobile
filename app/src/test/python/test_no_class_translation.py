from __future__ import annotations

import unittest
from pathlib import Path

from webui_backend.translation_service import TranslationService


DATABASE = Path(__file__).resolve().parents[2] / "main" / "assets" / "translated.db"


class NoClassTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = TranslationService(
            str(DATABASE),
            enable_fallback_matching=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.service.close()

    def test_sentence_templates_bind_arguments_in_both_directions(self) -> None:
        cases = (
            ("Yiela Eclat", "alician_to_zh", "来闪耀吧"),
            ("Yiep Eclat", "alician_to_zh", "请闪耀吧"),
            ("Syeilla Lqll", "alician_to_zh", "像天使一样"),
            ("来闪耀吧", "zh_to_alician", "Yiela Eclat"),
            ("请闪耀吧", "zh_to_alician", "Yiep Eclat"),
            ("像天使一样", "zh_to_alician", "Syeilla Lqll"),
            ("我来闪耀吧", "zh_to_alician", "Mii Yiela Eclat"),
            ("我像天使一样", "zh_to_alician", "Mii Syeilla Lqll"),
        )
        for source, direction, expected in cases:
            with self.subTest(source=source, direction=direction):
                result = self.service.translate(source, direction)
                self.assertEqual(result["result_text"], expected)
                self.assertEqual(result["stats"]["unknown"], 0)
                if direction == "zh_to_alician":
                    template = next(
                        token
                        for token in result["tokens"]
                        if token.get("method") == "sentence_template"
                    )
                    self.assertEqual(len(template.get("template_arguments") or []), 1)

    def test_fragmented_words_are_recomposed_before_dictionary_lookup(self) -> None:
        cases = {
            "E clat": ("Eclat", "闪耀", "fragment_recomposition"),
            "Sye illa": ("Syeilla", "天使", "fragment_recomposition"),
            "Loo taria": ("Lootaria", "永恒", "fragment_recomposition"),
            "Loo talia": ("Lootaria", "永恒", "fragment_recomposition_variant"),
        }
        for source, (normalized, expected, method) in cases.items():
            with self.subTest(source=source):
                result = self.service.translate(source, "alician_to_zh")
                self.assertEqual(result["result_text"], expected)
                self.assertEqual(len(result["tokens"]), 1)
                self.assertEqual(result["tokens"][0]["normalized_source"], normalized)
                self.assertEqual(result["tokens"][0]["method"], method)

    def test_standalone_fragments_use_parent_meaning_without_leaking_metadata(self) -> None:
        cases = {
            "clat": ("Eclat", "闪耀"),
            "illa": ("Syeilla", "天使"),
            "taria": ("Lootaria", "永恒"),
        }
        for source, (parent, expected) in cases.items():
            with self.subTest(source=source):
                result = self.service.translate(source, "alician_to_zh")
                self.assertEqual(result["result_text"], expected)
                self.assertNotIn("的一部分", result["result_text"])
                token = result["tokens"][0]
                self.assertEqual(token["status"], "approximate")
                self.assertEqual(token["method"], "fragment_reference")
                self.assertEqual(token["fragment_parent"], parent)

    def test_ambiguous_and_unknown_no_class_rows_remain_explicitly_unresolved(self) -> None:
        ambiguous = self.service.translate("e", "alician_to_zh")
        self.assertEqual(ambiguous["stats"]["unknown"], 1)
        self.assertEqual(ambiguous["tokens"][0]["method"], "ambiguous_fragment")
        self.assertNotIn("(?)", ambiguous["result_text"])

        unresolved = self.service.translate("ei", "alician_to_zh")
        self.assertEqual(unresolved["stats"]["unknown"], 1)
        self.assertEqual(unresolved["tokens"][0]["method"], "no_class_unresolved")
        self.assertNotIn("(?)", unresolved["result_text"])

    def test_passive_marker_and_alias_bind_to_the_following_predicate(self) -> None:
        direct = self.service.translate("Yien Eclat", "alician_to_zh")
        alias = self.service.translate("Yiend Eclat", "alician_to_zh")
        reverse = self.service.translate("我被闪耀", "zh_to_alician")

        self.assertEqual(direct["result_text"], "被闪耀")
        self.assertEqual(direct["tokens"][0]["syntax_role"], "passive_marker")
        self.assertEqual(alias["result_text"], "被闪耀")
        self.assertEqual(alias["tokens"][0]["normalized_source"], "Yien")
        self.assertEqual(reverse["result_text"], "Mii Yien Eclat")
        self.assertEqual(reverse["stats"]["unknown"], 0)


if __name__ == "__main__":
    unittest.main()
