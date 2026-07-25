from __future__ import annotations

import sqlite3
import threading
from typing import Any, Dict, List


def _quote_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


class DatabaseManagerService:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.RLock()
        self._db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)

    def get_tables(self) -> List[str]:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            return [row[0] for row in cursor.fetchall() if not str(row[0]).startswith("sqlite_")]

    def get_fields(self, table_name: str) -> List[str]:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(f"PRAGMA table_info({_quote_identifier(str(table_name))})")
            return [row[1] for row in cursor.fetchall()]

    def get_all_data(self, table_name: str) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            fields = self.get_fields(tn)
            cursor = self.conn.cursor()
            if "id" in fields:
                cursor.execute(f"SELECT * FROM {_quote_identifier(tn)} ORDER BY id")
            else:
                cursor.execute(f"SELECT rowid, * FROM {_quote_identifier(tn)} ORDER BY rowid")
            rows = cursor.fetchall()
            if "id" not in fields:
                fields = ["rowid"] + fields
            return {"ok": True, "data": [dict(zip(fields, row)) for row in rows], "fields": fields, "table": tn}

    def search_records(self, table_name: str, keyword: str,
                       exact_match: bool = False) -> Dict[str, Any]:
        with self._lock:
            tn, kw = str(table_name), str(keyword)
            if not kw:
                return self.get_all_data(tn)
            fields = self.get_fields(tn)
            if not fields:
                return {"ok": True, "data": [], "fields": fields, "table": tn}
            operator = "=" if exact_match else "LIKE"
            conditions = " OR ".join(
                f"CAST({_quote_identifier(f)} AS TEXT) {operator} ?" for f in fields)
            value = kw if exact_match else f"%{kw}%"
            params = tuple(value for _ in fields)
            cursor = self.conn.cursor()
            if "id" in fields:
                cursor.execute(f"SELECT * FROM {_quote_identifier(tn)} WHERE {conditions}", params)
            else:
                cursor.execute(f"SELECT rowid, * FROM {_quote_identifier(tn)} WHERE {conditions}", params)
            rows = cursor.fetchall()
            if "id" not in fields:
                fields = ["rowid"] + fields
            return {"ok": True, "data": [dict(zip(fields, row)) for row in rows], "fields": fields, "table": tn}

    def add_record(self, table_name: str, values: Dict[str, str]) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            vals = {str(k): str(v) for k, v in (values or {}).items()}
            if not vals:
                return {"ok": False, "message": "没有可插入的数据。"}
            fields = self.get_fields(tn)
            insertable = {k: v for k, v in vals.items() if k in fields and k != "id"}
            if not insertable:
                return {"ok": False, "message": "没有匹配的字段。"}
            try:
                placeholders = ", ".join("?" for _ in insertable)
                cols = ", ".join(_quote_identifier(c) for c in insertable)
                self.conn.execute(
                    f"INSERT INTO {_quote_identifier(tn)} ({cols}) VALUES ({placeholders})",
                    tuple(insertable.values()))
                self.conn.commit()
                return {"ok": True, "message": "新增记录成功。"}
            except Exception as exc:
                return {"ok": False, "message": f"新增失败: {exc}"}

    def update_record(self, table_name: str, record_id: int, values: Dict[str, str]) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            vals = {str(k): str(v) for k, v in (values or {}).items() if k not in ("id", "rowid")}
            if not vals:
                return {"ok": False, "message": "没有可更新的数据。"}
            try:
                setters = ", ".join(f"{_quote_identifier(k)} = ?" for k in vals)
                fields = self.get_fields(tn)
                if "id" in fields:
                    params = tuple(vals.values()) + (int(record_id),)
                    self.conn.execute(f"UPDATE {_quote_identifier(tn)} SET {setters} WHERE id = ?", params)
                else:
                    params = tuple(vals.values()) + (int(record_id),)
                    self.conn.execute(f"UPDATE {_quote_identifier(tn)} SET {setters} WHERE rowid = ?", params)
                self.conn.commit()
                return {"ok": True, "message": "修改成功。"}
            except Exception as exc:
                return {"ok": False, "message": f"修改失败: {exc}"}

    def delete_records(self, table_name: str, ids: List[int]) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            id_list = [int(i) for i in (ids or [])]
            if not id_list:
                return {"ok": False, "message": "请选择要删除的记录。"}
            try:
                placeholders = ", ".join("?" for _ in id_list)
                fields = self.get_fields(tn)
                if "id" in fields:
                    self.conn.execute(
                        f"DELETE FROM {_quote_identifier(tn)} WHERE id IN ({placeholders})", tuple(id_list))
                else:
                    self.conn.execute(
                        f"DELETE FROM {_quote_identifier(tn)} WHERE rowid IN ({placeholders})", tuple(id_list))
                self.conn.commit()
                self.conn.execute("VACUUM")
                return {"ok": True, "message": f"已删除 {len(id_list)} 条记录。"}
            except Exception as exc:
                return {"ok": False, "message": f"删除失败: {exc}"}

    def global_search(self, keyword: str, exact_match: bool = False) -> Dict[str, Any]:
        with self._lock:
            kw = str(keyword)
            if not kw:
                return {"ok": True, "results": []}
            results = self._global_search(kw, bool(exact_match))
            return {"ok": True, "results": results}

    def global_replace(self, keyword: str, replacement: str,
                       match_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            kw, rep, recs = str(keyword), str(replacement), match_records or []
            if not kw or not recs:
                return {"ok": False, "message": "缺少查找词或匹配记录。"}
            count, details = self._global_replace(kw, rep, recs)
            self.conn.execute("VACUUM")
            return {"ok": True, "replaced_count": count, "details": details}

    def close(self) -> None:
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None

    def batch_update(self, table_name: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            if not edits:
                return {"ok": False, "message": "没有要提交的更改。"}
            count = 0
            try:
                for edit in edits:
                    rid = int(edit.get("id", 0))
                    vals = {str(k): str(v) for k, v in (edit.get("values") or {}).items()
                            if k not in ("id", "rowid")}
                    if not vals:
                        continue
                    setters = ", ".join(f"{_quote_identifier(k)} = ?" for k in vals)
                    fields = self.get_fields(tn)
                    params = tuple(vals.values()) + (rid,)
                    if "id" in fields:
                        self.conn.execute(
                            f"UPDATE {_quote_identifier(tn)} SET {setters} WHERE id = ?", params)
                    else:
                        self.conn.execute(
                            f"UPDATE {_quote_identifier(tn)} SET {setters} WHERE rowid = ?", params)
                    count += 1
                self.conn.commit()
                self.conn.execute("VACUUM")
                return {"ok": True, "message": f"已提交 {count} 条更改。", "committed": count}
            except Exception as exc:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return {"ok": False, "message": f"提交失败，已回滚: {exc}"}

    def _get_all_text_fields(self) -> List[tuple[str, List[str]]]:
        tables = self.get_tables()
        all_fields = []
        for table in tables:
            fields = [field for field in self.get_fields(table) if field != "id"]
            if fields:
                all_fields.append((table, fields))
        return all_fields

    def _global_search(self, keyword: str, exact_match: bool = False) -> List[Dict[str, Any]]:
        results = []
        for table, fields in self._get_all_text_fields():
            column_names = self.get_fields(table)
            has_id = "id" in column_names
            select_columns = ", ".join(_quote_identifier(field) for field in column_names)
            operator = "=" if exact_match else "LIKE"
            where_clause = " OR ".join(
                f"CAST({_quote_identifier(field)} AS TEXT) {operator} ?" for field in fields)
            if has_id:
                query = f"SELECT {select_columns} FROM {_quote_identifier(table)} WHERE {where_clause}"
                id_col_idx = column_names.index("id")
            else:
                query = f"SELECT rowid, {select_columns} FROM {_quote_identifier(table)} WHERE {where_clause}"
                id_col_idx = 0

            try:
                cursor = self.conn.cursor()
                value = keyword if exact_match else f"%{keyword}%"
                cursor.execute(query, [value] * len(fields))
                for row in cursor.fetchall():
                    row_id = row[id_col_idx]
                    for field in fields:
                        field_index = column_names.index(field)
                        value_index = field_index if has_id else field_index + 1
                        field_value = row[value_index]
                        field_text = str(field_value) if field_value is not None else ""
                        matched = field_text == keyword if exact_match else keyword in field_text
                        if matched:
                            results.append({
                                "table": table,
                                "id": row_id,
                                "field": field,
                                "value": field_value,
                            })
            except sqlite3.Error:
                continue
        return results

    def _global_replace(
        self, keyword: str, replacement: str, match_records: List[Dict[str, Any]]
    ) -> tuple[int, List[Dict[str, Any]]]:
        replaced_count = 0
        replaced_records: List[Dict[str, Any]] = []
        try:
            self.conn.execute("BEGIN TRANSACTION")
            for record in match_records:
                table = str(record.get("table", ""))
                field = str(record.get("field", ""))
                row_id = int(record.get("id", 0))
                fields = self.get_fields(table)
                if not table or field not in fields:
                    continue
                id_column = "id" if "id" in fields else "rowid"
                cursor = self.conn.cursor()
                cursor.execute(
                    f"UPDATE {_quote_identifier(table)} "
                    f"SET {_quote_identifier(field)} = REPLACE({_quote_identifier(field)}, ?, ?) "
                    f"WHERE {id_column} = ?",
                    (keyword, replacement, row_id),
                )
                if cursor.rowcount > 0:
                    old_value = str(record.get("value", ""))
                    replaced_count += 1
                    replaced_records.append({
                        "table": table,
                        "id": row_id,
                        "field": field,
                        "old_value": old_value,
                        "new_value": old_value.replace(keyword, replacement),
                    })
            self.conn.commit()
            return replaced_count, replaced_records
        except Exception:
            self.conn.rollback()
            raise
