from __future__ import annotations

import unittest
from pathlib import Path

from webui_backend.translation_service import TranslationService


DATABASE = Path(__file__).resolve().parents[2] / "main" / "assets" / "translated.db"


class ErhuaTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = TranslationService(
            str(DATABASE),
            enable_fallback_matching=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.service.close()

    def test_erhua_forms_reuse_the_exact_stem_entry(self) -> None:
        for stem in ("风", "鸟", "鱼", "猫", "树"):
            with self.subTest(stem=stem):
                base = self.service.translate(stem, "zh_to_alician")
                erhua = self.service.translate(f"{stem}儿", "zh_to_alician")
                self.assertEqual(erhua["result_text"], base["result_text"])
                self.assertEqual(erhua["stats"]["unknown"], 0)
                self.assertEqual(erhua["tokens"][0]["source"], f"{stem}儿")
                self.assertEqual(erhua["tokens"][0]["normalized_source"], stem)
                self.assertEqual(erhua["tokens"][0]["method"], "erhua_normalization")
                self.assertEqual(erhua["tokens"][0]["confidence"], 1.0)

    def test_multiple_erhua_words_are_recognized_inside_a_sentence(self) -> None:
        result = self.service.translate("风儿鸟儿", "zh_to_alician")
        normalized = [
            token.get("normalized_source")
            for token in result["tokens"]
            if token.get("method") == "erhua_normalization"
        ]
        self.assertEqual(normalized, ["风", "鸟"])
        self.assertEqual(result["stats"]["unknown"], 0)

    def test_lexicalized_er_words_are_not_truncated(self) -> None:
        for source in ("这儿", "那儿", "哪儿", "女儿", "孤儿", "一会儿"):
            with self.subTest(source=source):
                result = self.service.translate(source, "zh_to_alician")
                self.assertFalse(
                    any(
                        token.get("method", "").startswith("erhua_")
                        for token in result["tokens"]
                    )
                )


if __name__ == "__main__":
    unittest.main()
