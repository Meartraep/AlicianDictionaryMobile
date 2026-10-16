"""Scratch: audit Qllsiim / Qllsiimtiel / Xianya against the official Japanese."""
import io
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(r"c:\Users\meart\Desktop\AlicianDictionaryMobile")
DB = ROOT / "app/src/main/assets/translated.db"
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from webui_backend.translation_service import TranslationService

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
TARGETS = ["Qllsiim", "Qllsiimtiel", "Xianya"]

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
svc = TranslationService(str(DB), enable_fallback_matching=False)

for word in TARGETS:
    low = word.lower()
    print("=" * 78)
    print(f"########## {word} ##########")

    print("\n--- 1) dictionary senses ---")
    for r in con.execute(
        "SELECT id, sense_order, words, explanation, class, count, variety,"
        " english_gloss, japanese_gloss FROM dictionary WHERE lower(words)=? ORDER BY sense_order",
        (low,),
    ):
        print(f"   id={r['id']} sense={r['sense_order']} expl={r['explanation']!r} class={r['class']}"
              f" count={r['count']} var={r['variety']}")
        print(f"        EN={r['english_gloss']!r}")
        print(f"        JP={r['japanese_gloss']!r}")

    print("--- 2) no_class / per-class tables ---")
    for r in con.execute("SELECT * FROM no_class WHERE lower(words)=?", (low,)):
        print("   no_class:", dict(r))
    for cl in ("pron.", "n.", "adj.", "adv."):
        try:
            for r in con.execute(
                f"SELECT words, translation, count, variety FROM `{cl}` WHERE lower(words)=?", (low,)
            ):
                print(f"   [{cl}] {r['translation']!r} count={r['count']} var={r['variety']}")
        except sqlite3.OperationalError:
            pass

    print("--- 3) official corpus rows (japanese / english) ---")
    rows = con.execute(
        "SELECT id, song_title, sentence, japanese, english FROM song_translations"
        " WHERE lower(sentence) LIKE ? ORDER BY id", (f"%{low}%",),
    ).fetchall()
    print(f"   总数: {len(rows)}")
    for r in rows:
        print(f"   offid={r['id']} [{r['song_title']}]")
        print(f"      AL={r['sentence']}")
        print(f"      JP={(r['japanese'] or '').replace(chr(10), ' | ')}")
        print(f"      EN={(r['english'] or '').replace(chr(10), ' | ')}")

    print("--- 4) Chinese localization rows (secondary signal) ---")
    for r in con.execute(
        "SELECT id, alician_sentence, chinese_translation FROM sentence_alignments"
        " WHERE lower(alician_sentence) LIKE ? ORDER BY id LIMIT 12", (f"%{low}%",),
    ):
        print(f"   sa_id={r['id']} AL={r['alician_sentence']}")
        print(f"            C={r['chinese_translation']}")

    print("--- 5) what the translator picks ---")
    for r in rows[:6]:
        res = svc.translate(r["sentence"], "alician_to_zh")
        tok = next(
            (t for t in res["tokens"]
             if str(t.get("source") or "").casefold() == low
             or str(t.get("normalized_source") or "").casefold() == low),
            None,
        )
        print(f"   AL={r['sentence'][:78]}")
        print(f"      OUT={res['result_text'][:78]}")
        if tok:
            print(f"      token target={tok.get('target')!r} resolved={tok.get('resolved_target')!r}"
                  f" method={tok.get('method')} expl={str(tok.get('explanation'))[:40]!r}")
        else:
            print("      token: <not found>")

svc.close()
con.close()
