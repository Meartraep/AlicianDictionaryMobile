from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Latin tokens that can safely take the whole-word GLOB path: GLOB has no escape
# syntax, so wildcard characters in user input must not reach it.
_LATIN_WORD_PATTERN = re.compile(r"[a-z]+(?:'[a-z]+)?")


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
                "SELECT id, words, display_explanation, display_class FROM dictionary_headwords "
                "WHERE words = ? ORDER BY id LIMIT 20",
                (query,),
            )
            alice_res = self.cursor.fetchall()
            self.cursor.execute(
                "SELECT DISTINCT h.id, h.words, h.display_explanation, h.display_class "
                "FROM dictionary d JOIN dictionary_headwords h ON h.id = d.headword_id "
                "WHERE d.explanation = ? ORDER BY h.id LIMIT 20",
                (query,),
            )
            chinese_res = self.cursor.fetchall()
        else:
            self.cursor.execute(
                "SELECT id, words, display_explanation, display_class FROM dictionary_headwords "
                "WHERE LOWER(words) LIKE LOWER(?) ORDER BY id LIMIT 20",
                (f"%{query}%",),
            )
            alice_res = self.cursor.fetchall()
            self.cursor.execute(
                "SELECT DISTINCT h.id, h.words, h.display_explanation, h.display_class "
                "FROM dictionary d JOIN dictionary_headwords h ON h.id = d.headword_id "
                "WHERE LOWER(d.explanation) LIKE LOWER(?) ORDER BY h.id LIMIT 20",
                (f"%{query}%",),
            )
            chinese_res = self.cursor.fetchall()
        return alice_res, chinese_res

    def get_headword_senses(
        self, headword_ids: List[int],
    ) -> Dict[int, List[Tuple[int, str, str, str, str]]]:
        """Return {headword_id: [(sense_id, explanation, class, english, japanese), ...]}.

        The edit dialog needs one row per sense so a save can never flatten the
        curated per-sense meanings into the headword summary.
        """
        ordered = sorted({int(hid) for hid in headword_ids if hid is not None})
        if not self.cursor or not ordered:
            return {}
        placeholders = ",".join("?" for _ in ordered)
        self.cursor.execute(
            "SELECT headword_id, id, explanation, class, english_gloss, japanese_gloss "
            f"FROM dictionary WHERE headword_id IN ({placeholders}) "
            "ORDER BY headword_id, sense_order, id",
            tuple(ordered),
        )
        senses: Dict[int, List[Tuple[int, str, str, str, str]]] = {}
        for headword_id, sense_id, explanation, word_class, english, japanese in self.cursor.fetchall():
            senses.setdefault(int(headword_id), []).append((
                int(sense_id),
                explanation or "",
                word_class or "",
                english or "",
                japanese or "",
            ))
        return senses

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

    def get_word_glosses(self, word: str) -> Tuple[str, str]:
        """Return (english_gloss, japanese_gloss) for a word, if recorded."""
        if not self.cursor:
            return "", ""
        try:
            self.cursor.execute(
                "SELECT english_gloss, japanese_gloss FROM dictionary "
                "WHERE LOWER(words) = LOWER(?) AND english_gloss <> '' LIMIT 1",
                (word.strip(),),
            )
        except sqlite3.Error:
            return "", ""
        row = self.cursor.fetchone()
        return (row[0] or "", row[1] or "") if row else ("", "")

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

    def find_song_alignments(self, title: str, album: str) -> List[Tuple[str, str, str, str, str]]:
        """Return per-line (alician, poetic, english, japanese, korean).

        Older databases may not carry song_translations yet; the missing table
        degrades gracefully to empty official translation fields.
        """
        if not self.cursor:
            return []
        try:
            self.cursor.execute(
                "SELECT sa.alician_sentence, sa.chinese_translation, "
                "st.english, st.japanese, st.korean "
                "FROM sentence_alignments sa "
                "LEFT JOIN song_translations st "
                "ON st.song_title = sa.song_title "
                "AND st.sentence = sa.alician_sentence "
                "WHERE sa.song_title = ? AND sa.album = ? "
                "AND TRIM(sa.alician_sentence) <> '' "
                "ORDER BY sa.song_sentence_order",
                (title.strip(), album.strip()),
            )
        except sqlite3.Error:
            self.cursor.execute(
                "SELECT alician_sentence, chinese_translation, '', '', '' "
                "FROM sentence_alignments "
                "WHERE song_title = ? AND album = ? "
                "AND TRIM(alician_sentence) <> '' "
                "ORDER BY song_sentence_order",
                (title.strip(), album.strip()),
            )
        return [
            (row[0], row[1] or "", row[2] or "", row[3] or "", row[4] or "")
            for row in self.cursor.fetchall()
        ]

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
            # Leaving an open implicit transaction behind used to make the next
            # write fail with "cannot start a transaction within a transaction".
            self.conn.rollback()
            return False
        except sqlite3.Error as exc:
            self.last_error = f"数据库更新错误: {exc}"
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            return False

    def search_song_translations(
        self, query: str, is_exact: bool = False, limit: int = 20,
    ) -> List[Tuple[str, str, str, str, str, str]]:
        """Search the official English/Japanese lyric translations.

        Returns (alician_sentence, chinese_translation, english, japanese,
        song_title, album).  The song identity is carried through because a
        lyric line is not attributable to a song otherwise.
        """
        stripped = (query or "").strip()
        if not self.cursor or not stripped:
            return []
        base_columns = (
            "SELECT sa.alician_sentence, MAX(sa.chinese_translation), "
            "st.english, st.japanese, MIN(sa.song_title), MIN(sa.album) "
            "FROM sentence_alignments sa "
            "JOIN song_translations st ON st.song_title = sa.song_title "
            "AND st.sentence = sa.alician_sentence "
        )
        group_order = (
            " AND TRIM(sa.alician_sentence) <> '' "
            "GROUP BY sa.alician_sentence, st.english, st.japanese "
            "ORDER BY MIN(sa.song_title), MIN(sa.song_sentence_order) LIMIT ?"
        )
        try:
            if is_exact:
                self.cursor.execute(
                    base_columns
                    + "WHERE (LOWER(st.english) = LOWER(?) OR LOWER(st.japanese) = LOWER(?))"
                    + group_order,
                    (stripped, stripped, int(limit)),
                )
            elif _LATIN_WORD_PATTERN.fullmatch(stripped.lower()):
                # Whole-word match: "love" must not match "loveless"/"glove".
                # GLOB has no escape syntax, so only metacharacter-free latin
                # tokens take this branch; everything else falls back to LIKE.
                pattern = "*[^a-z]" + stripped.lower() + "[^a-z]*"
                self.cursor.execute(
                    base_columns
                    + "WHERE ((' ' || LOWER(st.english) || ' ') GLOB ? "
                    "OR (' ' || LOWER(st.japanese) || ' ') GLOB ?)"
                    + group_order,
                    (pattern, pattern, int(limit)),
                )
            else:
                pattern = f"%{stripped}%"
                self.cursor.execute(
                    base_columns
                    + "WHERE (LOWER(st.english) LIKE LOWER(?) OR LOWER(st.japanese) LIKE LOWER(?))"
                    + group_order,
                    (pattern, pattern, int(limit)),
                )
            return [
                (
                    row[0] or "",
                    row[1] or "",
                    row[2] or "",
                    row[3] or "",
                    row[4] or "",
                    row[5] or "",
                )
                for row in self.cursor.fetchall()
            ]
        except sqlite3.Error:
            # Older databases predate the official translation tables.
            self.last_error = "当前数据库缺少歌词译文表，已跳过英/日译检索。"
            return []

    def search_songs(self, query: str, is_exact: bool, limit: int = 20) -> List[Tuple[str, str]]:
        """Return (title, album) rows whose title matches the query."""
        stripped = (query or "").strip()
        if not self.cursor or not stripped:
            return []
        if is_exact:
            self.cursor.execute(
                "SELECT title, COALESCE(Album, '') FROM songs "
                "WHERE LOWER(title) = LOWER(?) ORDER BY title LIMIT ?",
                (stripped, int(limit)),
            )
        else:
            self.cursor.execute(
                "SELECT title, COALESCE(Album, '') FROM songs "
                "WHERE LOWER(title) LIKE LOWER(?) ORDER BY title LIMIT ?",
                (f"%{stripped}%", int(limit)),
            )
        return [(row[0] or "", row[1] or "") for row in self.cursor.fetchall()]

    def get_song_lyric(self, title: str, album: str = "") -> Optional[Tuple[str, str, str]]:
        """Return (title, lyric, album) for one song, tolerating an empty album."""
        stripped_title = (title or "").strip()
        stripped_album = (album or "").strip()
        if not self.cursor or not stripped_title:
            return None
        self.cursor.execute(
            "SELECT title, COALESCE(lyric, ''), COALESCE(Album, '') FROM songs "
            "WHERE title = ? AND (? = '' OR COALESCE(Album, '') = ?) LIMIT 1",
            (stripped_title, stripped_album, stripped_album),
        )
        row = self.cursor.fetchone()
        return (row[0] or "", row[1] or "", row[2] or "") if row else None

    @staticmethod
    def _optional_gloss(item: Dict[str, Any], key: str, alias: str) -> Optional[str]:
        """Read an optional gloss, returning None when the caller omitted it."""
        if key in item:
            return str(item.get(key) or "").strip()
        if alias in item:
            return str(item.get(alias) or "").strip()
        return None

    def update_word_entry(
        self,
        headword_id: int,
        original_word: str,
        new_word: str,
        display_explanation: str,
        senses: List[Dict[str, Any]],
    ) -> bool:
        """Update one headword and its individual senses as a single transaction.

        Every sense is addressed by its own ``dictionary.id``; senses that are
        not part of ``senses`` are left untouched.  This is the whole point of
        the feature: the previous implementation wrote the headword summary into
        *every* sense, destroying the curated per-sense meanings.
        """
        if not self.conn or not self.cursor:
            self.last_error = "数据库未连接。"
            return False
        try:
            parsed_headword_id = int(headword_id)
        except (TypeError, ValueError):
            self.last_error = "未找到要修改的词条。"
            return False

        word = (new_word or "").strip()
        if not word:
            self.last_error = "原文不能为空。"
            return False
        if len(word) > 64:
            self.last_error = "原文过长。"
            return False
        if "\n" in word or "\r" in word:
            self.last_error = "原文不能包含换行。"
            return False

        display = (display_explanation or "").strip()
        if not display:
            self.last_error = "展示释义不能为空。"
            return False
        if len(display) > 500:
            self.last_error = "展示释义过长。"
            return False

        normalized_senses: List[Tuple[int, str, Optional[str], Optional[str]]] = []
        seen_sense_ids = set()
        for item in senses or []:
            if not isinstance(item, dict):
                self.last_error = "义项数据不一致，请刷新后重试。"
                return False
            try:
                sense_id = int(item.get("id"))
            except (TypeError, ValueError):
                self.last_error = "义项数据不一致，请刷新后重试。"
                return False
            if sense_id in seen_sense_ids:
                continue
            seen_sense_ids.add(sense_id)
            explanation = str(item.get("explanation") or "").strip()
            # A missing gloss key means "keep the stored value"; only an explicit
            # empty string clears it.  Otherwise a caller using the search-payload
            # key names (english_gloss) would silently wipe every gloss.
            english = self._optional_gloss(item, "english", "english_gloss")
            japanese = self._optional_gloss(item, "japanese", "japanese_gloss")
            if not explanation:
                self.last_error = "义项释义不能为空。"
                return False
            if len(explanation) > 500:
                self.last_error = "义项释义过长。"
                return False
            if english is not None and len(english) > 500:
                self.last_error = "义项译文过长。"
                return False
            if japanese is not None and len(japanese) > 500:
                self.last_error = "义项译文过长。"
                return False
            normalized_senses.append((sense_id, explanation, english, japanese))

        try:
            # A previous failed write must never leave the shared connection in a
            # transaction: "BEGIN IMMEDIATE" would then raise and the user would
            # see a raw SQLite message.
            if self.conn.in_transaction:
                self.conn.rollback()

            row = self.cursor.execute(
                "SELECT words FROM dictionary_headwords WHERE id = ?",
                (parsed_headword_id,),
            ).fetchone()
            if row is None:
                self.last_error = "未找到要修改的词条。"
                return False
            current_word = str(row[0] or "")
            if word.casefold() != current_word.casefold():
                duplicate = self.cursor.execute(
                    "SELECT id FROM dictionary_headwords "
                    "WHERE LOWER(words) = LOWER(?) AND id <> ? LIMIT 1",
                    (word, parsed_headword_id),
                ).fetchone()
                if duplicate is not None:
                    self.last_error = "已存在同名词条，请改用不同的原文。"
                    return False

            if normalized_senses:
                placeholders = ",".join("?" for _ in normalized_senses)
                owned_rows = self.cursor.execute(
                    "SELECT id FROM dictionary WHERE headword_id = ? AND id IN ("
                    + placeholders + ")",
                    (parsed_headword_id,) + tuple(sense_id for sense_id, *_ in normalized_senses),
                ).fetchall()
                owned = {int(entry[0]) for entry in owned_rows}
                if any(sense_id not in owned for sense_id, *_ in normalized_senses):
                    self.last_error = "义项数据不一致，请刷新后重试。"
                    return False

            self.conn.execute("BEGIN IMMEDIATE")
            self.cursor.execute(
                "UPDATE dictionary_headwords SET words = ?, display_explanation = ? WHERE id = ?",
                (word, display, parsed_headword_id),
            )
            # The headword spelling is shared by every sense.
            self.cursor.execute(
                "UPDATE dictionary SET words = ? WHERE headword_id = ?",
                (word, parsed_headword_id),
            )
            for sense_id, explanation, english, japanese in normalized_senses:
                if english is None and japanese is None:
                    self.cursor.execute(
                        "UPDATE dictionary SET explanation = ? WHERE id = ? AND headword_id = ?",
                        (explanation, sense_id, parsed_headword_id),
                    )
                elif english is None:
                    self.cursor.execute(
                        "UPDATE dictionary SET explanation = ?, japanese_gloss = ? "
                        "WHERE id = ? AND headword_id = ?",
                        (explanation, japanese, sense_id, parsed_headword_id),
                    )
                elif japanese is None:
                    self.cursor.execute(
                        "UPDATE dictionary SET explanation = ?, english_gloss = ? "
                        "WHERE id = ? AND headword_id = ?",
                        (explanation, english, sense_id, parsed_headword_id),
                    )
                else:
                    self.cursor.execute(
                        "UPDATE dictionary SET explanation = ?, english_gloss = ?, "
                        "japanese_gloss = ? WHERE id = ? AND headword_id = ?",
                        (explanation, english, japanese, sense_id, parsed_headword_id),
                    )
            self.conn.commit()
            self.last_error = ""
            return True
        except sqlite3.Error as exc:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            self.last_error = "保存失败，请稍后重试。"
            logger.error("update_word_entry failed: %s", exc, exc_info=True)
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
