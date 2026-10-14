# -*- coding: utf-8 -*-
"""Verify that database-manifest.json matches the bundled translated.db.

Run before publishing: the app compares the manifest revision with the revision
stored inside the database, so a stale manifest silently disables the update
prompt (or worse, points at a database whose hash does not match).

    python scripts/verify_database_manifest.py
"""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB = Path("app/src/main/assets/translated.db")
MANIFEST = Path("database-manifest.json")


def main() -> int:
    problems: list[str] = []
    if not DB.is_file():
        print("missing database:", DB)
        return 1
    if not MANIFEST.is_file():
        print("missing manifest:", MANIFEST)
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data = DB.read_bytes()
    sha1 = hashlib.sha1(data).hexdigest()

    with sqlite3.connect(DB) as conn:
        try:
            row = conn.execute(
                "SELECT value FROM database_metadata WHERE key='db_version'"
            ).fetchone()
            db_version = int(row[0]) if row else 0
        except sqlite3.Error:
            db_version = 0

    if manifest.get("sha1") != sha1:
        problems.append("sha1 mismatch: manifest=%s db=%s" % (manifest.get("sha1"), sha1))
    if int(manifest.get("size", -1)) != len(data):
        problems.append("size mismatch: manifest=%s db=%s" % (manifest.get("size"), len(data)))
    if int(manifest.get("db_version", -1)) != db_version:
        problems.append("db_version mismatch: manifest=%s db=%s" % (manifest.get("db_version"), db_version))
    if not str(manifest.get("url", "")).startswith("https://raw.githubusercontent.com/"):
        problems.append("url must be a raw.githubusercontent.com URL")
    if db_version < 1:
        problems.append("database carries no db_version marker (legacy layout)")

    print("db_version=%s size=%d sha1=%s" % (db_version, len(data), sha1))
    print("manifest %s" % json.dumps({k: manifest.get(k) for k in ("db_version", "size", "sha1", "published_at")}, ensure_ascii=False))
    if problems:
        for problem in problems:
            print("FAIL:", problem)
        return 1
    print("OK: manifest matches the bundled database")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
