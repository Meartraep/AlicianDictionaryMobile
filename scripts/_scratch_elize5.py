"""Scratch: re-examine Elize against OFFICIAL Japanese/English lines."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Official alignment rows whose Alician line contains Elize
off = con.execute(
    """
    SELECT id, song_title, sentence, english, japanese, korean
    FROM song_translations
    WHERE lower(sentence) LIKE '%elize%'
    ORDER BY song_title, id
    """
).fetchall()
print(f"=== song_translations rows containing Elize: {len(off)} ===")
for r in off:
    ws = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]*", r["sentence"] or "")]
    pos = ws.index("elize") if "elize" in ws else -1
    where = "INITIAL" if pos == 0 else ("FINAL" if pos == len(ws) - 1 else f"MID({pos+1}/{len(ws)})")
    print(f"\n--- offid={r['id']} song={r['song_title']!r} pos={where}")
    print("    ALICIAN :", r["sentence"])
    print("    JP      :", r["japanese"])
    print("    EN      :", r["english"])
    print("    KR      :", r["korean"])

print()
print("=== how many song_translations rows exist per Elize song ===")
for r in con.execute(
    "SELECT song_title, COUNT(*) n FROM song_translations GROUP BY song_title ORDER BY n DESC LIMIT 8"
):
    print("   ", r["song_title"], r["n"])

con.close()
