"""Scratch: find dictionary entries whose Chinese gloss conflicts with the
official Japanese/English columns (same defect class as Qllsiim/Xianya)."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def rows(sql, args=()):
    return con.execute(sql, args).fetchall()

print("=== A) 作者自标存疑 '(?)' 的义项，按语料出现次数排序 ===")
doubtful = rows(
    "SELECT words, explanation, class, count, english_gloss, japanese_gloss FROM dictionary"
    " WHERE explanation LIKE '%(?)%' ORDER BY count DESC"
)
print(f"总数: {len(doubtful)}")
for r in doubtful[:40]:
    print(f"  {r['words']:<14} {r['explanation']:<20} {r['class']:<6} cnt={r['count']:<4}"
          f" EN={str(r['english_gloss'])[:30]!r} JP={str(r['japanese_gloss'])[:26]!r}")

print("\n=== B) 人称/单复数冲突：中文含 人们/那个/它 但 JP/EN 指示复数或其他人称 ===")
PLURAL_JP = ("ら", "たち", "あいつ", "我々", "僕ら", "君ら")
PLURAL_EN = ("they", "those", "people", "we", "us", "ourselves", "them")
for r in rows(
    "SELECT words, explanation, class, count, english_gloss, japanese_gloss FROM dictionary"
    " WHERE explanation LIKE '%人们%' OR explanation LIKE '%那个%' OR explanation LIKE '%它%'"
    " ORDER BY count DESC"
):
    en = str(r["english_gloss"] or "").lower()
    jp = str(r["japanese_gloss"] or "")
    if any(p in jp for p in PLURAL_JP) or any(p in en for p in PLURAL_EN):
        print(f"  {r['words']:<14} 中文={r['explanation']!r:<14} {r['class']:<6} cnt={r['count']:<4}")
        print(f"       EN={r['english_gloss']!r}")
        print(f"       JP={r['japanese_gloss']!r}")

print("\n=== C) 词典是否有 'Qllsiim' 形近词条（同一词族的 we 系列）===")
for r in rows(
    "SELECT words, explanation, class, count, english_gloss, japanese_gloss FROM dictionary"
    " WHERE english_gloss LIKE '%we%' OR english_gloss LIKE '%us%'"
    " OR japanese_gloss LIKE '%我々%' OR japanese_gloss LIKE '%僕ら%'"
    " ORDER BY count DESC"
):
    print(f"  {r['words']:<14} {r['explanation']:<14} {r['class']:<6} cnt={r['count']:<4}"
          f" EN={str(r['english_gloss'])[:26]!r} JP={str(r['japanese_gloss'])[:22]!r}")

con.close()
