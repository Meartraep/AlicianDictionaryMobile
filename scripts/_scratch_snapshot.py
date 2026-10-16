"""Scratch: snapshot the 10 target entries across all three tables."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

TARGETS = ["Qllsiim", "Qllsiimtiel", "Xianya", "Salah", "Rinasia",
           "Loosya", "ob", "Coll", "tie", "Mail"]

print("=== dictionary + dictionary_headwords + per-class table ===")
for w in TARGETS:
    print(f"\n########## {w}")
    for r in con.execute(
        "SELECT id, headword_id, sense_order, explanation, class, count, variety"
        " FROM dictionary WHERE lower(words)=lower(?) ORDER BY sense_order", (w,),
    ):
        print(f"  [dictionary] id={r['id']} hw={r['headword_id']} sense={r['sense_order']}"
              f" class={r['class']} cnt={r['count']} expl={r['explanation']!r}")
    for r in con.execute(
        "SELECT id, words, display_explanation, display_class, count FROM dictionary_headwords"
        " WHERE lower(words)=lower(?)", (w,),
    ):
        print(f"  [headwords] id={r['id']} class={r['display_class']}"
              f" display={r['display_explanation']!r}")
    for cl in ("pron.", "n.", "adj.", "adv.", "v.", "prep.", "conj.", "interj.", "art.", "num."):
        try:
            for r in con.execute(
                f"SELECT words, translation, count, variety FROM `{cl}` WHERE lower(words)=lower(?)",
                (w,),
            ):
                print(f"  [{cl}] translation={r['translation']!r} cnt={r['count']}")
        except sqlite3.OperationalError:
            pass

print("\n=== where does 水面 live? ===")
for r in con.execute(
    "SELECT words, explanation, class, count FROM dictionary WHERE explanation LIKE '%水面%'"
):
    print(f"  {r['words']:<14} {r['explanation']!r} {r['class']} cnt={r['count']}")
for r in con.execute("SELECT words, translation FROM `n.` WHERE translation LIKE '%水面%'"):
    print(f"  [n.] {r['words']:<14} {r['translation']!r}")
for r in con.execute(
    "SELECT words, display_explanation FROM dictionary_headwords WHERE display_explanation LIKE '%水面%'"
):
    print(f"  [hw] {r['words']:<14} {r['display_explanation']!r}")

print("\n=== entries whose explanation contains a sentence/note (would leak as surface) ===")
import re
for r in con.execute(
    "SELECT words, explanation, class FROM dictionary"
    " WHERE explanation LIKE '%。%' OR explanation LIKE '%也可以写作%' OR explanation LIKE '%通常%'"
    " ORDER BY count DESC LIMIT 15"
):
    print(f"  {r['words']:<14} {r['explanation']!r}")

con.close()
