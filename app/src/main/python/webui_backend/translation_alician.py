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

    def _alician_grammar_token(
        self,
        source: str,
        canonical_word: str,
        target: str,
        role: str,
        word_class: str = "adv.",
        omit: bool = False,
    ) -> Dict[str, Any]:
        """Create a semantic token for an attested Alician function word."""
        entry = self._best_word_entry(canonical_word)
        token = self._token(
            source=source,
            target=target,
            status="exact",
            method="grammar_function",
            confidence=1.0,
            explanation=str((entry or {}).get("explanation") or role),
            word_class=word_class,
            count=int((entry or {}).get("count") or 0),
            variety=int((entry or {}).get("variety") or 0),
            note="已按语料和词典中明示的语法功能解析，未直译元数据。",
        )
        token["syntax_role"] = role
        if omit:
            token["omit_from_result"] = True
        return token

    @staticmethod
    def _next_alician_word_index(parts: List[str], start: int) -> int:
        index = start
        while index < len(parts) and parts[index].isspace():
            index += 1
        if index < len(parts) and re.fullmatch(r"[A-Za-z][A-Za-z'-]*", parts[index]):
            return index
        return -1

    @staticmethod
    def _clean_plural_explanation(explanation: str) -> str:
        cleaned = re.sub(
            r"^\s*[（(]\s*pl\.?\s*[）)]\s*",
            "",
            str(explanation or ""),
            flags=re.IGNORECASE,
        ).strip()
        return cleaned or str(explanation or "").strip()

    def _match_alician_productive_morphology(
        self, parts: List[str], start: int,
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """Recognize attached or spaced qls/lait forms before plain lookup."""
        source_word = parts[start]
        lower = source_word.casefold()
        stem = source_word
        suffix = ""
        end = start + 1

        for candidate in ("lait", "qls"):
            if lower.endswith(candidate) and len(lower) > len(candidate):
                stem = source_word[:-len(candidate)]
                suffix = candidate
                break
        if not suffix:
            suffix_index = self._next_alician_word_index(parts, start + 1)
            if suffix_index >= 0:
                candidate = parts[suffix_index].casefold()
                if candidate in {"qls", "lait"}:
                    suffix = candidate
                    end = suffix_index + 1
        if not suffix:
            return None, start

        expected_family = "n" if suffix == "qls" else "adj"
        result_family = "n." if suffix == "qls" else "adv."
        full_word = f"{stem}{suffix}"
        full_candidates = [
            entry for entry in (self._word_by_lower.get(full_word.casefold()) or [])
            if self._pos_family(entry.get("word_class", ""))
            in ({"n", "pron"} if suffix == "qls" else {"adv"})
        ]
        base_candidates = [
            entry for entry in (self._word_by_lower.get(stem.casefold()) or [])
            if self._pos_family(entry.get("word_class", "")) == expected_family
        ]
        if not full_candidates and not base_candidates:
            return None, start
        full_entry = min(
            full_candidates,
            key=lambda entry: (entry.get("sense_order", 1), -entry.get("count", 0)),
        ) if full_candidates else None
        base_entry = min(
            base_candidates,
            key=lambda entry: (entry.get("sense_order", 1), -entry.get("count", 0)),
        ) if base_candidates else None
        entry = full_entry or base_entry
        assert entry is not None

        if suffix == "qls":
            target = self._clean_plural_explanation(
                str((full_entry or base_entry or {}).get("explanation") or "")
            )
        else:
            full_target = str((full_entry or {}).get("explanation") or "").strip()
            if full_target and full_target not in {"后缀", "形容词变副词", "也可分开写"}:
                target = full_target
            else:
                target = str((base_entry or {}).get("explanation") or "").strip()
                target = re.sub(r"的$", "地", target) if target.endswith("的") else f"{target}地"

        source = "".join(parts[start:end]).strip()
        previous_index = start - 1
        while previous_index >= 0 and parts[previous_index].isspace():
            previous_index -= 1
        attested_three_eyes = (
            suffix == "qls"
            and stem.casefold() == "ran"
            and previous_index >= 0
            and parts[previous_index].casefold() == "tri"
        )
        if attested_three_eyes:
            target = "只眼睛"
        elif suffix == "qls" and target in {
            "人", "朋友", "天使", "旅人", "演员", "幽灵", "亡灵", "妖精", "怪物",
        }:
            target = f"{target}们"
        target = self._clean_surface_gloss(target)
        unresolved = not target
        token = self._token(
            source=source,
            target=target or f"〔{source}〕",
            status="unknown" if unresolved else "exact",
            method=(
                "unresolved_productive_morphology"
                if unresolved
                else "plural_suffix" if suffix == "qls" else "adverbial_suffix"
            ),
            confidence=0.0 if unresolved else 1.0,
            explanation=str(entry.get("explanation") or ""),
            word_class=result_family,
            count=int(entry.get("count") or 0),
            variety=int(entry.get("variety") or 0),
            note=(
                "完整派生词只有不确定性占位，保留为未解决词而不把“(?)”输出为译文。"
                if unresolved else
                "已识别名词后的 qls（含连写形式）并按复数名词解释。"
                if suffix == "qls"
                else "已识别形容词后的 lait（含连写形式）并转换为副词。"
            ),
        )
        token["normalized_source"] = full_word
        if attested_three_eyes:
            token["method"] = "attested_classifier_phrase"
            token["note"] = "已按 Tri Ran qls 的对齐金标补出中文量词“只”。"
        token["morphology"] = {
            "stem": stem,
            "suffix": suffix,
            "rule": "plural" if suffix == "qls" else "adjective_to_adverb",
            "attested_form": bool(full_entry),
        }
        return token, end

    def _alician_prefixed_negation_token(self, source: str) -> Optional[Dict[str, Any]]:
        """Resolve productive Dis- only when the complete form is not lexical."""
        lower = source.casefold()
        if not lower.startswith("dis") or len(source) <= 3:
            return None
        if self._word_by_lower.get(lower):
            return None
        stem = source[3:]
        candidates = [
            entry for entry in (self._word_by_lower.get(stem.casefold()) or [])
            if self._pos_family(entry.get("word_class", "")) == "v"
        ]
        if not candidates:
            return None
        entry = min(
            candidates,
            key=lambda item: (item.get("sense_order", 1), -item.get("count", 0)),
        )
        token = self._entry_to_chinese_token(
            entry, source, "exact", "negative_prefix",
        )
        token["target"] = f"不{entry['explanation']}"
        token["normalized_source"] = f"Dis-{stem}"
        token["morphology"] = {"prefix": "Dis", "stem": stem, "rule": "verbal_negation"}
        token["note"] = "已按 Dis- 动词否定前缀解析。"
        return token

    def _attested_lexical_override_token(self, source: str) -> Optional[Dict[str, Any]]:
        overrides = {
            "alice": ("爱丽丝", "n.", "两首歌中的独立对齐句均将 Alice 用作人名“爱丽丝”。"),
            "xianya": ("他们", "pron.", "对齐语料与官方译文均作 they/those。"),
            "qllsiim": ("我们", "pron.", "对齐语料与官方译文均作 we/us。"),
            "qllsiimtiel": ("我们自己", "pron.", "对齐语料与官方译文均作 ourselves。"),
            "syeillas": ("天使们", "n.", "词典与语料均标明为 Syeilla 的复数。"),
            "enes": ("人们", "n.", "词典明确标注的 -s 复数形式。"),
            "haols": ("双手", "n.", "词典明确标注的 -s 复数形式。"),
            "storys": ("故事", "n.", "词典明确标注的 -s 复数形式。"),
            "venesenes": ("幽灵", "n.", "词典明确标注的 -s 复数形式。"),
            "viazulus": ("旅人们", "n.", "词典明确标注的 -s 复数形式。"),
            "vinshellms": ("噩梦", "n.", "词典明确标注的 -s 复数形式。"),
        }
        override = overrides.get(source.casefold())
        if override is None:
            return None
        target, word_class, note = override
        token = self._alician_grammar_token(
            source, source, target, "attested_lexical_override", word_class,
        )
        token["method"] = "attested_lexical_override"
        token["note"] = note
        return token

    def _attested_transcription_alias_token(
        self, source: str,
    ) -> Optional[Dict[str, Any]]:
        """Resolve a small, corpus-attested spelling whitelist.

        Exact dictionary words always win.  This is essential for forms such
        as Yine, which is a real noun even though one transcription source has
        also used it for Yien.
        """
        if any(
            entry.get("kind") == "word"
            for entry in self._word_by_lower.get(source.casefold(), [])
        ):
            return None
        aliases = {
            "lefz": ("Lef", 0.95, "两首歌的独立对齐句均将 Lefz 用作 Lef 的转写变体。"),
            "yullk": ("Yulleia", 0.85, "两首歌支持 Yullk 为 Yulleia 的转写变体。"),
            "orb": ("Ord", 0.8, "转写白名单将 Orb 规范化为 Ord。"),
            "pole": ("Poet", 0.8, "转写白名单将 Pole 规范化为 Poet。"),
            "ehm": ("Eem", 0.8, "转写白名单将 Ehm 规范化为 Eem。"),
            "loqcia": ("Loqcka", 0.8, "转写白名单将 Loqcia 规范化为 Loqcka。"),
            "qulm": ("Quim", 0.8, "转写白名单将 Qulm 规范化为 Quim。"),
            "viccla": ("Ticcla", 0.8, "转写白名单将 Viccla 规范化为 Ticcla。"),
        }
        alias = aliases.get(source.casefold())
        if alias is None:
            return None
        canonical, confidence, note = alias
        entry = self._best_word_entry(canonical)
        if entry is None:
            return None
        token = self._entry_to_chinese_token(
            entry, source, "approximate", "attested_transcription_alias",
        )
        token["normalized_source"] = canonical
        token["confidence"] = confidence
        token["note"] = note
        return token

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
            if part.isdigit():
                tokens.append(self._token(
                    source=part,
                    target=part,
                    status="kept",
                    method="number",
                    confidence=1.0,
                    word_class="num.",
                    note="数字按原样保留，不作为标点切断句法。",
                ))
                i += 1
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", part):
                punctuation = self._punct_token(part)
                normalized_punctuation = re.sub(r"\.{3,}", "……", part)
                punctuation["target"] = normalized_punctuation.translate(str.maketrans({
                    "?": "？",
                    "!": "！",
                    ",": "，",
                    ";": "；",
                    ":": "：",
                    ".": "。",
                }))
                tokens.append(punctuation)
                i += 1
                continue

            morphology, morphology_end = self._match_alician_productive_morphology(
                parts, i,
            )
            if morphology is not None:
                tokens.append(morphology)
                i = morphology_end
                continue

            lexical_override = self._attested_lexical_override_token(part)
            if lexical_override is not None:
                tokens.append(lexical_override)
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

            lower_part = part.casefold()
            if lower_part in {"ol", "ob"}:
                tokens.append(self._alician_grammar_token(
                    part,
                    part,
                    "已" if lower_part == "ol" else "已经",
                    "perfect_aspect_marker" if lower_part == "ol" else "pluperfect_aspect_marker",
                ))
                i += 1
                continue
            if lower_part == "qleea":
                tokens.append(self._alician_grammar_token(
                    part, part, "将会", "prospective_auxiliary", "adv.",
                ))
                i += 1
                continue
            if lower_part == "ou":
                tokens.append(self._alician_grammar_token(
                    part, part, "的", "possessive_marker", "prep.",
                ))
                i += 1
                continue
            if lower_part == "ord":
                tokens.append(self._alician_grammar_token(
                    part, part, "用", "passive_agent_marker", "prep.",
                ))
                i += 1
                continue
            if lower_part in {"yiela", "yiep"}:
                tokens.append(self._alician_grammar_token(
                    part,
                    part,
                    "来" if lower_part == "yiela" else "请",
                    "imperative_clause_marker",
                    "adv.",
                ))
                i += 1
                continue
            if lower_part == "phier":
                tokens.append(self._alician_grammar_token(
                    part, part, "请", "imperative_marker",
                ))
                i += 1
                continue
            if lower_part == "poutie":
                tokens.append(self._alician_grammar_token(
                    part, part, "当", "temporal_or_conditional_marker", "conj.",
                ))
                i += 1
                continue
            if lower_part == "imeila":
                tokens.append(self._alician_grammar_token(
                    part, part, "即使", "concessive_marker", "conj.",
                ))
                i += 1
                continue
            if lower_part == "imm":
                tokens.append(self._alician_grammar_token(
                    part, part, "在", "locative_marker", "prep.",
                ))
                i += 1
                continue
            circumfix = {
                "arch": ("在", "上"),
                "arche": ("到", "上"),
                "lim": ("在", "下"),
                "alfloul": ("在", "周围"),
                "pllia": ("在", "前"),
                "uleim": ("在", "深处的"),
            }.get(lower_part)
            if circumfix is not None:
                opener, closer = circumfix
                token = self._alician_grammar_token(
                    part, part, opener, "locative_circumfix_marker", "prep.",
                )
                token["circumfix_closer"] = closer
                tokens.append(token)
                i += 1
                continue
            if lower_part in {"forle", "winde"}:
                token = self._alician_grammar_token(
                    part, part, "在", "clausal_circumfix_marker", "prep.",
                )
                token["circumfix_closer"] = "之前"
                tokens.append(token)
                i += 1
                continue
            simple_slot = {
                "folme": ("从", "source_preposition", "prep."),
                "lid": ("在", "locative_preposition", "prep."),
                "elied": ("直到", "temporal_boundary_marker", "conj."),
                "tozlom": ("当", "temporal_clause_marker", "conj."),
                "ijlim": ("当", "temporal_clause_marker", "conj."),
            }.get(lower_part)
            if simple_slot is not None:
                target, role, word_class = simple_slot
                tokens.append(self._alician_grammar_token(
                    part, part, target, role, word_class,
                ))
                i += 1
                continue
            if lower_part == "mols":
                tokens.append(self._alician_grammar_token(
                    part, part, "只", "focus_marker", "adv.",
                ))
                i += 1
                continue
            if lower_part == "osa":
                tokens.append(self._alician_grammar_token(
                    part, part, "也", "additive_focus_marker", "adv.",
                ))
                i += 1
                continue
            if lower_part == "baly":
                tokens.append(self._alician_grammar_token(
                    part, part, "总是", "habitual_adverb_marker", "adv.",
                ))
                i += 1
                continue
            if lower_part == "og":
                next_index = self._next_alician_word_index(parts, i + 1)
                if (
                    next_index >= 0
                    and parts[next_index].casefold() == "amiy"
                ):
                    tokens.append(self._alician_grammar_token(
                        part, part, "彼此", "reciprocal_marker", "adv.",
                    ))
                else:
                    tokens.append(self._token(
                        source=part,
                        target=f"〔{part}〕",
                        status="unknown",
                        method="unresolved_polyfunctional_marker",
                        confidence=0.0,
                        note=(
                            "Og 的两个独立对齐例语义冲突；仅 Og Amiy 可确定为互惠，"
                            "其他环境保持未决。"
                        ),
                    ))
                i += 1
                continue
            if lower_part in {"a", "es"}:
                tokens.append(self._alician_grammar_token(
                    part, part, "和", "coordinator", "conj.",
                ))
                i += 1
                continue
            if lower_part == "end":
                tokens.append(self._alician_grammar_token(
                    part, part, "", "relative_or_linker", "conj.", omit=True,
                ))
                i += 1
                continue
            if lower_part in {
                "en", "ta", "sii", "sip", "wei", "weiy", "dou", "endil",
            }:
                tokens.append(self._alician_grammar_token(
                    part, part, "", "semantically_light_particle", "conj.", omit=True,
                ))
                i += 1
                continue
            if lower_part == "iqyur":
                tokens.append(self._alician_grammar_token(
                    part, part, "", "honorific_marker", "", omit=True,
                ))
                i += 1
                continue
            if lower_part == "ra":
                tokens.append(self._alician_grammar_token(
                    part, part, "", "complement_clause_marker", "conj.", omit=True,
                ))
                i += 1
                continue
            if lower_part == "iy":
                tokens.append(self._alician_grammar_token(
                    part, part, "是", "topic_or_copula_marker", "v.",
                ))
                i += 1
                continue
            if lower_part in {"lend", "erikes"}:
                tokens.append(self._alician_grammar_token(
                    part, part, "是否", "yes_no_question_marker", "adv.",
                ))
                i += 1
                continue
            if lower_part == "crain":
                token = self._alician_grammar_token(
                    part, part, "不是吗？", "rhetorical_question_marker", "interj.",
                )
                token["note"] = "Crain 在两条例句中均为句末反问标记。"
                tokens.append(token)
                i += 1
                continue
            if lower_part == "iequim":
                tokens.append(self._alician_grammar_token(
                    part, part, "", "similative_auxiliary", "conj.", omit=True,
                ))
                i += 1
                continue
            if lower_part == "phim":
                tokens.append(self._alician_grammar_token(
                    part, part, "应该", "deontic_modal_marker", "adv.",
                ))
                i += 1
                continue
            if lower_part in {"qls", "lait"}:
                tokens.append(self._alician_grammar_token(
                    part, part, "", "unbound_morphology_marker", "", omit=True,
                ))
                i += 1
                continue
            if lower_part == "dis":
                next_index = self._next_alician_word_index(parts, i + 1)
                next_candidates = (
                    self._word_by_lower.get(parts[next_index].casefold()) or []
                    if next_index >= 0 else []
                )
                if any(
                    self._pos_family(entry.get("word_class", "")) == "v"
                    for entry in next_candidates
                ):
                    tokens.append(self._alician_grammar_token(
                        part, part, "不", "verbal_negation_marker",
                    ))
                    i += 1
                    continue

            prefixed_negation = self._alician_prefixed_negation_token(part)
            if prefixed_negation is not None:
                tokens.append(prefixed_negation)
                i += 1
                continue

            transcription_alias = self._attested_transcription_alias_token(part)
            if transcription_alias is not None:
                # Ord is structural and its first dictionary sense is only a
                # metalinguistic description, so preserve its grammar role.
                if transcription_alias.get("normalized_source") == "Ord":
                    transcription_alias = self._alician_grammar_token(
                        part, "Ord", "用", "passive_agent_marker", "prep.",
                    )
                    transcription_alias.update({
                        "status": "approximate",
                        "method": "attested_transcription_alias",
                        "confidence": 0.8,
                        "normalized_source": "Ord",
                        "note": "转写白名单将 Orb 规范化为 Ord。",
                    })
                tokens.append(transcription_alias)
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

            template_entry = self._sentence_template_entry(parts, i, part)
            preceding_role = str((tokens[-1] if tokens else {}).get("syntax_role") or "")
            earlier_role = str((tokens[-2] if len(tokens) > 1 else {}).get("syntax_role") or "")
            requires_verbal_complement = preceding_role in {
                "passive_marker",
                "perfect_aspect_marker",
                "pluperfect_aspect_marker",
                "deontic_modal_marker",
                "imperative_clause_marker",
                "imperative_marker",
                "verbal_negation_marker",
            } or (
                preceding_role == "negation_marker"
                and earlier_role == "passive_marker"
            )
            verbal_entry = next(
                (
                    candidate
                    for candidate in self._word_by_lower.get(part.casefold(), [])
                    if self._pos_family(candidate.get("word_class", "")) == "v"
                ),
                None,
            ) if requires_verbal_complement else None
            entry = (
                template_entry
                or verbal_entry
                or contextual_senses.get(i)
                or self._best_word_entry(part)
            )
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
                selected_family = self._pos_family(entry.get("word_class", ""))
                imperative_subject = (
                    preceding_role in {
                        "imperative_clause_marker", "imperative_marker",
                    }
                    and selected_family in {"n", "pron"}
                )
                if (
                    requires_verbal_complement
                    and verbal_entry is None
                    and not imperative_subject
                ):
                    token["lexical_word_class"] = token.get("word_class")
                    token["word_class"] = "v."
                    token["contextual_word_class"] = "v."
                    token["parse_method"] = "attested_predicate_context"
                    token["note"] = (
                        "该词虽仅以名词收录，但在被动、体貌、情态或祈使标记后"
                        "按语料中的谓词用法解析。"
                    )
                if template_entry is not None:
                    token["allow_template_resolution"] = True
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

        tokens = self._resolve_alician_function_words(tokens)
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

    @staticmethod
    def _local_alician_clause_bounds(
        tokens: List[Dict[str, Any]], index: int,
    ) -> Tuple[int, int]:
        """Return the local clause without crossing punctuation/connectors."""
        boundary_roles = {
            "coordinator", "complement_clause_marker", "relative_or_linker",
        }

        def is_boundary(token: Dict[str, Any]) -> bool:
            return (
                token.get("status") == "punct"
                or token.get("syntax_role") in boundary_roles
            )

        start = index
        while start > 0 and not is_boundary(tokens[start - 1]):
            start -= 1
        end = index + 1
        while end < len(tokens) and not is_boundary(tokens[end]):
            end += 1
        return start, end

    def _resolve_alician_function_words(
        self, tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Resolve polyfunctional particles from their local construction."""
        resolved = list(tokens)

        def neighbor(index: int, step: int) -> Optional[Dict[str, Any]]:
            position = index + step
            while 0 <= position < len(resolved):
                candidate = resolved[position]
                if candidate.get("status") == "punct":
                    return None
                if candidate.get("syntax_role") == "semantically_light_particle":
                    position += step
                    continue
                return candidate
            return None

        for index, token in enumerate(resolved):
            role = token.get("syntax_role")
            source = str(token.get("source") or "").casefold()
            if role == "coordinator" and source in {"a", "es"}:
                previous = neighbor(index, -1)
                following = neighbor(index, 1)
                previous_family = self._syntax_family(previous) if previous else ""
                following_source = str((following or {}).get("source") or "").casefold()
                if source == "a" and previous_family == "v" and following_source == "laiz":
                    token["resolved_target"] = ""
                    token["omit_from_result"] = True
                    token["syntax_role"] = "future_auxiliary_link"
                    if following is not None:
                        following["resolved_target"] = "将"
                        following["word_class"] = "adv."
                        following["syntax_role"] = "future_marker"
                        following["method"] = "grammar_function"
                        following["explanation"] = "动词 + a Laiz 构成将来时"
                        following["note"] = "已按动词 + a Laiz 将来时范式解析。"
                    continue
                following_family = self._syntax_family(following) if following else ""
                if not previous or not following:
                    token["resolved_target"] = ""
                    token["omit_from_result"] = True
                elif previous_family == "v" and following_family == "v":
                    token["resolved_target"] = "并"
                elif previous_family in {"n", "pron", "adj"} and following_family in {
                    "n", "pron", "adj",
                }:
                    token["resolved_target"] = "和"
                else:
                    token["resolved_target"] = "并"
                token["note"] = "已按相邻成分把 a 解析为并列/同时连接词或韵律填充。"
            elif role == "topic_or_copula_marker":
                clause_start, clause_end = self._local_alician_clause_bounds(
                    resolved, index,
                )
                preceding_clause = list(reversed(resolved[clause_start:index]))
                following_clause = resolved[index + 1:clause_end]
                has_verbal_predicate = any(
                    self._syntax_family(candidate) == "v"
                    and candidate.get("syntax_role") not in {
                        "perfect_aspect_marker",
                        "pluperfect_aspect_marker",
                        "passive_marker",
                    }
                    for candidate in preceding_clause + following_clause
                )
                if has_verbal_predicate:
                    token["resolved_target"] = ""
                    token["omit_from_result"] = True
                    token["copula_resolution"] = "topic_boundary"
                else:
                    token["resolved_target"] = "是"
                    token["copula_resolution"] = "nominal_predicate"
                token["note"] = "iy 已按同分句是否已有实义动词解析为话题边界或系词。"
            elif source == "aihel":
                _, clause_end = self._local_alician_clause_bounds(resolved, index)
                following_clause = resolved[index + 1:min(index + 5, clause_end)]
                locative = next(
                    (
                        candidate for candidate in following_clause
                        if candidate.get("syntax_role") == "locative_marker"
                    ),
                    None,
                )
                if locative is not None:
                    token["resolved_target"] = ""
                    token["omit_from_result"] = True
                    token["syntax_role"] = "existential_locative_auxiliary"
                    locative["resolved_target"] = "在"
                    token["note"] = "Aihel imm 已按存在/处所构式合并为中文“在”。"
            elif role == "prospective_auxiliary":
                clause_start, clause_end = self._local_alician_clause_bounds(
                    resolved, index,
                )
                before = resolved[clause_start:index]
                after = resolved[index + 1:clause_end]
                prior_ol = next(
                    (
                        candidate for candidate in reversed(before)
                        if str(candidate.get("source") or "").casefold() == "ol"
                    ),
                    None,
                )
                imperative = any(
                    candidate.get("syntax_role") in {
                        "imperative_clause_marker", "imperative_marker",
                    }
                    for candidate in before
                )
                concessive = any(
                    candidate.get("syntax_role") == "concessive_marker"
                    for candidate in before
                )
                conditional = any(
                    str(candidate.get("source") or "").casefold() == "quim"
                    for candidate in before
                )
                existing_future = next(
                    (
                        candidate for candidate in reversed(before)
                        if str(candidate.get("source") or "").casefold() == "vell"
                    ),
                    None,
                )
                deliberative_question = any(
                    str(candidate.get("source") or "").casefold() == "fevla"
                    for candidate in before
                )
                trailing_bai = next(
                    (
                        candidate for candidate in after
                        if str(candidate.get("source") or "").casefold() == "bai"
                    ),
                    None,
                )
                if deliberative_question and trailing_bai is not None:
                    token["resolved_target"] = ""
                    token["omit_from_result"] = True
                    trailing_bai["resolved_target"] = ""
                    trailing_bai["omit_from_result"] = True
                    token["note"] = (
                        "Fevla Qleea … Bai 的实证疑问句不表达未来完成，"
                        "已抑制冲突的“将会已经”。"
                    )
                elif prior_ol is not None:
                    emphatic = next(
                        (
                            candidate for candidate in after
                            if str(candidate.get("source") or "").casefold() == "foul"
                            and str(candidate.get("target") or "").startswith("一定")
                        ),
                        None,
                    )
                    prior_ol["resolved_target"] = "一定已经" if emphatic else "已经"
                    token["resolved_target"] = ""
                    token["omit_from_result"] = True
                    if emphatic is not None:
                        emphatic["resolved_target"] = ""
                        emphatic["omit_from_result"] = True
                    token["note"] = "ol Qleea 已按完成/强调语境解析，避免输出矛盾的“已将会”。"
                elif imperative:
                    trailing_quick = next(
                        (
                            candidate for candidate in after
                            if str(candidate.get("source") or "").casefold() == "falke"
                        ),
                        None,
                    )
                    if trailing_quick is not None:
                        token["resolved_target"] = ""
                        token["omit_from_result"] = True
                        trailing_quick["resolved_target"] = "快"
                        trailing_quick["syntax_role"] = "imperative_degree_marker"
                    else:
                        token["resolved_target"] = "快"
                        token["syntax_role"] = "imperative_degree_marker"
                    token["note"] = "祈使环境中的 Qleea 按催促/临近义解析。"
                elif concessive:
                    token["resolved_target"] = ""
                    token["omit_from_result"] = True
                    token["note"] = "让步从句中的未来性由中文语境表达，不机械输出“将会”。"
                elif existing_future is not None:
                    token["resolved_target"] = ""
                    token["omit_from_result"] = True
                    token["note"] = "同分句已有 Vell 表达未来性，Qleea 不再重复输出“将会”。"
                elif conditional:
                    token["resolved_target"] = "即将"
                    token["note"] = "条件从句中的 Qleea 按临近义解析为“即将”。"
            elif role == "temporal_or_conditional_marker":
                clause_start, _ = self._local_alician_clause_bounds(resolved, index)
                previous_clause = list(reversed(resolved[clause_start:index]))
                following = neighbor(index, 1)
                following_source = str((following or {}).get("source") or "").casefold()
                if any(
                    str(candidate.get("source") or "").casefold() == "brey"
                    for candidate in previous_clause
                ):
                    token["resolved_target"] = "正如"
                    token["poutie_resolution"] = "comparison"
                elif following_source in {"ell", "albel", "qleea", "noa"}:
                    token["resolved_target"] = "如果"
                    token["poutie_resolution"] = "conditional"
                elif following_source == "ani":
                    token["resolved_target"] = "随着"
                    token["poutie_resolution"] = "accompaniment"
                else:
                    token["resolved_target"] = "当"
                    token["poutie_resolution"] = "temporal_fallback"
                token["note"] = "Poutie 已按相邻构式解析为时间、条件、伴随或比较关系。"
        return resolved

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

            clause_start, clause_end = self._local_alician_clause_bounds(
                resolved, index,
            )
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
        templates = list(self._no_class_templates.get(str(word or "").casefold()) or [])
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
