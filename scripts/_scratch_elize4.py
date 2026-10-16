"""Scratch: final supplementary checks for the Elize investigation (part 4)."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== A) Every dictionary sense whose gloss contains 因 / 故 ===")
rows = con.execute(
    "SELECT words, explanation, class, count, variety FROM dictionary"
    " WHERE explanation LIKE '%因%' OR explanation LIKE '%故%' ORDER BY count DESC"
).fetchall()
for r in rows:
    print("   %-16s | %-24s | %-7s | count=%-4s var=%s" % (
        r["words"], r["explanation"], r["class"], r["count"], r["variety"]))

print()
print("=== B) no_class rows containing 因/故 ===")
for r in con.execute("SELECT * FROM no_class WHERE translation LIKE '%因%' OR translation LIKE '%故%'"):
    print("   ", dict(r))

print()
print("=== C) Elize distribution by position (unique sentences) ===")
import re
from collections import Counter
rows = con.execute(
    "SELECT DISTINCT alician_sentence FROM sentence_alignments"
    " WHERE lower(alician_sentence) LIKE '%elize%'"
).fetchall()
pos = Counter()
for r in rows:
    ws = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]*", r["alician_sentence"] or "")]
    i = ws.index("elize")
    where = "INITIAL" if i == 0 else ("FINAL" if i == len(ws) - 1 else "MID")
    pos[where] += 1
print("   unique:", len(rows), dict(pos))

print()
print("=== D) Does any Elize sentence also contain Oltemia/Endjulf? ===")
for r in rows:
    a = (r["alician_sentence"] or "").lower()
    co = [w for w in ("oltemia", "endjulf", "fevla") if w in a]
    if co:
        print("   ", co, r["alician_sentence"])

print()
print("=== E) alignment_status breakdown for Elize rows ===")
for r in con.execute(
    "SELECT alignment_status, COUNT(*) n FROM sentence_alignments"
    " WHERE lower(alician_sentence) LIKE '%elize%' GROUP BY alignment_status"
):
    print("   ", r["alignment_status"], r["n"])

print()
print("=== F) Japanese/English gloss of Elize and rivals ===")
for w in ("Elize", "Oltemia", "Endjulf"):
    for r in con.execute(
        "SELECT words, explanation, english_gloss, japanese_gloss FROM dictionary"
        " WHERE lower(words)=lower(?)", (w,),
    ):
        print("   %-9s cn=%-9s en=%-18s jp=%s" % (
            r["words"], r["explanation"], r["english_gloss"], r["japanese_gloss"]))

con.close()
