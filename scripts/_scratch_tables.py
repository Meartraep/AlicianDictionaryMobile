"""Scratch: locate official Japanese/English text in the corpus database."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== ALL TABLES ===")
tables = [r["name"] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for t in tables:
    n = con.execute(f"SELECT COUNT(*) c FROM `{t}`").fetchone()["c"]
    cols = [r["name"] for r in con.execute(f"PRAGMA table_info(`{t}`)")]
    print(f"\n--- {t}  (rows={n})")
    print("    cols:", cols)

print()
print("=== sample rows of every table (2 each) ===")
for t in tables:
    print(f"\n--- {t} ---")
    for r in con.execute(f"SELECT * FROM `{t}` LIMIT 2"):
        d = dict(r)
        for k, v in d.items():
            s = str(v)
            print(f"    {k} = {s[:160]!r}")
        print("    .")

con.close()
