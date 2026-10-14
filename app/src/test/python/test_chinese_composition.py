from __future__ import annotations

import unittest
from pathlib import Path

from webui_backend.translation_service import TranslationService


DATABASE = Path(__file__).resolve().parents[2] / "main" / "assets" / "translated.db"


class ChineseCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = TranslationService(
            str(DATABASE),
            enable_fallback_matching=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.service.close()

    def test_function_particles_are_neutralized_instead_of_unknown(self) -> None:
        # 吧 has no lexical entry; without the particle layer it used to leak
        # as “〔吧〕” and forced users to delete it from natural sentences.
        result = self.service.translate("大海吧", "zh_to_alician")
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertEqual(result["result_text"], "Oul Meele")
        particle = next(
            token for token in result["tokens"] if token["source"] == "吧"
        )
        self.assertEqual(particle["method"], "chinese_function_particle")
        self.assertTrue(particle.get("omit_from_result"))
        self.assertNotIn("吧", result["result_text"])

    def test_aspect_particle_is_dropped_without_breaking_the_clause(self) -> None:
        result = self.service.translate("花开了", "zh_to_alician")
        particle = next(
            token for token in result["tokens"] if token["source"] == "了"
        )
        self.assertEqual(particle["method"], "chinese_function_particle")
        self.assertTrue(particle.get("omit_from_result"))
        # 花开 itself is still out of dictionary, so only the particle is
        # resolved; the genuinely unmatched word must stay visible.
        self.assertEqual(result["stats"]["unknown"], 1)

    def test_attested_coordinator_particle_reuses_the_alician_conjunction(self) -> None:
        result = self.service.translate("月亮与太阳", "zh_to_alician")
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertEqual(result["result_text"], "Minelia a Sail")

    def test_compound_is_split_into_known_morphemes(self) -> None:
        # 海水 is not a dictionary term although 海 and 水 both are.
        result = self.service.translate("海水", "zh_to_alician")
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertEqual(len(result["tokens"]), 2)
        self.assertEqual(
            [token["source"] for token in result["tokens"]],
            ["海", "水"],
        )
        for token in result["tokens"]:
            self.assertEqual(token["status"], "approximate")
            self.assertEqual(token["method"], "compound_decomposition")
            self.assertEqual(token["compound_source"], "海水")
        self.assertIn("海水", result["tokens"][0]["note"])

    def test_adjective_modifier_compound_keeps_chinese_order(self) -> None:
        result = self.service.translate("高山", "zh_to_alician")
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertEqual(
            [(token["source"], token["target"]) for token in result["tokens"]],
            [("高", "Gent"), ("山", "Berte")],
        )

    def test_non_compositional_words_are_not_guessed(self) -> None:
        for source in ("东西", "上海", "小说"):
            with self.subTest(source=source):
                result = self.service.translate(source, "zh_to_alician")
                self.assertEqual(result["stats"]["unknown"], 1)
                self.assertFalse(
                    any(
                        token["method"] == "compound_decomposition"
                        for token in result["tokens"]
                    )
                )

    def test_exact_entries_and_morphology_still_win_over_composition(self) -> None:
        erhua = self.service.translate("风儿", "zh_to_alician")
        self.assertEqual(erhua["tokens"][0]["method"], "erhua_normalization")
        lexicalized = self.service.translate("不得不", "zh_to_alician")
        self.assertEqual(lexicalized["tokens"][0]["method"], "dictionary_term")

    def test_composition_can_be_disabled(self) -> None:
        service = TranslationService(
            str(DATABASE),
            enable_fallback_matching=False,
            enable_composition=False,
        )
        try:
            result = service.translate("海水", "zh_to_alician")
        finally:
            service.close()
        self.assertEqual(result["stats"]["unknown"], 1)
        self.assertEqual(result["result_text"], "〔海水〕")


if __name__ == "__main__":
    unittest.main()
