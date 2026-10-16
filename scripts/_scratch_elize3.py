"""Scratch: cross-checks for the Elize investigation (part 3)."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

CONNECTIVES = ["因为", "所以", "因此", "正因", "由于", "那是因为", "那么", "于是",
               "不管怎样", "无论如何", "再", "先", "而", "但"]

print("=== 1) Do the rival words Endjulf / Oltemia appear in the corpus? ===")
for w in ("Endjulf", "Oltemia"):
    rows = con.execute(
        "SELECT id, song_title, alician_sentence, chinese_translation, alignment_status"
        " FROM sentence_alignments WHERE lower(alician_sentence) LIKE ?",
        (f"%{w.lower()}%",),
    ).fetchall()
    print(f"\n--- {w}: {len(rows)} rows ---")
    for r in rows:
        print("   id=%s [%s] %r" % (r["id"], r["alignment_status"], r["alician_sentence"]))
        print("        C:", r["chinese_translation"])

print()
print("=== 2) Connective occurrence in Elize references vs full corpus ===")
rows = con.execute(
    "SELECT DISTINCT alician_sentence, chinese_translation FROM sentence_alignments"
    " WHERE lower(alician_sentence) LIKE '%elize%'"
).fetchall()
print(f"unique Elize sentences: {len(rows)}")
from collections import Counter
cnt = Counter()
for r in rows:
    c = r["chinese_translation"] or ""
    for k in CONNECTIVES:
        if k in c:
            cnt[k] += 1
print("connective counts across Elize references:", dict(cnt))
print()
print("per-sentence connective detail:")
for r in rows:
    c = r["chinese_translation"] or ""
    hits = [k for k in CONNECTIVES if k in c]
    print("   ", r["alician_sentence"][:58], "=>", hits, "|", c)

print()
print("=== 3) Corpus-wide: which Chinese connectives appear, and how often ===")
allref = con.execute(
    "SELECT chinese_translation FROM sentence_alignments"
).fetchall()
allc = Counter()
for r in allref:
    c = r["chinese_translation"] or ""
    for k in ("因为", "所以", "因此", "正因", "由于", "那么", "于是", "不管怎样"):
        if k in c:
            allc[k] += 1
print("corpus-wide:", dict(allc))

print()
print("=== 4) Chinese->Alician dictionary candidates for 因为 / 所以 ===")
for term in ("因为", "所以", "因此", "由于"):
    rows = con.execute(
        "SELECT words, explanation, class, count, variety FROM dictionary"
        " WHERE explanation LIKE ? ORDER BY count DESC", (f"%{term}%",),
    ).fetchall()
    print(f"\n--- explanation contains {term}: {len(rows)} ---")
    for r in rows[:12]:
        print("   %-16s | %-22s | %-6s | count=%s var=%s" % (
            r["words"], r["explanation"], r["class"], r["count"], r["variety"]))

con.close()
