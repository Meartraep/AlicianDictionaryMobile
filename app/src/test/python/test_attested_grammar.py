from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from webui_backend.translation_service import TranslationService


DATABASE = Path(__file__).resolve().parents[2] / "main" / "assets" / "translated.db"


class AttestedGrammarTests(unittest.TestCase):
    """Regression tests for grammar explicitly attested by the bundled data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = TranslationService(
            str(DATABASE),
            enable_fallback_matching=False,
        )
        cls.connection = sqlite3.connect(DATABASE)
        cls.connection.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls) -> None:
        cls.service.close()
        cls.connection.close()

    def assertTranslation(self, source: str, direction: str, expected: str) -> None:
        result = self.service.translate(source, direction)
        self.assertEqual(result["result_text"], expected)
        self.assertEqual(result["stats"]["unknown"], 0)

    def assertNoMetadata(self, source: str) -> None:
        result = self.service.translate(source, "alician_to_zh")
        forbidden = (
            "引导名词性从句",
            "连接作用",
            "表并列",
            "无实义",
            "助动词",
            "用于过去",
            "常置于表示被动的动词后",
            "表示施事者",
            "不与o混用",
            "表祈使",
            "语气词",
            "后缀",
            "用在单数名词后",
        )
        leaked = [fragment for fragment in forbidden if fragment in result["result_text"]]
        self.assertEqual(leaked, [], result["result_text"])

    def test_nested_ou_possession_round_trips_in_head_marker_possessor_order(self) -> None:
        # Individual aligned examples establish head-ou-possessor (for
        # example "Disverry ou Crai" -> "你的魔法").  The nested case below
        # is the compositional consequence of that attested direction; the
        # corpus itself does not contain this exact synthetic chain.
        self.assertTranslation(
            "Ween ou Myte Hellm",
            "alician_to_zh",
            "我的梦的尽头",
        )
        self.assertTranslation(
            "我的梦的尽头",
            "zh_to_alician",
            "Ween ou Myte Hellm",
        )

    def test_qls_plural_supports_separate_and_productive_chinese_forms(self) -> None:
        # no_class explicitly says qls follows a singular noun to make it
        # plural and may also be written as a suffix.
        self.assertTranslation("Ene qls", "alician_to_zh", "人们")
        self.assertTranslation("Saray qls", "alician_to_zh", "朋友们")
        for chinese, compact_alician in (
            ("天使们", "Syeillaqls"),
            ("朋友们", "Sarayqls"),
        ):
            with self.subTest(chinese=chinese):
                result = self.service.translate(chinese, "zh_to_alician")
                self.assertEqual(
                    result["result_text"].replace(" ", "").casefold(),
                    compact_alician.casefold(),
                )
                self.assertEqual(result["stats"]["unknown"], 0)

    def test_lait_adverb_supports_separate_and_productive_chinese_forms(self) -> None:
        # no_class explicitly describes lait as an adjective-to-adverb suffix
        # which may be written separately.
        self.assertTranslation("Shelim lait", "alician_to_zh", "寂静地")
        result = self.service.translate("美好地", "zh_to_alician")
        self.assertEqual(
            result["result_text"].replace(" ", "").casefold(),
            "Moutlait".casefold(),
        )
        self.assertEqual(result["stats"]["unknown"], 0)

    def test_ol_and_ob_render_aspect_instead_of_dictionary_metadata(self) -> None:
        # The dictionary identifies ol as past/present-perfect and ob as
        # past-perfect.  Exact aligned row 3272 translates "Ollenes ob Inay"
        # as "我们已经等待了许久".
        cases = (
            ("Mii ol Harie Crai", ("已", "曾", "过", "了"), ("我", "记得", "你")),
            ("Ollenes ob Inay", ("已", "曾", "过", "了"), ("等待",)),
        )
        for source, aspect_markers, lexical_items in cases:
            with self.subTest(source=source):
                result = self.service.translate(source, "alician_to_zh")
                self.assertFalse(
                    any(fragment in result["result_text"] for fragment in ("助动词", "用于过去")),
                    result["result_text"],
                )
                self.assertTrue(
                    any(marker in result["result_text"] for marker in aspect_markers),
                    result["result_text"],
                )
                for item in lexical_items:
                    self.assertIn(item, result["result_text"])

    def test_dis_is_productive_preverbal_negation_when_separate_or_prefixed(self) -> None:
        # Dis has a noun homograph, but its second dictionary sense explicitly
        # marks preverbal negation and says it may be attached as a prefix.
        self.assertTranslation("Dis Harie", "alician_to_zh", "不记得")
        self.assertTranslation("Disharie", "alician_to_zh", "不记得")

    def test_phier_is_an_imperative_particle_not_a_metadata_label(self) -> None:
        self.assertTranslation("Phier Harie", "alician_to_zh", "请记得")

    def test_a_laiz_is_a_postverbal_future_construction_in_both_directions(self) -> None:
        # Laiz sense 2 explicitly records "动词+a Laiz变为将来时".
        self.assertTranslation(
            "Mii Dist a Laiz Crai",
            "alician_to_zh",
            "我将忘记你",
        )
        self.assertTranslation(
            "我将忘记你",
            "zh_to_alician",
            "Mii Dist a Laiz Crai",
        )

    def test_yien_verb_ord_agent_binds_the_passive_agent(self) -> None:
        # Yien marks a following passive verb; Ord is attested after that verb
        # to introduce its agent.
        self.assertTranslation(
            "Yien Harie Ord Mii",
            "alician_to_zh",
            "被我记得",
        )
        self.assertTranslation(
            "我被你记得",
            "zh_to_alician",
            "Mii Yien Harie Ord Crai",
        )

    def test_lqll_is_postposed_as_in_every_exact_aligned_example(self) -> None:
        rows = self.connection.execute(
            """
            SELECT alician_sentence
            FROM sentence_alignments
            WHERE alignment_status = 'aligned_exact'
              AND lower(alician_sentence) LIKE '% lqll'
            """
        ).fetchall()
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(
            all(str(row["alician_sentence"]).casefold().endswith(" lqll") for row in rows)
        )
        self.assertTranslation("Syeilla Lqll", "alician_to_zh", "像天使一样")
        self.assertTranslation("像天使一样", "zh_to_alician", "Syeilla Lqll")

    def test_end_a_and_en_never_leak_metalinguistic_glosses(self) -> None:
        # These are high-frequency structural words.  Their dictionary notes
        # describe functions; those notes are not natural-language output.
        for source in (
            "Mii end Crai",
            "Mii a Crai",
            "Mii en Crai",
            "Mii iy Crai",
            "Mii sii",
            "Mii sip",
            "Mii Ta",
        ):
            with self.subTest(source=source):
                self.assertNoMetadata(source)

    def test_repeated_line_from_one_song_cannot_establish_a_sentence_pattern(self) -> None:
        # "Brait Xia Eist" occurs twice in one song and is translated as
        # "那扇大门，要打开吗？".  It is one repeated V-(demonstrative)-N
        # example, not two independent attestations of a generic V-N-N order.
        rows = self.connection.execute(
            """
            SELECT song_title, alician_sentence, chinese_translation
            FROM sentence_alignments
            WHERE alignment_status = 'aligned_exact'
              AND lower(alician_sentence) = lower('Brait Xia Eist')
            """
        ).fetchall()
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(len({row["song_title"] for row in rows}), 1)
        self.assertEqual(len({row["alician_sentence"].casefold() for row in rows}), 1)
        self.assertEqual(
            {row["chinese_translation"] for row in rows},
            {"那扇大门，要打开吗？"},
        )

        self.assertIsNone(self.service._dominant_sentence_pattern(["n", "v", "n"]))
        result = self.service.translate("朋友看月亮", "zh_to_alician")
        self.assertFalse(
            any(
                token.get("order_method") == "database_sentence_pattern"
                for token in result["tokens"]
            )
        )

    def test_pos_statistics_never_swap_semantic_subject_and_object(self) -> None:
        # Aligned row 3640 is Shelista Skelat Mii -> “世界总是嘲笑我”.
        # POS signatures alone cannot reinterpret the pronoun as subject.
        self.assertTranslation(
            "世界嘲笑我", "zh_to_alician", "Shelista Skelat Mii",
        )
        self.assertTranslation(
            "朋友看我", "zh_to_alician", "Saray Pleesa Mii",
        )

    def test_adjectival_de_is_not_misparsed_as_nominal_possession(self) -> None:
        self.assertTranslation("美好的梦", "zh_to_alician", "Mout Hellm")
        result = self.service.translate("闪耀的天使", "zh_to_alician")
        self.assertEqual(
            sum(token.get("target") == "Eclat" for token in result["tokens"]),
            1,
            result["result_text"],
        )

    def test_complete_chinese_relative_clause_moves_before_head_and_keeps_passive(self) -> None:
        self.assertTranslation(
            "我记得的天使",
            "zh_to_alician",
            "Syeilla end Mii Harie",
        )
        self.assertTranslation(
            "被我记得的人",
            "zh_to_alician",
            "Ene end Yien Harie Ord Mii",
        )

    def test_closed_possessive_adjectives_win_before_generic_ou(self) -> None:
        # The aligned corpus repeatedly uses Myte/Crait directly before a
        # noun; these established possessive adjectives are more specific
        # than the productive nominal ou construction.
        self.assertTranslation("Myte Herz", "alician_to_zh", "我的心")
        self.assertTranslation("我的心", "zh_to_alician", "Myte Herz")
        self.assertTranslation("你的梦", "zh_to_alician", "Crait Hellm")

    def test_s_suffix_is_an_attested_plural_variant(self) -> None:
        # Syeilla has both -s and -qls plural forms in the bundled corpus.
        self.assertTranslation("Syeillas", "alician_to_zh", "天使们")

    def test_lend_introduces_a_yes_no_question(self) -> None:
        # Exact aligned row 3166 is "Lend Cloud Skeem Gete Liumd" ->
        # "是否开始新游戏？"; Chinese may retain or elide the explicit 你.
        result = self.service.translate(
            "Lend Cloud Skeem Gete Liumd",
            "alician_to_zh",
        )
        self.assertIn(
            result["result_text"],
            {"是否开始新游戏", "你是否开始新游戏", "你是否开始新的游戏"},
        )
        self.assertEqual(result["stats"]["unknown"], 0)

    def test_ra_is_a_clausal_marker_not_an_unknown_surface_word(self) -> None:
        # In 19 independent annotated lines Ra is explicitly glossed as an
        # object-clause introducer.  Row 3013 supplies this complete example.
        result = self.service.translate(
            "Mii Velaiye Ra Miis Prifiel Klar",
            "alician_to_zh",
        )
        ra = next(token for token in result["tokens"] if token.get("source") == "Ra")
        self.assertNotEqual(ra.get("status"), "unknown")
        self.assertNotIn("〔Ra〕", result["result_text"])
        self.assertNotIn("引导宾语从句", result["result_text"])
        self.assertLess(result["result_text"].index("认为"), result["result_text"].index("我自己"))
        self.assertLess(result["result_text"].index("我自己"), result["result_text"].index("理解"))

    def test_iequim_lef_is_an_attested_similative_construction(self) -> None:
        # Iequim is absent from the main dictionary, but 13 annotations across
        # seven songs consistently say it combines with Lef/Lefz as 像/仿佛.
        result = self.service.translate("Iequim Lef Mono", "alician_to_zh")
        marker = next(
            token for token in result["tokens"]
            if token.get("source", "").casefold() == "iequim"
        )
        self.assertNotEqual(marker.get("status"), "unknown")
        self.assertNotIn("〔Iequim〕", result["result_text"])
        self.assertTrue(
            any(value in result["result_text"] for value in ("像", "仿佛")),
            result["result_text"],
        )
        self.assertIn("无色", result["result_text"])

    def test_lefz_is_a_conservative_alias_of_lef(self) -> None:
        result = self.service.translate("Iequim Lefz Mono", "alician_to_zh")
        alias = next(
            token for token in result["tokens"]
            if token.get("source", "").casefold() == "lefz"
        )
        self.assertEqual(alias.get("normalized_source"), "Lef")
        self.assertEqual(alias.get("method"), "attested_transcription_alias")
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertTrue(
            any(value in result["result_text"] for value in ("像", "仿佛")),
            result["result_text"],
        )
        self.assertIn("无色", result["result_text"])

    def test_imperative_markers_scope_over_the_complete_clause(self) -> None:
        result = self.service.translate(
            "Yiela Brait Tri Ran qls", "alician_to_zh",
        )
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertTrue(result["result_text"].endswith("吧"), result["result_text"])
        self.assertLess(result["result_text"].index("三"), result["result_text"].rindex("吧"))
        self.assertLess(result["result_text"].index("眼睛"), result["result_text"].rindex("吧"))

        combined = self.service.translate(
            "Yiep Seek Ra Mizy ol Ignai Phier", "alician_to_zh",
        )
        self.assertEqual(combined["stats"]["unknown"], 0)
        self.assertEqual(combined["result_text"].count("请"), 1, combined["result_text"])
        self.assertEqual(combined["result_text"].count("吧"), 1, combined["result_text"])
        self.assertTrue(combined["result_text"].endswith("吧"), combined["result_text"])
        self.assertNotIn("表祈使", combined["result_text"])

        explicit_subject = self.service.translate(
            "Yiela Mill Arm Selaf Fiqqlait", "alician_to_zh",
        )
        self.assertTrue(explicit_subject["result_text"].startswith("让我们"), explicit_subject["result_text"])
        mill = next(token for token in explicit_subject["tokens"] if token["source"] == "Mill")
        self.assertEqual(mill["word_class"], "pron.")

    def test_phim_is_a_deontic_modal_not_an_empty_particle(self) -> None:
        result = self.service.translate("Phim Felia", "alician_to_zh")
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertIn("应该", result["result_text"])
        self.assertIn("忍耐", result["result_text"])
        self.assertNotIn("表祈使", result["result_text"])

    def test_ord_instrument_moves_before_the_predicate(self) -> None:
        self.assertTranslation(
            "Poutie Mii Clooshe Eist Ord Ail Entic",
            "alician_to_zh",
            "当我用全部的力气关闭门",
        )
        self.assertTranslation(
            "Poutie Mii Clooshe Eist Ord",
            "alician_to_zh",
            "当我关闭门",
        )

    def test_real_relative_clause_selects_the_verbal_passive_sense(self) -> None:
        self.assertTranslation(
            "Flea end ol Yien Amiy Ord Lusia",
            "alician_to_zh",
            "已被光茫爱的人",
        )
        extended = self.service.translate(
            "Flea end ol Yien Amiy Ord Lusia Rie Vell Amiy Lusia",
            "alician_to_zh",
        )["result_text"]
        self.assertIn("已被光茫爱的人", extended)
        self.assertNotIn("光茫不久爱", extended)

    def test_poutie_uses_attested_local_clause_readings(self) -> None:
        cases = {
            "Poutie Mii Clooshe Eist Ord": "当",
            "Poutie Albel Bisoli Crai Vell Idem Pils Wei": "如果",
            "Poutie Ani Emsa Trane Eala": "随着",
            "Zia ol iy Brey Poutie noa Rinasia": "正如",
        }
        for source, marker in cases.items():
            with self.subTest(source=source):
                result = self.service.translate(source, "alician_to_zh")
                self.assertIn(marker, result["result_text"])
                self.assertNotIn("后加名词", result["result_text"])

    def test_negative_passive_accepts_both_attested_marker_orders(self) -> None:
        self.assertTranslation("Herz Nai Yien Amiy", "alician_to_zh", "心不被爱")
        self.assertTranslation("Yien Nai Amiy", "alician_to_zh", "不被爱")
        nominal = self.service.translate("Nai Hellm", "alician_to_zh")
        self.assertNotIn("不梦", nominal["result_text"])
        hellm = next(token for token in nominal["tokens"] if token["source"] == "Hellm")
        self.assertNotEqual(hellm.get("contextual_word_class"), "v.")

    def test_nai_ou_forms_an_absence_attributive_not_a_possessive(self) -> None:
        self.assertTranslation(
            "Nai ou Finz Hait", "alician_to_zh", "无结局的自由",
        )

    def test_known_light_particles_do_not_become_unknown_or_metadata(self) -> None:
        for source, retained in (
            ("Iqyur Shellius", "神明"),
            ("Mii Dou", "我"),
            ("Mii weiy", "我"),
        ):
            with self.subTest(source=source):
                result = self.service.translate(source, "alician_to_zh")
                self.assertEqual(result["result_text"], retained)
                self.assertEqual(result["stats"]["unknown"], 0)
                self.assertNotIn("提示一个动作", result["result_text"])

    def test_qleea_uses_local_aspect_mood_and_clause_context(self) -> None:
        completed = self.service.translate(
            "Zia ol Qleea Womphil Anys Biziq Foul",
            "alician_to_zh",
        )["result_text"]
        self.assertTrue(completed.startswith("我一定已经"), completed)
        self.assertNotIn("将会", completed)

        self.assertTranslation(
            "Yiep Qleea Tigilijk Falke",
            "alician_to_zh",
            "请快崩塌吧",
        )
        self.assertTranslation(
            "Quim Qleea Miz Elza",
            "alician_to_zh",
            "假如即将变成羽翼",
        )
        self.assertTranslation(
            "Imeila Zia Qleea Verse",
            "alician_to_zh",
            "即使我消失",
        )
        duplicate_future = self.service.translate(
            "Poutie Xia Ran Clooshe a Toubi Crai Vell Qleea osa Miz Volp",
            "alician_to_zh",
        )["result_text"]
        self.assertLessEqual(duplicate_future.count("将会"), 1, duplicate_future)
        self.assertTranslation(
            "Fevla Crai Qleea Endekta Bai",
            "alician_to_zh",
            "你为什么不承认",
        )
        self.assertTranslation(
            "Mii ol Eclat a Crai Qleea Verse",
            "alician_to_zh",
            "我已闪耀并你将会消失",
        )
        self.assertTranslation(
            "Yiep Eclat a Crai Qleea Verse",
            "alician_to_zh",
            "请闪耀吧并你将会消失",
        )

    def test_function_word_resolution_does_not_cross_coordinated_clauses(self) -> None:
        self.assertTranslation(
            "Mii Nai Eclat a Crai Foul Verse",
            "alician_to_zh",
            "我不闪耀并你一定消失",
        )
        self.assertTranslation(
            "Mii Aihel a Crai imm Hellm",
            "alician_to_zh",
            "我有并你在梦",
        )
        poutie = self.service.translate(
            "Mii Brey a Poutie Crai Eclat", "alician_to_zh",
        )["result_text"]
        self.assertNotIn("正如", poutie)

    def test_attested_locative_and_focus_markers_take_chinese_positions(self) -> None:
        self.assertTranslation("Hait Aihel imm Bis", "alician_to_zh", "自由在这")
        self.assertTranslation(
            "Yuwlpie Aihel Mols imm Brai ou Millte Herz",
            "alician_to_zh",
            "乌托邦只在我们的心的中央",
        )
        self.assertTranslation(
            "Shelista Skelat Mii Baly",
            "alician_to_zh",
            "世界总是嘲笑我",
        )
        self.assertTranslation("Mii Verse osa", "alician_to_zh", "我也消失")
        self.assertTranslation("Qllsiim Og Amiy", "alician_to_zh", "我们彼此爱")

        unresolved_og = self.service.translate(
            "Kleet Kleet Kleet Og Perte", "alician_to_zh",
        )
        self.assertNotIn("彼此", unresolved_og["result_text"])
        og = next(token for token in unresolved_og["tokens"] if token["source"] == "Og")
        self.assertEqual(og["status"], "unknown")

        reciprocal = self.service.translate("我们彼此相爱", "zh_to_alician")
        self.assertTrue(reciprocal["result_text"].endswith("Og Amiy"), reciprocal["result_text"])
        self.assertEqual(reciprocal["stats"]["unknown"], 0)

    def test_numbers_do_not_break_syntax_and_chinese_punctuation_is_normalized(self) -> None:
        self.assertTranslation("Mii 3 Ran qls!", "alician_to_zh", "我3眼睛！")
        self.assertTranslation(
            "Lend Crai Awlst?", "alician_to_zh", "你是否做好准备？",
        )
        quoted = self.service.translate("“Lend Crai Awlst?”", "alician_to_zh")
        self.assertEqual(quoted["result_text"], "“你是否做好准备？”")
        self.assertTranslation("Mii Eclat.", "alician_to_zh", "我闪耀。")
        self.assertTranslation("Mii Eclat...", "alician_to_zh", "我闪耀……")

    def test_the_attested_three_eye_classifier_phrase_round_trips(self) -> None:
        result = self.service.translate(
            "请睁开三只眼睛吧！", "zh_to_alician",
        )
        self.assertEqual(result["result_text"], "Yiep Brait Tri Ran qls！")
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertTranslation(
            "Tri Ran qls", "alician_to_zh", "三只眼睛",
        )
        self.assertTranslation(
            "Yiela Brait Tri Ran qls",
            "alician_to_zh",
            "来睁开三只眼睛吧",
        )

    def test_alice_is_a_two_song_attested_proper_name(self) -> None:
        self.assertTranslation("Alice", "alician_to_zh", "爱丽丝")
        self.assertTranslation("爱丽丝", "zh_to_alician", "Alice")

    def test_o_and_iy_distinguish_copula_from_topic_boundary(self) -> None:
        self.assertTranslation(
            "Bis Shelista o Hellm", "alician_to_zh", "这世界是梦",
        )
        self.assertTranslation("Bis o Nai Hellm", "alician_to_zh", "这不是梦")

        adjectival = self.service.translate(
            "Xia iy Kysei Tepistl Wei", "alician_to_zh",
        )
        self.assertIn("是", adjectival["result_text"])
        self.assertNotIn("不与o混用", adjectival["result_text"])

        topic = self.service.translate(
            "Ail ou Vigyte Aihel iy Ueyzij", "alician_to_zh",
        )
        iy = next(token for token in topic["tokens"] if token["source"].casefold() == "iy")
        self.assertTrue(iy.get("omit_from_result"), topic["result_text"])
        self.assertEqual(iy.get("copula_resolution"), "topic_boundary")
        self.assertTranslation(
            "Mii iy Syeilla a Crai Eclat",
            "alician_to_zh",
            "我是天使和你闪耀",
        )

    def test_editorial_uncertainty_stays_in_evidence_not_surface_text(self) -> None:
        result = self.service.translate("Iequim Lefz Mono", "alician_to_zh")
        self.assertNotIn("(?)", result["result_text"])
        mono = next(
            token for token in result["tokens"]
            if token.get("source", "").casefold() == "mono"
        )
        self.assertIn("(?)", mono["explanation"])

    def test_surface_gloss_removes_labels_but_keeps_semantic_supplements(self) -> None:
        expected = {
            "Sar": "随着",
            "Meila": "更深地",
            "Craill": "你",
            "Xlleidies": "幽灵",
            "Zel": "没有任何事物",
            "Saut": "声音",
            "Staps": "拍手",
            "Sigik": "移开目光",
        }
        for source, target in expected.items():
            with self.subTest(source=source):
                self.assertTranslation(source, "alician_to_zh", target)
        self.assertTranslation("Mii endil Crai", "alician_to_zh", "我你")

    def test_all_exact_aligned_sentences_hide_grammar_metadata(self) -> None:
        rows = self.connection.execute(
            """
            SELECT rowid, alician_sentence
            FROM sentence_alignments
            WHERE alignment_status = 'aligned_exact'
            """
        ).fetchall()
        self.assertGreaterEqual(len(rows), 1000)
        forbidden = (
            "引导名词性从句",
            "引导宾语从句",
            "连接作用",
            "表并列",
            "无实义",
            "助动词",
            "用于过去",
            "常置于表示被动的动词后",
            "表示施事者",
            "不与o混用",
            "表祈使",
            "语气词",
            "用在单数名词后",
            "提示一个动作的结果",
            "后加名词",
            "(程度)",
            "贱称",
            "(pl",
            "引导地点状语从句",
            "疑为",
            "好像是arcaea",
            "在动词后",
            "(?)",
            "...",
            "……",
        )
        leaks = []
        for row in rows:
            result = self.service.translate(
                row["alician_sentence"], "alician_to_zh",
            )["result_text"]
            leaked = [fragment for fragment in forbidden if fragment in result]
            if leaked:
                leaks.append((row["rowid"], row["alician_sentence"], result, leaked))
        self.assertEqual(leaks, [])

    def test_attested_slot_words_do_not_leak_literal_ellipsis(self) -> None:
        self.assertTranslation(
            "Tollm Arch Fenklu", "alician_to_zh", "流在脸庞上",
        )
        possessive_location = self.service.translate(
            "Arla Insloadiviqls Lanskeem Arch Zyte Lipiq",
            "alician_to_zh",
        )["result_text"]
        self.assertIn("在我的皮上", possessive_location)
        self.assertNotIn("...", possessive_location)
        self.assertNotIn("……", possessive_location)

        for source in (
            "Olm Sarga Oulayz Eist Frait folme Bis",
            "Tozlom Di Allssqls ol Brait",
            "Zeit Poetolt Peil Imiylt Swinia",
        ):
            with self.subTest(source=source):
                result = self.service.translate(source, "alician_to_zh")
                self.assertNotIn("...", result["result_text"])
                self.assertNotIn("……", result["result_text"])
        self.assertTranslation(
            "Olzy Kerla forle Sai Elay",
            "alician_to_zh",
            "必须逃离在清晨到来之前",
        )
        winde = self.service.translate(
            "Erikes Kull Efitu Ail winde Sartain", "alician_to_zh",
        )
        self.assertEqual(winde["stats"]["unknown"], 0)
        self.assertIn("之前", winde["result_text"])
        unresolved = self.service.translate("Heilim", "alician_to_zh")
        self.assertEqual(unresolved["stats"]["unknown"], 1)
        self.assertEqual(unresolved["tokens"][0]["status"], "unknown")

    def test_crain_is_a_sentence_final_rhetorical_question_particle(self) -> None:
        # Both aligned Crain examples are sentence-final and annotated
        # "表反问，不是吗？".
        result = self.service.translate("Heip Crain", "alician_to_zh")
        self.assertNotIn("〔Crain〕", result["result_text"])
        self.assertTrue(result["result_text"].endswith("不是吗？"), result["result_text"])

    def test_exact_lexicalized_negation_terms_win_before_productive_nai(self) -> None:
        # Both complete Chinese forms are exact dictionary terms; productive
        # character-level negation must not split them first.
        self.assertTranslation("不自然地", "zh_to_alician", "Fouzanoalait")
        self.assertTranslation("不得不", "zh_to_alician", "Oudiq")


if __name__ == "__main__":
    unittest.main()
