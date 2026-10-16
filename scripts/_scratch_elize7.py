"""Scratch: corrected Elize classification + audit other changes against JP/EN."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def classify(jp: str) -> str:
    flat = (jp or "").replace("\n", " ").strip()
    if not flat:
        return "NO-JP"
    if flat.endswith("だから") or flat.endswith("から") or re.search(r"(だから|から)[ねよ。、！？…\s]*$", flat):
        return "因为(から)"
    if re.search(r"^だから|[\s　]だから", flat):
        return "所以(だから分)" if "だから" in flat[:14] else "?"
    if "だから" in flat:
        return "因为(だ+から)"
    return "无から"


print("=== A) CORRECTED classification of all Elize rows ===")
rows = con.execute(
    "SELECT id, sentence, japanese, english FROM song_translations"
    " WHERE lower(sentence) LIKE '%elize%' ORDER BY id"
).fetchall()
from collections import Counter
c = Counter()
for r in rows:
    k = classify(r["japanese"])
    c[k] += 1
    print(f"  offid={r['id']:<5} {k:<14} | {(r['japanese'] or '').replace(chr(10),' | ')[:70]}")
print("  TOTALS:", dict(c))

print()
print("=== B) Elize followed by which Alician clause? (verify から-host mapping) ===")
for r in rows:
    ws = re.split(r"\s+", (r["sentence"] or "").strip())
    for i, w in enumerate(ws):
        if w.lower() == "elize":
            after = " ".join(ws[i + 1:])
            before = " ".join(ws[:i])
            print(f"  offid={r['id']:<5} BEFORE=[{before}]  ELIZE  AFTER=[{after}]")
            break

print()
print("=== C) AUDIT: my other changed rules vs OFFICIAL JP ===")
audit = [
    ("Poetklar 正在", "Poetklar"),
    ("end 枚举", "end ol Kllea"),
    ("ifa 前置", "ifa"),
]
for label, needle in audit:
    print(f"\n--- {label} ({needle!r}) ---")
    for r in con.execute(
        "SELECT id, sentence, japanese, english FROM song_translations"
        " WHERE lower(sentence) LIKE ? LIMIT 8", (f"%{needle.lower()}%",),
    ):
        print(f"  offid={r['id']}")
        print(f"    ALICIAN={r['sentence']}")
        print(f"    JP     ={(r['japanese'] or '').replace(chr(10),' | ')}")
        print(f"    EN     ={(r['english'] or '').replace(chr(10),' | ')}")

print()
print("=== D) specific lines ===")
for s in ("Arupe Elled Nols end ol Kllea end ol Sjiyupe",
          "Kulu Nai Ranya Zel Note",
          "Tifijl Xia end Yien Stea ifa Enbrikardi Fas",
          "Poetklar Myte Herz Yien Torjest Mii"):
    rs = con.execute(
        "SELECT id, sentence, japanese, english FROM song_translations WHERE sentence = ?", (s,)
    ).fetchall()
    print(f"\n  ALICIAN={s}")
    if not rs:
        print("     (no official row)")
    for r in rs:
        print(f"     offid={r['id']} JP={(r['japanese'] or '').replace(chr(10),' | ')}")
        print(f"            EN={(r['english'] or '').replace(chr(10),' | ')}")

con.close()
