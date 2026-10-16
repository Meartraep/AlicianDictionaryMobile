"""Scratch: verify extra Chinese-gloss candidates against official Japanese."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

CANDIDATES = ["Salah", "Loot", "Loosya", "Mail", "tie", "ob", "Coll", "Rinasia"]
for word in CANDIDATES:
    low = word.lower()
    rows = con.execute(
        "SELECT id, sentence, japanese, english FROM song_translations"
        " WHERE lower(sentence) LIKE ? ORDER BY id LIMIT 6", (f"%{low}%",),
    ).fetchall()
    print(f"\n########## {word}  ({len(rows)} rows shown)")
    for r in rows:
        words = [w.lower() for w in WORD_RE.findall(r["sentence"])]
        if low not in words:
            continue
        i = words.index(low)
        ctx = " ".join(words[max(0, i - 2):i + 3])
        print(f"   offid={r['id']} 上下文=…{ctx}…")
        print(f"      JP={(r['japanese'] or '').replace(chr(10), ' | ')[:100]}")
        if r["english"]:
            print(f"      EN={r['english'].replace(chr(10), ' | ')[:100]}")

con.close()
