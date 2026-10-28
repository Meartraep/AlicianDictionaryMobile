"""Legacy adapter kept for the old database-manager screen.

Before the P0 refactor this class owned a second SQLite connection to the same
file and wrote to it with no validation, no transactions and no foreign-key
enforcement.  It now delegates every operation to :class:`DataCore`, so there is
exactly one writable connection and one set of write rules.

The public method names and return shapes are unchanged because the current
``DatabaseScreen`` (removed in P4) still calls them through the bridge.  New UI
should talk to ``DataCore`` directly through the ``data_*`` bridge methods.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from webui_backend.data_core import DataCore, DataError


class DatabaseManagerService:
    """Thin compatibility layer over :class:`DataCore`."""

    def __init__(self, db_path: Optional[str] = None, core: Optional[DataCore] = None) -> None:
        if core is None:
            if not db_path:
                raise ValueError("DatabaseManagerService 需要 db_path 或 core。")
            core = DataCore(str(db_path))
            core.connect()
        self._core = core

    @property
    def core(self) -> DataCore:
        return self._core

    # ---------------------------------------------------------------- read

    def get_tables(self) -> List[str]:
        return self._core.table_names()

    def get_fields(self, table_name: str) -> List[str]:
        try:
            return [str(field["name"]) for field in self._core.table_fields(table_name)]
        except DataError:
            return []

    def _page_payload(self, table: str, keyword: str, exact: bool) -> Dict[str, Any]:
        page = self._core.page(table, keyword=keyword, exact=exact, offset=0, limit=200)
        return {
            "ok": True,
            "table": page["table"],
            "fields": page["fields"],
            "data": page["rows"],
        }

    def get_all_data(self, table_name: str) -> Dict[str, Any]:
        """First page of a table (legacy callers; never the full table)."""
        try:
            return self._page_payload(table_name, "", False)
        except DataError as error:
            return {"ok": False, "message": str(error)}

    def search_records(
        self, table_name: str, keyword: str, exact_match: bool = False
    ) -> Dict[str, Any]:
        try:
            return self._page_payload(table_name, keyword, exact_match)
        except DataError as error:
            return {"ok": False, "message": str(error)}

    # --------------------------------------------------------------- write

    def add_record(self, table_name: str, values: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self._core.create(table_name, values)
            return {"ok": True, "message": "新增记录成功。"}
        except DataError as error:
            return {"ok": False, "message": str(error)}

    def update_record(
        self, table_name: str, record_id: int, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            self._core.update(table_name, int(record_id), values)
            return {"ok": True, "message": "修改成功。"}
        except DataError as error:
            return {"ok": False, "message": str(error)}

    def delete_records(self, table_name: str, ids: List[Any]) -> Dict[str, Any]:
        try:
            outcome = self._core.delete(table_name, ids)
            return {
                "ok": True,
                "message": f"已删除 {outcome['deleted']} 条记录。",
                "deleted": outcome["deleted"],
            }
        except DataError as error:
            return {"ok": False, "message": str(error)}

    def batch_update(self, table_name: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            outcome = self._core.batch_update(table_name, edits)
            return {
                "ok": True,
                "message": f"已提交 {outcome['committed']} 条更改。",
                "committed": outcome["committed"],
            }
        except DataError as error:
            return {"ok": False, "message": str(error)}

    # -------------------------------------------------------------- global

    def global_search(self, keyword: str, exact_match: bool = False) -> Dict[str, Any]:
        try:
            return {
                "ok": True,
                "results": self._core.global_search(keyword, exact_match),
            }
        except DataError as error:
            return {"ok": False, "message": str(error), "results": []}

    def global_replace(
        self, keyword: str, replacement: str, match_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        try:
            outcome = self._core.replace_apply(keyword, replacement, match_records)
            return {
                "ok": True,
                "replaced_count": outcome["replaced"],
                "message": f"已替换 {outcome['replaced']} 处。",
                "details": [],
            }
        except DataError as error:
            return {"ok": False, "message": str(error), "replaced_count": 0, "details": []}

    def close(self) -> None:
        """The connection belongs to ``DataCore``; nothing to close here."""
