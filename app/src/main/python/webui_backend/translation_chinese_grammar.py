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


class ChineseGrammarMixin:
    """Arrange Chinese input using Alician grammar and corpus evidence."""

    def _translate_zh_to_alician(self, text: str, direction: str) -> Dict[str, Any]:
        tokens: List[Dict[str, Any]] = []
        for part in _CHINESE_PART_RE.findall(text):
            if not part:
                continue
            if part.isspace():
                # Whitespace separates source words; it is formatting, not a
                # translatable/reorderable token. Output spacing is composed
                # from the semantic tokens below.
                continue
            elif _CJK_RUN_RE.fullmatch(part):
                tokens.extend(self._translate_chinese_run(part))
            elif re.fullmatch(r"[^\sA-Za-z\d\u3400-\u9fff]+", part):
                tokens.append(self._punct_token(part))
            else:
                tokens.append(
                    self._token(
                        source=part,
                        target=part,
                        status="kept",
                        method="kept",
                        confidence=1.0,
                        note="非中文片段已保留。",
                    )
                )
        ordered = self._arrange_chinese_to_alician(tokens)
        result_text = self._compose_alician_result(ordered)
        stats = self._stats(ordered)
        return {
            "ok": True,
            "direction": direction,
            "source_text": text,
            "result_text": result_text,
            "tokens": ordered,
            "stats": stats,
            "message": self._message(stats),
        }

    def _arrange_chinese_to_alician(self, tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = self._apply_alician_grammar_lexemes(tokens)
        result: List[Dict[str, Any]] = []
        clause: List[Dict[str, Any]] = []

        def flush() -> None:
            if clause:
                result.extend(self._arrange_chinese_clause(clause))
                clause.clear()

        for token in normalized:
            if token.get("status") == "punct":
                flush()
                result.append(token)
            else:
                clause.append(token)
        flush()
        return result

    def _apply_alician_grammar_lexemes(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        grammar_words = {
            "不": "Nai", "没": "Nai", "没有": "Nai",
            "将": "Laiz", "将要": "Laiz",
            "被": "Yien",
        }
        for token in tokens:
            source = str(token.get("source") or "")
            target_word = "Nai" if source in _CHINESE_NEGATION_FORMS else grammar_words.get(source)
            if not target_word:
                continue
            entry = self._best_word_entry(target_word)
            if not entry:
                continue
            token["target"] = entry["target"]
            token["explanation"] = entry["explanation"]
            token["word_class"] = "adv."
            token["method"] = "grammar_function"
            if source == "被":
                token["syntax_role"] = "passive_marker"
            token["confidence"] = 1.0
            token["note"] = "按爱丽丝语语法功能词生成。"
        return tokens

    @staticmethod

    def _negative_form_at(text: str, start: int) -> str:
        for form in _CHINESE_NEGATION_FORMS:
            if text.startswith(form, start):
                return form
        return ""

    def _grammar_function_token(self, source: str, target_word: str) -> Dict[str, Any]:
        entry = self._best_word_entry(target_word)
        if not entry:
            return self._token(source, target_word, "exact", "grammar_function", 1.0)
        token = self._entry_to_token(source, entry, "exact")
        token["word_class"] = "adv."
        token["method"] = "grammar_function"
        token["note"] = "中文否定表达统一按爱丽丝语否定功能词生成。"
        return token

    def _arrange_chinese_possessives(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert Chinese possessor-的-head into Alician head-ou-possessor."""
        arranged = list(tokens)
        index = 1
        while index < len(arranged) - 1:
            token = arranged[index]
            if str(token.get("target") or "").lower() != "ou":
                index += 1
                continue
            left, right = arranged[index - 1], arranged[index + 1]
            # “的” explicitly marks the Chinese A-的-B construction.  Do not
            # gate its Alician order on dictionary POS data: short or
            # approximate matches are frequently classified as another sense
            # (for example a noun used here may have a verb as its top entry).
            arranged[index - 1:index + 2] = [right, token, left]
            token["syntax_role"] = "possessive_marker"
            token["note"] = "中文领属结构已转换为爱丽丝语 head-ou-possessor 语序。"
            index += 3
        return arranged

    def _arrange_by_attested_pattern(
        self, tokens: List[Dict[str, Any]], families: List[str],
    ) -> Optional[List[Dict[str, Any]]]:
        """Apply a dominant corpus POS pattern with the same lexical inventory."""
        if len(tokens) < 3 or len(tokens) > 12 or "unknown" in families:
            return None
        if any(token.get("status") != "exact" for token in tokens):
            return None
        if any(token.get("syntax_role") == "possessive_marker" for token in tokens):
            return None
        match = self._dominant_sentence_pattern(families)
        if match is None:
            return None
        pattern, count, confidence = match

        available: DefaultDict[str, List[int]] = defaultdict(list)
        for index, family in enumerate(families):
            available[family].append(index)
        order: List[int] = []
        for family in pattern:
            indexes = available.get(family)
            if not indexes:
                return None
            order.append(indexes.pop(0))
        if len(set(order)) != len(tokens):
            return None

        source_pattern = "-".join(families)
        target_pattern = "-".join(pattern)
        example = self._sentence_pattern_examples.get(pattern, "")
        arranged: List[Dict[str, Any]] = []
        for output_position, source_index in enumerate(order):
            token = tokens[source_index]
            token["source_position"] = source_index
            token["reordered_position"] = output_position
            token["alician_order_pattern"] = target_pattern
            token["sentence_pattern_source"] = source_pattern
            token["sentence_pattern_example"] = example
            token["sentence_pattern_count"] = count
            token["sentence_pattern_confidence"] = round(confidence, 4)
            token["order_method"] = "database_sentence_pattern"
            token["note"] = (
                f"按数据库范式 {target_pattern} 重排（{count} 条实例，"
                f"置信度 {confidence:.0%}；例句：{example}）。"
            )
            arranged.append(token)
        return arranged

    def _dominant_sentence_pattern(
        self, families: List[str],
    ) -> Optional[Tuple[Tuple[str, ...], int, float]]:
        candidates = self._sentence_patterns.get(self._pattern_signature(families))
        if not candidates:
            return None
        ranked = candidates.most_common(2)
        pattern, count = ranked[0]
        total = sum(candidates.values())
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        confidence = count / total if total else 0.0
        # Repeated corpus evidence is required.  For a divided signature, the
        # winner must also have a useful lead so a valid alternative order is
        # not overwritten by a near tie.
        if count < 2 or (confidence < 0.5 and count - runner_up < 2):
            return None
        return pattern, count, confidence

    def _core_pattern_evidence(self, families: List[str]) -> Optional[Tuple[int, float]]:
        core = [family for family in families if family in {"n", "pron", "v"}]
        candidates = self._core_sentence_patterns.get(self._pattern_signature(core))
        if not candidates:
            return None
        count = max(candidates.values())
        total = sum(candidates.values())
        confidence = count / total if total else 0.0
        if count < 2 or confidence < 0.4:
            return None
        return count, confidence

    def _apply_chinese_pattern_senses(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Use attested sentence patterns to resolve ambiguous Chinese terms."""
        if len(tokens) < 3 or len(tokens) > 8:
            return tokens
        option_rows: List[List[Optional[Dict[str, Any]]]] = []
        for token in tokens:
            source = str(token.get("source") or "")
            candidates = self._term_candidates.get(source) or []
            current_family = self._pos_family(str(token.get("word_class") or ""))
            if (
                token.get("status") != "exact" or not candidates
                or current_family in {"pron", "art", "prep", "conj", "interj", "num"}
                or token.get("method") == "grammar_function"
            ):
                option_rows.append([None])
                continue
            by_family: Dict[str, Dict[str, Any]] = {}
            for entry in candidates:
                family = self._pos_family(entry.get("word_class", ""))
                current = by_family.get(family)
                if current is None or self._sense_base_score(entry) > self._sense_base_score(current):
                    by_family[family] = entry
            option_rows.append(list(by_family.values())[:4] or [None])

        beams: List[Tuple[float, List[Optional[Dict[str, Any]]], List[str]]] = [(0.0, [], [])]
        for token, options in zip(tokens, option_rows):
            expanded: List[Tuple[float, List[Optional[Dict[str, Any]]], List[str]]] = []
            for score, selected, families in beams:
                for entry in options:
                    if entry is None:
                        family = self._pos_family(str(token.get("word_class") or ""))
                        entry_score = 0.0
                    else:
                        family = self._pos_family(entry.get("word_class", ""))
                        entry_score = self._sense_base_score(entry) * 0.25
                    expanded.append((score + entry_score, selected + [entry], families + [family]))
            beams = sorted(expanded, key=lambda item: item[0], reverse=True)[:128]

        best: Optional[Tuple[float, List[Optional[Dict[str, Any]]], List[str]]] = None
        for base_score, selected, families in beams:
            if families.count("v") != 1 or not any(
                family in {"n", "pron"} for family in families
            ):
                continue
            match = self._dominant_sentence_pattern(families)
            if match is not None:
                _, count, confidence = match
            else:
                core_match = self._core_pattern_evidence(families)
                if core_match is None:
                    continue
                count, confidence = core_match
            score = base_score + math.log1p(count) + confidence * 2.0
            if best is None or score > best[0]:
                best = (score, selected, families)
        if best is None:
            return tokens

        _, selected, _ = best
        resolved: List[Dict[str, Any]] = []
        for token, entry in zip(tokens, selected):
            if entry is None or (
                token.get("target") == entry.get("target")
                and token.get("word_class") == entry.get("word_class")
            ):
                resolved.append(token)
                continue
            replacement = self._entry_to_token(str(token.get("source") or ""), entry, "exact")
            alternatives = self._term_candidates.get(str(token.get("source") or "")) or []
            replacement["alternatives"] = [self._alternative(item, 1.0 if item is entry else 0.0) for item in alternatives]
            replacement["method"] = "sentence_pattern_sense"
            replacement["note"] = "已依据数据库句子范式选择当前词性和义项。"
            resolved.append(replacement)
        return resolved

    def _arrange_chinese_clause(self, clause: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        semantic = [token for token in clause if token.get("status") != "space"]
        if not semantic:
            return clause
        if any(
            token.get("syntax_role") == "sentence_template_marker"
            for token in semantic
        ):
            return semantic
        semantic = self._apply_chinese_pattern_senses(semantic)
        semantic = self._arrange_chinese_possessives(semantic)
        families = [self._pos_family(str(token.get("word_class") or "")) for token in semantic]
        attested = self._arrange_by_attested_pattern(semantic, families)
        if attested is not None:
            return self._apply_adverb_position_preferences(attested)
        grammar_sources = {"不", "没", "没有", "将", "将要"}
        verb_indexes = [
            index for index, family in enumerate(families)
            if family == "v" and str(semantic[index].get("source") or "") not in grammar_sources
        ]
        if len(verb_indexes) != 1:
            return self._apply_adverb_position_preferences(semantic)
        verb_index = verb_indexes[0]
        possessive_groups: Dict[int, List[int]] = {}
        possessive_members = set()
        for marker_index, token in enumerate(semantic):
            if token.get("syntax_role") != "possessive_marker":
                continue
            if marker_index <= 0 or marker_index + 1 >= len(semantic):
                continue
            head_index = marker_index - 1
            possessive_groups[head_index] = [head_index, marker_index, marker_index + 1]
            possessive_members.update({marker_index, marker_index + 1})

        def phrase(index: int) -> List[int]:
            return possessive_groups.get(index, [index])

        before_nominals = [
            i for i in range(verb_index)
            if i not in possessive_members and families[i] in {"n", "pron"}
        ]
        after_nominals = [
            i for i in range(verb_index + 1, len(semantic))
            if i not in possessive_members and families[i] in {"n", "pron"}
        ]
        if not before_nominals:
            return self._apply_adverb_position_preferences(semantic)
        subject = before_nominals[0]
        obj = after_nominals[0] if after_nominals else None

        core = {verb_index, *phrase(subject)}
        if obj is not None:
            core.update(phrase(obj))
        manner = [
            i for i, token in enumerate(semantic)
            if i not in core and families[i] == "adv"
            and str(token.get("source") or "").endswith("地")
        ]
        modal = [
            i for i, token in enumerate(semantic)
            if i not in core and str(token.get("target") or "") == "Foul"
        ]
        prefixes = [
            i for i, family in enumerate(families)
            if i not in core and i not in manner and i not in modal
            and family in {"conj", "interj"}
        ]
        remaining = [
            i for i in range(len(semantic))
            if i not in core and i not in manner and i not in modal and i not in prefixes
        ]

        # Attested emphatic pattern: Foul + S + O + V.
        if modal and obj is not None:
            order = prefixes + modal + phrase(subject) + phrase(obj) + remaining + [verb_index] + manner
            pattern = "SOV-emphatic"
        # A nominal subject with a pronominal/demonstrative object commonly permits VOS.
        elif obj is not None and families[subject] == "n" and (
            families[obj] == "pron" or str(semantic[obj].get("target") or "") == "Xia"
        ):
            order = prefixes + remaining + [verb_index] + phrase(obj) + phrase(subject) + manner
            pattern = "VOS-focus"
        else:
            order = prefixes + modal + phrase(subject) + remaining + [verb_index]
            if obj is not None:
                order += phrase(obj)
            order += manner
            pattern = "SVO"
        if len(set(order)) != len(semantic):
            return self._apply_adverb_position_preferences(semantic)
        arranged = []
        for output_position, source_index in enumerate(order):
            token = semantic[source_index]
            token["source_position"] = source_index
            token["reordered_position"] = output_position
            token["alician_order_pattern"] = pattern
            arranged.append(token)
        return self._apply_adverb_position_preferences(arranged)

    def _apply_adverb_position_preferences(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if len(tokens) < 2 or not self._adverb_position_stats:
            return tokens

        preferred: Dict[str, List[Dict[str, Any]]] = {
            "start": [], "middle": [], "end": [],
        }
        retained: List[Dict[str, Any]] = []
        for token in tokens:
            family = self._pos_family(str(token.get("word_class") or ""))
            stats = self._adverb_position_stats.get(
                str(token.get("target") or "").casefold()
            )
            position = str((stats or {}).get("preferred_position") or "")
            if (
                family != "adv"
                or not stats
                or not stats.get("is_preferred")
                or position not in preferred
            ):
                retained.append(token)
                continue
            preferred[position].append(token)
            token["adverb_position_preference"] = position
            token["adverb_position_confidence"] = round(
                float(stats.get("ratio") or 0.0), 4
            )
            token["adverb_position_counts"] = {
                key: int(stats.get(key) or 0)
                for key in ("start", "middle", "end")
            }
            token["order_method"] = "adverb_position_statistics"
            position_label = {"start": "句首", "middle": "句中", "end": "句末"}[position]
            statistical_note = (
                f"该副词在歌词语料中明显倾向{position_label}"
                f"（{int(stats.get('total') or 0)} 次，"
                f"{float(stats.get('ratio') or 0.0):.0%}）。"
            )
            existing_note = str(token.get("note") or "").strip()
            token["note"] = (
                f"{existing_note} {statistical_note}".strip()
                if existing_note else statistical_note
            )

        if not any(preferred.values()):
            return tokens

        arranged = preferred["start"] + retained
        middle = preferred["middle"]
        if middle:
            families = [
                self._pos_family(str(token.get("word_class") or ""))
                for token in arranged
            ]
            verb_index = next(
                (index for index, family in enumerate(families) if family == "v"),
                -1,
            )
            if verb_index > 0:
                insert_at = verb_index
            elif verb_index == 0 and len(arranged) > 1:
                insert_at = 1
            else:
                insert_at = max(1, len(arranged) // 2)
            insert_at = min(insert_at, len(arranged))
            arranged[insert_at:insert_at] = middle
        arranged.extend(preferred["end"])

        for output_position, token in enumerate(arranged):
            token["reordered_position"] = output_position
        return arranged
