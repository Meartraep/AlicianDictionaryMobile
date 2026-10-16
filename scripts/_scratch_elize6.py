"""Scratch: quantify Elize vs Japanese から / だから, and check rivals."""
import io
import re
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== A) Elize rows: classify JP ending ===")
rows = con.execute(
    "SELECT id, song_title, sentence, japanese, english FROM song_translations"
    " WHERE lower(sentence) LIKE '%elize%' ORDER BY id"
).fetchall()
kaku = soko = other = 0
for r in rows:
    jp = (r["japanese"] or "")
    flat = jp.replace("\n", " ").strip()
    if flat.endswith("だから") or flat.endswith("だから…") or "だから" in flat[-12:]:
        kind = "Dakara-conj(所以)"
        soko += 1
    elif re.search(r"から[。、！？…\s]*$", flat) or "から" in flat:
        kind = "Kara(因为)"
        kaku += 1
    else:
        kind = "NO-KARA"
        other += 1
    print(f"  offid={r['id']:<5} {kind:<18} | {flat[-46:]}")
print(f"\n  TOTALS: kara(因为)={kaku}  dakara-conj(所以)={soko}  none={other}")

print()
print("=== B) Neighbours of offid=233 (Doppelgängers) ===")
for r in con.execute(
    "SELECT id, sentence, japanese, english FROM song_translations"
    " WHERE song_title='Doppelgängers' AND id BETWEEN 231 AND 237 ORDER BY id"
):
    print(f"  offid={r['id']} ALICIAN={r['sentence']}")
    print(f"        JP={(r['japanese'] or '').replace(chr(10),' | ')}")
    print(f"        EN={(r['english'] or '').replace(chr(10),' | ')}")

print()
print("=== C) ALL rows whose JP line starts with だから (line-initial conjunction) ===")
rows = con.execute(
    "SELECT id, song_title, sentence, japanese, english FROM song_translations WHERE japanese LIKE 'だから%'"
).fetchall()
print(f"  count={len(rows)}")
for r in rows:
    ws = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]*", r["sentence"] or "")]
    print(f"  offid={r['id']:<5} firstword={ws[0] if ws else '?':<12} | {r['sentence']}")
    print(f"        JP={r['japanese'].replace(chr(10),' | ')}")

print()
print("=== D) JP/EN for Endjulf and Oltemia rows ===")
for w in ("Endjulf", "Oltemia"):
    for r in con.execute(
        "SELECT id, song_title, sentence, japanese, english FROM song_translations"
        " WHERE lower(sentence) LIKE ?", (f"%{w.lower()}%",),
    ):
        print(f"  [{w}] offid={r['id']}")
        print(f"        ALICIAN={r['sentence']}")
        print(f"        JP={(r['japanese'] or '').replace(chr(10),' | ')}")
        print(f"        EN={(r['english'] or '').replace(chr(10),' | ')}")

print()
print("=== E) How often does JP contain から vs だから overall? ===")
allrows = con.execute("SELECT japanese FROM song_translations").fetchall()
c = Counter()
for r in allrows:
    jp = (r["japanese"] or "").replace("\n", " ")
    if "だから" in jp:
        c["だから"] += 1
    elif "から" in jp:
        c["から(other)"] += 1
print("  ", dict(c), "of", len(allrows))

print()
print("=== F) JP から lines that do NOT contain Elize (what else marks から?) ===")
rows = con.execute(
    "SELECT id, sentence, japanese FROM song_translations WHERE japanese LIKE '%から%'"
    " AND lower(sentence) NOT LIKE '%elize%'"
).fetchall()
print(f"  count={len(rows)}")
for r in rows[:30]:
    print(f"  offid={r['id']:<5} | {r['sentence'][:60]}")
    print(f"        JP={r['japanese'].replace(chr(10),' | ')[:80]}")

con.close()
