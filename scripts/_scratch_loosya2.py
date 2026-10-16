"""Scratch: find the 4th Loosya occurrence and any 每/任何-type reading."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== A) raw lyrics / songs.lyric 中的 Loosya ===")
for r in con.execute("SELECT id, title, lyric FROM songs WHERE lyric LIKE '%oosya%'"):
    print(f"  songs id={r['id']} {r['title']}")
    for line in str(r["lyric"]).splitlines():
        if "oosya" in line.lower():
            print("     ", line)
for r in con.execute("SELECT id, songs_raw, lyric_raw FROM raw WHERE lyric_raw LIKE '%oosya%'"):
    print(f"  raw id={r['id']} {r['songs_raw']}")
    for line in str(r["lyric_raw"]).splitlines():
        if "oosya" in line.lower():
            print("     ", line)

print("\n=== B) sentence_alignments ===")
for r in con.execute(
    "SELECT id, song_title, alician_sentence, chinese_translation, alignment_status"
    " FROM sentence_alignments WHERE lower(alician_sentence) LIKE '%loosya%'"
):
    print(f"  sa_id={r['id']} [{r['song_title']}] {r['alignment_status']}")
    print(f"     AL={r['alician_sentence']}")
    print(f"     C ={r['chinese_translation']}")

print("\n=== C) 变体拼写 ===")
for pat in ("%losya%", "%loosia%", "%lousya%", "%loosy%"):
    rows = con.execute(
        "SELECT words, explanation, class FROM dictionary WHERE lower(words) LIKE ?", (pat,)
    ).fetchall()
    if rows:
        for r in rows:
            print(f"  {pat}: {r['words']} {r['explanation']} {r['class']}")

print("\n=== D) 官方日文里 も/すら/でも/さえ 与 Alician 焦点词 的对照 ===")
print("  含 も 的日文行数:",
      con.execute("SELECT COUNT(*) c FROM song_translations WHERE japanese LIKE '%も%'").fetchone()["c"])
print("  词典里 JP 含 も 的 Alician 词条（可能是焦点助词）:")
for r in con.execute(
    "SELECT words, explanation, class, japanese_gloss, english_gloss FROM dictionary"
    " WHERE japanese_gloss LIKE '%も%' OR japanese_gloss LIKE '%すら%' OR english_gloss LIKE '%even%'"
    " ORDER BY count DESC LIMIT 20"
):
    print(f"    {r['words']:<12} {r['explanation']:<12} {r['class']:<6}"
          f" EN={str(r['english_gloss'])[:24]!r} JP={str(r['japanese_gloss'])[:18]!r}")

print("\n=== E) offid=865 与 236 的完整对照（含词级） ===")
for offid in (236, 631, 865):
    r = con.execute("SELECT * FROM song_translations WHERE id=?", (offid,)).fetchone()
    print(f"\n  offid={offid}")
    print(f"    AL={r['sentence']}")
    print(f"    JP={r['japanese']}")
    print(f"    EN={r['english']}")
    print(f"    KR={r['korean']}")

con.close()
