from __future__ import annotations

import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from webui_backend.dictionary_service import _lev_ratio
from webui_backend.writing_config import ConfigManager
from webui_backend.writing_database import DatabaseManager
from webui_backend.writing_highlight import HighlightManager
from webui_backend.writing_checker import WordChecker


class VirtualTextArea:
    def __init__(self, text: str):
        self.text = text or ""
        self._tk_text = self.text if self.text.endswith("\n") else self.text + "\n"
        self._line_offsets = self._build_line_offsets(self._tk_text)
        self.tags: Dict[str, List[Tuple[int, int]]] = {"unknown": [], "lowstat": []}

    @staticmethod
    def _build_line_offsets(text: str) -> List[int]:
        offsets = [0]
        for index, char in enumerate(text):
            if char == "\n":
                offsets.append(index + 1)
        return offsets

    def get(self, start: str, end: str) -> str:
        _ = (start, end)
        return self._tk_text

    def tag_remove(self, tag_name: str, start: str, end: str) -> None:
        _ = (start, end)
        if tag_name in self.tags:
            self.tags[tag_name] = []

    def tag_add(self, tag_name: str, start: str, end: str) -> None:
        if tag_name not in self.tags:
            self.tags[tag_name] = []
        start_offset = self._index_to_offset(start)
        end_offset = self._index_to_offset(end)
        if end_offset < start_offset:
            start_offset, end_offset = end_offset, start_offset
        if start_offset == end_offset:
            return
        self.tags[tag_name].append((start_offset, end_offset))

    def update_idletasks(self) -> None:
        return

    def _index_to_offset(self, index: str) -> int:
        if index == "end":
            return len(self._tk_text)
        if "." not in index:
            return 0
        line_part, col_part = index.split(".", 1)
        try:
            line = max(1, int(line_part))
            col = max(0, int(col_part))
        except Exception:
            return 0
        line_index = line - 1
        if line_index >= len(self._line_offsets):
            return len(self._tk_text)
        base_offset = self._line_offsets[line_index]
        return min(len(self._tk_text), base_offset + col)


class WritingAssistantService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.highlight_manager = HighlightManager(self.config_manager)
        self._status_message = ""
        self.reload_known_words()

    def reload_known_words(self) -> str:
        with self._lock:
            self._status_message = self.highlight_manager.load_known_words_from_db(self.db_manager)
            return self._status_message

    def get_status_message(self) -> str:
        with self._lock:
            return self._status_message

    def get_settings(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "strict_case": bool(self.config_manager.get("strict_case", True)),
                "max_undo_steps": int(self.config_manager.get("max_undo_steps", 100)),
                "excluded_words": list(self.config_manager.get("excluded_words", [])),
                "dictionary_format_enabled": bool(self.config_manager.get("dictionary_format_enabled", False)),
                "dictionary_format_separators": list(
                    self.config_manager.get("dictionary_format_separators", [":", "："]) or []
                ),
            }

    def save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            strict_case = bool(settings.get("strict_case", self.config_manager.get("strict_case", True)))
            try:
                max_undo_steps = int(settings.get("max_undo_steps",
                    self.config_manager.get("max_undo_steps", 100)))
            except Exception:
                max_undo_steps = int(self.config_manager.get("max_undo_steps", 100))
            max_undo_steps = max(1, min(1000, max_undo_steps))
            excluded_words = settings.get("excluded_words", self.config_manager.get("excluded_words", []))
            if not isinstance(excluded_words, list):
                excluded_words = []
            normalized_excluded = []
            seen = set()
            for value in excluded_words:
                word = str(value).strip()
                if not word or word in seen:
                    continue
                seen.add(word)
                normalized_excluded.append(word)
            dictionary_format_enabled = bool(settings.get(
                "dictionary_format_enabled",
                self.config_manager.get("dictionary_format_enabled", False)
            ))
            separators = settings.get(
                "dictionary_format_separators",
                self.config_manager.get("dictionary_format_separators", [":", "："])
            )
            if isinstance(separators, str):
                separators = [part.strip() for part in re.split(r"[\n,，]+", separators)]
            if not isinstance(separators, list):
                separators = []
            normalized_separators = []
            seen_separators = set()
            for value in separators:
                separator = str(value).strip()
                if not separator or separator in seen_separators:
                    continue
                seen_separators.add(separator)
                normalized_separators.append(separator)
            self.config_manager.set("strict_case", strict_case)
            self.config_manager.set("max_undo_steps", max_undo_steps)
            self.config_manager.set("excluded_words", normalized_excluded)
            self.config_manager.set("dictionary_format_enabled", dictionary_format_enabled)
            self.config_manager.set("dictionary_format_separators", normalized_separators)
            self.config_manager.save_config()
            self.reload_known_words()
            return {
                "ok": True, "message": "设置已保存。",
                "settings": self.get_settings(), "status": self._status_message,
            }

    def check_text(self, text: str) -> Dict[str, Any]:
        with self._lock:
            area = VirtualTextArea(text or "")
            checker = WordChecker(None, area, self.highlight_manager, self.config_manager)
            checker.reset_state()
            unknown_count = checker.check_words() or 0
            unknown_ranges = sorted(area.tags.get("unknown", []), key=lambda item: (item[0], item[1]))
            lowstat_ranges = sorted(area.tags.get("lowstat", []), key=lambda item: (item[0], item[1]))
            unknowns, lowstats = self.highlight_manager.categorize_sidebar_items()
            ordered = self.highlight_manager.sort_sidebar_items(unknowns, lowstats)
            sidebar_items = []
            for _, key, info in ordered:
                display_word = info.get("display", key)
                stats_key = display_word if self.config_manager.get("strict_case") else str(display_word).lower()
                count, variety = self.highlight_manager.word_stats.get(stats_key, (0, 0))
                sidebar_items.append({
                    "key": key, "display": display_word,
                    "type": info.get("type", "unknown"),
                    "pos": int(info.get("pos", 0)),
                    "reasons": sorted(list(info.get("reasons", set()))),
                    "count": int(count), "variety": int(variety),
                })
            strict_label = "严格区分大小写" if self.config_manager.get("strict_case") else "不区分大小写"
            status_text = (
                f"状态：已检查 - 未知词 {unknown_count} 个 - 已加载 "
                f"{len(self.highlight_manager.known_words)} 个已知词（{strict_label}）"
            )
            return {
                "ok": True, "unknown_count": int(unknown_count),
                "unknown_ranges": unknown_ranges, "lowstat_ranges": lowstat_ranges,
                "sidebar_items": sidebar_items, "status": status_text,
            }

    def lookup_explanations(self, selected_text: str) -> Dict[str, Any]:
        text = (selected_text or "").strip()
        if not text:
            return {"ok": False, "message": "请选择要查询的内容。", "explanations": [], "similar_words": []}
        with self._lock:
            explanations: Dict[str, Dict[str, str]] = {}
            similar_words: Dict[str, Dict[str, Any]] = {}
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT PHRASE FROM phrase")
            all_phrases = [row[0] for row in cursor.fetchall()]
            all_phrases.sort(key=len, reverse=True)
            cursor.execute("SELECT words FROM dictionary_headwords")
            all_words = [row[0] for row in cursor.fetchall()]
            strict_case = bool(self.config_manager.get("strict_case"))
            remaining_text = text
            matched_phrases: List[str] = []
            for phrase in all_phrases:
                if phrase in remaining_text:
                    matched_phrases.append(phrase)
                    remaining_text = remaining_text.replace(phrase, " ")
            for phrase in matched_phrases:
                query = "SELECT explanation FROM phrase WHERE PHRASE = ?" if strict_case else \
                    "SELECT explanation FROM phrase WHERE LOWER(PHRASE) = LOWER(?)"
                cursor.execute(query, (phrase,))
                result = cursor.fetchone()
                explanations[phrase] = {
                    "part_of_speech": "phrase",
                    "explanation": result[0] if result else "未找到释义",
                }
            remaining_words = re.findall(r"\b\w+\b", remaining_text)
            for word in remaining_words:
                if not word.strip():
                    continue
                query = "SELECT display_explanation, display_class FROM dictionary_headwords WHERE words = ?" if strict_case else \
                    "SELECT display_explanation, display_class FROM dictionary_headwords WHERE LOWER(words) = LOWER(?)"
                cursor.execute(query, (word,))
                result = cursor.fetchone()
                if result:
                    explanations[word] = {
                        "part_of_speech": result[1] or "",
                        "explanation": result[0] or "未找到释义",
                    }
                    continue
                explanations[word] = {"part_of_speech": "", "explanation": "未找到释义"}
                best_match, best_score = None, 0.0
                for dict_word in all_words:
                    score = _lev_ratio(word, dict_word) if strict_case else _lev_ratio(word.lower(), dict_word.lower())
                    if score > best_score and score > 0.6:
                        best_score, best_match = score, dict_word
                if best_match:
                    q2 = "SELECT display_explanation, display_class FROM dictionary_headwords WHERE words = ?" if strict_case else \
                        "SELECT display_explanation, display_class FROM dictionary_headwords WHERE LOWER(words) = LOWER(?)"
                    cursor.execute(q2, (best_match,))
                    sr = cursor.fetchone()
                    if sr:
                        similar_words[word] = {
                            "similar_word": best_match,
                            "part_of_speech": sr[1] or "",
                            "explanation": sr[0] or "未找到释义",
                            "score": round(best_score, 4),
                        }
            if not explanations:
                q = "SELECT display_explanation, display_class FROM dictionary_headwords WHERE words = ?" if strict_case else \
                    "SELECT display_explanation, display_class FROM dictionary_headwords WHERE LOWER(words) = LOWER(?)"
                cursor.execute(q, (text,))
                result = cursor.fetchone()
                explanations[text] = {
                    "part_of_speech": (result[1] or "") if result else "",
                    "explanation": (result[0] or "未找到释义") if result else "未找到释义",
                }
            explanation_items = [
                {
                    "word": key,
                    "part_of_speech": value.get("part_of_speech", ""),
                    "explanation": value.get("explanation", "未找到释义"),
                }
                for key, value in explanations.items()
            ]
            similar_items = [
                {"word": key, "similar_word": value["similar_word"],
                 "part_of_speech": value.get("part_of_speech", ""),
                 "explanation": value["explanation"], "score": value["score"]}
                for key, value in similar_words.items()
            ]
            return {"ok": True, "message": "", "explanations": explanation_items, "similar_words": similar_items}

    def close(self) -> None:
        with self._lock:
            self.db_manager.close_connection()
