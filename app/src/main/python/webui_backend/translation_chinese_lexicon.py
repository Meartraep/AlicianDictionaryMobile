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


class ChineseLexiconMixin:
    """Segment Chinese text and resolve lexical translation candidates."""

    def _translate_chinese_run(self, text: str) -> List[Dict[str, Any]]:
        template_tokens = self._translate_chinese_sentence_template(text)
        if template_tokens is not None:
            return template_tokens
        tokens: List[Dict[str, Any]] = []
        for word in self._segment_chinese_run(text):
            tokens.append(self._translate_segmented_chinese_word(word))
        return tokens

    def _translate_chinese_sentence_template(
        self, text: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Bind a Chinese construction, including one embedded in a longer run."""
        matches: List[Tuple[Tuple[int, int, int], Dict[str, Any], Any, List[str]]] = []
        for template in self._chinese_sentence_templates:
            match = template["pattern"].search(text)
            if match is None:
                continue
            arguments = [str(value).strip() for value in match.groups()]
            if len(arguments) != template["arity"] or not all(arguments):
                continue
            rank = (
                match.end() - match.start(),
                int(template["literal_length"]),
                int(template["entry"].get("count") or 0),
            )
            matches.append((rank, template, match, arguments))
        if not matches:
            return None

        _, template, match, arguments = max(matches, key=lambda item: item[0])
        entry = template["entry"]
        canonical_template = _TEMPLATE_SLOT_RE.sub(
            "……",
            str(template["template"]),
        )
        marker = self._entry_to_token(canonical_template, entry, "exact")
        marker["method"] = "sentence_template"
        marker["syntax_role"] = "sentence_template_marker"
        marker["template_arguments"] = arguments
        marker["note"] = (
            f"已从 no_class 识别完整句式，并绑定 {len(arguments)} 个论元。"
        )
        tokens: List[Dict[str, Any]] = []
        prefix = text[:match.start()]
        suffix = text[match.end():]
        if prefix:
            tokens.extend(self._translate_chinese_run(prefix))
        tokens.append(marker)
        for argument in arguments:
            tokens.extend(self._translate_chinese_run(argument))
        if suffix:
            tokens.extend(self._translate_chinese_run(suffix))
        return tokens

    def _segment_chinese_run(self, text: str) -> List[str]:
        """Split a complete Chinese run before consulting Alician entries."""
        if self._jieba is not None and len(text) > 1:
            try:
                parts = [
                    str(part)
                    for part in self._jieba.cut(text, cut_all=False, HMM=True)
                    if str(part).strip()
                ]
            except Exception:
                parts = []
            if parts and "".join(parts) == text:
                # Jieba correctly finds most ordinary word boundaries, but it
                # may keep productive negative constructions (for example
                # “不喜欢” or “非你不可”) in a single token.  Run every piece
                # through the dictionary-aware fallback so negation is found
                # independently of the optional tokenizer.
                refined: List[str] = []
                for part in parts:
                    if self._contains_productive_negation(part):
                        refined.extend(self._fallback_segment_chinese_run(part))
                    else:
                        refined.append(part)
                return refined
        return self._fallback_segment_chinese_run(text)

    def _is_lexicalized_negation_at(self, text: str, start: int) -> bool:
        """Return whether a negation-looking character belongs to a fixed word."""
        suffix = text[start:]
        return any(
            suffix.startswith(word)
            for word in _CHINESE_LEXICALIZED_NEGATION_PREFIXES
        )

    def _contains_productive_negation(self, text: str) -> bool:
        return any(
            text.startswith(negative, start)
            and not self._is_lexicalized_negation_at(text, start)
            for start in range(len(text))
            for negative in _CHINESE_NEGATION_FORMS
        )

    def _fallback_segment_chinese_run(self, text: str) -> List[str]:
        """Keep unknown spans intact while finding high-confidence word islands."""
        if not text:
            return []

        candidates_at: DefaultDict[int, List[Tuple[int, str, float]]] = defaultdict(list)
        for start in range(len(text)):
            max_exact_len = min(self._max_term_len, len(text) - start)
            for size in range(2, max_exact_len + 1):
                term = text[start:start + size]
                if term in self._term_candidates:
                    candidates_at[start].append((start + size, term, 12.0 + size * 2.0))

            if self._use_semantic_expansions:
                max_semantic_len = min(self._max_semantic_term_len, len(text) - start)
                for size in range(2, max_semantic_len + 1):
                    term = text[start:start + size]
                    if term in self._semantic_term_candidates:
                        candidates_at[start].append((start + size, term, 10.0 + size * 2.0))

            one_character = text[start:start + 1]
            if (
                one_character in _CHINESE_FALLBACK_BOUNDARIES
                and one_character in self._term_candidates
            ):
                candidates_at[start].append((start + 1, one_character, 7.0))

            for negative in _CHINESE_NEGATION_FORMS:
                if (
                    text.startswith(negative, start)
                    and not self._is_lexicalized_negation_at(text, start)
                ):
                    candidates_at[start].append(
                        (start + len(negative), negative, 9.0 + len(negative))
                    )

        # State values are (score, known characters, negative piece count,
        # segmented words). Longer coherent unknown spans win equal scores.
        best: List[Optional[Tuple[float, int, int, List[str]]]] = [
            None for _ in range(len(text) + 1)
        ]
        best[0] = (0.0, 0, 0, [])
        for start in range(len(text)):
            state = best[start]
            if state is None:
                continue
            score, known_characters, negative_pieces, words = state

            for end, term, reward in candidates_at.get(start, []):
                proposal = (
                    score + reward,
                    known_characters + len(term),
                    negative_pieces - 1,
                    words + [term],
                )
                current = best[end]
                if current is None or proposal[:3] > current[:3]:
                    best[end] = proposal

            for end in range(start + 1, len(text) + 1):
                unknown = text[start:end]
                proposal = (
                    score - 4.0 - len(unknown) * 0.05,
                    known_characters,
                    negative_pieces - 1,
                    words + [unknown],
                )
                current = best[end]
                if current is None or proposal[:3] > current[:3]:
                    best[end] = proposal

        final = best[len(text)]
        return final[3] if final is not None else [text]

    def _translate_segmented_chinese_word(self, word: str) -> Dict[str, Any]:
        exact = self._term_candidates.get(word)
        negative = self._negative_form_at(word, 0)
        if negative == word:
            return self._grammar_function_token(word, "Nai")

        if exact:
            token = self._entry_to_token(
                word,
                self._choose_candidate(exact, word),
                "exact",
            )
            token["method"] = "dictionary_term"
            return token

        erhua_base = self._erhua_base_form(word)
        if erhua_base:
            base_exact = self._term_candidates.get(erhua_base)
            if base_exact:
                token = self._entry_to_token(
                    word,
                    self._choose_candidate(base_exact, erhua_base),
                    "exact",
                )
                token["method"] = "erhua_normalization"
                token["normalized_source"] = erhua_base
                token["note"] = (
                    f"已识别儿化后缀，并按词根“{erhua_base}”匹配词典。"
                )
                return token

            base_candidate, base_method, confidence, alternatives = (
                self._find_chinese_candidate(erhua_base)
            )
            if base_candidate:
                token = self._entry_to_token(word, base_candidate, "approximate")
                token["method"] = f"erhua_{base_method}"
                token["confidence"] = round(confidence, 4)
                token["alternatives"] = alternatives
                token["normalized_source"] = erhua_base
                token["note"] = (
                    f"已去除儿化后缀，并按词根“{erhua_base}”完成近似匹配。"
                )
                return token

        candidate, method, confidence, alternatives = self._find_chinese_candidate(word)
        if candidate:
            token = self._entry_to_token(word, candidate, "approximate")
            token["method"] = method
            token["confidence"] = round(confidence, 4)
            token["alternatives"] = alternatives
            token["note"] = (
                "爱丽丝语没有直接词条，已用预计算语义别名匹配。"
                if method == "semantic_expansion"
                else "爱丽丝语没有直接词条，已用词义近似匹配。"
            )
            return token

        return self._token(
            source=word,
            target=f"〔{word}〕",
            status="unknown",
            method="missing",
            confidence=0.0,
            note="该中文词未找到可用的爱丽丝语对应词。",
        )

    @staticmethod

    def _erhua_base_form(word: str) -> str:
        """Return the lexical stem of a safe, productive 儿化 form."""
        source = str(word or "").strip()
        if (
            len(source) < 2
            or not source.endswith("儿")
            or source in _CHINESE_NON_ERHUA_WORDS
        ):
            return ""
        return source[:-1]

    def _find_chinese_candidate(
        self, query: str,
    ) -> Tuple[Optional[Dict[str, Any]], str, float, List[Dict[str, Any]]]:
        if self._use_semantic_expansions:
            expanded = self._find_semantic_expansion_candidate(query)
            if expanded[0] is not None:
                return expanded

        scored: List[Tuple[float, Dict[str, Any]]] = []
        if self._enable_fallback_matching:
            query_set = set(query)
            for entry in self._entries:
                if (
                    entry.get("fragment_parents")
                    or entry.get("no_class_unknown")
                    or entry.get("no_class_template")
                ):
                    continue
                score = 0.0
                explanation = entry["explanation"]
                terms = entry.get("terms", set())
                if query in terms:
                    score = max(score, 95.0)
                if explanation == query:
                    score = max(score, 92.0)
                elif query and query in explanation:
                    score = max(score, 64.0 - min(len(explanation), 40) * 0.3)
                for term in terms:
                    if len(term) < 2 and len(query) > 1:
                        continue
                    if term and term in query:
                        coverage = len(term) / max(len(query), 1)
                        score = max(score, 34.0 + coverage * 30.0)
                    elif query in term:
                        coverage = len(query) / max(len(term), 1)
                        score = max(score, 28.0 + coverage * 28.0)
                if score <= 0 and len(query) >= 2 and query_set:
                    exp_chars = {ch for ch in explanation if _CJK_RE.match(ch)}
                    if exp_chars:
                        overlap = len(query_set & exp_chars) / max(len(query_set), 1)
                        if overlap >= 0.6:
                            score = 22.0 + overlap * 18.0
                if score > 0:
                    score += min(entry["count"], 20) * 0.08 + min(entry["variety"], 10) * 0.12
                    if entry["kind"] == "phrase" and len(query) >= 2:
                        score += 3.0
                    scored.append((score, entry))
            scored.sort(key=lambda item: item[0], reverse=True)
            threshold = 50.0 if len(query) == 1 else 36.0
            if scored and scored[0][0] >= threshold:
                alternatives = [
                    self._alternative(item[1], item[0] / 100.0)
                    for item in scored[:5]
                ]
                if len(alternatives) < 5:
                    seen = {item.get("target") for item in alternatives}
                    for item in self._collect_semantic_alternatives(query, 5):
                        if item.get("target") in seen:
                            continue
                        alternatives.append(item)
                        seen.add(item.get("target"))
                        if len(alternatives) >= 5:
                            break
                return (
                    scored[0][1],
                    "meaning_overlap",
                    min(0.88, scored[0][0] / 100.0),
                    alternatives,
                )

        if self._enable_fallback_matching:
            semantic = self._find_semantic_candidate(query)
            if semantic[0] is not None:
                return semantic
        return None, "missing", 0.0, []

    def _find_semantic_expansion_candidate(
        self, query: str,
    ) -> Tuple[Optional[Dict[str, Any]], str, float, List[Dict[str, Any]]]:
        normalized_query = re.sub(r"\s+", "", str(query or "").strip())
        if not normalized_query or not self._semantic_term_candidates:
            return None, "missing", 0.0, []

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for item in self._semantic_term_candidates.get(normalized_query, []):
            semantic_score = max(0.0, float(item["similarity"]))
            entry = item["entry"]
            score = semantic_score
            score += min(entry["count"], 20) * 0.0008
            score += min(entry["variety"], 10) * 0.0012
            score -= max(0, int(item["rank"]) - 1) * 0.001
            scored.append((score, entry))

        scored.sort(
            key=lambda row: (
                row[0],
                row[1]["count"],
                row[1]["variety"],
                -row[1]["sense_order"],
            ),
            reverse=True,
        )
        if not scored:
            return None, "missing", 0.0, []

        alternatives: List[Dict[str, Any]] = []
        seen = set()
        for score, entry in scored:
            key = (entry["target"].casefold(), entry["sense_id"])
            if key in seen:
                continue
            seen.add(key)
            alternatives.append(self._alternative(entry, min(1.0, score)))
            if len(alternatives) >= 5:
                break
        return (
            scored[0][1],
            "semantic_expansion",
            min(0.95, max(0.55, scored[0][0])),
            alternatives,
        )

    def _find_semantic_candidate(
        self, query: str,
    ) -> Tuple[Optional[Dict[str, Any]], str, float, List[Dict[str, Any]]]:
        alternatives = self._collect_semantic_alternatives(query, 5)
        if alternatives:
            entry = self._best_word_entry(str(alternatives[0].get("target", "")))
            if entry is not None:
                score = float(alternatives[0].get("score") or 0.0)
                confidence = min(0.78, max(0.45, score if score <= 1 else 0.62))
                method = str(alternatives[0].get("method") or "text2vec")
                return entry, method, confidence, alternatives
        return None, "missing", 0.0, alternatives

    def _collect_semantic_alternatives(self, query: str, limit: int) -> List[Dict[str, Any]]:
        if not query or self._similarity_matcher is None:
            return []
        self._ensure_similarity_index()
        suggestions = self._similarity_matcher.find_similar(query, top_k=max(8, limit * 2))
        alternatives: List[Dict[str, Any]] = []
        for suggestion in suggestions:
            score = float(suggestion.get("similarity") or 0.0)
            for word in suggestion.get("words") or []:
                entry = self._best_word_entry(str(word))
                if not entry:
                    continue
                if any(item.get("target") == entry["target"] for item in alternatives):
                    continue
                alternative = self._alternative(entry, score)
                if (
                    self._use_semantic_expansions
                    and (
                        entry["target"].casefold(),
                        str(suggestion.get("explanation") or ""),
                    ) in self._semantic_expansion_pairs
                ):
                    alternative["method"] = "semantic_expansion"
                    alternative["matched_expansion"] = str(
                        suggestion.get("explanation") or ""
                    )
                alternatives.append(alternative)
                if len(alternatives) >= limit:
                    break
            if len(alternatives) >= limit:
                break
        return alternatives

    def _ensure_similarity_index(self) -> None:
        use_expansions = bool(
            self._use_semantic_expansions and self._semantic_expansions
        )
        if (
            self._similarity_index_built
            and self._similarity_index_uses_expansions == use_expansions
        ):
            return
        if self._similarity_matcher is None:
            return
        pairs = [
            (entry["target"], entry["explanation"])
            for entry in self._word_entries
            if not entry.get("fragment_parents")
            and not entry.get("no_class_unknown")
            and not entry.get("no_class_template")
        ]
        if use_expansions:
            pairs.extend(
                (item["entry"]["target"], item["expansion"])
                for item in self._semantic_expansions
            )
        self._similarity_matcher.build_index(pairs)
        self._similarity_index_built = True
        self._similarity_index_uses_expansions = use_expansions

    def _choose_candidate(self, candidates: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
        ranked = sorted(
            candidates,
            key=lambda entry: (
                query in entry.get("terms", set()),
                entry["explanation"] == query,
                entry["kind"] == "phrase",
                entry["count"],
                entry["variety"],
                -len(entry["target"]),
            ),
            reverse=True,
        )
        return ranked[0]
