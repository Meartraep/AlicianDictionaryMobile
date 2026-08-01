from __future__ import annotations

import unittest
from pathlib import Path

from webui_backend.translation_service import TranslationService


DATABASE = Path(__file__).resolve().parents[2] / "main" / "assets" / "translated.db"


class NaiNegationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = TranslationService(
            str(DATABASE),
            enable_fallback_matching=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.service.close()

    def test_compound_chinese_negations_are_recognized_before_lookup(self) -> None:
        cases = {
            "我不喜欢你": ["我", "不", "喜欢", "你"],
            "我无家可归": ["我", "无", "家可归"],
            "我非你不可": ["我", "非", "你", "不可"],
        }
        for source, expected_segments in cases.items():
            with self.subTest(source=source):
                self.assertEqual(
                    self.service._segment_chinese_run(source),
                    expected_segments,
                )
                result = self.service.translate(source, "zh_to_alician")
                nai_sources = [
                    token["source"]
                    for token in result["tokens"]
                    if token["target"].casefold() == "nai"
                ]
                self.assertTrue(nai_sources)

    def test_lexicalized_prefixes_are_not_mistaken_for_negation(self) -> None:
        for source in ("未来", "非常", "无论"):
            with self.subTest(source=source):
                segments = self.service._segment_chinese_run(source)
                self.assertEqual(segments, [source])

    def test_nai_never_leaks_dictionary_metadata_into_translation(self) -> None:
        for source in (
            "Nai",
            "Nai Aihel",
            "imm Kolto Xia Nai Dialoss",
            "Iequim Lef Kopiita Tordu Eist Naits o Nai Zel Note",
        ):
            with self.subTest(source=source):
                result = self.service.translate(source, "alician_to_zh")
                self.assertNotIn("表否定", result["result_text"])
                nai = [
                    token for token in result["tokens"]
                    if token["source"].casefold() == "nai"
                ]
                self.assertEqual(len(nai), 1)
                self.assertEqual(nai[0]["method"], "grammar_function")
                self.assertEqual(nai[0]["word_class"], "adv.")

    def test_nai_selects_idiomatic_contextual_negative_forms(self) -> None:
        expected_results = {
            "Nai Aihel": "没有",
            "Bis o Nai Hellm": "这不是梦",
            "Kulu Nai Harie": "不能记得",
            "Poet Nai Clooshe": "请别关闭",
            "Nai Drone": "不孤单的",
            "Ween Nai": "没有尽头",
            "Mii Nai Dist Crai Foul": "我绝不忘记你",
        }
        for source, expected in expected_results.items():
            with self.subTest(source=source):
                result = self.service.translate(source, "alician_to_zh")
                self.assertEqual(result["result_text"], expected)


if __name__ == "__main__":
    unittest.main()
