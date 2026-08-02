from __future__ import annotations

import logging
import math
import re
import sqlite3
from collections import Counter, defaultdict
from typing import Any, Counter as CounterType, DefaultDict, Dict, List, Optional, Tuple

from webui_backend.dictionary_service import _lev_ratio
from webui_backend.translation_common import (
    _ALICIAN_PART_RE,
    _CHINESE_FALLBACK_BOUNDARIES,
    _CHINESE_LEXICALIZED_NEGATION_PREFIXES,
    _CHINESE_NEGATION_FORMS,
    _CHINESE_NON_ERHUA_WORDS,
    _CHINESE_PART_RE,
    _CJK_RE,
    _CJK_RUN_RE,
    _NO_CLASS_ALIAS_RE,
    _POS_RE,
    _TEMPLATE_SLOT_RE,
    _WORD_FRAGMENT_PARENT_RE,
    _as_int,
)


class AlicianSyntaxMixin:
    """Select Alician senses and reorder clauses for Chinese output."""

    @staticmethod
    def _pos_family(word_class: str) -> str:
        value = str(word_class or "").strip().lower().rstrip(".")
        return "v" if value in {"vi", "vt"} else (value or "unknown")

    @classmethod

    def _pos_transition_score(cls, left: str, right: str) -> float:
        left, right = cls._pos_family(left), cls._pos_family(right)
        preferred = {
            ("art", "n"): 1.5, ("art", "adj"): 1.2,
            ("pron", "v"): 1.4, ("n", "v"): 1.25,
            ("adj", "n"): 1.45, ("adv", "v"): 1.15,
            ("adv", "adj"): 1.0, ("v", "n"): 1.15,
            ("v", "pron"): 1.0, ("v", "adv"): 0.65,
            ("prep", "n"): 1.35, ("prep", "pron"): 1.25,
            ("num", "n"): 1.3, ("conj", "pron"): 0.7,
            ("conj", "n"): 0.7, ("conj", "v"): 0.55,
        }
        discouraged = {
            ("art", "v"), ("art", "adv"), ("prep", "v"),
            ("adj", "v"), ("pron", "pron"), ("num", "v"),
        }
        if (left, right) in preferred:
            return preferred[(left, right)]
        if (left, right) in discouraged:
            return -0.8
        if "unknown" in {left, right}:
            return 0.0
        return -0.05

    def _sense_base_score(self, entry: Dict[str, Any]) -> float:
        order = max(1, int(entry.get("sense_order") or 1))
        frequency = math.log1p(max(0, entry.get("count", 0))) * 0.02
        return frequency - (order - 1) * 0.18

    def _select_contextual_senses(self, parts: List[str]) -> Dict[int, Dict[str, Any]]:
        """Choose one sense per recognized word using sentence-level POS scoring."""
        selected: Dict[int, Dict[str, Any]] = {}
        segment: List[Tuple[int, List[Dict[str, Any]]]] = []

        def solve() -> None:
            if not segment:
                return
            scores: List[List[float]] = []
            back: List[List[int]] = []
            for position, (_, candidates) in enumerate(segment):
                row_scores: List[float] = []
                row_back: List[int] = []
                for candidate in candidates:
                    base = self._sense_base_score(candidate)
                    if position == 0:
                        row_scores.append(base)
                        row_back.append(-1)
                        continue
                    previous_candidates = segment[position - 1][1]
                    options = [
                        scores[position - 1][j] + self._pos_transition_score(
                            "adv." if previous["target"].casefold() == "nai" else previous["word_class"],
                            "adv." if candidate["target"].casefold() == "nai" else candidate["word_class"],
                        )
                        for j, previous in enumerate(previous_candidates)
                    ]
                    best_index = max(range(len(options)), key=options.__getitem__)
                    row_scores.append(base + options[best_index])
                    row_back.append(best_index)
                scores.append(row_scores)
                back.append(row_back)
            candidate_index = max(range(len(scores[-1])), key=scores[-1].__getitem__)
            for position in range(len(segment) - 1, -1, -1):
                part_index, candidates = segment[position]
                selected[part_index] = candidates[candidate_index]
                candidate_index = back[position][candidate_index]
            segment.clear()

        for index, part in enumerate(parts):
            if part.isspace():
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", part):
                solve()
                continue
            candidates = self._word_by_lower.get(part.lower()) or []
            if candidates:
                segment.append((index, candidates))
            else:
                solve()
        solve()
        return selected

    def _find_similar_alician_word(self, word: str) -> Tuple[Optional[Dict[str, Any]], float]:
        best_entry = None
        best_score = 0.0
        query = str(word or "").lower()
        if not query:
            return None, 0.0
        for entry in self._word_entries:
            if (
                entry.get("fragment_parents")
                or entry.get("no_class_unknown")
            ):
                continue
            score = _lev_ratio(query, entry["target"].lower())
            if score > best_score:
                best_score = score
                best_entry = entry
        if best_entry and best_score >= 0.72:
            return best_entry, best_score
        return None, 0.0

    @staticmethod

    def _is_nominal_family(family: str) -> bool:
        return family in {"n", "pron"}

    def _syntax_family(self, token: Dict[str, Any]) -> str:
        source = str(token.get("source") or "").lower()
        if source in {"laiz", "nai"}:
            return "adv"
        if str(token.get("target") or "") == "一定":
            return "adv"
        return self._pos_family(str(token.get("word_class") or ""))

    def _reorder_alician_possessives(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert head-ou-possessor chains to Chinese possessor-的-head."""
        arranged = list(tokens)
        index = 0
        group = 0
        while index + 2 < len(arranged):
            if (
                index + 3 < len(arranged)
                and arranged[index + 1].get("syntax_role") == "possessive_marker"
                and self._syntax_family(arranged[index + 2]) == "adj"
                and self._is_nominal_family(self._syntax_family(arranged[index + 3]))
            ):
                group += 1
                marker = arranged[index + 1]
                marker.update({
                    "resolved_target": "的",
                    "explanation": "领属标记",
                    "possessive_group": group,
                    "omit_from_result": False,
                    "parse_method": "attested_possessive_grammar",
                })
                possessor = [arranged[index + 2], arranged[index + 3]]
                for token in possessor + [arranged[index]]:
                    token["possessive_group"] = group
                arranged[index:index + 4] = [
                    *possessor, marker, arranged[index],
                ]
                index += 4
                continue
            operands = [index]
            markers: List[int] = []
            cursor = index + 1
            while cursor + 1 < len(arranged):
                marker = arranged[cursor]
                if marker.get("syntax_role") != "possessive_marker":
                    break
                markers.append(cursor)
                operands.append(cursor + 1)
                cursor += 2
            if not markers:
                index += 1
                continue
            group += 1
            replacement: List[Dict[str, Any]] = []
            reversed_operands = [arranged[position] for position in reversed(operands)]
            marker_tokens = [arranged[position] for position in reversed(markers)]
            for offset, operand in enumerate(reversed_operands):
                operand["possessive_group"] = group
                replacement.append(operand)
                if offset < len(marker_tokens):
                    marker = marker_tokens[offset]
                    marker.update({
                        "resolved_target": "的",
                        "explanation": "领属标记",
                        "possessive_group": group,
                        "omit_from_result": False,
                        "parse_method": "attested_possessive_grammar",
                    })
                    replacement.append(marker)
            arranged[index:cursor] = replacement
            index += len(replacement)
        return arranged

    def _resolve_alician_absence_attributive(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert Nai ou N + head into the attested Chinese 无 N 的 head."""
        arranged = list(tokens)
        index = 0
        while index + 3 < len(arranged):
            negation, marker, absent, head = arranged[index:index + 4]
            if not (
                negation.get("syntax_role") == "negation_marker"
                and marker.get("syntax_role") == "possessive_marker"
                and self._is_nominal_family(self._syntax_family(absent))
                and self._is_nominal_family(self._syntax_family(head))
            ):
                index += 1
                continue
            negation.update({
                "resolved_target": "无",
                "negation_form_reason": "absence_attributive",
                "parse_method": "attested_absence_attributive",
            })
            marker.update({
                "resolved_target": "的",
                "omit_from_result": False,
                "syntax_role": "absence_attributive_marker",
                "parse_method": "attested_absence_attributive",
                "note": "Nai ou N 已按“无 N 的”定语构式解析。",
            })
            arranged[index:index + 3] = [negation, absent, marker]
            for position, token in enumerate(arranged):
                token["reordered_position"] = position
                token["grammar_order_locked"] = True
            index += 4
        return arranged

    def _resolve_alician_circumfixes(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Close attested 在/到-NP-上/下/周围 locative frames."""
        arranged = list(tokens)
        index = 0
        while index < len(arranged):
            marker = arranged[index]
            marker_role = marker.get("syntax_role")
            if marker_role not in {
                "locative_circumfix_marker", "clausal_circumfix_marker",
            }:
                index += 1
                continue
            closer_target = str(marker.get("circumfix_closer") or "")
            if not closer_target or index + 1 >= len(arranged):
                index += 1
                continue
            if marker_role == "clausal_circumfix_marker":
                phrase_end = len(arranged)
            else:
                phrase_end = index + 2
                first_family = self._syntax_family(arranged[index + 1])
                if first_family in {"adj", "art", "num"}:
                    while (
                        phrase_end < len(arranged)
                        and self._syntax_family(arranged[phrase_end]) in {"adj", "art", "num"}
                    ):
                        phrase_end += 1
                    if (
                        phrase_end < len(arranged)
                        and self._is_nominal_family(self._syntax_family(arranged[phrase_end]))
                    ):
                        phrase_end += 1
            closer = self._token(
                source="",
                target=closer_target,
                status="exact",
                method="attested_locative_circumfix",
                confidence=1.0,
                explanation=f"{marker.get('source')} 的后置方位成分",
                word_class="postp.",
                note="已把词典槽位实现为包围完整名词短语的中文方位结构。",
            )
            closer["syntax_role"] = "locative_circumfix_closer"
            arranged.insert(phrase_end, closer)
            marker["parse_method"] = "attested_locative_circumfix"
            for position, token in enumerate(arranged):
                token["reordered_position"] = position
                token["grammar_order_locked"] = True
            index = phrase_end + 1
        return arranged

    def _reorder_alician_passive(
        self, tokens: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Convert Yien-V-Ord-agent into Chinese 被-agent-V."""
        passive_indexes = [
            index for index, token in enumerate(tokens)
            if token.get("syntax_role") == "passive_marker"
        ]
        if len(passive_indexes) != 1:
            return None
        marker_index = passive_indexes[0]
        predicate_index = next(
            (
                index for index in range(marker_index + 1, len(tokens))
                if self._syntax_family(tokens[index]) == "v"
                and tokens[index].get("syntax_role") not in {
                    "topic_or_copula_marker",
                }
            ),
            -1,
        )
        if predicate_index < 0:
            return None
        ord_index = next(
            (
                index for index in range(predicate_index + 1, len(tokens))
                if tokens[index].get("syntax_role") == "passive_agent_marker"
            ),
            -1,
        )
        if ord_index < 0:
            return None
        before = tokens[:marker_index]
        predicate = tokens[marker_index + 1:ord_index]
        agent = tokens[ord_index + 1:]
        if not predicate or not agent:
            return None
        internal_negations = [
            token for token in predicate
            if token.get("syntax_role") == "negation_marker"
        ]
        if internal_negations:
            predicate = [
                token for token in predicate
                if token.get("syntax_role") != "negation_marker"
            ]
            for negation in internal_negations:
                negation["resolved_target"] = "不"
                negation["omit_from_result"] = False
            before = before + internal_negations
        passive_marker = tokens[marker_index]
        agent_marker = tokens[ord_index]
        passive_marker["resolved_target"] = "被"
        agent_marker["resolved_target"] = ""
        agent_marker["omit_from_result"] = True
        arranged = before + [passive_marker] + agent + predicate + [agent_marker]
        for position, token in enumerate(arranged):
            token["reordered_position"] = position
            token["parse_method"] = "attested_passive_grammar"
            token["grammar_order_locked"] = True
        return arranged

    def _reorder_alician_instrumental(
        self, tokens: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Move post-predicate Ord NP to Chinese preverbal 用 NP position."""
        if any(token.get("syntax_role") == "passive_marker" for token in tokens):
            return None
        ord_indexes = [
            index for index, token in enumerate(tokens)
            if token.get("syntax_role") == "passive_agent_marker"
        ]
        verb_indexes = [
            index for index, token in enumerate(tokens)
            if self._syntax_family(token) == "v"
            and token.get("syntax_role") != "topic_or_copula_marker"
        ]
        if len(ord_indexes) != 1 or len(verb_indexes) != 1:
            return None
        ord_index, verb_index = ord_indexes[0], verb_indexes[0]
        if ord_index + 1 >= len(tokens):
            marker = tokens[ord_index]
            marker.update({
                "resolved_target": "",
                "omit_from_result": True,
                "syntax_role": "semantically_light_particle",
                "parse_method": "dangling_ord_suppression",
                "note": "句末 Ord 没有可绑定的施事或工具名词，已避免输出悬空的“用”。",
            })
            arranged = list(tokens)
            for position, token in enumerate(arranged):
                token["reordered_position"] = position
                token["grammar_order_locked"] = True
            return arranged
        if ord_index <= verb_index:
            return None
        marker = tokens[ord_index]
        marker.update({
            "resolved_target": "用",
            "syntax_role": "instrument_marker",
            "parse_method": "attested_instrumental_grammar",
            "note": "非被动环境中的 Ord NP 已按工具/手段短语移到谓词前。",
        })
        arranged = (
            tokens[:verb_index]
            + [marker]
            + tokens[ord_index + 1:]
            + [tokens[verb_index]]
            + tokens[verb_index + 1:ord_index]
        )
        for position, token in enumerate(arranged):
            token["reordered_position"] = position
            token["grammar_order_locked"] = True
        return arranged

    def _reorder_negative_passive_markers(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Normalize Yien Nai V to idiomatic Chinese Nai Yien V order."""
        arranged = list(tokens)
        for index in range(len(arranged) - 1):
            if (
                arranged[index].get("syntax_role") == "passive_marker"
                and arranged[index + 1].get("syntax_role") == "negation_marker"
            ):
                negation = arranged.pop(index + 1)
                negation["resolved_target"] = "不"
                negation["omit_from_result"] = False
                arranged.insert(index, negation)
                for position, token in enumerate(arranged):
                    token["reordered_position"] = position
                    token["grammar_order_locked"] = True
                break
        return arranged

    def _reorder_alician_relative_clause(
        self, tokens: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Move an attested head-end-relative clause before its Chinese head."""
        for marker_index, marker in enumerate(tokens):
            if marker.get("syntax_role") != "relative_or_linker" or marker_index < 1:
                continue
            head_index = marker_index - 1
            if not self._is_nominal_family(self._syntax_family(tokens[head_index])):
                continue
            verb_indexes = [
                index for index in range(marker_index + 1, len(tokens))
                if self._syntax_family(tokens[index]) == "v"
                and tokens[index].get("syntax_role") not in {
                    "topic_or_copula_marker",
                }
            ]
            if not verb_indexes:
                continue
            first_verb = verb_indexes[0]
            relative_end = len(tokens)
            if len(verb_indexes) > 1:
                relative_end = verb_indexes[1]
                while relative_end > first_verb + 1 and (
                    tokens[relative_end - 1].get("syntax_role") in {
                        "perfect_aspect_marker",
                        "pluperfect_aspect_marker",
                        "passive_marker",
                    }
                    or self._syntax_family(tokens[relative_end - 1]) == "adv"
                ):
                    relative_end -= 1
            modifier = tokens[marker_index + 1:relative_end]
            passive_modifier = self._reorder_alician_passive(modifier)
            if passive_modifier is not None:
                modifier = passive_modifier
            marker.update({
                "resolved_target": "的",
                "explanation": "关系从句标记",
                "omit_from_result": False,
                "syntax_role": "relative_clause_marker",
                "parse_method": "attested_relative_clause_grammar",
            })
            arranged = (
                tokens[:head_index]
                + modifier
                + [marker, tokens[head_index]]
                + tokens[relative_end:]
            )
            for position, token in enumerate(arranged):
                token["reordered_position"] = position
                token["grammar_order_locked"] = True
            return arranged
        return None

    def _reorder_alician_markers(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Place future, polite, and interrogative markers idiomatically."""
        arranged = list(tokens)
        predicate_index = next(
            (
                index for index, token in enumerate(arranged)
                if self._syntax_family(token) == "v"
                and token.get("syntax_role") not in {
                    "topic_or_copula_marker", "passive_marker",
                }
            ),
            -1,
        )
        if predicate_index >= 0:
            for role in ("future_marker", "imperative_marker"):
                marker_index = next(
                    (
                        index for index, token in enumerate(arranged)
                        if token.get("syntax_role") == role
                    ),
                    -1,
                )
                if role == "imperative_marker" and marker_index > predicate_index:
                    arranged[marker_index]["resolved_target"] = "吧"
                    arranged[marker_index]["note"] = (
                        "句末 Phier 按语料中的祈使/礼貌语气译为“吧”。"
                    )
                    continue
                if marker_index > predicate_index:
                    marker = arranged.pop(marker_index)
                    predicate_index = next(
                        index for index, token in enumerate(arranged)
                        if self._syntax_family(token) == "v"
                        and token.get("syntax_role") not in {
                            "topic_or_copula_marker", "passive_marker",
                        }
                    )
                    arranged.insert(predicate_index, marker)
            for role in (
                "focus_marker",
                "additive_focus_marker",
                "habitual_adverb_marker",
                "reciprocal_marker",
                "imperative_degree_marker",
            ):
                marker_index = next(
                    (
                        index for index, token in enumerate(arranged)
                        if token.get("syntax_role") == role
                    ),
                    -1,
                )
                if marker_index > predicate_index:
                    marker = arranged.pop(marker_index)
                    predicate_index = next(
                        index for index, token in enumerate(arranged)
                        if self._syntax_family(token) == "v"
                        and token.get("syntax_role") not in {
                            "topic_or_copula_marker", "passive_marker",
                        }
                    )
                    arranged.insert(predicate_index, marker)
        question_index = next(
            (
                index for index, token in enumerate(arranged)
                if token.get("syntax_role") == "yes_no_question_marker"
            ),
            -1,
        )
        if question_index >= 0:
            marker = arranged.pop(question_index)
            subject_end = 1 if arranged and self._is_nominal_family(
                self._syntax_family(arranged[0])
            ) else 0
            arranged.insert(subject_end, marker)
        if arranged != tokens:
            for position, token in enumerate(arranged):
                token["reordered_position"] = position
                token["grammar_order_locked"] = True
        return arranged

    def _resolve_postposed_lqll(
        self, tokens: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        if len(tokens) < 2 or str(tokens[-1].get("source") or "").casefold() != "lqll":
            return None
        marker = tokens[-1]
        opener = self._token(
            source="",
            target="像",
            status="approximate",
            method="postposed_similative_fallback",
            confidence=0.75,
            explanation="后置 Lqll 相似结构",
            word_class="prep.",
            note=(
                "Lqll 的后置位置有多条对齐支持；“像……一样”只由一条金标"
                "明确支持，作为中置信兜底表面形式。"
            ),
        )
        opener["syntax_role"] = "similative_opener"
        marker.update({
            "resolved_target": "一样",
            "explanation": "后置相似标记",
            "method": "postposed_similative_fallback",
            "status": "approximate",
            "confidence": 0.75,
            "syntax_role": "similative_closer",
        })
        arranged = [opener, *tokens[:-1], marker]
        for position, token in enumerate(arranged):
            token["reordered_position"] = position
            token["grammar_order_locked"] = True
        return arranged

    def _resolve_imperative_clause(
        self, tokens: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Give Yiela/Yiep scope over the complete following clause.

        The no_class descriptions spell these constructions as 来/请……吧,
        while aligned lyric translations sometimes leave one or both Chinese
        particles implicit.  Keeping the opener and a single clause-final 吧
        is a deterministic fallback; most importantly, it must not close the
        construction immediately after the first verb.
        """
        clause_markers = [
            index for index, token in enumerate(tokens)
            if token.get("syntax_role") == "imperative_clause_marker"
        ]
        if len(clause_markers) != 1:
            return None

        arranged = list(tokens)
        clause_marker_index = clause_markers[0]
        scope_end = len(arranged)
        for index in range(clause_marker_index + 1, len(arranged) - 1):
            if (
                arranged[index].get("syntax_role") == "coordinator"
                and self._is_nominal_family(self._syntax_family(arranged[index + 1]))
            ):
                scope_end = index
                break
        predicate_indexes = [
            index for index, token in enumerate(arranged)
            if clause_marker_index < index < scope_end
            and self._syntax_family(token) == "v"
            and token.get("syntax_role") not in {
                "topic_or_copula_marker", "passive_marker",
            }
        ]
        if not predicate_indexes:
            return None
        last_predicate = predicate_indexes[-1]
        imperative_indexes = [
            index for index, token in enumerate(arranged)
            if token.get("syntax_role") == "imperative_marker"
        ]
        trailing_indexes = [
            index for index in imperative_indexes
            if last_predicate < index < scope_end
        ]

        # A trailing Phier already realizes the clause-final mood.  Collapse
        # any other imperative particles instead of producing 请……吧……吧.
        if trailing_indexes:
            closer_index = trailing_indexes[-1]
            closer = arranged[closer_index]
            closer.update({
                "resolved_target": "吧",
                "omit_from_result": False,
                "parse_method": "attested_imperative_grammar",
                "note": "已将句末祈使成分归并为整句唯一的“吧”。",
            })
            for index in imperative_indexes:
                if index == closer_index:
                    continue
                arranged[index]["resolved_target"] = ""
                arranged[index]["omit_from_result"] = True
        else:
            closer = self._token(
                source="",
                target="吧",
                status="exact",
                method="attested_imperative_grammar",
                confidence=1.0,
                explanation="整句祈使语气",
                word_class="interj.",
                note="Yiela/Yiep 的作用域延伸到完整后续分句，句末只生成一次“吧”。",
            )
            closer["syntax_role"] = "imperative_clause_closer"
            arranged.insert(scope_end, closer)

        opener = arranged[clause_marker_index]
        source_sequence = [
            str(token.get("source") or "").casefold() for token in arranged
        ]
        if (
            str(opener.get("source") or "").casefold() == "yiela"
            and "brait" in source_sequence
            and "tri" in source_sequence
            and any(
                str((token.get("morphology") or {}).get("stem") or "").casefold()
                == "ran"
                and (token.get("morphology") or {}).get("suffix") == "qls"
                for token in arranged
            )
        ):
            brait = arranged[source_sequence.index("brait")]
            brait["resolved_target"] = "睁开"
            brait["parse_method"] = "attested_three_eyes_phrase"
            brait["note"] = "在 Tri Ran qls 的唯一明确对齐句中，Brait 按“睁开”解析。"
        following = next(
            (
                token for token in arranged[clause_marker_index + 1:]
                if token.get("syntax_role") != "semantically_light_particle"
            ),
            None,
        )
        if (
            str(opener.get("source") or "").casefold() == "yiela"
            and following is not None
            and self._is_nominal_family(self._syntax_family(following))
        ):
            opener["resolved_target"] = "让"
            opener["note"] = "Yiela 后接显式主语时按“让……”祈使构式解析。"
        opener["parse_method"] = "attested_imperative_grammar"
        opener["imperative_scope_end"] = scope_end
        for position, token in enumerate(arranged):
            token["reordered_position"] = position
            token["grammar_order_locked"] = True
        return arranged

    def _reorder_alician_clauses(self, tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize simple SOV/VOS clauses to Chinese SVO while preserving punctuation."""
        result: List[Dict[str, Any]] = []
        clause: List[Dict[str, Any]] = []

        def flush() -> None:
            if clause:
                result.extend(self._reorder_simple_clause(clause))
                clause.clear()

        for token in tokens:
            if token.get("status") == "punct":
                flush()
                result.append(token)
            else:
                clause.append(token)
        flush()
        return result

    def _reorder_simple_clause(self, clause: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        semantic = [token for token in clause if token.get("status") != "space"]
        similative = self._resolve_postposed_lqll(semantic)
        if similative is not None:
            return similative
        semantic = self._resolve_alician_absence_attributive(semantic)
        semantic = self._reorder_alician_possessives(semantic)
        semantic = self._resolve_alician_circumfixes(semantic)
        relative = self._reorder_alician_relative_clause(semantic)
        if relative is not None:
            return relative
        passive = self._reorder_alician_passive(semantic)
        if passive is not None:
            return passive
        instrumental = self._reorder_alician_instrumental(semantic)
        if instrumental is not None:
            semantic = instrumental
        semantic = self._reorder_negative_passive_markers(semantic)
        semantic = self._reorder_alician_markers(semantic)
        imperative = self._resolve_imperative_clause(semantic)
        if imperative is not None:
            return imperative
        if any(token.get("grammar_order_locked") for token in semantic):
            return semantic
        if len(semantic) < 3:
            return semantic
        if any(self._template_arity(str(token.get("explanation") or "")) for token in semantic):
            return semantic
        if any(
            token.get("syntax_role") in {
                "coordinator", "future_auxiliary_link", "relative_or_linker",
            }
            for token in semantic
        ):
            return semantic

        families = [self._syntax_family(token) for token in semantic]
        pattern = tuple(families)
        attested_count = self._sentence_patterns.get(
            self._pattern_signature(families), Counter()
        ).get(pattern, 0)
        if attested_count:
            example = self._sentence_pattern_examples.get(pattern, "")
            for token in semantic:
                token["matched_sentence_pattern"] = "-".join(pattern)
                token["sentence_pattern_example"] = example
                token["sentence_pattern_count"] = attested_count
                token["parse_method"] = "database_sentence_pattern"
        verb_indexes = [index for index, family in enumerate(families) if family == "v"]
        if len(verb_indexes) != 1:
            return semantic
        verb_index = verb_indexes[0]

        # Attach Chinese prenominal modifiers to the following noun phrase.
        units: List[List[int]] = []
        index = 0
        while index < len(semantic):
            possessive_group = semantic[index].get("possessive_group")
            if possessive_group:
                end = index
                while (
                    end + 1 < len(semantic)
                    and semantic[end + 1].get("possessive_group") == possessive_group
                ):
                    end += 1
                units.append(list(range(index, end + 1)))
                index = end + 1
                continue
            if families[index] in {"adj", "art", "num"}:
                end = index
                while end + 1 < len(semantic) and families[end + 1] in {"adj", "art", "num"}:
                    end += 1
                if end + 1 < len(semantic) and self._is_nominal_family(families[end + 1]):
                    units.append(list(range(index, end + 2)))
                    index = end + 2
                    continue
            units.append([index])
            index += 1

        verb_unit = next((i for i, unit in enumerate(units) if verb_index in unit), -1)
        nominal_units = [
            i for i, unit in enumerate(units)
            if self._is_nominal_family(families[unit[-1]])
        ]
        if verb_unit < 0 or not nominal_units:
            return semantic

        before = [i for i in nominal_units if i < verb_unit]
        after = [i for i in nominal_units if i > verb_unit]
        if not before and len(after) >= 2:  # VOS -> SVO
            subject_unit, object_units = after[-1], after[:-1]
        elif not before and len(after) == 1 and families[units[after[0]][-1]] == "pron":
            subject_unit, object_units = after[0], []  # V-(Adv)-S -> S-Adv-V
        elif not before and len(after) == 1:
            subject_unit, object_units = None, after  # (Adv)-V-O, omitted subject
        elif len(before) >= 2 and not after:  # SOV -> SVO
            subject_unit, object_units = before[0], before[1:]
        else:  # already SVO, or the closest safe S/V/O interpretation
            subject_unit = before[0] if before else nominal_units[0]
            object_units = [i for i in after if i != subject_unit]
        if not object_units and not (
            (subject_unit is not None and not before and subject_unit in after)
            or any(family == "adv" for family in families)
        ):
            return semantic

        core_units = {verb_unit, *object_units}
        if subject_unit is not None:
            core_units.add(subject_unit)
        prefixes: List[int] = []
        for unit_index, unit in enumerate(units):
            if unit_index in core_units or families[unit[-1]] not in {"conj", "interj"}:
                break
            prefixes.append(unit_index)
        modifiers = [
            i for i, unit in enumerate(units)
            if i not in core_units and i not in prefixes
        ]
        ordered_units = prefixes + ([subject_unit] if subject_unit is not None else []) + modifiers + [verb_unit] + object_units
        if len(ordered_units) != len(units) or len(set(ordered_units)) != len(units):
            return semantic

        reordered: List[Dict[str, Any]] = []
        for output_position, unit_index in enumerate(ordered_units):
            role = (
                "subject" if subject_unit is not None and unit_index == subject_unit else
                "predicate" if unit_index == verb_unit else
                "object" if unit_index in object_units else "modifier"
            )
            for semantic_index in units[unit_index]:
                token = semantic[semantic_index]
                token["syntax_role"] = role
                token["source_position"] = semantic_index
                token["reordered_position"] = output_position
                source = str(token.get("source") or "").lower()
                if role == "modifier" and source == "laiz":
                    token["resolved_target"] = "将"
                elif (
                    role == "modifier" and source == "nai"
                    and not token.get("resolved_target")
                ):
                    token["resolved_target"] = "不"
                reordered.append(token)
        return reordered
