"""Scratch: verify `end` (relative-clause vs enumeration) and `qleea` vs JP."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== A) The claimed head-end-relative examples, with JP ===")
for s in ("Syeilla end Mii Harie", "Ene end Yien Amiy Ord Lusia", "Flea end ol Yien Amiy Ord Lusia"):
    for r in con.execute(
        "SELECT id, sentence, japanese, english FROM song_translations WHERE lower(sentence) LIKE ?",
        (f"%{s.lower()}%",),
    ):
        print(f"  offid={r['id']} AL={r['sentence']}")
        print(f"     JP={(r['japanese'] or '').replace(chr(10),' | ')}")
        print(f"     EN={(r['english'] or '').replace(chr(10),' | ')}")

print("\n=== B) 30 sample rows containing `end`: JP correspondence ===")
rows = con.execute(
    "SELECT id, sentence, japanese, english FROM song_translations"
    " WHERE lower(sentence) LIKE '% end %' OR lower(sentence) LIKE 'end %'"
    " OR lower(sentence) LIKE '% end' ORDER BY id LIMIT 30"
).fetchall()
for r in rows:
    print(f"  offid={r['id']}")
    print(f"     AL={r['sentence'][:104]}")
    print(f"     JP={(r['japanese'] or '').replace(chr(10),' | ')[:104]}")

print("\n=== C) How often does the JP block have no 'and-like' marker? (sanity) ===")
tot = con.execute("SELECT COUNT(*) c FROM song_translations WHERE lower(sentence) LIKE '%end%'").fetchone()["c"]
print("  Alician rows containing 'end':", tot)

print("\n=== D) qleea rows with JP ===")
for r in con.execute(
    "SELECT id, sentence, japanese, english FROM song_translations"
    " WHERE lower(sentence) LIKE '%qleea%' ORDER BY id"
):
    print(f"  offid={r['id']}")
    print(f"     AL={r['sentence'][:100]}")
    print(f"     JP={(r['japanese'] or '').replace(chr(10),' | ')[:100]}")

con.close()
