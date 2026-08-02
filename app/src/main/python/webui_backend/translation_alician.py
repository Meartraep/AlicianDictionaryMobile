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


class AlicianTranslationMixin:
    """Translate Alician tokens and no-class morphology into Chinese."""

    def _merge_fragmented_alician_parts(
        self, parts: List[str],
    ) -> Tuple[List[str], Dict[int, Dict[str, Any]]]:
        """Rejoin spaced lyric fragments when no_class names the parent word."""
        merged_parts: List[str] = []
        merged_sources: Dict[int, Dict[str, Any]] = {}
        index = 0
        while index < len(parts):
            if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", parts[index]):
                merged_parts.append(parts[index])
                index += 1
                continue

            pieces: List[str] = []
            position = index
            best: Optional[Tuple[Tuple[int, int, int], str, int, float]] = None
            while position < len(parts) and len(pieces) < 4:
                current = parts[position]
                if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", current):
                    break
                pieces.append(current)
                if len(pieces) >= 2:
                    joined = "".join(pieces)
                    referenced_parents = {
                        parent
                        for piece in pieces
                        for parent in self._fragment_parents.get(piece.casefold(), set())
                    }
                    for parent in referenced_parents:
                        candidates = self._word_by_lower.get(parent.casefold()) or []
                        if not candidates:
                            continue
                        canonical = candidates[0]["target"]
                        confidence = _lev_ratio(joined.casefold(), canonical.casefold())
                        exact = joined.casefold() == canonical.casefold()
                        near_variant = (
                            abs(len(joined) - len(canonical)) <= 1
                            and confidence >= 0.86
                        )
                        if not exact and not near_variant:
                            continue
                        rank = (1 if exact else 0, len(pieces), len(joined))
                        proposal = (rank, canonical, position + 1, confidence)
                        if best is None or proposal[0] > best[0]:
                            best = proposal

                next_position = position + 1
                while next_position < len(parts) and parts[next_position].isspace():
                    next_position += 1
                if (
                    next_position >= len(parts)
                    or not re.fullmatch(
                        r"[A-Za-z][A-Za-z'-]*",
                        parts[next_position],
                    )
                ):
                    break
                position = next_position

            if best is None:
                merged_parts.append(parts[index])
                index += 1
                continue

            _, canonical, end, confidence = best
            output_index = len(merged_parts)
            source = "".join(parts[index:end]).strip()
            merged_parts.append(canonical)
            merged_sources[output_index] = {
                "source": source,
                "normalized_source": canonical,
                "confidence": confidence,
                "exact": confidence == 1.0,
            }
            index = end
        return merged_parts, merged_sources

    def _alician_passive_token(
        self, source: str, canonical_word: str, is_alias: bool = False,
    ) -> Dict[str, Any]:
        entry = self._best_word_entry(canonical_word)
        status = "approximate" if is_alias else "exact"
        token = self._token(
            source=source,
            target="被",
            status=status,
            method="no_class_alias" if is_alias else "grammar_function",
            confidence=0.8 if is_alias else 1.0,
            explanation=str((entry or {}).get("explanation") or "动词前表被动"),
            word_class="adv.",
            count=int((entry or {}).get("count") or 0),
            variety=int((entry or {}).get("variety") or 0),
            note="已将 no_class 被动标记绑定到后续谓词。",
        )
        token["syntax_role"] = "passive_marker"
        if is_alias:
            token["normalized_source"] = canonical_word
        return token

    def _no_class_alias_token(
        self, source: str, canonical_word: str,
    ) -> Optional[Dict[str, Any]]:
        entry = self._best_word_entry(canonical_word)
        if entry is None:
            return None
        token = self._entry_to_chinese_token(
            entry,
            source,
            "approximate",
            "no_class_alias",
        )
        token["confidence"] = 0.8
        token["normalized_source"] = entry["target"]
        token["note"] = (
            f"no_class 将该形式标为 {entry['target']} 的疑似同形词，"
            "已按规范词条解释。"
        )
        return token

    def _fragment_reference_token(self, source: str) -> Optional[Dict[str, Any]]:
        parents = sorted(self._fragment_parents.get(source.casefold()) or set())
        if not parents:
            return None
        if len(parents) == 1:
            entry = self._best_word_entry(parents[0])
            if entry is not None:
                token = self._entry_to_chinese_token(
                    entry,
                    source,
                    "approximate",
                    "fragment_reference",
                )
                token["confidence"] = 0.75
                token["fragment_parent"] = entry["target"]
                token["note"] = (
                    f"no_class 仅将 {source} 记录为 {entry['target']} 的片段；"
                    "当前结果借用完整词的含义，不把片段视作独立同义词。"
                )
                return token
        parent_names = "/".join(parents)
        token = self._token(
            source=source,
            target=f"〔{source}：{parent_names} 的片段〕",
            status="unknown",
            method="ambiguous_fragment",
            confidence=0.0,
            note="该片段可能属于多个完整词，缺少相邻片段时无法确定词义。",
        )
        token["fragment_parents"] = parents
        return token

    def _unknown_no_class_token(self, source: str) -> Optional[Dict[str, Any]]:
        if source.casefold() not in self._no_class_unknown_words:
            return None
        return self._token(
            source=source,
            target=f"〔{source}〕",
            status="unknown",
            method="no_class_unresolved",
            confidence=0.0,
            note="no_class 中仅有“(?)”记录，未将未知元数据当作译文输出。",
        )

    def _translate_alician_to_zh(self, text: str, direction: str) -> Dict[str, Any]:
        parts, merged_sources = self._merge_fragmented_alician_parts(
            _ALICIAN_PART_RE.findall(text)
        )
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

            # Nai is a productive grammar particle, not the literal Chinese
            # phrase “表否定” stored as its dictionary explanation.  Recognize
            # it before phrase and sense lookup so its interpretation remains
            # available to sentence-level context.
            if part.casefold() == "nai":
                tokens.append(self._alician_negation_token(part))
                i += 1
                continue

            alias_word = self._no_class_aliases.get(part.casefold(), "")
            canonical_word = alias_word or part
            if canonical_word.casefold() in self._passive_words:
                tokens.append(
                    self._alician_passive_token(
                        part,
                        canonical_word,
                        is_alias=bool(alias_word),
                    )
                )
                i += 1
                continue

            phrase, end_index = self._match_phrase(parts, i)
            if phrase:
                tokens.append(self._entry_to_chinese_token(phrase, phrase["target"], "exact", "phrase"))
                i = end_index
                continue

            fragment_token = self._fragment_reference_token(part)
            if fragment_token is not None:
                tokens.append(fragment_token)
                i += 1
                continue

            unknown_no_class = self._unknown_no_class_token(part)
            if unknown_no_class is not None:
                tokens.append(unknown_no_class)
                i += 1
                continue

            if alias_word:
                alias_token = self._no_class_alias_token(part, alias_word)
                if alias_token is not None:
                    tokens.append(alias_token)
                    i += 1
                    continue

            entry = self._sentence_template_entry(parts, i, part)
            entry = entry or contextual_senses.get(i) or self._best_word_entry(part)
            if entry:
                merge = merged_sources.get(i)
                status = "exact" if merge is None or merge["exact"] else "approximate"
                source = str((merge or {}).get("source") or part)
                method = (
                    "fragment_recomposition"
                    if merge is not None and merge["exact"]
                    else "fragment_recomposition_variant"
                    if merge is not None
                    else "contextual_sense"
                )
                token = self._entry_to_chinese_token(entry, source, status, method)
                candidates = self._word_by_lower.get(part.lower()) or []
                token["alternatives"] = [
                    self._alternative(candidate, 1.0 if candidate is entry else 0.0)
                    for candidate in candidates
                ]
                if merge is not None:
                    token["normalized_source"] = part
                    token["confidence"] = round(float(merge["confidence"]), 4)
                    token["note"] = (
                        f"已依据 no_class 的构词关系将“{source}”重组为 {part}。"
                    )
                else:
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

        tokens = self._resolve_alician_negations(tokens)
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
            # Phrases containing Nai encode only one possible Chinese reading
            # and hide the productive negation particle from context (for
            # example “Nai Drone” can mean “不再孤独”, not only “没有一个人”).
            if "nai" in words:
                continue
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

    def _alician_negation_token(self, source: str) -> Dict[str, Any]:
        """Create a grammatical Nai token with a safe standalone rendering."""
        entry = self._best_word_entry("Nai")
        token = self._token(
            source=source,
            target="不",
            status="exact",
            method="grammar_function",
            confidence=1.0,
            explanation=str((entry or {}).get("explanation") or "表否定"),
            word_class="adv.",
            count=int((entry or {}).get("count") or 0),
            variety=int((entry or {}).get("variety") or 0),
            note="已将 Nai 识别为通用否定功能词，并等待上下文确定中文形式。",
        )
        token["syntax_role"] = "negation_marker"
        return token

    @staticmethod

    def _negative_modal_form(target: str) -> str:
        """Return the idiomatic negative form for a preceding Chinese modal."""
        compact = re.sub(r"[，,；;].*$", "", str(target or "").strip())
        forms = {
            "能": "不能", "能够": "不能", "可以": "不可以",
            "会": "不会", "将会": "不会", "将": "将不",
            "是": "不是", "有": "没有", "存在": "不存在",
        }
        return forms.get(compact, "")

    def _resolve_alician_negations(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Resolve Nai from local predicate context before general reordering."""
        resolved = list(tokens)
        index = 0
        while index < len(resolved):
            token = resolved[index]
            if str(token.get("source") or "").casefold() != "nai":
                index += 1
                continue

            previous = resolved[index - 1] if index > 0 else None
            following = resolved[index + 1] if index + 1 < len(resolved) else None
            if previous and previous.get("status") == "punct":
                previous = None
            if following and following.get("status") == "punct":
                following = None

            previous_source = str((previous or {}).get("source") or "").casefold()
            previous_target = str(
                (previous or {}).get("resolved_target")
                or (previous or {}).get("target")
                or ""
            )
            following_source = str((following or {}).get("source") or "").casefold()
            following_target = str((following or {}).get("target") or "")
            following_family = self._syntax_family(following) if following else ""
            previous_family = self._syntax_family(previous) if previous else ""

            clause_start = index
            while clause_start > 0 and resolved[clause_start - 1].get("status") != "punct":
                clause_start -= 1
            clause_end = index + 1
            while clause_end < len(resolved) and resolved[clause_end].get("status") != "punct":
                clause_end += 1
            emphatics = [
                item for item in resolved[clause_start:clause_end]
                if str(item.get("target") or "").startswith("一定")
                and str(item.get("source") or "").casefold() != "nai"
            ]

            # Chinese imperatives conventionally use “别”.
            if previous_source == "poet" or previous_target.startswith("请"):
                token["resolved_target"] = "别"
                token["negation_form_reason"] = "imperative"
            elif emphatics:
                token["resolved_target"] = "绝不"
                token["negation_form_reason"] = "emphatic_negation"
                for emphatic in emphatics:
                    emphatic["omit_from_result"] = True
            else:
                modal = self._negative_modal_form(previous_target)
                if previous and previous_family == "v" and modal:
                    previous["resolved_target"] = modal
                    token["omit_from_result"] = True
                    token["negation_form_reason"] = "preceding_modal_or_copula"
                    if modal == "不是" and following:
                        nominal_candidates = [
                            entry
                            for entry in self._word_by_lower.get(following_source, [])
                            if self._pos_family(entry.get("word_class", "")) == "n"
                        ]
                        if nominal_candidates:
                            nominal = min(
                                nominal_candidates,
                                key=lambda entry: (
                                    entry.get("sense_order", 1),
                                    -entry.get("count", 0),
                                ),
                            )
                            replacement = self._entry_to_chinese_token(
                                nominal,
                                str(following.get("source") or ""),
                                "exact",
                                "negation_context_sense",
                            )
                            replacement["note"] = "已按否定系词结构选择名词义项。"
                            resolved[index + 1] = replacement
                elif (
                    following_source in {"aihel", "dilem"}
                    or following_target.startswith(("有", "存在"))
                ):
                    token["resolved_target"] = (
                        "不" if following_target.startswith("存在") else "没"
                    )
                    token["negation_form_reason"] = "existence_or_possession"
                elif following_family in {"v", "adj", "adv"}:
                    token["resolved_target"] = "不"
                    token["negation_form_reason"] = "predicate"
                elif following and following_family in {"n", "pron"}:
                    token["resolved_target"] = "无"
                    token["negation_form_reason"] = "nominal_absence"
                elif previous and previous_family in {"n", "pron"}:
                    # Post-nominal Nai expresses absence (“Ween Nai” = no
                    # end).  Chinese places the existential negative first.
                    token["resolved_target"] = "没有"
                    token["negation_form_reason"] = "post_nominal_absence"
                    resolved[index - 1:index + 1] = [token, previous]
                else:
                    token["resolved_target"] = "不"
                    token["negation_form_reason"] = "generic"

            token["note"] = (
                "已按相邻谓词和句法位置解析 Nai 的中文否定形式。"
            )
            index += 1
        return resolved

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
        templates = list(self._no_class_templates.get(str(word or "").casefold()) or [])
        for entry in candidates:
            if (
                self._template_arity(entry["explanation"]) > 0
                and entry not in templates
            ):
                templates.append(entry)
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
