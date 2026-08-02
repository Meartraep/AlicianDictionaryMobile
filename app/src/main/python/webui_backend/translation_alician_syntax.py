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
        if len(semantic) < 3:
            return clause
        if any(self._template_arity(str(token.get("explanation") or "")) for token in semantic):
            return clause

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
            return clause
        verb_index = verb_indexes[0]

        # Attach Chinese prenominal modifiers to the following noun phrase.
        units: List[List[int]] = []
        index = 0
        while index < len(semantic):
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
            return clause

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
            return clause

        core_units = {verb_unit, *object_units}
        if subject_unit is not None:
            core_units.add(subject_unit)
        prefixes = [
            i for i, unit in enumerate(units)
            if i not in core_units and families[unit[-1]] in {"conj", "interj"}
        ]
        modifiers = [
            i for i, unit in enumerate(units)
            if i not in core_units and i not in prefixes
        ]
        ordered_units = prefixes + ([subject_unit] if subject_unit is not None else []) + modifiers + [verb_unit] + object_units
        if len(set(ordered_units)) != len(units):
            return clause

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
