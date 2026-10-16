"""Scratch: exhaustive re-investigation of the Alician word Loosya."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

print("=== 1) dictionary senses / headword / per-class ===")
for r in con.execute(
    "SELECT id, headword_id, sense_order, words, explanation, class, count, variety,"
    " english_gloss, japanese_gloss FROM dictionary WHERE lower(words) LIKE 'loos%' OR lower(words)='losya'"
):
    print(f"  id={r['id']} hw={r['headword_id']} s={r['sense_order']} {r['words']!r}"
          f" expl={r['explanation']!r} class={r['class']} cnt={r['count']} var={r['variety']}")
    print(f"      EN={r['english_gloss']!r}")
    print(f"      JP={r['japanese_gloss']!r}")
for r in con.execute("SELECT * FROM dictionary_headwords WHERE lower(words) LIKE 'loos%'"):
    print(f"  [hw] {r['words']!r} display={r['display_explanation']!r} class={r['display_class']}")
for t in ("adj.", "adv.", "n.", "conj.", "prep.", "pron."):
    for r in con.execute(f"SELECT words, translation, count FROM `{t}` WHERE lower(words) LIKE 'loos%'"):
        print(f"  [{t}] {r['words']!r} {r['translation']!r} cnt={r['count']}")
for r in con.execute("SELECT * FROM no_class WHERE lower(words) LIKE 'loos%'"):
    print("  [no_class]", dict(r))
for r in con.execute("SELECT words FROM All_words WHERE lower(words) LIKE 'loos%'"):
    print("  [All_words]", r["words"])
for r in con.execute("SELECT words FROM `Unknown` WHERE lower(words) LIKE 'loos%'"):
    print("  [Unknown]", r["words"])

print("\n=== 2) every official row containing Loosya (with position) ===")
rows = con.execute(
    "SELECT id, song_title, sentence, japanese, english FROM song_translations"
    " WHERE lower(sentence) LIKE '%loosya%' ORDER BY id"
).fetchall()
print(f"  总数: {len(rows)}")
for r in rows:
    ws = WORD_RE.findall(r["sentence"])
    low = [w.lower() for w in ws]
    idx = low.index("loosya") if "loosya" in low else -1
    left = " ".join(ws[max(0, idx - 3):idx])
    right = " ".join(ws[idx + 1:idx + 4])
    print(f"\n  offid={r['id']} [{r['song_title']}]  位置 {idx + 1}/{len(low)}")
    print(f"     左: {left!r}   >>> LOOSYA <<<   右: {right!r}")
    print(f"     AL={r['sentence']}")
    print(f"     JP={(r['japanese'] or '').replace(chr(10), ' | ')}")
    print(f"     EN={(r['english'] or '').replace(chr(10), ' | ')}")

print("\n=== 3) Chinese localization for the same lines ===")
for r in rows:
    sa = con.execute(
        "SELECT id, alician_sentence, chinese_translation FROM sentence_alignments"
        " WHERE alician_sentence = ?", (r["sentence"],),
    ).fetchall()
    for s in sa:
        print(f"  offid={r['id']} sa_id={s['id']} C={s['chinese_translation']}")
    if not sa:
        print(f"  offid={r['id']} (无对应中文本地化行)")
        for s in con.execute(
            "SELECT id, alician_sentence, chinese_translation FROM sentence_alignments"
            " WHERE lower(alician_sentence) LIKE '%loosya%'"
        ):
            print(f"      sa_id={s['id']} AL={s['alician_sentence']} C={s['chinese_translation']}")

print("\n=== 4) JP sentences containing すら/さえ/も near a 'none/every' meaning ===")
for kw in ("すら", "さえ"):
    n = con.execute("SELECT COUNT(*) c FROM song_translations WHERE japanese LIKE ?", (f"%{kw}%",)).fetchone()["c"]
    print(f"  JP 行含 {kw}: {n}")
    for r in con.execute(
        "SELECT id, sentence, japanese FROM song_translations WHERE japanese LIKE ? LIMIT 8", (f"%{kw}%",)
    ):
        print(f"    offid={r['id']} AL={r['sentence'][:66]}")
        print(f"        JP={r['japanese'].replace(chr(10), ' | ')[:80]}")

con.close()
