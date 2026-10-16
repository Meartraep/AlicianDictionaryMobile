"""Scratch: inspect suspicious function words against official JP."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def show(word, limit=14, marker_hint=""):
    rows = con.execute(
        "SELECT id, sentence, japanese, english FROM song_translations"
        " WHERE lower(sentence) LIKE ? AND japanese IS NOT NULL AND japanese <> ''"
        " ORDER BY id LIMIT ?", (f"%{word.lower()}%", limit),
    ).fetchall()
    print(f"\n########## {word}  (rows shown={len(rows)}) ##########")
    for r in rows:
        jp = str(r["japanese"]).replace("\n", " | ")
        en = str(r["english"] or "").replace("\n", " | ")
        print(f"  offid={r['id']} JP={jp[:96]}")
        if en:
            print(f"        EN={en[:96]}")
        print(f"        AL={r['sentence'][:96]}")

for w in ("lend", "erikes", "qleea", "hiele", "tie", "weil", "ol", "iy", "ah"):
    show(w)

print("\n\n=== what are lend/erikes glossed as now? ===")
for r in con.execute(
    "SELECT words, explanation, class, count, english_gloss, japanese_gloss FROM dictionary"
    " WHERE lower(words) IN ('lend','erikes','qleea','hiele','tie','weil','ol','ob','iy','ah','rie','laiz')"
):
    print(f"  {r['words']:<9} {r['explanation']:<12} {r['class']:<6} cnt={r['count']:<4}"
          f" en={str(r['english_gloss'])[:40]!r} jp={str(r['japanese_gloss'])[:34]!r}")

con.close()
