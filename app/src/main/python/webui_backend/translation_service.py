from __future__ import annotations

import os
import re
import sqlite3
import threading
import logging
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Counter as CounterType, DefaultDict, Dict, List, Optional, Tuple

from webui_backend.build_mode import is_lite_build
from webui_backend.dictionary_service import _lev_ratio


_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_CJK_RUN_RE = re.compile(r"[\u3400-\u9fff]+")
_ALICIAN_PART_RE = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+|\s+|[^\sA-Za-z\d]+")
_CHINESE_PART_RE = re.compile(r"[\u3400-\u9fff]+|[A-Za-z][A-Za-z'-]*|\d+|\s+|[^\sA-Za-z\d\u3400-\u9fff]+")
_POS_RE = re.compile(
    r"\b(?:adj|adv|art|conj|interj|n|num|prep|pron|v|vi|vt)\.?",
    re.IGNORECASE,
)
_TEMPLATE_SLOT_RE = re.compile(r"(?:\.{2,}|…+)")
_CHINESE_NEGATION_FORMS = tuple(sorted({
    "不可能", "不可以", "不会", "不能", "不可", "不要", "不必", "不得",
    "没有", "没能", "未能", "未曾", "从未", "并不", "并非", "绝不", "毫不",
    "不是", "不", "没", "未", "无", "非",
}, key=len, reverse=True))


def _default_db_path() -> str:
    env_db = os.environ.get("ALICIAN_DB_PATH")
    if env_db:
        return os.path.abspath(env_db)
    return str(Path(__file__).resolve().parent.parent / "translated.db")


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


class TranslationService:
    """Bidirectional translator with dictionary and corpus-backed grammar."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        enable_fallback_matching: Optional[bool] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._db_path = db_path or _default_db_path()
        self._enable_fallback_matching = (
            not is_lite_build()
            if enable_fallback_matching is None
            else bool(enable_fallback_matching)
        )
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._entries: List[Dict[str, Any]] = []
        self._word_entries: List[Dict[str, Any]] = []
        self._word_by_lower: Dict[str, List[Dict[str, Any]]] = {}
        self._phrases: List[Dict[str, Any]] = []
        self._term_candidates: Dict[str, List[Dict[str, Any]]] = {}
        self._max_term_len = 1
        self._sentence_patterns: DefaultDict[
            Tuple[Tuple[str, int], ...], CounterType[Tuple[str, ...]]
        ] = defaultdict(Counter)
        self._core_sentence_patterns: DefaultDict[
            Tuple[Tuple[str, int], ...], CounterType[Tuple[str, ...]]
        ] = defaultdict(Counter)
        self._sentence_pattern_examples: Dict[Tuple[str, ...], str] = {}
        self._adverb_position_stats: Dict[str, Dict[str, Any]] = {}
        self._similarity_matcher = (
            self._create_similarity_matcher()
            if self._enable_fallback_matching else None
        )
        self._similarity_index_built = False
        self._jieba: Any = None
        self._load_entries()
        self._load_adverb_position_stats()
        self._load_sentence_patterns()
        self._try_load_jieba()

    @staticmethod
    def _create_similarity_matcher() -> Any:
        try:
            from importlib import import_module

            module = import_module("webui_backend.similarity_matcher")
            return module.SimilarityMatcher()
        except Exception:
            logging.getLogger(__name__).info(
                "翻译器语义匹配模块不可用，已使用严格词典匹配模式。",
                exc_info=True,
            )
            return None

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def translate(self, text: str, direction: str = "auto") -> Dict[str, Any]:
        source = str(text or "").strip()
        if not source:
            return {
                "ok": False,
                "direction": direction or "auto",
                "source_text": "",
                "result_text": "",
                "tokens": [],
                "stats": {"exact": 0, "approximate": 0, "unknown": 0},
                "message": "请输入要翻译的内容。",
            }

        normalized_direction = self._normalize_direction(direction, source)
        with self._lock:
            if normalized_direction == "alician_to_zh":
                return self._translate_alician_to_zh(source, normalized_direction)
            return self._translate_zh_to_alician(source, normalized_direction)

    def _normalize_direction(self, direction: str, text: str) -> str:
        value = str(direction or "auto").strip()
        if value in {"zh_to_alician", "alician_to_zh"}:
            return value
        return "zh_to_alician" if _CJK_RE.search(text) else "alician_to_zh"

    def _load_entries(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT words, explanation, class, count, variety, sense_order FROM dictionary "
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
            )
            self._entries.append(entry)
            self._word_entries.append(entry)
            self._word_by_lower.setdefault(entry["target"].lower(), []).append(entry)
            self._index_chinese_terms(entry)

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
    ) -> Dict[str, Any]:
        return {
            "kind": kind,
            "target": str(target or "").strip(),
            "explanation": str(explanation or "").strip(),
            "word_class": str(word_class or "").strip(),
            "count": _as_int(count),
            "variety": _as_int(variety),
            "sense_order": max(1, _as_int(sense_order)),
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
        self._jieba = jieba
        for term in self._term_candidates.keys():
            if len(term) >= 2:
                try:
                    jieba.add_word(term, freq=200000)
                except Exception:
                    pass

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

    def _translate_chinese_run(self, text: str) -> List[Dict[str, Any]]:
        tokens: List[Dict[str, Any]] = []
        i = 0
        while i < len(text):
            match = self._find_longest_term(text, i)
            negative = self._negative_form_at(text, i)
            # Preserve longer complete lexical entries such as “无数”; otherwise
            # consume the whole negative phrase before character-level matching.
            matched_term = match[0] if match else ""
            if negative and len(negative) >= len(matched_term):
                tokens.append(self._grammar_function_token(negative, "Nai"))
                i += len(negative)
                continue
            if match:
                term, candidates = match
                tokens.append(self._entry_to_token(term, self._choose_candidate(candidates, term), "exact"))
                i += len(term)
                continue

            start = i
            i += 1
            while i < len(text) and self._find_longest_term(text, i) is None:
                i += 1
            tokens.extend(self._translate_unknown_chinese_segment(text[start:i], allow_jieba=True))
        return tokens

    def _find_longest_term(self, text: str, start: int) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        max_len = min(self._max_term_len, len(text) - start)
        for size in range(max_len, 0, -1):
            term = text[start:start + size]
            # Keep an explicit Chinese possessive marker visible to the syntax
            # pass.  Otherwise entries such as “我的” consume it as part of one
            # lexical token and A-的-B can never become B-ou-A.
            if "的" in term and term != "的":
                continue
            candidates = self._term_candidates.get(term)
            if candidates:
                return term, candidates
        return None

    def _translate_unknown_chinese_segment(
        self, segment: str, allow_jieba: bool,
    ) -> List[Dict[str, Any]]:
        if not segment:
            return []

        if allow_jieba and self._jieba is not None and len(segment) > 1:
            try:
                parts = [part for part in self._jieba.cut(segment) if part.strip()]
            except Exception:
                parts = []
            if len(parts) > 1 and "".join(parts) == segment:
                split_tokens: List[Dict[str, Any]] = []
                for part in parts:
                    exact = self._term_candidates.get(part)
                    if exact:
                        split_tokens.append(self._entry_to_token(part, self._choose_candidate(exact, part), "exact"))
                    else:
                        split_tokens.extend(self._translate_unknown_chinese_segment(part, allow_jieba=False))
                return split_tokens

        candidate, method, confidence, alternatives = self._find_chinese_candidate(segment)
        if candidate:
            token = self._entry_to_token(segment, candidate, "approximate")
            token["method"] = method
            token["confidence"] = round(confidence, 4)
            token["alternatives"] = alternatives
            token["note"] = "爱丽丝语没有直接词条，已用词义近似匹配。"
            return [token]

        return [
            self._token(
                source=segment,
                target=f"〔{segment}〕",
                status="unknown",
                method="missing",
                confidence=0.0,
                note="未找到可用的爱丽丝语对应词。",
            )
        ]

    def _find_chinese_candidate(
        self, query: str,
    ) -> Tuple[Optional[Dict[str, Any]], str, float, List[Dict[str, Any]]]:
        if not self._enable_fallback_matching:
            return None, "missing", 0.0, []
        scored: List[Tuple[float, Dict[str, Any]]] = []
        query_set = set(query)
        for entry in self._entries:
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
            alternatives = [self._alternative(item[1], item[0] / 100.0) for item in scored[:5]]
            if len(alternatives) < 5:
                seen = {item.get("target") for item in alternatives}
                for item in self._collect_semantic_alternatives(query, 5):
                    if item.get("target") in seen:
                        continue
                    alternatives.append(item)
                    seen.add(item.get("target"))
                    if len(alternatives) >= 5:
                        break
            return scored[0][1], "meaning_overlap", min(0.88, scored[0][0] / 100.0), alternatives

        semantic = self._find_semantic_candidate(query)
        if semantic[0] is not None:
            return semantic
        return None, "missing", 0.0, []

    def _find_semantic_candidate(
        self, query: str,
    ) -> Tuple[Optional[Dict[str, Any]], str, float, List[Dict[str, Any]]]:
        alternatives = self._collect_semantic_alternatives(query, 5)
        if alternatives:
            entry = self._best_word_entry(str(alternatives[0].get("target", "")))
            if entry is not None:
                score = float(alternatives[0].get("score") or 0.0)
                confidence = min(0.78, max(0.45, score if score <= 1 else 0.62))
                return entry, "text2vec", confidence, alternatives
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
                alternatives.append(self._alternative(entry, score))
                if len(alternatives) >= limit:
                    break
            if len(alternatives) >= limit:
                break
        return alternatives

    def _ensure_similarity_index(self) -> None:
        if self._similarity_index_built or self._similarity_matcher is None:
            return
        pairs = [(entry["target"], entry["explanation"]) for entry in self._word_entries]
        self._similarity_matcher.build_index(pairs)
        self._similarity_index_built = True

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

    def _translate_alician_to_zh(self, text: str, direction: str) -> Dict[str, Any]:
        parts = _ALICIAN_PART_RE.findall(text)
        contextual_senses = self._select_contextual_senses(parts)
        tokens: List[Dict[str, Any]] = []
        i = 0
        while i < len(parts):
            part = parts[i]
            if part.isspace():
                i += 1
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", part):
                tokens.append(self._punct_token(part))
                i += 1
                continue

            phrase, end_index = self._match_phrase(parts, i)
            if phrase:
                tokens.append(self._entry_to_chinese_token(phrase, phrase["target"], "exact", "phrase"))
                i = end_index
                continue

            entry = self._sentence_template_entry(parts, i, part)
            entry = entry or contextual_senses.get(i) or self._best_word_entry(part)
            if entry:
                token = self._entry_to_chinese_token(entry, part, "exact", "contextual_sense")
                candidates = self._word_by_lower.get(part.lower()) or []
                token["alternatives"] = [
                    self._alternative(candidate, 1.0 if candidate is entry else 0.0)
                    for candidate in candidates
                ]
                token["note"] = (
                    f"已结合上下文从 {len(candidates)} 个释义中选择当前释义。"
                    if len(candidates) > 1 else "词典单义词条命中。"
                )
                tokens.append(token)
                i += 1
                continue

            similar_entry, score = (
                self._find_similar_alician_word(part)
                if self._enable_fallback_matching else (None, 0.0)
            )
            if similar_entry:
                token = self._entry_to_chinese_token(similar_entry, part, "approximate", "spelling_similarity")
                token["confidence"] = round(score, 4)
                token["note"] = f"未找到精确词条，按拼写相似匹配到 {similar_entry['target']}。"
                token["alternatives"] = [self._alternative(similar_entry, score)]
                tokens.append(token)
                i += 1
                continue

            tokens.append(
                self._token(
                    source=part,
                    target=f"〔{part}〕",
                    status="unknown",
                    method="missing",
                    confidence=0.0,
                    note="未在爱丽丝语词典中找到该词。",
                )
            )
            i += 1

        ordered_tokens = self._reorder_alician_clauses(tokens)
        result_text = self._compose_chinese_result(ordered_tokens, resolve_templates=True)
        stats = self._stats(tokens)
        return {
            "ok": True,
            "direction": direction,
            "source_text": text,
            "result_text": result_text,
            "tokens": ordered_tokens,
            "stats": stats,
            "message": self._message(stats),
        }

    def _match_phrase(
        self, parts: List[str], start: int,
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        for phrase in self._phrases:
            words = phrase.get("phrase_words") or []
            pos = start
            matched = True
            for expected in words:
                while pos < len(parts) and parts[pos].isspace():
                    pos += 1
                if pos >= len(parts) or parts[pos].lower() != expected:
                    matched = False
                    break
                pos += 1
            if matched:
                return phrase, pos
        return None, start

    def _best_word_entry(self, word: str) -> Optional[Dict[str, Any]]:
        candidates = self._word_by_lower.get(str(word or "").lower()) or []
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda entry: (entry.get("sense_order", 1), -entry["count"], -entry["variety"]),
        )[0]

    @staticmethod
    def _template_arity(explanation: str) -> int:
        return len(_TEMPLATE_SLOT_RE.findall(str(explanation or "")))

    def _sentence_template_entry(
        self, parts: List[str], start: int, word: str,
    ) -> Optional[Dict[str, Any]]:
        """Prefer a template sense only when its following argument slots exist."""
        candidates = self._word_by_lower.get(str(word or "").lower()) or []
        templates = [entry for entry in candidates if self._template_arity(entry["explanation"]) > 0]
        if not templates:
            return None
        following_words = 0
        for part in parts[start + 1:]:
            if part.isspace():
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", part):
                break
            following_words += 1
        eligible = [
            entry for entry in templates
            if self._template_arity(entry["explanation"]) <= following_words
        ]
        if not eligible:
            return None
        return min(eligible, key=lambda entry: entry.get("sense_order", 1))

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
                            previous["word_class"], candidate["word_class"]
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
                elif role == "modifier" and source == "nai":
                    token["resolved_target"] = "不"
                reordered.append(token)
        return reordered

    def _entry_to_token(self, source: str, entry: Dict[str, Any], status: str) -> Dict[str, Any]:
        method = "dictionary_term" if status == "exact" else "meaning_overlap"
        return self._token(
            source=source,
            target=entry["target"],
            status=status,
            method=method,
            confidence=1.0 if status == "exact" else 0.7,
            explanation=entry["explanation"],
            word_class=entry["word_class"],
            count=entry["count"],
            variety=entry["variety"],
            alternatives=[self._alternative(entry, 1.0)],
            note="词典释义直接命中。" if status == "exact" else "",
        )

    def _entry_to_chinese_token(
        self, entry: Dict[str, Any], source: str, status: str, method: str,
    ) -> Dict[str, Any]:
        return self._token(
            source=source,
            target=entry["explanation"] or f"〔{source}〕",
            status=status,
            method=method,
            confidence=1.0 if status == "exact" else 0.7,
            explanation=entry["explanation"],
            word_class=entry["word_class"],
            count=entry["count"],
            variety=entry["variety"],
            alternatives=[self._alternative(entry, 1.0)],
            note="词典词条命中。" if status == "exact" else "",
        )

    def _token(
        self,
        source: str,
        target: str,
        status: str,
        method: str,
        confidence: float,
        explanation: str = "",
        word_class: str = "",
        count: int = 0,
        variety: int = 0,
        alternatives: Optional[List[Dict[str, Any]]] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        return {
            "source": source,
            "target": target,
            "status": status,
            "method": method,
            "confidence": round(float(confidence), 4),
            "explanation": explanation,
            "word_class": word_class,
            "count": int(count),
            "variety": int(variety),
            "alternatives": alternatives or [],
            "note": note,
        }

    def _punct_token(self, source: str) -> Dict[str, Any]:
        return self._token(source, source, "punct", "punct", 1.0)

    def _alternative(self, entry: Dict[str, Any], score: float) -> Dict[str, Any]:
        return {
            "target": entry["target"],
            "explanation": entry["explanation"],
            "word_class": entry["word_class"],
            "score": round(float(score), 4),
        }

    def _compose_alician_result(self, tokens: List[Dict[str, Any]]) -> str:
        out: List[str] = []
        for token in tokens:
            status = token.get("status")
            target = str(token.get("resolved_target") or token.get("target") or "")
            if not target:
                continue
            if status == "space":
                if out and out[-1] not in {" ", "\n"}:
                    out.append(" ")
                continue
            if status == "punct":
                while out and out[-1] == " ":
                    out.pop()
                out.append(target)
                out.append(" ")
                continue
            if out and out[-1] not in {" ", "\n"}:
                out.append(" ")
            out.append(target)
        return "".join(out).strip()

    @staticmethod
    def _clean_sentence_template(explanation: str) -> str:
        template = str(explanation or "").strip()
        template = re.sub(r"^[（(][^）)]*[）)]", "", template).strip()
        template = re.sub(r"[（(]\?+[）)]", "", template)
        return template

    def _template_argument_target(
        self, token: Dict[str, Any], template: str,
    ) -> str:
        source = str(token.get("source") or "")
        candidates = self._word_by_lower.get(source.lower()) or []
        if not candidates:
            return str(token.get("target") or "")
        if (template.startswith("一") and "就" in template) or template.startswith(("来", "请")):
            preferred_families = {"v", "adj", "adv"}
        else:
            preferred_families = {"n", "pron", "num"}
        preferred = [
            entry for entry in candidates
            if self._pos_family(entry.get("word_class", "")) in preferred_families
        ]
        chosen = min(
            preferred or candidates,
            key=lambda entry: (entry.get("sense_order", 1), -entry.get("count", 0)),
        )
        token["template_resolved_target"] = chosen["explanation"]
        token["template_resolved_class"] = chosen["word_class"]
        return str(chosen["explanation"] or token.get("target") or "")

    def _compose_chinese_result(
        self, tokens: List[Dict[str, Any]], resolve_templates: bool = False,
    ) -> str:
        out: List[str] = []
        consumed = set()
        for index, token in enumerate(tokens):
            if index in consumed:
                continue
            status = token.get("status")
            target = str(token.get("resolved_target") or token.get("target") or "")
            if status == "space":
                continue
            if resolve_templates and status not in {"space", "punct"}:
                explanation = str(token.get("explanation") or "")
                arity = self._template_arity(explanation)
                if arity:
                    argument_indexes: List[int] = []
                    for next_index in range(index + 1, len(tokens)):
                        next_status = tokens[next_index].get("status")
                        if next_status == "punct":
                            break
                        if next_status == "space" or next_index in consumed:
                            continue
                        argument_indexes.append(next_index)
                        if len(argument_indexes) >= arity:
                            break
                    if len(argument_indexes) == arity:
                        template = self._clean_sentence_template(explanation)
                        arguments = [
                            self._template_argument_target(tokens[arg], template)
                            for arg in argument_indexes
                        ]
                        iterator = iter(arguments)
                        target = _TEMPLATE_SLOT_RE.sub(lambda _: next(iterator), template)
                        consumed.update(argument_indexes)
                        token["resolved_target"] = target
                        token["template_arguments"] = arguments
                        token["note"] = f"已按词典句式填充 {arity} 个论元并调整中文语序。"
                        token["method"] = "sentence_template"
                    else:
                        template = self._clean_sentence_template(explanation)
                        target = _TEMPLATE_SLOT_RE.sub("", template)
                        token["note"] = f"该句式需要 {arity} 个论元，当前输入不完整。"
                        token["method"] = "sentence_template_incomplete"
            out.append(target)
        return "".join(out).strip()

    def _stats(self, tokens: List[Dict[str, Any]]) -> Dict[str, int]:
        exact = approximate = unknown = 0
        for token in tokens:
            status = token.get("status")
            if status == "exact":
                exact += 1
            elif status == "approximate":
                approximate += 1
            elif status == "unknown":
                unknown += 1
        return {"exact": exact, "approximate": approximate, "unknown": unknown}

    def _message(self, stats: Dict[str, int]) -> str:
        if stats.get("unknown"):
            return "翻译完成，但仍有词未解决。"
        if stats.get("approximate"):
            return "翻译完成，其中部分词使用了近似匹配。"
        return "翻译完成。"
