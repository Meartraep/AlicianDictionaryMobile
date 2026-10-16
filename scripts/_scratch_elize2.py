"""Scratch: exhaustive investigation of the Alician word Elize (part 2)."""
import io
import json
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== ALL senses of Elize / Endjulf / Oltemia (by headword) ===")
for w in ("Elize", "Endjulf", "Oltemia"):
    rows = con.execute(
        "SELECT id, headword_id, words, explanation, class, sense_order, count, variety,"
        " english_gloss, japanese_gloss FROM dictionary WHERE lower(words)=lower(?)"
        " ORDER BY sense_order", (w,),
    ).fetchall()
    print(f"\n--- {w}: {len(rows)} senses ---")
    for r in rows:
        print("   id=%s hw=%s sense=%s class=%s count=%s variety=%s expl=%r en=%r jp=%r" % (
            r["id"], r["headword_id"], r["sense_order"], r["class"], r["count"],
            r["variety"], r["explanation"], r["english_gloss"], r["japanese_gloss"]))

print()
print("=== ALL aligned rows containing Elize (any case) ===")
rows = con.execute(
    """
    SELECT id, song_title, album, song_sentence_order, alician_sentence,
           txt_alician_sentence, chinese_translation, alignment_status,
           match_score, match_method, notes, word_glosses_json
    FROM sentence_alignments
    WHERE lower(alician_sentence) LIKE '%elize%'
       OR lower(txt_alician_sentence) LIKE '%elize%'
    ORDER BY song_title, song_sentence_order, id
    """
).fetchall()
print(f"TOTAL ROWS: {len(rows)}")
for r in rows:
    a = r["alician_sentence"] or ""
    ta = r["txt_alician_sentence"] or ""
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", a)
    low = [w.lower() for w in words]
    pos = low.index("elize") if "elize" in low else -1
    where = "?" if pos < 0 else ("INITIAL" if pos == 0 else
            ("FINAL" if pos == len(low) - 1 else f"MID({pos+1}/{len(low)})"))
    print("\n--- id=%s status=%s score=%s song=%r order=%s" % (
        r["id"], r["alignment_status"], r["match_score"], r["song_title"],
        r["song_sentence_order"]))
    print("    A :", a)
    if ta and ta != a:
        print("    A2:", ta)
    print("    C :", r["chinese_translation"])
    print("    pos:", where, "| notes:", r["notes"])
    if r["word_glosses_json"]:
        try:
            gj = json.loads(r["word_glosses_json"])
            print("    glosses:", gj)
        except Exception:
            print("    glosses(raw):", r["word_glosses_json"][:300])

con.close()
