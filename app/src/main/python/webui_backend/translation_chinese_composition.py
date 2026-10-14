from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from webui_backend.translation_common import (
    _CHINESE_COMPOUND_CONTENT_FAMILIES,
    _CHINESE_COMPOUND_HEAD_FAMILIES,
    _CHINESE_COMPOUND_MAX_LENGTH,
    _CHINESE_COMPOUND_MODIFIER_FAMILIES,
    _CHINESE_FUNCTION_PARTICLES,
    _CHINESE_NON_COMPOSITIONAL_COMPOUNDS,
)


class ChineseCompositionMixin:
    """Resolve fluent Chinese particles and compositional compounds.

    The dictionary glosses are short and song-derived, so a natural sentence
    such as “下着大雨” matches neither 着 (an aspect particle) nor 大雨 (a
    transparent modifier+head compound) even though 大 and 雨 both exist.  This
    layer keeps the exact-match path untouched and only contributes when a
    segmented word would otherwise be unknown:

    * function particles with no lexical entry are neutralized or mapped onto
      an attested Alician function word;
    * a compound is decomposed into known morphemes only when the whole word is
      absent, every piece is a content word, the last piece is a nominal or
      verbal head, and the word is not a lexicalized idiom.

    Every generated token is marked ``approximate`` with a visible note, so a
    compositional guess is never confused with a dictionary hit.
    """

    def _chinese_particle_token(self, word: str) -> Optional[Dict[str, Any]]:
        """Neutralize a Chinese function particle which has no lexical entry."""
        if not self._enable_composition:
            return None
        source = str(word or "").strip()
        if not source or source in self._term_candidates:
            return None
        particle = _CHINESE_FUNCTION_PARTICLES.get(source)
        if particle is None:
            return None
        target, role = particle
        if not target:
            token = self._token(
                source=source,
                target="",
                status="exact",
                method="chinese_function_particle",
                confidence=1.0,
                word_class="particle",
                note="该中文虚词只承担语法功能，爱丽丝语无需对应词元，已省略。",
            )
            token["syntax_role"] = role
            token["omit_from_result"] = True
            return token
        token = self._grammar_function_token(source, target)
        token["method"] = "chinese_function_particle"
        token["syntax_role"] = role
        token["note"] = "按已证实的爱丽丝语功能词对齐中文虚词。"
        return token

    def _expand_chinese_word(self, word: str) -> List[Dict[str, Any]]:
        """Resolve one segmented word into one or more tokens."""
        particle = self._chinese_particle_token(word)
        if particle is not None:
            return [particle]
        compound = self._compose_chinese_compound(word)
        if compound is not None:
            return compound
        return [self._translate_segmented_chinese_word(word)]

    def _compose_chinese_compound(
        self, word: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Decompose an unknown Chinese compound into known morphemes."""
        if not self._enable_composition:
            return None
        source = str(word or "").strip()
        if not source or len(source) < 2 or len(source) > _CHINESE_COMPOUND_MAX_LENGTH:
            return None
        if source in self._term_candidates:
            return None
        if source in _CHINESE_NON_COMPOSITIONAL_COMPOUNDS:
            return None
        if self._negative_form_at(source, 0) == source:
            return None
        if self._is_lexicalized_negation_at(source, 0):
            return None
        if self._erhua_base_form(source):
            return None
        if self._translate_chinese_productive_morphology(source) is not None:
            return None
        if self._use_semantic_expansions:
            alias, _, _, _ = self._find_semantic_expansion_candidate(source)
            if alias is not None:
                return None

        pieces = self._best_compound_decomposition(source)
        if pieces is None:
            return None

        resolved: List[Tuple[str, Dict[str, Any], str]] = []
        for piece in pieces:
            entry, family = self._compound_piece_entry(piece)
            if entry is None or family not in _CHINESE_COMPOUND_CONTENT_FAMILIES:
                return None
            resolved.append((piece, entry, family))
        families = [family for _, _, family in resolved]
        if families[-1] not in _CHINESE_COMPOUND_HEAD_FAMILIES:
            return None
        if families[0] not in _CHINESE_COMPOUND_MODIFIER_FAMILIES:
            return None
        # Adj+Adj and verb-final compounds without a nominal head are usually
        # reordered idioms rather than transparent modifier+head words.
        if len(resolved) == 2 and families[0] == "adj" and families[1] == "adj":
            return None
        if len(set(pieces)) == 1 and len(pieces) > 1:
            return None

        tokens: List[Dict[str, Any]] = []
        join = " + ".join(pieces)
        for position, (piece, entry, family) in enumerate(resolved):
            token = self._entry_to_token(piece, entry, "approximate")
            token.update({
                "method": "compound_decomposition",
                "confidence": 0.55,
                "compound_source": source,
                "compound_pieces": list(pieces),
                "compound_position": position,
                "note": (
                    f"爱丽丝语没有“{source}”的整词词条，已按中文构词法拆成"
                    f"{join} 组合匹配，请留意是否与原意相符。"
                ),
            })
            tokens.append(token)
        return tokens

    def _best_compound_decomposition(self, word: str) -> Optional[List[str]]:
        """Return the fewest-piece all-exact segmentation of ``word``."""
        length = len(word)
        best: List[Optional[List[str]]] = [None] * (length + 1)
        best[0] = []
        for start in range(length):
            prefix = best[start]
            if prefix is None:
                continue
            for end in range(length, start, -1):
                piece = word[start:end]
                if piece not in self._term_candidates:
                    continue
                candidate = prefix + [piece]
                current = best[end]
                if current is None or self._compound_order_key(
                    candidate
                ) < self._compound_order_key(current):
                    best[end] = candidate
        result = best[length]
        if result is None or len(result) < 2:
            return None
        return result

    def _compound_piece_entry(
        self, piece: str,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        candidates = self._term_candidates.get(piece) or []
        if not candidates:
            return None, ""
        entry = self._choose_candidate(candidates, piece)
        return entry, self._pos_family(str(entry.get("word_class") or ""))

    @staticmethod
    def _compound_order_key(pieces: List[str]) -> Tuple[int, Tuple[int, ...]]:
        # Prefer the segmentation with the fewest pieces, then the one whose
        # earlier pieces are the longest (longest-match first).
        return (len(pieces), tuple(-len(piece) for piece in pieces))
