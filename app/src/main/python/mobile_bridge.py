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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


_lock = threading.RLock()
_db_path = ""
_data_dir = ""
_dictionary = None
_writing = None
_translator = None
_dbmanager = None
_remote_candidate = ""


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
    global _dictionary, _writing, _translator, _dbmanager
    for service in (_dictionary, _writing, _translator, _dbmanager):
        if service is not None:
            try:
                service.close()
            except Exception:
                pass
    _dictionary = _writing = _translator = _dbmanager = None


def _open_services() -> None:
    global _dictionary, _writing, _translator, _dbmanager
    from webui_backend.dictionary_core import DictionaryConfig
    from webui_backend.dictionary_service import DictionaryService
    from webui_backend.writing_database import DatabaseManager
    from webui_backend.writing_service import WritingAssistantService
    from webui_backend.translation_service import TranslationService
    from webui_backend.dbmanager_service import DatabaseManagerService

    DictionaryConfig.DB_NAME = _db_path
    DictionaryConfig.CURRENT_DB = _db_path
    DatabaseManager().close_connection()
    _dictionary = DictionaryService(enable_semantic=False)
    _writing = WritingAssistantService()
    _translator = TranslationService(_db_path, enable_fallback_matching=False)
    _dbmanager = DatabaseManagerService(_db_path)


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
    if not all((_dictionary, _writing, _translator, _dbmanager)):
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


def _table_page(payload: Dict[str, Any]) -> Dict[str, Any]:
    table = str(payload.get("table") or "")
    keyword = str(payload.get("keyword") or "")
    exact = bool(payload.get("exact", False))
    offset = max(0, int(payload.get("offset", 0)))
    limit = max(1, min(200, int(payload.get("limit", 50))))
    fields = _dbmanager.get_fields(table)
    if not fields:
        return _ok(table=table, fields=[], data=[], total=0, offset=offset, limit=limit)
    quoted_table = '"' + table.replace('"', '""') + '"'
    quoted = lambda value: '"' + str(value).replace('"', '""') + '"'
    selected_fields = fields if "id" in fields else ["rowid", *fields]
    columns = ", ".join(quoted(field) if field != "rowid" else "rowid" for field in selected_fields)
    params = []
    where = ""
    if keyword:
        operator = "=" if exact else "LIKE"
        where = " WHERE " + " OR ".join(
            f"CAST({quoted(field)} AS TEXT) {operator} ?" for field in fields
        )
        value = keyword if exact else f"%{keyword}%"
        params = [value] * len(fields)
    with _dbmanager._lock:
        cursor = _dbmanager.conn.cursor()
        total = cursor.execute(
            f"SELECT COUNT(*) FROM {quoted_table}{where}", params
        ).fetchone()[0]
        rows = cursor.execute(
            f"SELECT {columns} FROM {quoted_table}{where} "
            f"ORDER BY {'id' if 'id' in fields else 'rowid'} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return _ok(
        table=table,
        fields=selected_fields,
        data=[dict(zip(selected_fields, row)) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
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


def _compare_database(remote_path: Path) -> Dict[str, Any]:
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
    local_sha = hashlib.sha1(Path(_db_path).read_bytes()).hexdigest()
    remote_sha = hashlib.sha1(remote.read_bytes()).hexdigest()
    _remote_candidate = str(remote)
    return _ok(
        up_to_date=local_sha == remote_sha,
        local_sha1=local_sha,
        remote_sha1=remote_sha,
        comparison=_compare_database(remote),
        message="已是最新数据库。" if local_sha == remote_sha else "发现新的云端数据库。",
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


def _replace_database(source_path: str) -> Dict[str, Any]:
    source = Path(source_path)
    _validate_database(source)
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
                )
            elif method == "dictionary_examples":
                result = _dictionary.get_examples(
                    str(payload.get("word") or ""),
                    str(payload.get("position") or "any"),
                )
            elif method == "dictionary_update_lyric":
                result = _dictionary.update_song_lyric(
                    str(payload.get("title") or ""),
                    str(payload.get("album") or ""),
                    str(payload.get("lyric") or ""),
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
                )
            elif method == "db_tables":
                result = _ok(tables=_dbmanager.get_tables())
            elif method == "db_table_page":
                result = _table_page(payload)
            elif method == "db_add":
                result = _dbmanager.add_record(
                    str(payload.get("table") or ""), payload.get("values") or {}
                )
            elif method == "db_update":
                result = _dbmanager.update_record(
                    str(payload.get("table") or ""),
                    int(payload.get("id") or 0),
                    payload.get("values") or {},
                )
            elif method == "db_delete":
                result = _dbmanager.delete_records(
                    str(payload.get("table") or ""), payload.get("ids") or []
                )
            elif method == "db_global_search":
                result = _dbmanager.global_search(
                    str(payload.get("keyword") or ""),
                    bool(payload.get("exact", False)),
                )
            elif method == "db_global_replace":
                result = _dbmanager.global_replace(
                    str(payload.get("keyword") or ""),
                    str(payload.get("replacement") or ""),
                    payload.get("records") or [],
                )
            elif method == "update_word_count":
                result = _run_maintenance("word_count")
            elif method == "classify_words":
                result = _run_maintenance("classify")
            elif method == "export_csv_zip":
                result = _export_csv_zip(str(payload.get("path") or ""))
            elif method == "database_info":
                result = _ok(database=_database_info())
            elif method == "check_remote_update":
                result = _check_remote_update()
            elif method == "apply_remote_update":
                result = _apply_remote_update()
            elif method == "replace_database":
                result = _replace_database(str(payload.get("path") or ""))
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

