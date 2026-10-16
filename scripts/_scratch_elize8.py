"""Scratch: verify Zel / Poetklar / end against official JP."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== Zel: find official JP for the Zel sentences ===")
for r in con.execute(
    "SELECT id, sentence, japanese, english FROM song_translations"
    " WHERE lower(sentence) LIKE '%zel%'"
):
    print(f"  offid={r['id']}  ALICIAN={r['sentence']}")
    print(f"     JP={(r['japanese'] or '').replace(chr(10),' | ')}")
    print(f"     EN={(r['english'] or '').replace(chr(10),' | ')}")

print()
print("=== JP for 'Kulu Nai Ranya end Kulu Nai Prifiel Zel Note' (Chinese: 我什么也看不见) ===")
sa = con.execute(
    "SELECT id, song_title, song_sentence_order, chinese_translation FROM sentence_alignments"
    " WHERE lower(alician_sentence) LIKE '%kulu nai ranya end kulu%'"
).fetchall()
for r in sa:
    print(f"  sa_id={r['id']} song={r['song_title']} C={r['chinese_translation']}")
    jp = con.execute(
        "SELECT id, japanese, english FROM song_translations WHERE song_title=? ORDER BY id",
        (r["song_title"],),
    ).fetchall()
    for j in jp:
        if j["japanese"] and ("見え" in j["japanese"] or "感じ" in j["japanese"]):
            print(f"     offid={j['id']} JP={j['japanese'].replace(chr(10),' | ')}")
            print(f"            EN={(j['english'] or '').replace(chr(10),' | ')}")

print()
print("=== Poetklar full inventory ===")
rows = con.execute(
    "SELECT id, sentence, japanese FROM song_translations WHERE lower(sentence) LIKE '%poetklar%'"
).fetchall()
print(f"  count={len(rows)}")
for r in rows:
    print(f"  offid={r['id']:<5} JP={(r['japanese'] or '').replace(chr(10),' | ')[:76]}")

print()
print("=== How often does JP contain ながら overall? ===")
n = con.execute(
    "SELECT COUNT(*) c FROM song_translations WHERE japanese LIKE '%ながら%'"
).fetchone()["c"]
print("  JP lines with ながら:", n)
print("  of which also contain Poetklar:",
      con.execute("SELECT COUNT(*) c FROM song_translations WHERE japanese LIKE '%ながら%'"
                  " AND lower(sentence) LIKE '%poetklar%'").fetchone()["c"])

con.close()
