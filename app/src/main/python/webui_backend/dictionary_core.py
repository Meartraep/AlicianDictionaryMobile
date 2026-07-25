from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional, Tuple


def _get_default_db_path() -> str:
    env_db = os.environ.get("ALICIAN_DB_PATH")
    if env_db:
        return os.path.abspath(env_db)
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "translated.db")
    return str(Path(__file__).resolve().parent.parent / "translated.db")


def _quote_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


class DictionaryConfig:
    REQUIRED_TABLES = {
        "dictionary": ["headword_id", "words", "explanation", "class", "sense_order"],
        "dictionary_headwords": ["words", "display_explanation", "display_class"],
        "songs": ["title", "lyric", "Album"],
        "phrase": ["PHRASE", "explanation"],
    }
    DB_NAME = _get_default_db_path()
    CURRENT_DB = DB_NAME


class HistoryManager:
    def __init__(self, file_path: str = "search_history.json", max_records: int = 10):
        self.file_path = file_path
        self.max_records = max_records
        self.history = self._load_history()

    def _load_history(self) -> List[str]:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    return history if isinstance(history, list) else []
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save_history(self) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add_record(self, record: str) -> None:
        if not record.strip():
            return
        if record in self.history:
            self.history.remove(record)
        self.history.insert(0, record)
        if len(self.history) > self.max_records:
            self.history = self.history[:self.max_records]
        self._save_history()

    def get_history(self) -> List[str]:
        return self.history.copy()

    def clear_history(self) -> None:
        self.history.clear()
        self._save_history()

    def delete_record(self, record: str) -> None:
        if record in self.history:
            self.history.remove(record)
            self._save_history()

    def delete_index(self, index: int) -> None:
        if 0 <= index < len(self.history):
            self.history.pop(index)
            self._save_history()


class DatabaseHandler:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
        self.last_error = ""

    def connect(self) -> bool:
        try:
            if self.conn is not None:
                try:
                    self.conn.execute("SELECT 1")
                    return True
                except sqlite3.Error:
                    self.close()

            if not self.db_name.startswith(":memory:") and not os.path.exists(self.db_name):
                self.last_error = f"数据库文件不存在: {self.db_name}"
                return False

            self.close()
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.conn.execute("PRAGMA cache_size = -1000")
            self.conn.execute("PRAGMA synchronous = OFF")
            self.cursor = self.conn.cursor()
            return self._verify_database_structure()
        except sqlite3.Error as exc:
            self.last_error = f"连接数据库失败: {exc}"
            self.close()
            return False

    def __del__(self):
        self.close()

    def _is_table_exists(self, table: str) -> bool:
        if not self.cursor:
            return False
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        return bool(self.cursor.fetchone())

    def _get_table_fields(self, table: str) -> List[str]:
        if not self.cursor:
            return []
        self.cursor.execute(f"PRAGMA table_info({_quote_identifier(table)})")
        return [row[1] for row in self.cursor.fetchall()]

    def _verify_table_fields(self, table: str, required_fields: List[str]) -> bool:
        actual_fields = self._get_table_fields(table)
        missing_fields = [field for field in required_fields if field not in actual_fields]
        if missing_fields:
            raise RuntimeError(f"{table}表缺少字段: {', '.join(missing_fields)}")
        return True

    def _verify_database_structure(self) -> bool:
        try:
            for table, required_fields in DictionaryConfig.REQUIRED_TABLES.items():
                if not self._is_table_exists(table):
                    raise RuntimeError(f"缺少{table}表")
                self._verify_table_fields(table, required_fields)
            return True
        except Exception as exc:
            self.last_error = f"数据库结构验证失败: {exc}"
            return False

    def search_words(
        self, query: str, is_exact: bool
    ) -> Tuple[List[Tuple[str, str, str]], List[Tuple[str, str, str]]]:
        if not self.cursor:
            return [], []
        if is_exact:
            self.cursor.execute(
                "SELECT words, display_explanation, display_class FROM dictionary_headwords WHERE words = ? LIMIT 20",
                (query,),
            )
            alice_res = self.cursor.fetchall()
            self.cursor.execute(
                "SELECT DISTINCT h.words, h.display_explanation, h.display_class "
                "FROM dictionary d JOIN dictionary_headwords h ON h.id = d.headword_id "
                "WHERE d.explanation = ? LIMIT 20",
                (query,),
            )
            chinese_res = self.cursor.fetchall()
        else:
            self.cursor.execute(
                "SELECT words, display_explanation, display_class FROM dictionary_headwords "
                "WHERE LOWER(words) LIKE LOWER(?) LIMIT 20",
                (f"%{query}%",),
            )
            alice_res = self.cursor.fetchall()
            self.cursor.execute(
                "SELECT DISTINCT h.words, h.display_explanation, h.display_class "
                "FROM dictionary d JOIN dictionary_headwords h ON h.id = d.headword_id "
                "WHERE LOWER(d.explanation) LIKE LOWER(?) LIMIT 20",
                (f"%{query}%",),
            )
            chinese_res = self.cursor.fetchall()
        return alice_res, chinese_res

    def search_phrases(self, query: str, is_exact: bool) -> List[Tuple[str, str]]:
        if not self.cursor:
            return []
        if is_exact:
            self.cursor.execute(
                "SELECT PHRASE, explanation FROM phrase WHERE PHRASE = ? LIMIT 20",
                (query,),
            )
        else:
            self.cursor.execute(
                "SELECT PHRASE, explanation FROM phrase WHERE LOWER(PHRASE) LIKE LOWER(?) LIMIT 20",
                (f"%{query}%",),
            )
        return self.cursor.fetchall()

    def get_all_words(self) -> List[Tuple[str, str]]:
        if not self.cursor:
            return []
        self.cursor.execute("SELECT words, display_explanation FROM dictionary_headwords")
        return self.cursor.fetchall()

    def find_songs_with_word(self, word: str) -> List[Tuple[str, str, str]]:
        if not self.cursor or not word:
            return []
        pattern = f"%{word}%"
        self.cursor.execute(
            "SELECT title, lyric, Album FROM songs "
            "WHERE LOWER(lyric) LIKE LOWER(?) OR LOWER(title) LIKE LOWER(?) OR LOWER(Album) LIKE LOWER(?)",
            (pattern, pattern, pattern),
        )
        return self.cursor.fetchall()

    def update_song_lyric(self, title: str, album: str, new_lyric: str) -> bool:
        if not self.cursor or not self.conn:
            return False
        try:
            self.cursor.execute(
                "UPDATE songs SET lyric = ? WHERE title = ? AND Album = ?",
                (new_lyric, title.strip(), album.strip()),
            )
            if self.cursor.rowcount <= 0:
                self.cursor.execute(
                    "UPDATE songs SET lyric = ? WHERE title = ?",
                    (new_lyric, title.strip()),
                )
            if self.cursor.rowcount > 0:
                self.conn.commit()
                return True
            return False
        except sqlite3.Error as exc:
            self.last_error = f"数据库更新错误: {exc}"
            return False

    def get_word_stats(self, word: str, is_exact: bool = True) -> Optional[Tuple[int, int]]:
        if not self.cursor or not word:
            return None
        if is_exact:
            self.cursor.execute("SELECT count, variety FROM dictionary_headwords WHERE words = ?", (word,))
        else:
            self.cursor.execute(
                "SELECT count, variety FROM dictionary_headwords WHERE LOWER(words) = LOWER(?)",
                (word,),
            )
        result = self.cursor.fetchone()
        return result if result else None

    def get_phrase_stats(self, phrase: str, is_exact: bool = True) -> Optional[Tuple[int, int]]:
        if not self.cursor or not phrase:
            return None
        if is_exact:
            self.cursor.execute("SELECT count, variety FROM phrase WHERE PHRASE = ?", (phrase,))
        else:
            self.cursor.execute(
                "SELECT count, variety FROM phrase WHERE LOWER(PHRASE) = LOWER(?)",
                (phrase,),
            )
        result = self.cursor.fetchone()
        return result if result else None

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None


class TextProcessor:
    _WHITESPACE_PATTERN = re.compile(r"\s+")
    _COLON_PATTERN = re.compile(r"[：:]")
    _BOUNDARY_PUNCTUATION = re.compile(r"^[\s\.,!?;，。！？；…'\"“”‘’()（）\[\]【】<>《》—-]*$")
    _compiled_patterns = {}

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            line = line.replace("\u3000", " ").replace("\t", " ").replace("\u00A0", " ")
            stripped = line.strip()
            if stripped:
                lines.append(TextProcessor._WHITESPACE_PATTERN.sub(" ", stripped))
        return "\n".join(lines)

    @staticmethod
    def is_annotation_line(line: str) -> bool:
        return bool(line and TextProcessor._COLON_PATTERN.search(line))

    @staticmethod
    def split_paragraphs(lyric: str) -> List[dict]:
        if not lyric:
            return []
        lines = lyric.splitlines()
        paragraphs = []
        current_lines = []

        def flush() -> None:
            if current_lines:
                paragraphs.append(TextProcessor._build_paragraph(current_lines))
                current_lines.clear()

        for raw_line in lines:
            if not raw_line.strip():
                if current_lines:
                    current_lines.append(raw_line)
                continue
            if not TextProcessor.is_annotation_line(raw_line):
                flush()
                current_lines.append(raw_line)
            elif current_lines:
                current_lines.append(raw_line)

        flush()
        return paragraphs

    @staticmethod
    def _build_paragraph(lines: List[str]) -> dict:
        items = []
        for raw in lines:
            items.append(
                {
                    "raw": raw,
                    "normalized": TextProcessor.normalize_text(raw),
                    "is_annotation": TextProcessor.is_annotation_line(raw),
                }
            )
        return {"lines": items, "text": "\n".join(item["raw"] for item in items)}

    @staticmethod
    def extract_valid_examples(lyric: str, search_word: str) -> List[str]:
        return TextProcessor.extract_all_valid_paragraphs(lyric, search_word)

    @classmethod
    def matches_position(cls, paragraph: str, word: str, position: str) -> bool:
        """Return whether a whole-word match is at a sentence line boundary."""
        if position not in {"start", "end"}:
            return True
        pattern = cls._get_compiled_pattern(word)
        for raw_line in paragraph.splitlines():
            if cls.is_annotation_line(raw_line):
                continue
            text = cls.normalize_text(raw_line)
            if not text:
                continue
            match = pattern.search(text)
            while match:
                if position == "start" and cls._BOUNDARY_PUNCTUATION.fullmatch(text[:match.start()]):
                    return True
                if position == "end" and cls._BOUNDARY_PUNCTUATION.fullmatch(text[match.end():]):
                    return True
                match = pattern.search(text, match.end())
        return False

    @staticmethod
    def extract_all_valid_paragraphs(lyric: str, search_word: Optional[str] = None) -> List[str]:
        if not lyric:
            return []
        paragraphs = TextProcessor.split_paragraphs(lyric)
        valid = []
        has_search_word = bool(search_word)
        pattern = TextProcessor._get_compiled_pattern(search_word) if has_search_word else None

        for paragraph in paragraphs:
            if not paragraph["text"].strip():
                continue
            if has_search_word and not any(
                pattern.search(line["raw"])
                for line in paragraph["lines"]
                if not line["is_annotation"]
            ):
                continue
            valid.append(paragraph["text"])
        return valid

    @staticmethod
    def find_paragraph_positions(lyric: str, paragraph: str) -> Tuple[int, int]:
        if not lyric or not paragraph:
            return 0, 0

        target = TextProcessor.normalize_text(paragraph)
        offset = 0
        for block in TextProcessor.split_paragraphs(lyric):
            block_text = block["text"]
            if TextProcessor.normalize_text(block_text) == target:
                start_pos = lyric.find(block_text, offset)
                if start_pos != -1:
                    return start_pos, start_pos + len(block_text)
            offset = lyric.find(block_text, offset)
            if offset != -1:
                offset += len(block_text)

        start_pos = lyric.find(paragraph)
        if start_pos != -1:
            return start_pos, start_pos + len(paragraph)
        return 0, min(len(paragraph), len(lyric))

    @classmethod
    def _get_compiled_pattern(cls, word: str) -> re.Pattern:
        if word not in cls._compiled_patterns:
            cls._compiled_patterns[word] = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
        return cls._compiled_patterns[word]
