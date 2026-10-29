"""Android bridge for the Alician Dictionary Lite business services.

The UI talks to a single JSON-in/JSON-out function so the Kotlin boundary stays
small and every result can be logged and regression-tested independently.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_lock = threading.RLock()
_db_path = ""
_data_dir = ""
_dictionary = None
_writing = None
_translator = None
_dbmanager = None
_data_core = None
_remote_candidate = ""
_MAX_DIFF_DETAILS = 2000
_TRANSLATOR_TABLES = {
    "dictionary",
    "phrase",
    "dictionary_semantic_aliases",
    "dictionary_sense_expansions",
    "adverb_position_stats",
    "songs",
}


def _json_default(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default)


def _ok(**kwargs: Any) -> Dict[str, Any]:
    return {"ok": True, **kwargs}


def _close_services() -> None:
    global _dictionary, _writing, _translator, _dbmanager, _data_core
    # The dictionary handler shares DataCore's connection, so DataCore closes last.
    for service in (_dictionary, _writing, _translator, _dbmanager, _data_core):
        if service is not None:
            try:
                service.close()
            except Exception:
                pass
    _dictionary = _writing = _translator = _dbmanager = _data_core = None


def _on_data_write(tables: Any) -> None:
    """Invalidate in-memory caches after a committed data-layer write."""
    _reload_translator_if_needed(tables)


def _open_services() -> None:
    global _dictionary, _writing, _translator, _dbmanager, _data_core
    from webui_backend.dictionary_core import DictionaryConfig
    from webui_backend.dictionary_service import DictionaryService
    from webui_backend.data_core import DataCore
    from webui_backend.writing_database import DatabaseManager
    from webui_backend.writing_service import WritingAssistantService
    from webui_backend.translation_service import TranslationService
    from webui_backend.dbmanager_service import DatabaseManagerService

    DictionaryConfig.DB_NAME = _db_path
    DictionaryConfig.CURRENT_DB = _db_path
    DatabaseManager().close_connection()
    # Single writer: one connection, one set of PRAGMAs, one set of write rules.
    _data_core = DataCore(_db_path, backups_dir=str(Path(_data_dir) / "backups"))
    if not _data_core.connect():
        raise RuntimeError(f"无法打开数据库：{_db_path}")
    _data_core.set_event_sink(_on_data_write)
    _dictionary = DictionaryService(enable_semantic=False, core=_data_core)
    _writing = WritingAssistantService()
    _translator = TranslationService(_db_path, enable_fallback_matching=False)
    _dbmanager = DatabaseManagerService(core=_data_core)


def _reload_translator_if_needed(table_names: Any) -> None:
    global _translator
    normalized = {str(name or "") for name in (table_names or [])}
    if not normalized.intersection(_TRANSLATOR_TABLES):
        return
    from webui_backend.translation_service import TranslationService

    replacement = TranslationService(_db_path, enable_fallback_matching=False)
    previous = _translator
    _translator = replacement
    if previous is not None:
        previous.close()


def initialize(db_path: str, data_dir: str) -> str:
    global _db_path, _data_dir
    with _lock:
        resolved_db = str(Path(db_path).resolve())
        resolved_data = str(Path(data_dir).resolve())
        Path(resolved_data).mkdir(parents=True, exist_ok=True)
        if not Path(resolved_db).is_file():
            return _dumps({"ok": False, "message": f"数据库不存在：{resolved_db}"})
        _close_services()
        _db_path = resolved_db
        _data_dir = resolved_data
        os.environ["ALICIAN_DB_PATH"] = resolved_db
        os.environ["ALICIAN_LITE_BUILD"] = "1"
        os.chdir(resolved_data)
        _open_services()
        return _dumps(_ok(
            message="移动端服务已就绪。",
            features={
                "lite": True,
                "translator": True,
                "fuzzy_search": True,
                "semantic_search": False,
            },
            database=_database_info(),
        ))


def _ensure_ready() -> None:
    if not all((_dictionary, _writing, _translator, _dbmanager, _data_core)):
        raise RuntimeError("移动端服务尚未初始化。")


def _database_info() -> Dict[str, Any]:
    path = Path(_db_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    table_count = 0
    word_count = 0
    song_count = 0
    if path.is_file():
        with sqlite3.connect(path) as conn:
            table_count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
            word_count = conn.execute("SELECT COUNT(*) FROM dictionary_headwords").fetchone()[0]
            song_count = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
    return {
        "path": str(path),
        "size": path.stat().st_size if path.is_file() else 0,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        if path.is_file() else "",
        "sha256": digest,
        "table_count": table_count,
        "word_count": word_count,
        "song_count": song_count,
    }


def _database_metadata() -> Dict[str, Any]:
    """Version marker stored inside the database itself.

    Databases published before the marker existed simply report version 0, which
    lets the app offer them the first versioned update.
    """
    path = Path(_db_path)
    values: Dict[str, str] = {}
    if path.is_file():
        connection = sqlite3.connect(path)
        try:
            for key, value in connection.execute("SELECT key, value FROM database_metadata"):
                values[str(key)] = str(value)
        except sqlite3.Error:
            values = {}
        finally:
            connection.close()
    try:
        version = int(values.get("db_version", "0"))
    except (TypeError, ValueError):
        version = 0
    return _ok(database_version=version, metadata=values)


def _table_page(payload: Dict[str, Any]) -> Dict[str, Any]:
    from webui_backend.data_core import DataError

    table = str(payload.get("table") or "")
    keyword = str(payload.get("keyword") or "")
    exact = bool(payload.get("exact", False))
    offset = max(0, int(payload.get("offset", 0)))
    limit = max(1, min(200, int(payload.get("limit", 50))))
    try:
        page = _data_core.page(
            table, keyword=keyword, exact=exact, offset=offset, limit=limit
        )
    except DataError as error:
        return {"ok": False, "message": str(error)}
    return _ok(
        table=page["table"],
        fields=page["fields"],
        data=page["rows"],
        total=page["total"],
        offset=page["offset"],
        limit=page["limit"],
    )


def _export_csv_zip(path: str) -> Dict[str, Any]:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=_data_dir) as temp_dir:
        temp_root = Path(temp_dir)
        with sqlite3.connect(_db_path) as conn:
            tables = [
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            for table in tables:
                safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in table)
                csv_path = temp_root / f"{safe_name}.csv"
                escaped = table.replace('"', '""')
                cursor = conn.execute(f'SELECT * FROM "{escaped}"')
                with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
                    writer = csv.writer(handle)
                    writer.writerow([item[0] for item in cursor.description])
                    writer.writerows(cursor)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for csv_path in sorted(temp_root.glob("*.csv")):
                archive.write(csv_path, csv_path.name)
    return _ok(path=str(output), size=output.stat().st_size, message="CSV 压缩包已生成。")


def _run_maintenance(kind: str) -> Dict[str, Any]:
    _close_services()
    try:
        if kind == "word_count":
            from update_word_count import main
            main(verbose=False)
            message = "词频与泛度已更新。"
        else:
            from classify_words import classify_words
            classify_words()
            message = "词性统计表已更新。"
    finally:
        _open_services()
    return _ok(message=message, database=_database_info())


def _validate_database(path: Path) -> None:
    required = {"dictionary", "dictionary_headwords", "songs", "phrase", "raw"}
    with sqlite3.connect(path) as conn:
        present = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = sorted(required - present)
        if missing:
            raise ValueError("数据库缺少必要数据表：" + "、".join(missing))
        conn.execute("PRAGMA integrity_check").fetchone()


def _compare_database_counts(remote_path: Path) -> Dict[str, Any]:
    summary = {}
    for label, path in (("local", Path(_db_path)), ("remote", remote_path)):
        with sqlite3.connect(path) as conn:
            summary[label] = {
                "words": conn.execute("SELECT COUNT(*) FROM dictionary_headwords").fetchone()[0],
                "senses": conn.execute("SELECT COUNT(*) FROM dictionary").fetchone()[0],
                "songs": conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0],
                "phrases": conn.execute("SELECT COUNT(*) FROM phrase").fetchone()[0],
            }
    return summary


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _database_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    }


def _database_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({_quoted_identifier(table)})")
    ]


def _diff_value(value: Any, max_len: int = 240) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= max_len else text[:max_len] + "..."


def _read_diff_rows(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
    identity: str,
) -> Dict[Any, Dict[str, Any]]:
    selected = ", ".join(_quoted_identifier(column) for column in columns)
    identity_sql = _quoted_identifier(identity) if identity != "rowid" else "rowid"
    sql = (
        f"SELECT {identity_sql} AS __diff_id__"
        + (f", {selected}" if selected else "")
        + f" FROM {_quoted_identifier(table)}"
    )
    result: Dict[Any, Dict[str, Any]] = {}
    for row in conn.execute(sql):
        result[row[0]] = dict(zip(columns, row[1:]))
    return result


def _row_diff_payload(
    row_id: Any,
    values: Dict[str, Any],
    identity: str,
) -> Dict[str, Any]:
    return {
        "id": str(row_id),
        "values": {
            key: _diff_value(value)
            for key, value in values.items()
            if key not in {identity, "rowid"}
        },
    }


def _build_database_diff(local_path: Path, remote_path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "total_added": 0,
        "total_removed": 0,
        "total_modified": 0,
        "total_field_changes": 0,
        "tables": [],
    }
    with sqlite3.connect(local_path) as local_conn, sqlite3.connect(remote_path) as remote_conn:
        local_tables = _database_tables(local_conn)
        remote_tables = _database_tables(remote_conn)
        for table in sorted(local_tables | remote_tables):
            local_columns = (
                _database_columns(local_conn, table) if table in local_tables else []
            )
            remote_columns = (
                _database_columns(remote_conn, table) if table in remote_tables else []
            )
            local_count = (
                local_conn.execute(
                    f"SELECT COUNT(*) FROM {_quoted_identifier(table)}"
                ).fetchone()[0]
                if table in local_tables else 0
            )
            remote_count = (
                remote_conn.execute(
                    f"SELECT COUNT(*) FROM {_quoted_identifier(table)}"
                ).fetchone()[0]
                if table in remote_tables else 0
            )
            common_columns = [
                column for column in remote_columns if column in local_columns
            ]
            identity = "id" if "id" in common_columns else "rowid"
            local_read_columns = common_columns
            remote_read_columns = common_columns
            if table not in remote_tables:
                identity = "id" if "id" in local_columns else "rowid"
                local_read_columns = local_columns
            elif table not in local_tables:
                identity = "id" if "id" in remote_columns else "rowid"
                remote_read_columns = remote_columns
            elif not common_columns:
                local_read_columns = local_columns
                remote_read_columns = remote_columns

            local_rows = (
                _read_diff_rows(local_conn, table, local_read_columns, identity)
                if table in local_tables else {}
            )
            remote_rows = (
                _read_diff_rows(remote_conn, table, remote_read_columns, identity)
                if table in remote_tables else {}
            )
            local_ids = set(local_rows)
            remote_ids = set(remote_rows)
            added_ids = sorted(remote_ids - local_ids, key=str)
            removed_ids = sorted(local_ids - remote_ids, key=str)
            common_ids = sorted(local_ids & remote_ids, key=str)

            added_rows = [
                _row_diff_payload(row_id, remote_rows[row_id], identity)
                for row_id in added_ids[:_MAX_DIFF_DETAILS]
            ]
            removed_rows = [
                _row_diff_payload(row_id, local_rows[row_id], identity)
                for row_id in removed_ids[:_MAX_DIFF_DETAILS]
            ]
            field_diffs = []
            modified = 0
            field_changes = 0
            for row_id in common_ids:
                row_changed = False
                for column in common_columns:
                    local_value = local_rows[row_id].get(column)
                    remote_value = remote_rows[row_id].get(column)
                    if str(local_value) == str(remote_value):
                        continue
                    row_changed = True
                    field_changes += 1
                    if len(field_diffs) < _MAX_DIFF_DETAILS:
                        field_diffs.append({
                            "row_id": str(row_id),
                            "column": column,
                            "local_value": _diff_value(local_value, 120),
                            "remote_value": _diff_value(remote_value, 120),
                        })
                if row_changed:
                    modified += 1

            table_diff = {
                "table": table,
                "local_rows": local_count,
                "remote_rows": remote_count,
                "added": len(added_ids),
                "removed": len(removed_ids),
                "modified": modified,
                "field_changes": field_changes,
                "added_rows": added_rows,
                "removed_rows": removed_rows,
                "field_diffs": field_diffs,
                "truncated_added": len(added_ids) > len(added_rows),
                "truncated_removed": len(removed_ids) > len(removed_rows),
                "truncated_modified": field_changes > len(field_diffs),
            }
            if len(added_ids) or len(removed_ids) or modified:
                result["tables"].append(table_diff)
            result["total_added"] += len(added_ids)
            result["total_removed"] += len(removed_ids)
            result["total_modified"] += modified
            result["total_field_changes"] += field_changes
    return result


def _check_remote_update() -> Dict[str, Any]:
    global _remote_candidate
    remote = Path(_data_dir) / "remote_translated.db"
    request = urllib.request.Request(
        "https://raw.githubusercontent.com/Meartraep/Alician_dictionary/main/translated.db",
        headers={"User-Agent": "AlicianDictionaryMobile/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        with remote.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    _validate_database(remote)
    local_path = Path(_db_path)
    local_sha = hashlib.sha1(local_path.read_bytes()).hexdigest()
    remote_sha = hashlib.sha1(remote.read_bytes()).hexdigest()
    local_version = _read_database_version(local_path)
    remote_version = _read_database_version(remote)
    if local_version > 0 and remote_version > 0:
        # The version marker is the database identity; the byte hash additionally
        # changes whenever the user edits a word locally, and comparing hashes
        # alone used to make the app report "update available" forever.
        up_to_date = local_version >= remote_version
    else:
        up_to_date = local_sha == remote_sha
    local_modified = up_to_date and local_sha != remote_sha
    _remote_candidate = str(remote)
    if up_to_date:
        message = "本地词条有手工修改，云端数据库为同一版本。" if local_modified else "已是最新数据库。"
    else:
        message = "发现新的云端数据库。"
    return _ok(
        up_to_date=up_to_date,
        local_modified=local_modified,
        local_sha1=local_sha,
        remote_sha1=remote_sha,
        local_db_version=local_version,
        remote_db_version=remote_version,
        comparison=_compare_database_counts(remote),
        diff=(
            {
                "total_added": 0,
                "total_removed": 0,
                "total_modified": 0,
                "total_field_changes": 0,
                "tables": [],
            }
            if up_to_date else _build_database_diff(local_path, remote)
        ),
        message=message,
    )


def _apply_remote_update() -> Dict[str, Any]:
    candidate = Path(_remote_candidate)
    if not candidate.is_file():
        return {"ok": False, "message": "请先检查更新。"}
    _validate_database(candidate)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(_data_dir) / f"translated.backup_{timestamp}.db"
    _close_services()
    try:
        shutil.copy2(_db_path, backup)
        shutil.copy2(candidate, _db_path)
    finally:
        _open_services()
    return _ok(
        message="数据库已更新，旧版本已自动备份。",
        backup=str(backup),
        database=_database_info(),
    )


def _read_database_version(path: Path) -> int:
    """Version marker of an arbitrary database file (0 when it has none)."""
    if not path.is_file():
        return 0
    connection = sqlite3.connect(path)
    try:
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


PUBLICATION_FORMAT = "alician-lite"


def _publication_manifest(entry: Dict[str, Any], database_url: str,
                          database_format: str) -> Dict[str, Any]:
    """Mirror of database_versioning.build_manifest (asserted by the tests).

    The manifest's "url" is where clients download the database itself, not where
    the manifest lives.
    """
    return {
        "db_version": int(entry["db_version"]),
        "published_at": entry["published_at"],
        "notes": entry.get("notes", ""),
        "format": database_format,
        "size": int(entry["size"]),
        "sha1": entry["sha1"],
        "url": database_url,
    }


def _prepare_database_publication(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Stamp the next version into a copy of the local database.

    The phone -- not the CI pipeline -- writes the version, so no bot commit is
    pushed to the pull request. The pipeline still enforces that the version is
    exactly the one after the published ledger, so a stale ledger is refused here
    before anything is uploaded.

    Returns the stamped database path plus the ledger and manifest files to commit.
    """
    source = Path(str(payload.get("source") or ""))
    target = Path(str(payload.get("target") or ""))
    database_url = str(payload.get("database_url") or "")
    database_format = str(payload.get("format") or PUBLICATION_FORMAT)
    notes = " ".join(str(payload.get("notes") or "").split())[:500]
    published_at = str(payload.get("published_at") or "") or \
        datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not source.is_file():
        raise ValueError("本地数据库不存在，无法发布。")
    if not notes:
        raise ValueError("请填写版本说明。")
    try:
        entries = json.loads(str(payload.get("ledger_json") or ""))
    except ValueError as error:
        raise ValueError("无法读取已发布台账：%s" % error)
    if not isinstance(entries, list) or not entries:
        raise ValueError("已发布台账为空，无法确定下一个版本号。")

    try:
        published_version = int(entries[-1]["db_version"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("已发布台账的最后一条缺少版本号。")
    expected = published_version + 1
    requested = int(payload.get("version") or expected)
    if requested != expected:
        raise ValueError(
            "台账已更新（当前 v%d），请重新检查更新后重试。" % published_version)

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(target)
    try:
        # SQLite's backup API copies a consistent snapshot even while the app holds
        # the database open.
        source_connection.backup(target_connection)
        target_connection.execute(
            "CREATE TABLE IF NOT EXISTS database_metadata (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in (
            ("db_version", str(requested)),
            ("published_at", published_at),
            ("notes", notes),
            ("format", database_format),
        ):
            target_connection.execute(
                "INSERT OR REPLACE INTO database_metadata (key, value) VALUES (?, ?)",
                (key, value))
        target_connection.commit()
    finally:
        source_connection.close()
        target_connection.close()

    digest = hashlib.sha1(target.read_bytes()).hexdigest()
    size = target.stat().st_size
    entry = {
        "db_version": requested,
        "sha1": digest,
        "size": size,
        "published_at": published_at,
        "app_tag": "",
        "notes": notes,
    }
    return {
        "ok": True,
        "version": requested,
        "previous_version": published_version,
        "previous_sha1": str(entries[-1]["sha1"]).lower(),
        "published_at": published_at,
        "size": size,
        "sha1": digest,
        "database_path": str(target),
        "ledger_json": json.dumps(list(entries) + [entry], ensure_ascii=False, indent=2) + "\n",
        "manifest_json": json.dumps(
            _publication_manifest(entry, database_url, database_format),
            ensure_ascii=False, indent=2) + "\n",
    }


def _replace_database(source_path: str, expected_db_version: Optional[int] = None) -> Dict[str, Any]:
    source = Path(source_path)
    _validate_database(source)
    if expected_db_version is not None:
        actual = _read_database_version(source)
        if actual != expected_db_version:
            raise ValueError(
                "数据库内容与发布清单不一致：清单为 v%d，文件为 v%d，已取消更新。"
                % (expected_db_version, actual)
            )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(_data_dir) / f"translated.backup_{timestamp}.db"
    _close_services()
    try:
        shutil.copy2(_db_path, backup)
        shutil.copy2(source, _db_path)
    finally:
        _open_services()
    return _ok(
        message="数据库导入成功，原数据库已备份。",
        backup=str(backup),
        database=_database_info(),
    )


def _data_page(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Server-side paginated table page with the table's UI metadata."""
    from webui_backend import data_schema
    from webui_backend.data_core import DataError

    table = str(payload.get("table") or "")
    keyword = str(payload.get("keyword") or "")
    exact = bool(payload.get("exact", False))
    offset = max(0, int(payload.get("offset", 0)))
    limit = max(1, min(200, int(payload.get("limit", 50))))
    try:
        page = _data_core.page(
            table, keyword=keyword, exact=exact, offset=offset, limit=limit
        )
    except DataError as error:
        return {"ok": False, "message": str(error)}
    spec = data_schema.spec_for(page["table"])
    return _ok(
        table=page["table"],
        label=spec.label,
        group=spec.group,
        editable=bool(spec.editable),
        display=list(spec.display),
        fields=page["fields"],
        rows=page["rows"],
        total=page["total"],
        offset=page["offset"],
        limit=page["limit"],
    )


def _data_call(action: Any) -> Dict[str, Any]:
    """Run a data-layer action, turning DataError into a clean user-facing failure."""
    from webui_backend.data_core import DataError

    try:
        return action()
    except DataError as error:
        return {"ok": False, "message": str(error)}


def _create_recovery_point(reason: str) -> str:
    """Snapshot the database before a destructive action.

    A destructive write must not proceed when the recovery point cannot be made:
    losing a word without a way back is worse than refusing the operation.
    """
    try:
        snapshot = _data_core.backup_create(reason)
    except Exception as error:  # noqa: BLE001 - report a Chinese reason instead
        raise RuntimeError(f"无法创建恢复点，已取消操作：{error}") from error
    return str(snapshot.get("path") or "")


def _restore_backup(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Restore a recovery point: validate, snapshot the current state, replace atomically."""
    from webui_backend.data_core import (
        DataError,
        atomic_replace_file,
        validate_database_file,
    )

    source = Path(str(payload.get("path") or ""))
    try:
        restored = validate_database_file(source)
    except DataError as error:
        return {"ok": False, "message": str(error)}
    safety: Dict[str, Any] = {}
    try:
        safety = _data_core.backup_create("before_restore")
    except Exception:  # noqa: BLE001 - a failed safety snapshot must not stop the restore
        safety = {}
    _close_services()
    try:
        atomic_replace_file(source, Path(_db_path))
    except DataError as error:
        _open_services()
        return {"ok": False, "message": str(error)}
    _open_services()
    return _ok(
        message="已恢复到所选恢复点。",
        restored=restored,
        safety_backup=str(safety.get("path") or ""),
        database=_database_info(),
    )


def invoke(method: str, payload_json: str = "{}") -> str:
    try:
        payload = json.loads(payload_json or "{}")
        with _lock:
            _ensure_ready()
            if method == "bootstrap":
                result = _ok(
                    history=_dictionary.get_history(),
                    writing_settings=_writing.get_settings(),
                    features={
                        "lite": True,
                        "translator": True,
                        "fuzzy_search": True,
                        "semantic_search": False,
                    },
                    database=_database_info(),
                )
            elif method == "dictionary_search":
                result = _dictionary.search(
                    str(payload.get("query") or ""),
                    bool(payload.get("exact", False)),
                    str(payload.get("position") or "any"),
                    record_history=bool(payload.get("record_history", True)),
                )
            elif method == "dictionary_examples":
                result = _dictionary.get_examples(
                    str(payload.get("word") or ""),
                    str(payload.get("position") or "any"),
                )
            elif method == "dictionary_song_lyrics":
                result = _dictionary.get_song_lyrics(
                    str(payload.get("title") or ""),
                    str(payload.get("album") or ""),
                )
            elif method == "dictionary_update_word":
                result = _dictionary.update_word_entry(
                    payload.get("headword_id"),
                    str(payload.get("original_word") or ""),
                    str(payload.get("word") or ""),
                    str(payload.get("display_explanation") or ""),
                    payload.get("senses") or [],
                )
                if result.get("ok"):
                    # The translator keeps the dictionary in memory; a word edit
                    # stays invisible to translate() until that cache is rebuilt.
                    _reload_translator_if_needed(["dictionary"])
                    _data_core.record_local_edit(
                        "dictionary_headwords",
                        payload.get("headword_id"),
                        "update",
                        str(result.get("word") or ""),
                        notify=False,
                    )
            elif method == "dictionary_entry":
                result = _dictionary.get_headword_entry(
                    int(payload.get("headword_id") or 0)
                )
            elif method == "dictionary_create_word":
                result = _dictionary.create_word_entry(
                    str(payload.get("word") or ""),
                    str(payload.get("display_explanation") or ""),
                    str(payload.get("display_class") or ""),
                    payload.get("senses") or [],
                )
                if result.get("ok"):
                    _reload_translator_if_needed(["dictionary"])
                    _data_core.record_local_edit(
                        "dictionary_headwords",
                        result.get("headword_id"),
                        "insert",
                        str(result.get("word") or ""),
                        notify=False,
                    )
            elif method == "dictionary_add_sense":
                result = _dictionary.add_sense_entry(
                    int(payload.get("headword_id") or 0),
                    str(payload.get("explanation") or ""),
                    str(payload.get("class") or ""),
                    str(payload.get("english") or ""),
                    str(payload.get("japanese") or ""),
                )
                if result.get("ok"):
                    _reload_translator_if_needed(["dictionary"])
                    _data_core.record_local_edit(
                        "dictionary",
                        result.get("sense_id"),
                        "insert",
                        str(payload.get("explanation") or ""),
                        notify=False,
                    )
            elif method == "dictionary_delete_sense":
                sense_id = int(payload.get("sense_id") or 0)
                backup = _create_recovery_point("before_delete_sense")
                result = _dictionary.delete_sense_entry(sense_id)
                if result.get("ok"):
                    result["backup"] = backup
                    _reload_translator_if_needed(["dictionary"])
                    _data_core.record_local_edit(
                        "dictionary", sense_id, "delete", "删除义项", notify=False
                    )
            elif method == "dictionary_delete_headword":
                headword_id = int(payload.get("headword_id") or 0)
                backup = _create_recovery_point("before_delete_word")
                result = _dictionary.delete_headword_entry(headword_id)
                if result.get("ok"):
                    result["backup"] = backup
                    _reload_translator_if_needed(["dictionary"])
                    _data_core.record_local_edit(
                        "dictionary_headwords",
                        headword_id,
                        "delete",
                        str(payload.get("word") or ""),
                        notify=False,
                    )
            elif method == "lyric_translations":
                result = _dictionary.get_lyric_translations(
                    str(payload.get("title") or ""),
                    str(payload.get("album") or ""),
                )
            elif method == "dictionary_update_lyric":
                result = _dictionary.update_song_lyric(
                    str(payload.get("title") or ""),
                    str(payload.get("album") or ""),
                    str(payload.get("lyric") or ""),
                )
                if result.get("ok"):
                    _reload_translator_if_needed(["songs"])
                    _data_core.record_local_edit(
                        "songs",
                        str(payload.get("title") or ""),
                        "update",
                        str(payload.get("title") or ""),
                        notify=False,
                    )
            elif method == "writing_check":
                result = _writing.check_text(str(payload.get("text") or ""))
            elif method == "writing_lookup":
                result = _writing.lookup_explanations(str(payload.get("text") or ""))
            elif method == "writing_get_settings":
                result = _ok(settings=_writing.get_settings())
            elif method == "writing_save_settings":
                result = _writing.save_settings(payload)
            elif method == "translate":
                result = _translator.translate(
                    str(payload.get("text") or ""),
                    str(payload.get("direction") or "auto"),
                    bool(payload.get("use_semantic_expansions", False)),
                )
            elif method == "db_tables":
                result = _ok(tables=_dbmanager.get_tables())
            elif method == "db_table_page":
                result = _table_page(payload)
            elif method == "db_add":
                table = str(payload.get("table") or "")
                result = _dbmanager.add_record(
                    table, payload.get("values") or {}
                )
            elif method == "db_update":
                table = str(payload.get("table") or "")
                result = _dbmanager.update_record(
                    table,
                    int(payload.get("id") or 0),
                    payload.get("values") or {},
                )
            elif method == "db_delete":
                table = str(payload.get("table") or "")
                result = _dbmanager.delete_records(
                    table, payload.get("ids") or []
                )
            elif method == "db_global_search":
                result = _dbmanager.global_search(
                    str(payload.get("keyword") or ""),
                    bool(payload.get("exact", False)),
                )
            elif method == "db_global_replace":
                records = payload.get("records") or []
                result = _dbmanager.global_replace(
                    str(payload.get("keyword") or ""),
                    str(payload.get("replacement") or ""),
                    records,
                )
            elif method == "data_tables":
                from webui_backend import data_schema

                result = _ok(
                    groups=data_schema.grouped_tables(),
                    editable=data_schema.editable_table_names(),
                )
            elif method == "data_diagnose":
                result = _data_core.diagnose()
            elif method == "data_page":
                result = _data_page(payload)
            elif method == "data_form":
                table = str(payload.get("table") or "")
                result = _data_call(lambda: _data_core.form_meta(table))
            elif method == "data_create":
                table = str(payload.get("table") or "")
                values = payload.get("values") or {}
                outcome = _data_call(lambda: _data_core.create(table, values))
                if outcome.get("ok"):
                    outcome["message"] = "记录已新增。"
                result = outcome
            elif method == "data_update":
                table = str(payload.get("table") or "")
                key = payload.get("key")
                values = payload.get("values") or {}
                outcome = _data_call(lambda: _data_core.update(table, key, values))
                if outcome.get("ok"):
                    outcome["message"] = "记录已保存。"
                result = outcome
            elif method == "data_delete":
                table = str(payload.get("table") or "")
                key = payload.get("key")
                backup = _create_recovery_point("before_delete")
                outcome = _data_call(lambda: _data_core.delete(table, [key]))
                if outcome.get("ok"):
                    outcome["message"] = f"已删除 {outcome.get('deleted', 0)} 条记录。"
                    outcome["backup"] = backup
                result = outcome
            elif method == "data_delete_preview":
                table = str(payload.get("table") or "")
                key = payload.get("key")
                result = _data_call(lambda: _data_core.delete_preview(table, key))
            elif method == "data_reference_options":
                table = str(payload.get("table") or "")
                column = str(payload.get("column") or "")
                keyword = str(payload.get("keyword") or "")
                result = _data_call(
                    lambda: _data_core.reference_options(table, column, keyword)
                )
            elif method == "gov_backups":
                backups = _data_core.backup_list()
                result = _ok(backups=backups, count=len(backups))
            elif method == "gov_backup_create":
                try:
                    result = _data_core.backup_create(
                        str(payload.get("reason") or "manual")
                    )
                except Exception as error:  # noqa: BLE001 - surface a Chinese message
                    result = {"ok": False, "message": str(error)}
            elif method == "gov_backup_restore":
                result = _restore_backup(payload)
            elif method == "update_word_count":
                result = _run_maintenance("word_count")
            elif method == "classify_words":
                result = _run_maintenance("classify")
            elif method == "export_csv_zip":
                result = _export_csv_zip(str(payload.get("path") or ""))
            elif method == "database_info":
                result = _ok(database=_database_info())
            elif method == "database_metadata":
                result = _database_metadata()
            elif method == "check_remote_update":
                result = _check_remote_update()
            elif method == "apply_remote_update":
                result = _apply_remote_update()
            elif method == "prepare_database_publication":
                result = _prepare_database_publication(payload)
            elif method == "replace_database":
                expected = payload.get("expected_db_version")
                result = _replace_database(
                    str(payload.get("path") or ""),
                    None if expected is None else int(expected),
                )
            elif method == "reinitialize":
                _close_services()
                _open_services()
                result = _ok(message="数据库服务已重新加载。", database=_database_info())
            else:
                result = {"ok": False, "message": f"未知方法：{method}"}
        return _dumps(result)
    except Exception as exc:
        import traceback
        return _dumps({
            "ok": False,
            "message": str(exc) or exc.__class__.__name__,
            "error_type": exc.__class__.__name__,
            "traceback": traceback.format_exc(),
        })
