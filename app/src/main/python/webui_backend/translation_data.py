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


class TranslationDataMixin:
    """Load and index dictionary, corpus, and no-class translation data."""

    def _load_entries(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, words, explanation, class, count, variety, sense_order FROM dictionary "
            "WHERE words IS NOT NULL AND TRIM(words) <> '' ORDER BY headword_id, sense_order"
        )
        for row in cur.fetchall():
            entry = self._make_entry(
                kind="word",
                target=row["words"],
                explanation=row["explanation"],
                word_class=row["class"],
                count=row["count"],
                variety=row["variety"],
                sense_order=row["sense_order"],
                sense_id=row["id"],
            )
            self._entries.append(entry)
            self._word_entries.append(entry)
            self._word_by_lower.setdefault(entry["target"].lower(), []).append(entry)
            self._word_by_sense_id[entry["sense_id"]] = entry
            self._index_chinese_terms(entry)

        self._load_no_class_metadata(cur)

        cur.execute(
            "SELECT PHRASE, explanation, count, variety FROM phrase "
            "WHERE PHRASE IS NOT NULL AND TRIM(PHRASE) <> ''"
        )
        for row in cur.fetchall():
            entry = self._make_entry(
                kind="phrase",
                target=row["PHRASE"],
                explanation=row["explanation"],
                word_class="phrase",
                count=row["count"],
                variety=row["variety"],
                sense_order=1,
            )
            words = [part.lower() for part in re.findall(r"[A-Za-z][A-Za-z'-]*", entry["target"])]
            if words:
                entry["phrase_words"] = words
                self._phrases.append(entry)
            self._entries.append(entry)
            self._index_chinese_terms(entry)
        self._phrases.sort(key=lambda item: len(item.get("phrase_words", [])), reverse=True)

    def _load_no_class_metadata(self, cur: sqlite3.Cursor) -> None:
        """Load grammar and morphology which cannot be represented as plain senses."""
        try:
            rows = cur.execute(
                "SELECT rowid, words, translation, count, variety FROM no_class "
                "WHERE words IS NOT NULL AND TRIM(words) <> '' ORDER BY rowid"
            ).fetchall()
        except sqlite3.Error:
            return

        for row in rows:
            word = str(row["words"] or "").strip()
            explanation = str(row["translation"] or "").strip()
            if not word:
                continue
            key = word.casefold()
            candidates = self._word_by_lower.get(key) or []
            if not candidates:
                entry = self._make_entry(
                    kind="no_class",
                    target=word,
                    explanation=explanation,
                    word_class="",
                    count=row["count"],
                    variety=row["variety"],
                )
                self._entries.append(entry)
                self._word_entries.append(entry)
                self._word_by_lower.setdefault(key, []).append(entry)
                candidates = [entry]

            for entry in candidates:
                entry["no_class_translation"] = explanation

            fragment_parents = {
                parent.strip()
                for parent in _WORD_FRAGMENT_PARENT_RE.findall(explanation)
                if parent.strip()
            }
            if fragment_parents:
                self._fragment_parents[key].update(fragment_parents)
                for entry in candidates:
                    entry["fragment_parents"] = sorted(fragment_parents)
                    self._remove_entry_from_chinese_index(entry)

            alias = _NO_CLASS_ALIAS_RE.search(explanation)
            if alias:
                self._no_class_aliases[key] = alias.group(1)

            if re.fullmatch(r"\s*[（(]?\?+[）)]?\s*", explanation):
                self._no_class_unknown_words.add(key)
                for entry in candidates:
                    entry["no_class_unknown"] = True

            if "动词前表被动" in explanation:
                self._passive_words.add(key)
                for entry in candidates:
                    entry["no_class_role"] = "passive_marker"

            arity = self._template_arity(explanation)
            if not arity:
                continue
            template_entry = next(
                (
                    entry for entry in candidates
                    if self._template_arity(str(entry.get("explanation") or ""))
                ),
                None,
            )
            if template_entry is None:
                template_entry = dict(candidates[0])
                template_entry["kind"] = "no_class_template"
                template_entry["explanation"] = explanation
                template_entry["terms"] = set()
            else:
                self._remove_entry_from_chinese_index(template_entry)
            template_entry["no_class_template"] = True
            template_entry["no_class_translation"] = explanation
            self._no_class_templates[key].append(template_entry)

            cleaned = self._clean_sentence_template(explanation)
            segments = _TEMPLATE_SLOT_RE.split(cleaned)
            if len(segments) != arity + 1 or not any(segments):
                continue
            pattern_source = "(.+?)".join(
                re.escape(segment) for segment in segments
            )
            self._chinese_sentence_templates.append({
                "entry": template_entry,
                "template": cleaned,
                "segments": segments,
                "pattern": re.compile(pattern_source),
                "arity": arity,
                "literal_length": sum(len(segment) for segment in segments),
            })

        self._chinese_sentence_templates.sort(
            key=lambda item: (
                item["literal_length"],
                item["entry"].get("count", 0),
            ),
            reverse=True,
        )
        for passive_word in self._passive_words:
            candidates = self._word_by_lower.get(passive_word) or []
            if not candidates:
                continue
            entry = candidates[0]
            entry["terms"].add("被")
            bucket = self._term_candidates.setdefault("被", [])
            if entry not in bucket:
                bucket.append(entry)

    def _remove_entry_from_chinese_index(self, entry: Dict[str, Any]) -> None:
        """Prevent morphology notes such as 'Eclat的一部分' becoming meanings."""
        for term in list(entry.get("terms") or set()):
            bucket = self._term_candidates.get(term)
            if not bucket:
                continue
            self._term_candidates[term] = [item for item in bucket if item is not entry]
            if not self._term_candidates[term]:
                del self._term_candidates[term]
        entry["terms"] = set()

    def _load_semantic_expansions(self) -> None:
        try:
            rows = self._conn.execute(
                "SELECT sense_id, alias AS expansion, similarity, rank "
                "FROM dictionary_semantic_aliases ORDER BY alias, rank, sense_id"
            ).fetchall()
        except sqlite3.Error:
            return

        for row in rows:
            entry = self._word_by_sense_id.get(_as_int(row["sense_id"]))
            expansion = str(row["expansion"] or "").strip()
            if (
                entry is None
                or entry.get("fragment_parents")
                or entry.get("no_class_unknown")
                or entry.get("no_class_template")
                or not expansion
            ):
                continue
            try:
                similarity = float(row["similarity"])
            except (TypeError, ValueError):
                continue
            if not math.isfinite(similarity):
                continue
            compact = re.sub(r"\s+", "", expansion)
            terms = self._extract_terms(expansion)
            if compact and compact not in terms:
                terms.insert(0, compact)
            usable_terms = [
                term for term in terms
                if term and term not in self._term_candidates
            ]
            if not usable_terms:
                continue
            item = {
                "entry": entry,
                "expansion": expansion,
                "terms": usable_terms,
                "similarity": max(-1.0, min(1.0, similarity)),
                "rank": max(1, _as_int(row["rank"])),
            }
            self._semantic_expansions.append(item)
            for term in usable_terms:
                bucket = self._semantic_term_candidates.setdefault(term, [])
                bucket.append(item)
                self._max_semantic_term_len = max(
                    self._max_semantic_term_len,
                    len(term),
                )
            self._semantic_expansion_pairs.add(
                (entry["target"].casefold(), expansion)
            )
        if self._semantic_term_candidates:
            self._semantic_dataset_kind = "semantic_alias"

    @staticmethod

    def _pattern_signature(families: List[str]) -> Tuple[Tuple[str, int], ...]:
        return tuple(sorted(Counter(families).items()))

    def _load_sentence_patterns(self) -> None:
        """Index fully recognized POS patterns attested in the song corpus."""
        try:
            rows = self._conn.execute(
                "SELECT lyric FROM songs WHERE lyric IS NOT NULL AND TRIM(lyric) <> ''"
            ).fetchall()
        except sqlite3.Error:
            return

        for row in rows:
            for raw_line in str(row["lyric"] or "").splitlines():
                line = raw_line.strip()
                if not line or re.search(r"[：:]", line):
                    continue
                words = re.findall(r"[A-Za-z][A-Za-z'-]*", line)
                if len(words) < 3 or len(words) > 12:
                    continue
                families: List[str] = []
                recognized = True
                for word in words:
                    entry = self._best_word_entry(word)
                    if not entry:
                        recognized = False
                        break
                    families.append(self._pos_family(entry["word_class"]))
                if not recognized or families.count("v") != 1:
                    continue
                if sum(family in {"n", "pron"} for family in families) < 1:
                    continue
                pattern = tuple(families)
                self._sentence_patterns[self._pattern_signature(families)][pattern] += 1
                core_pattern = tuple(
                    family for family in families if family in {"n", "pron", "v"}
                )
                self._core_sentence_patterns[
                    self._pattern_signature(list(core_pattern))
                ][core_pattern] += 1
                self._sentence_pattern_examples.setdefault(pattern, line)

    def _load_adverb_position_stats(self) -> None:
        try:
            rows = self._conn.execute(
                "SELECT word, start_count, middle_count, end_count, "
                "positioned_count, dominant_ratio, preferred_position, is_preferred "
                "FROM adverb_position_stats"
            ).fetchall()
        except sqlite3.Error:
            return
        for row in rows:
            word = str(row["word"] or "").strip().casefold()
            if not word:
                continue
            self._adverb_position_stats[word] = {
                "start": _as_int(row["start_count"]),
                "middle": _as_int(row["middle_count"]),
                "end": _as_int(row["end_count"]),
                "total": _as_int(row["positioned_count"]),
                "ratio": float(row["dominant_ratio"] or 0.0),
                "preferred_position": str(row["preferred_position"] or ""),
                "is_preferred": bool(row["is_preferred"]),
            }

    def _make_entry(
        self,
        kind: str,
        target: Any,
        explanation: Any,
        word_class: Any,
        count: Any,
        variety: Any,
        sense_order: Any = 1,
        sense_id: Any = 0,
    ) -> Dict[str, Any]:
        return {
            "kind": kind,
            "target": str(target or "").strip(),
            "explanation": str(explanation or "").strip(),
            "word_class": str(word_class or "").strip(),
            "count": _as_int(count),
            "variety": _as_int(variety),
            "sense_order": max(1, _as_int(sense_order)),
            "sense_id": _as_int(sense_id),
            "terms": set(),
        }

    def _try_load_jieba(self) -> None:
        try:
            import jieba  # type: ignore
        except Exception:
            return
        try:
            jieba.setLogLevel(logging.ERROR)
        except Exception:
            pass
        try:
            # Use an isolated general-purpose tokenizer. Dictionary
            # explanations must not modify its word boundaries: segmentation
            # is completed before Alician lookup begins.
            tokenizer = jieba.Tokenizer()
            tokenizer.initialize()
            self._jieba = tokenizer
        except Exception:
            self._jieba = None

    def _index_chinese_terms(self, entry: Dict[str, Any]) -> None:
        for term in self._extract_terms(entry["explanation"]):
            entry["terms"].add(term)
            bucket = self._term_candidates.setdefault(term, [])
            if entry not in bucket:
                bucket.append(entry)
            self._max_term_len = max(self._max_term_len, len(term))

    def _extract_terms(self, explanation: str) -> List[str]:
        source = str(explanation or "")
        if not source or not _CJK_RE.search(source):
            return []
        cleaned = re.sub(r"[（(]\s*\d+\s*[）)]", "，", source)
        cleaned = _POS_RE.sub("，", cleaned)
        parts = re.split(r"[,，、;；/|｜\n\r\t]+", cleaned)
        terms: List[str] = []
        seen = set()

        def add(raw: str) -> None:
            term = self._normalize_term(raw)
            if not term or term in seen:
                return
            seen.add(term)
            terms.append(term)

        for part in parts:
            add(part)
            normalized = self._normalize_term(part)
            if not normalized:
                continue
            if normalized.startswith("表") and len(normalized) > 2:
                add(normalized[1:])
            if normalized.endswith("的") and len(normalized) > 1:
                add(normalized[:-1])
        return terms

    def _normalize_term(self, raw: str) -> str:
        term = str(raw or "").strip()
        term = re.sub(r"[\"'“”‘’《》<>【】\[\]{}（）()]", "", term)
        term = re.sub(r"\s+", "", term)
        term = term.strip("。.!?？：:；;，,、")
        if not term or not _CJK_RE.search(term):
            return ""
        if term in {"不译", "未找到释义"}:
            return ""
        if len(term) > 12:
            return ""
        return term
