"""Single-writer data layer for the dictionary database.

The app used to write the same SQLite file through two independent services
(``DictionaryService`` and ``DatabaseManagerService``) with different rules,
different PRAGMAs and no shared validation.  This module is the one place that
owns the writable connection and every write rule:

* connection policy: ``foreign_keys=ON``, ``busy_timeout=5000``,
  ``synchronous=FULL``; **no WAL** on purpose (see ``connect()``);
* declarative table rules live in :mod:`webui_backend.data_schema`;
* every write goes through one guard: table whitelist -> required/length/type ->
  uniqueness -> foreign keys -> single ``BEGIN IMMEDIATE`` transaction ->
  local-edit ledger -> post-commit event;
* recovery points are full database snapshots with a JSON sidecar and an atomic
  replace on restore.

Errors that a user may see are raised as :class:`DataError` with a Chinese
message; raw SQLite text never reaches the UI.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from webui_backend import data_schema

#: Tables that a database file must contain to be accepted as installable.
REQUIRED_TABLES: Tuple[str, ...] = ("dictionary", "dictionary_headwords", "songs", "phrase")

#: Recovery points kept by default when pruning.
DEFAULT_BACKUP_KEEP = 10

#: Upper bound for one page payload.
MAX_PAGE_LIMIT = 200

#: Order in which a write is validated.  The first failing step decides the
#: message the user sees, so this order is part of the write contract.
VALIDATION_ORDER: Tuple[str, ...] = (
    "table",       # unknown table / unknown column
    "readonly",    # table is not editable
    "payload",     # per-field coercion (empty / integer / number)
    "required",    # spec.required and other NOT NULL columns
    "type",        # declared INTEGER / REAL columns
    "length",      # spec.max_length
    "unique",      # case-insensitive uniqueness groups
    "fk",          # referenced parent row must exist
    "transaction", # single BEGIN IMMEDIATE, rolled back on failure
)

#: Known referential checks reported by :meth:`DataCore.diagnose`.
ORPHAN_CHECKS: Tuple[Dict[str, str], ...] = (
    {
        "table": "dictionary",
        "label": "义项缺少词头",
        "sql": "SELECT COUNT(*) FROM dictionary d LEFT JOIN dictionary_headwords h "
               "ON h.id = d.headword_id WHERE h.id IS NULL",
    },
    {
        "table": "sentence_alignments",
        "label": "对齐句缺少歌曲",
        "sql": "SELECT COUNT(*) FROM sentence_alignments a LEFT JOIN songs s "
               "ON s.id = a.song_id WHERE s.id IS NULL",
    },
    {
        "table": "dictionary_semantic_aliases",
        "label": "语义别名缺少义项",
        "sql": "SELECT COUNT(*) FROM dictionary_semantic_aliases a LEFT JOIN dictionary d "
               "ON d.id = a.sense_id WHERE d.id IS NULL",
    },
    {
        "table": "song_translations",
        "label": "官方译文缺少歌曲",
        "sql": "SELECT COUNT(*) FROM song_translations t LEFT JOIN songs s "
               "ON s.title = t.song_title WHERE s.id IS NULL",
    },
)


class DataError(Exception):
    """A user-facing failure.  ``message`` is shown verbatim."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = str(message)


def _quote(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_reason(reason: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_-]+", "_", str(reason or "manual")).strip("_")
    return (cleaned or "manual")[:32]


def read_database_marker(path: str | Path) -> int:
    """Return ``database_metadata.db_version`` (0 when the marker is missing)."""
    target = Path(path)
    if not target.is_file():
        return 0
    try:
        connection = sqlite3.connect("file:" + target.as_posix() + "?mode=ro", uri=True)
    except sqlite3.Error:
        return 0
    try:
        row = connection.execute(
            "SELECT value FROM database_metadata WHERE key='db_version'"
        ).fetchone()
    except sqlite3.Error:
        return 0
    finally:
        connection.close()
    try:
        return int(row[0]) if row else 0
    except (TypeError, ValueError):
        return 0


def database_identity(path: str | Path) -> Dict[str, Any]:
    """Byte identity of a database file: size, sha1 and the in-file version."""
    target = Path(path)
    if not target.is_file():
        raise DataError("数据库文件不存在。")
    return {
        "size": target.stat().st_size,
        "sha1": hashlib.sha1(target.read_bytes()).hexdigest(),
        "db_version": read_database_marker(target),
    }


def validate_database_file(path: str | Path) -> Dict[str, Any]:
    """Reject files that must not be installed as the app database."""
    target = Path(path)
    if not target.is_file():
        raise DataError("数据库文件不存在。")
    try:
        connection = sqlite3.connect("file:" + target.as_posix() + "?mode=ro", uri=True)
    except sqlite3.Error:
        raise DataError("无法打开数据库文件。") from None
    try:
        try:
            present = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing = [name for name in REQUIRED_TABLES if name not in present]
            if missing:
                raise DataError("数据库缺少必要数据表：" + "、".join(missing))
            row = connection.execute("PRAGMA integrity_check").fetchone()
            if not row or str(row[0]).lower() != "ok":
                raise DataError("数据库完整性检查未通过。")
        except sqlite3.Error:
            raise DataError("数据库文件已损坏或不是 SQLite 数据库。") from None
    finally:
        connection.close()
    identity = database_identity(target)
    return {"ok": True, **identity}


def atomic_replace_file(source: str | Path, target: str | Path) -> None:
    """Copy ``source`` over ``target`` so readers never see a half-written file."""
    source_path = Path(source)
    target_path = Path(target)
    if not source_path.is_file():
        raise DataError("源文件不存在。")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_path.with_name(
        target_path.name + ".tmp-" + uuid.uuid4().hex[:8]
    )
    try:
        shutil.copyfile(source_path, temporary)
        with temporary.open("rb+") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target_path)
        try:
            directory_fd = os.open(str(target_path.parent), os.O_RDONLY)
        except (OSError, AttributeError):
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except DataError:
        raise
    except OSError as exc:
        raise DataError("替换数据库文件失败。") from exc
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


class DataCore:
    """Owns the single writable connection and every write rule."""

    def __init__(self, db_path: str, backups_dir: Optional[str] = None) -> None:
        self.db_path = str(Path(db_path).resolve()) if db_path != ":memory:" else db_path
        default_backups = (
            str(Path(self.db_path).parent / "backups")
            if self.db_path != ":memory:"
            else ":memory:"
        )
        self.backups_dir = str(backups_dir or default_backups)
        self.conn: Optional[sqlite3.Connection] = None
        self.last_error = ""
        self._lock = threading.RLock()
        self._event_sink: Optional[Callable[[Set[str]], None]] = None
        self._pending_tables: Set[str] = set()

    # ------------------------------------------------------------------ setup

    def set_event_sink(self, sink: Optional[Callable[[Set[str]], None]]) -> None:
        """Register a post-commit callback receiving the set of written tables."""
        self._event_sink = sink

    def connect(self) -> bool:
        with self._lock:
            if self.conn is not None:
                try:
                    self.conn.execute("SELECT 1")
                    return True
                except sqlite3.Error:
                    self.close()
            if self.db_path != ":memory:" and not os.path.exists(self.db_path):
                self.last_error = "数据库文件不存在。"
                return False
            try:
                self.conn = sqlite3.connect(
                    self.db_path, timeout=5.0, check_same_thread=False
                )
                # WAL is deliberately NOT enabled: the app exports and backs up by
                # copying the single .db file (SAF export, Android cloud backup),
                # and a WAL journal would make those copies lose recent commits.
                self.conn.execute("PRAGMA foreign_keys = ON")
                self.conn.execute("PRAGMA busy_timeout = 5000")
                self.conn.execute("PRAGMA synchronous = FULL")
                self.conn.execute("PRAGMA cache_size = -2000")
                return True
            except sqlite3.Error as exc:
                self.last_error = str(exc)
                self.close()
                return False

    def close(self) -> None:
        with self._lock:
            if self.conn is not None:
                try:
                    self.conn.close()
                except sqlite3.Error:
                    pass
                self.conn = None

    def _ensure_ledger_table(self, connection: Optional[sqlite3.Connection] = None) -> None:
        """Create the local-edit ledger on demand.

        Deliberately *not* done in ``connect()``: it would change the installed
        database bytes on every fresh install and weaken the "publishing must
        contain an actual change" guard.
        """
        target = connection or self.conn
        if target is None:
            return
        target.execute(
            "CREATE TABLE IF NOT EXISTS local_edits ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "table_name TEXT NOT NULL, "
            "row_key TEXT NOT NULL, "
            "op TEXT NOT NULL, "
            "summary TEXT NOT NULL, "
            "changed_at TEXT NOT NULL)"
        )
        if connection is None:
            self.conn.commit()

    def _require_connection(self) -> sqlite3.Connection:
        if self.conn is None:
            if not self.connect() or self.conn is None:
                raise DataError("数据库未连接。")
        return self.conn

    # -------------------------------------------------------------- read side

    def table_names(self) -> List[str]:
        with self._lock:
            connection = self._require_connection()
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            return [str(row[0]) for row in rows]

    def _require_table(self, table: str) -> str:
        name = str(table or "")
        if not name or name not in self.table_names():
            raise DataError(f"未知数据表：{name or '（空）'}")
        return name

    def table_fields(self, table: str) -> List[Dict[str, Any]]:
        with self._lock:
            connection = self._require_connection()
            name = self._require_table(table)
            rows = connection.execute(f"PRAGMA table_info({_quote(name)})").fetchall()
            return [
                {
                    "name": str(row[1]),
                    "type": str(row[2] or ""),
                    "notnull": bool(row[3]),
                    "default": row[4],
                    "pk": int(row[5] or 0),
                }
                for row in rows
            ]

    @staticmethod
    def _key_column(fields: Sequence[Dict[str, Any]]) -> str:
        names = [str(field["name"]) for field in fields]
        return "id" if "id" in names else "rowid"

    def _keyword_clause(
        self, columns: Sequence[str], keyword: str, exact: bool
    ) -> Tuple[str, List[Any]]:
        text = str(keyword or "").strip()
        if not text:
            return "", []
        if exact:
            condition = "LOWER(CAST({column} AS TEXT)) = LOWER(?)"
            value: Any = text
        else:
            condition = "CAST({column} AS TEXT) LIKE ?"
            value = f"%{text}%"
        parts = [condition.format(column=_quote(column)) for column in columns]
        return " WHERE (" + " OR ".join(parts) + ")", [value] * len(columns)

    def page(
        self,
        table: str,
        keyword: str = "",
        exact: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        with self._lock:
            connection = self._require_connection()
            name = self._require_table(table)
            fields = self.table_fields(name)
            columns = [str(field["name"]) for field in fields]
            key = self._key_column(fields)
            selected = columns if key == "id" else ["rowid", *columns]
            offset = max(0, int(offset or 0))
            limit = max(1, min(MAX_PAGE_LIMIT, int(limit or 50)))
            where, params = self._keyword_clause(
                [column for column in columns if column not in ("rowid",)], keyword, exact
            )
            total = connection.execute(
                f"SELECT COUNT(*) FROM {_quote(name)}{where}", params
            ).fetchone()[0]
            ordering = _quote(key) if key == "id" else "rowid"
            selected_sql = ", ".join(
                "rowid" if column == "rowid" else _quote(column) for column in selected
            )
            rows = connection.execute(
                f"SELECT {selected_sql} FROM {_quote(name)}{where} "
                f"ORDER BY {ordering} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            return {
                "ok": True,
                "table": name,
                "fields": selected,
                "rows": [dict(zip(selected, row)) for row in rows],
                "total": int(total),
                "offset": offset,
                "limit": limit,
            }

    def row(self, table: str, key: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            connection = self._require_connection()
            name = self._require_table(table)
            fields = self.table_fields(name)
            columns = [str(field["name"]) for field in fields]
            key_column = self._key_column(fields)
            selected = columns if key_column == "id" else ["rowid", *columns]
            selected_sql = ", ".join(
                "rowid" if column == "rowid" else _quote(column) for column in selected
            )
            row = connection.execute(
                f"SELECT {selected_sql} FROM {_quote(name)} "
                f"WHERE {_quote(key_column)} = ? LIMIT 1",
                (key,),
            ).fetchone()
            return dict(zip(selected, row)) if row else None

    # ------------------------------------------------------------- write side

    def _guard_write(self, tables: Iterable[str], action: Callable[[sqlite3.Connection], Any]) -> Any:
        """Run ``action`` inside one transaction, then commit and notify listeners."""
        with self._lock:
            connection = self._require_connection()
            self._pending_tables = set(tables)
            try:
                # A previous failed operation must never leave a transaction open.
                if connection.in_transaction:
                    connection.rollback()
                connection.execute("BEGIN IMMEDIATE")
                outcome = action(connection)
                connection.commit()
            except DataError:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                raise
            except sqlite3.Error as exc:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                self.last_error = str(exc)
                raise DataError("保存失败，请稍后重试。") from exc
            touched = set(self._pending_tables)
            self._pending_tables = set()
            if touched and self._event_sink is not None:
                try:
                    self._event_sink(touched)
                except Exception:  # pragma: no cover - listeners must not break writes
                    pass
            return outcome

    def _field_map(self, table: str) -> Dict[str, Dict[str, Any]]:
        return {str(field["name"]): field for field in self.table_fields(table)}

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _coerce_value(
        self, table: str, field: Dict[str, Any], spec: data_schema.TableSpec, value: Any
    ) -> Any:
        column = str(field["name"])
        declared = str(field.get("type") or "").upper()
        notnull = bool(field.get("notnull"))
        raw_text = "" if value is None else str(value).strip()
        if not raw_text:
            if notnull and field.get("default") is None:
                raise DataError(f"字段「{column}」不能为空。")
            return None
        if "INT" in declared:
            try:
                return int(raw_text)
            except ValueError:
                raise DataError(f"字段「{column}」必须是整数。") from None
        if any(token in declared for token in ("REAL", "FLOA", "DOUB", "NUM")):
            try:
                return float(raw_text)
            except ValueError:
                raise DataError(f"字段「{column}」必须是数字。") from None
        limit = spec.max_length_of(column)
        if limit and len(raw_text) > limit:
            raise DataError(f"字段「{column}」过长（最多 {limit} 字）。")
        return raw_text

    def _normalize(
        self,
        table: str,
        values: Dict[str, Any],
        *,
        creating: bool,
        key: Any = None,
    ) -> Dict[str, Any]:
        spec = data_schema.spec_for(table)
        if not spec.editable:
            raise DataError(f"「{spec.label}」为只读表，不能编辑。")
        fields = self._field_map(table)
        normalized: Dict[str, Any] = {}
        for raw_key, raw_value in (values or {}).items():
            column = str(raw_key)
            if column in ("id", "rowid"):
                continue
            if column not in fields:
                raise DataError(f"字段「{column}」不存在。")
            normalized[column] = self._coerce_value(
                table, fields[column], spec, raw_value
            )
        if creating:
            for column in spec.required:
                if column not in normalized or normalized[column] in (None, ""):
                    raise DataError(f"字段「{column}」不能为空。")
            # Any other NOT NULL column without a default must be supplied too,
            # otherwise SQLite would reject the row with an English message.
            for column, field in fields.items():
                if (
                    str(column) in normalized
                    or bool(field.get("pk"))
                    or not bool(field.get("notnull"))
                    or field.get("default") is not None
                ):
                    continue
                raise DataError(f"字段「{column}」不能为空。")
        else:
            if not normalized:
                raise DataError("没有可保存的修改。")
            for column in spec.required:
                if column in normalized and normalized[column] in (None, ""):
                    raise DataError(f"字段「{column}」不能为空。")
        self._check_unique(table, spec, normalized, creating=creating, key=key)
        self._check_foreign_keys(table, normalized)
        return normalized

    def _check_unique(
        self,
        table: str,
        spec: data_schema.TableSpec,
        normalized: Dict[str, Any],
        *,
        creating: bool,
        key: Any,
    ) -> None:
        connection = self._require_connection()
        key_column = self._key_column(self.table_fields(table))
        for group in spec.unique:
            if not all(column in normalized for column in group):
                continue
            conditions = [
                f"LOWER(CAST({_quote(column)} AS TEXT)) = LOWER(?)" for column in group
            ]
            params: List[Any] = [normalized[column] for column in group]
            sql = f"SELECT {_quote(key_column)} FROM {_quote(table)} WHERE " + " AND ".join(
                conditions
            )
            if not creating and key is not None:
                sql += f" AND {_quote(key_column)} <> ?"
                params.append(key)
            existing = connection.execute(sql + " LIMIT 1", params).fetchone()
            if existing is not None:
                shown = "／".join(self._as_text(normalized[column]) for column in group)
                raise DataError(f"已存在相同的{spec.label}（{shown}）。")

    def _check_foreign_keys(self, table: str, normalized: Dict[str, Any]) -> None:
        connection = self._require_connection()
        checks: List[Tuple[str, str, str]] = []
        try:
            references = connection.execute(
                f"PRAGMA foreign_key_list({_quote(table)})"
            ).fetchall()
            for reference in references:
                checks.append(
                    (str(reference[3]), str(reference[2]), str(reference[4] or "id"))
                )
        except sqlite3.Error:
            pass
        # Historical tables sometimes never got a real FOREIGN KEY; the declarative
        # references in data_schema cover those so the guard still rejects orphans.
        for from_column, parent_table, to_column in data_schema.spec_for(table).references:
            if (from_column, parent_table, to_column) not in checks:
                checks.append((from_column, parent_table, to_column))
        for from_column, parent_table, to_column in checks:
            if from_column not in normalized:
                continue
            value = normalized[from_column]
            if value in (None, ""):
                continue
            found = connection.execute(
                f"SELECT 1 FROM {_quote(parent_table)} "
                f"WHERE {_quote(to_column)} = ? LIMIT 1",
                (value,),
            ).fetchone()
            if found is None:
                raise DataError(
                    f"关联的「{data_schema.spec_for(parent_table).label}」不存在。"
                )

    def _touched_tables(self, table: str) -> Set[str]:
        """Tables whose content changes when a write touches ``table``.

        Used for cache invalidation: a headword edit also rewrites
        ``dictionary.words`` (invariant), and deleting a parent removes cascade
        children, so a listener that only sees the parent name would keep stale
        translations.
        """
        touched: Set[str] = {str(table)}
        spec = data_schema.spec_for(table)
        for child_table, _, _ in spec.cascade:
            touched.add(child_table)
        if table == "dictionary_headwords":
            touched.add("dictionary")
        if table == "dictionary":
            touched.add("dictionary_semantic_aliases")
        return touched

    def _apply_invariants(
        self, connection: sqlite3.Connection, table: str, key: Any, normalized: Dict[str, Any]
    ) -> None:
        """Keep the headword/sense spelling pair consistent (contract §0.2)."""
        if table == "dictionary_headwords" and "words" in normalized:
            connection.execute(
                "UPDATE dictionary SET words = ? WHERE headword_id = ?",
                (normalized["words"], key),
            )
        if table == "dictionary" and "words" in normalized:
            row = connection.execute(
                "SELECT h.words FROM dictionary d "
                "JOIN dictionary_headwords h ON h.id = d.headword_id WHERE d.id = ?",
                (key,),
            ).fetchone()
            if row is not None and self._as_text(row[0]) != self._as_text(normalized["words"]):
                raise DataError("义项的词形必须与词头一致，请修改词头。")

    def _record_local_edit(
        self,
        connection: sqlite3.Connection,
        table: str,
        row_key: Any,
        op: str,
        summary: str,
    ) -> None:
        self._ensure_ledger_table(connection)
        connection.execute(
            "INSERT INTO local_edits (table_name, row_key, op, summary, changed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(table), str(row_key), str(op), str(summary)[:200], _now_iso()),
        )

    def record_local_edit(
        self, table: str, row_key: Any, op: str, summary: str, notify: bool = True
    ) -> None:
        """Record a write that happened outside :meth:`create`/:meth:`update`.

        ``DictionaryService`` keeps using the shared connection for its curated
        word/lyric edits; those must still show up in the local-edit ledger.
        ``notify=False`` skips the post-commit event when the caller already
        reloads the caches itself.
        """
        with self._lock:
            connection = self._require_connection()
            try:
                self._record_local_edit(connection, table, row_key, op, summary)
                connection.commit()
                if notify and self._event_sink is not None:
                    try:
                        self._event_sink({str(table)})
                    except Exception:  # pragma: no cover
                        pass
            except sqlite3.Error as exc:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                self.last_error = str(exc)

    def _summary(self, table: str, row: Dict[str, Any]) -> str:
        spec = data_schema.spec_for(table)
        parts = []
        for column in spec.display:
            value = self._as_text(row.get(column))
            if value:
                parts.append(value)
        if not parts:
            for column, value in row.items():
                text = self._as_text(value)
                if text:
                    parts.append(text)
                if len(parts) >= 2:
                    break
        return " · ".join(parts)[:200] or str(table)

    def create(self, table: str, values: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            name = self._require_table(table)
            normalized = self._normalize(name, values, creating=True)

            def action(connection: sqlite3.Connection) -> Dict[str, Any]:
                columns = list(normalized)
                placeholders = ", ".join("?" for _ in columns)
                connection.execute(
                    f"INSERT INTO {_quote(name)} "
                    f"({', '.join(_quote(column) for column in columns)}) "
                    f"VALUES ({placeholders})",
                    tuple(normalized[column] for column in columns),
                )
                new_key = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                self._apply_invariants(connection, name, new_key, normalized)
                self._record_local_edit(
                    connection,
                    name,
                    new_key,
                    "insert",
                    self._summary(name, normalized),
                )
                return {"ok": True, "key": int(new_key), "table": name}

            return self._guard_write(self._touched_tables(name), action)

    def update(self, table: str, key: Any, values: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            name = self._require_table(table)
            fields = self.table_fields(name)
            key_column = self._key_column(fields)
            existing = self.row(name, key)
            if existing is None:
                raise DataError("未找到要修改的记录。")
            normalized = self._normalize(name, values, creating=False, key=key)

            def action(connection: sqlite3.Connection) -> Dict[str, Any]:
                setters = ", ".join(f"{_quote(column)} = ?" for column in normalized)
                connection.execute(
                    f"UPDATE {_quote(name)} SET {setters} "
                    f"WHERE {_quote(key_column)} = ?",
                    (*normalized.values(), key),
                )
                self._apply_invariants(connection, name, key, normalized)
                self._record_local_edit(
                    connection,
                    name,
                    key,
                    "update",
                    self._summary(name, {**existing, **normalized}),
                )
                return {"ok": True, "key": key, "table": name}

            return self._guard_write(self._touched_tables(name), action)

    @staticmethod
    def _delete_rows(
        connection: sqlite3.Connection,
        table: str,
        spec: data_schema.TableSpec,
        fields: Sequence[Dict[str, Any]],
        key_column: str,
        keys: Sequence[Any],
    ) -> List[Tuple[Any, Dict[str, Any]]]:
        """Delete rows plus their cascade children, returning the removed parents."""
        column_names = [str(field["name"]) for field in fields]
        removed: List[Tuple[Any, Dict[str, Any]]] = []
        for key in keys:
            parent = connection.execute(
                f"SELECT * FROM {_quote(table)} WHERE {_quote(key_column)} = ?",
                (key,),
            ).fetchone()
            if parent is None:
                continue
            parent_row = dict(zip(column_names, parent))
            for child_table, child_column, parent_column in spec.cascade:
                parent_value = parent_row.get(parent_column)
                if parent_value in (None, ""):
                    continue
                connection.execute(
                    f"DELETE FROM {_quote(child_table)} "
                    f"WHERE {_quote(child_column)} = ?",
                    (parent_value,),
                )
            connection.execute(
                f"DELETE FROM {_quote(table)} WHERE {_quote(key_column)} = ?",
                (key,),
            )
            removed.append((key, parent_row))
        return removed

    def delete(self, table: str, keys: List[Any]) -> Dict[str, Any]:
        with self._lock:
            name = self._require_table(table)
            spec = data_schema.spec_for(name)
            if not spec.editable:
                raise DataError(f"「{spec.label}」为只读表，不能删除记录。")
            key_list = [item for item in (keys or []) if item not in (None, "")]
            if not key_list:
                raise DataError("请选择要删除的记录。")
            fields = self.table_fields(name)
            key_column = self._key_column(fields)

            def action(connection: sqlite3.Connection) -> Dict[str, Any]:
                removed = self._delete_rows(
                    connection, name, spec, fields, key_column, key_list
                )
                if not removed:
                    raise DataError("未找到要删除的记录。")
                for key, parent_row in removed:
                    self._record_local_edit(
                        connection,
                        name,
                        key,
                        "delete",
                        self._summary(name, parent_row),
                    )
                return {"ok": True, "deleted": len(removed), "table": name}

            return self._guard_write(self._touched_tables(name), action)

    def delete_preview(self, table: str, key: Any) -> Dict[str, Any]:
        """Rows that a delete would remove.

        The preview is exact because it performs the delete inside a transaction
        and rolls it back, so foreign-key cascades and the declarative cascade
        rules are both accounted for.
        """
        with self._lock:
            connection = self._require_connection()
            name = self._require_table(table)
            spec = data_schema.spec_for(name)
            if not spec.editable:
                raise DataError(f"「{spec.label}」为只读表，不能删除记录。")
            fields = self.table_fields(name)
            key_column = self._key_column(fields)
            existing = self.row(name, key)
            if existing is None:
                raise DataError("未找到要删除的记录。")

            def counts() -> Dict[str, int]:
                return {
                    item: int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {_quote(item)}"
                        ).fetchone()[0]
                    )
                    for item in self.table_names()
                }

            if connection.in_transaction:
                connection.rollback()
            before = counts()
            connection.execute("BEGIN IMMEDIATE")
            after: Dict[str, int] = {}
            try:
                self._delete_rows(connection, name, spec, fields, key_column, [key])
                after = counts()
            finally:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
            removed = {
                item: before[item] - after.get(item, before[item])
                for item in before
                if before[item] - after.get(item, before[item]) > 0
            }
            deleted_self = int(removed.pop(name, 0))
            children = [
                {
                    "table": item,
                    "label": data_schema.spec_for(item).label,
                    "group": data_schema.spec_for(item).group,
                    "count": int(count),
                }
                for item, count in sorted(removed.items())
            ]
            return {
                "ok": True,
                "table": name,
                "label": spec.label,
                "key": key,
                "summary": self._summary(name, existing),
                "deleted_self": deleted_self,
                "children": children,
                "total_removed": deleted_self + sum(
                    int(child["count"]) for child in children
                ),
            }

    def form_meta(self, table: str) -> Dict[str, Any]:
        """Schema-driven description of one table for the curated editor UI."""
        with self._lock:
            connection = self._require_connection()
            name = self._require_table(table)
            spec = data_schema.spec_for(name)
            fields = self.table_fields(name)
            reference_map: Dict[str, Tuple[str, str]] = {}
            try:
                for reference in connection.execute(
                    f"PRAGMA foreign_key_list({_quote(name)})"
                ).fetchall():
                    reference_map.setdefault(
                        str(reference[3]), (str(reference[2]), str(reference[4] or "id"))
                    )
            except sqlite3.Error:
                pass
            for column, parent, parent_column in spec.references:
                reference_map.setdefault(str(column), (str(parent), str(parent_column)))
            field_metas = []
            for field in fields:
                column = str(field["name"])
                required = column in spec.required or (
                    bool(field.get("notnull"))
                    and field.get("default") is None
                    and not bool(field.get("pk"))
                )
                reference = reference_map.get(column)
                field_metas.append(
                    {
                        "name": column,
                        "label": data_schema.field_label(column),
                        "type": str(field.get("type") or ""),
                        "notnull": bool(field.get("notnull")),
                        "default": field.get("default"),
                        "max_length": spec.max_length_of(column),
                        "required": required,
                        "primary_key": bool(field.get("pk")),
                        "multiline": column in data_schema.MULTILINE_FIELDS,
                        "reference": (
                            {
                                "table": reference[0],
                                "label": data_schema.spec_for(reference[0]).label,
                                "column": reference[1],
                            }
                            if reference
                            else None
                        ),
                    }
                )
            return {
                "ok": True,
                "table": name,
                "label": spec.label,
                "group": spec.group,
                "note": spec.note,
                "editable": bool(spec.editable),
                "key_column": self._key_column(fields),
                "display": list(spec.display),
                "fields": field_metas,
                "cascade": [
                    {
                        "table": child,
                        "label": data_schema.spec_for(child).label,
                        "column": column,
                    }
                    for child, column, _ in spec.cascade
                ],
            }

    def reference_options(
        self, table: str, column: str, keyword: str = "", limit: int = 200
    ) -> Dict[str, Any]:
        """Candidate values for a reference (foreign key) field."""
        with self._lock:
            connection = self._require_connection()
            name = self._require_table(table)
            spec = data_schema.spec_for(name)
            reference = next(
                (
                    item
                    for item in spec.references
                    if str(item[0]) == str(column)
                ),
                None,
            )
            if reference is None:
                raise DataError("该字段不是关联字段。")
            _, parent_table, parent_column = reference
            parent_spec = data_schema.spec_for(parent_table)
            label_column = (
                parent_spec.display[0]
                if parent_spec.display and parent_spec.display[0] in self._columns(parent_table)
                else parent_column
            )
            limit = max(1, min(500, int(limit or 200)))
            text = str(keyword or "").strip()
            where = ""
            params: List[Any] = []
            if text:
                where = f" WHERE LOWER(CAST({_quote(label_column)} AS TEXT)) LIKE LOWER(?)"
                params.append(f"%{text}%")
            rows = connection.execute(
                f"SELECT {_quote(parent_column)}, {_quote(label_column)} "
                f"FROM {_quote(parent_table)}{where} "
                f"ORDER BY {_quote(label_column)} LIMIT ?",
                [*params, limit],
            ).fetchall()
            return {
                "ok": True,
                "table": name,
                "column": column,
                "parent": parent_table,
                "options": [
                    {"value": "" if row[0] is None else str(row[0]),
                     "label": "" if row[1] is None else str(row[1])}
                    for row in rows
                ],
            }

    def _columns(self, table: str) -> List[str]:
        return [str(field["name"]) for field in self.table_fields(table)]

    def batch_update(self, table: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            name = self._require_table(table)
            if not edits:
                raise DataError("没有要提交的更改。")
            fields = self.table_fields(name)
            key_column = self._key_column(fields)
            prepared: List[Tuple[Any, Dict[str, Any], Dict[str, Any]]] = []
            for edit in edits:
                key = edit.get("id", edit.get("key"))
                if key is None:
                    raise DataError("批量修改缺少记录标识。")
                existing = self.row(name, key)
                if existing is None:
                    raise DataError("未找到要修改的记录。")
                normalized = self._normalize(name, edit.get("values") or {}, creating=False, key=key)
                prepared.append((key, normalized, existing))

            def action(connection: sqlite3.Connection) -> Dict[str, Any]:
                for key, normalized, existing in prepared:
                    setters = ", ".join(f"{_quote(column)} = ?" for column in normalized)
                    connection.execute(
                        f"UPDATE {_quote(name)} SET {setters} "
                        f"WHERE {_quote(key_column)} = ?",
                        (*normalized.values(), key),
                    )
                    self._apply_invariants(connection, name, key, normalized)
                    self._record_local_edit(
                        connection,
                        name,
                        key,
                        "update",
                        self._summary(name, {**existing, **normalized}),
                    )
                return {"ok": True, "committed": len(prepared), "table": name}

            return self._guard_write(self._touched_tables(name), action)

    # -------------------------------------------------------- global search

    def _editable_text_columns(self, table: str) -> List[str]:
        return [
            str(field["name"])
            for field in self.table_fields(table)
            if str(field["name"]) not in ("id", "rowid")
        ]

    def global_search(self, keyword: str, exact: bool = False) -> List[Dict[str, Any]]:
        text = str(keyword or "").strip()
        if not text:
            return []
        with self._lock:
            connection = self._require_connection()
            results: List[Dict[str, Any]] = []
            for table in data_schema.editable_table_names():
                if table not in self.table_names():
                    continue
                columns = self._editable_text_columns(table)
                where, params = self._keyword_clause(columns, text, exact)
                if not where:
                    continue
                key_column = self._key_column(self.table_fields(table))
                selected = ", ".join(
                    [_quote(key_column), *( _quote(column) for column in columns)]
                )
                try:
                    rows = connection.execute(
                        f"SELECT {selected} FROM {_quote(table)}{where} LIMIT 500",
                        params,
                    ).fetchall()
                except sqlite3.Error:
                    continue
                for row in rows:
                    row_id = row[0]
                    for index, column in enumerate(columns, start=1):
                        value = row[index]
                        text_value = "" if value is None else str(value)
                        hit = text_value == text if exact else text in text_value
                        if hit:
                            results.append(
                                {
                                    "table": table,
                                    "id": row_id,
                                    "field": column,
                                    "value": value,
                                }
                            )
                            if len(results) >= 500:
                                return results
            return results

    def replace_preview(self, keyword: str, replacement: str) -> List[Dict[str, Any]]:
        text = str(keyword or "")
        if not text:
            raise DataError("请先填写查找内容。")
        previews = []
        for match in self.global_search(text):
            value = "" if match["value"] is None else str(match["value"])
            previews.append({**match, "new_value": value.replace(text, str(replacement or ""))})
        return previews

    def replace_apply(
        self, keyword: str, replacement: str, matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        text = str(keyword or "")
        if not text:
            raise DataError("请先填写查找内容。")
        if not matches:
            raise DataError("没有要替换的匹配项。")
        editable = set(data_schema.editable_table_names())
        prepared: List[Tuple[str, str, Any]] = []
        for match in matches:
            table = str(match.get("table") or "")
            column = str(match.get("field") or "")
            if table not in editable:
                raise DataError(f"「{table}」为只读表，不能替换。")
            if column not in self._editable_text_columns(table):
                raise DataError(f"字段「{column}」不存在。")
            prepared.append((table, column, match.get("id")))
        tables = {table for table, _, _ in prepared}

        def action(connection: sqlite3.Connection) -> Dict[str, Any]:
            replaced = 0
            for table, column, row_id in prepared:
                key_column = self._key_column(self.table_fields(table))
                cursor = connection.execute(
                    f"UPDATE {_quote(table)} "
                    f"SET {_quote(column)} = REPLACE({_quote(column)}, ?, ?) "
                    f"WHERE {_quote(key_column)} = ?",
                    (text, str(replacement or ""), row_id),
                )
                if cursor.rowcount and cursor.rowcount > 0:
                    replaced += 1
            if replaced:
                self._record_local_edit(
                    connection,
                    "多个表" if len(tables) > 1 else next(iter(tables)),
                    "-",
                    "replace",
                    f"全局替换「{text}」→「{replacement or ''}」",
                )
            return {"ok": True, "replaced": replaced}

        return self._guard_write(tables, action)

    # ------------------------------------------------------------- diagnose

    def diagnose(self) -> Dict[str, Any]:
        with self._lock:
            connection = self._require_connection()
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                integrity_text = str(integrity[0]).lower() if integrity else "unknown"
            except sqlite3.Error:
                integrity_text = "error"
            try:
                violations = len(connection.execute("PRAGMA foreign_key_check").fetchall())
            except sqlite3.Error:
                violations = -1
            orphans = []
            for check in ORPHAN_CHECKS:
                try:
                    count = connection.execute(check["sql"]).fetchone()[0]
                except sqlite3.Error:
                    count = -1
                orphans.append(
                    {
                        "table": check["table"],
                        "label": check["label"],
                        "count": int(count),
                    }
                )
            tables = []
            for name in self.table_names():
                try:
                    rows = connection.execute(
                        f"SELECT COUNT(*) FROM {_quote(name)}"
                    ).fetchone()[0]
                except sqlite3.Error:
                    rows = -1
                tables.append(
                    {
                        "name": name,
                        "rows": int(rows),
                        "group": data_schema.spec_for(name).group,
                    }
                )
            pragmas = {
                "foreign_keys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
                "busy_timeout": connection.execute("PRAGMA busy_timeout").fetchone()[0],
                "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0],
                "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
            }
            return {
                "ok": integrity_text == "ok",
                "integrity": integrity_text,
                "foreign_key_violations": violations,
                "orphans": orphans,
                "tables": tables,
                "local_edits": self._local_edits_count(connection),
                "pragmas": pragmas,
            }

    # --------------------------------------------------------- local ledger

    def _local_edits_count(self, connection: sqlite3.Connection) -> int:
        try:
            return int(
                connection.execute("SELECT COUNT(*) FROM local_edits").fetchone()[0]
            )
        except sqlite3.Error:
            return 0

    def local_edits_count(self) -> int:
        with self._lock:
            return self._local_edits_count(self._require_connection())

    def local_edits(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            connection = self._require_connection()
            try:
                rows = connection.execute(
                    "SELECT id, table_name, row_key, op, summary, changed_at "
                    "FROM local_edits ORDER BY id DESC LIMIT ?",
                    (max(1, min(500, int(limit or 100))),),
                ).fetchall()
            except sqlite3.Error:
                return []
            return [
                {
                    "id": row[0],
                    "table": row[1],
                    "row_key": row[2],
                    "op": row[3],
                    "summary": row[4],
                    "changed_at": row[5],
                }
                for row in rows
            ]

    # -------------------------------------------------------- recovery points

    def _backup_directory(self) -> Path:
        directory = Path(self.backups_dir)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def backup_create(self, reason: str = "manual") -> Dict[str, Any]:
        with self._lock:
            connection = self._require_connection()
            directory = self._backup_directory()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = f"translated_{stamp}_{_safe_reason(reason)}"
            target = directory / f"{base}.db"
            suffix = 1
            while target.exists():
                target = directory / f"{base}_{suffix}.db"
                suffix += 1
            snapshot = sqlite3.connect(str(target))
            try:
                connection.backup(snapshot)
            finally:
                snapshot.close()
            identity = database_identity(target)
            sidecar = {
                "db_version": identity["db_version"],
                "sha1": identity["sha1"],
                "size": identity["size"],
                "created_at": _now_iso(),
                "reason": str(reason or "manual"),
                "source": "installed",
            }
            target.with_suffix(".db.json").write_text(
                json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return {"ok": True, "path": str(target), **sidecar}

    def backup_list(self) -> List[Dict[str, Any]]:
        directory = Path(self.backups_dir)
        if not directory.is_dir():
            return []
        entries: List[Dict[str, Any]] = []
        for path in directory.glob("translated_*.db"):
            sidecar_path = path.with_suffix(".db.json")
            if not sidecar_path.is_file():
                continue
            try:
                sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            try:
                if int(sidecar.get("size", -1)) != path.stat().st_size:
                    continue
                if str(sidecar.get("sha1", "")).lower() != hashlib.sha1(
                    path.read_bytes()
                ).hexdigest():
                    continue
            except OSError:
                continue
            entries.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "db_version": int(sidecar.get("db_version", 0) or 0),
                    "size": int(sidecar.get("size", 0) or 0),
                    "sha1": str(sidecar.get("sha1", "")),
                    "created_at": str(sidecar.get("created_at", "")),
                    "reason": str(sidecar.get("reason", "")),
                }
            )
        entries.sort(key=lambda item: (item["created_at"], item["name"]), reverse=True)
        return entries

    def backup_prune(self, keep: int = DEFAULT_BACKUP_KEEP) -> int:
        keep = max(1, int(keep or DEFAULT_BACKUP_KEEP))
        entries = self.backup_list()
        removed = 0
        for entry in entries[keep:]:
            for suffix in ("", ".json"):
                target = Path(entry["path"] + suffix)
                try:
                    if target.is_file():
                        target.unlink()
                except OSError:
                    continue
            removed += 1
        return removed
