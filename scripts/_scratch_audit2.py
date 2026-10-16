"""Audit v2: translator hard-coded glosses vs dictionary JP/EN glosses."""
import io
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(r"c:\Users\meart\Desktop\AlicianDictionaryMobile")
SRC = ROOT / "app/src/main/python/webui_backend"
DB = ROOT / "app/src/main/assets/translated.db"

text = (SRC / "translation_alician.py").read_text(encoding="utf-8")
CALL = re.compile(
    r'_alician_grammar_token\(\s*part,\s*(?:part|canonical_word)?\s*,?\s*"([^"]*)"\s*,\s*"([^"]*)"',
    re.S,
)
GUARD = re.compile(r'lower_part\s*(?:==\s*"([^"]+)"|in\s*\{([^}]+)\})')

guards = [(m.start(), m) for m in GUARD.finditer(text)]
calls = [(m.start(), m) for m in CALL.finditer(text)]

gloss = {}
for pos, m in calls:
    prev = [g for g in guards if g[0] < pos]
    if not prev:
        continue
    gm = prev[-1][1]
    words = [gm.group(1)] if gm.group(1) else re.findall(r'"([^"]+)"', gm.group(2) or "")
    for w in words:
        if w:
            gloss.setdefault(w.lower(), []).append((m.group(1), m.group(2)))

print(f"harvested {len(gloss)} words, {len(calls)} call sites")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
print("\n=== translator gloss | dict expl | dict EN | dict JP ===")
for w in sorted(gloss):
    rows = con.execute(
        "SELECT explanation, english_gloss, japanese_gloss FROM dictionary"
        " WHERE lower(words)=? ORDER BY sense_order", (w,),
    ).fetchall()
    gl = gloss[w][0][0]
    role = gloss[w][0][1]
    if not rows:
        print(f"  {w:<10} -> {gl!r} ({role})   ** 词典无此词 **")
        continue
    expl = " / ".join(dict.fromkeys(str(r["explanation"]) for r in rows))
    en = " / ".join(dict.fromkeys(str(r["english_gloss"] or "") for r in rows)).strip(" /")
    jp = " / ".join(dict.fromkeys(str(r["japanese_gloss"] or "") for r in rows)).strip(" /")
    print(f"  {w:<10} -> {gl!r:<8} ({role})")
    print(f"       expl: {expl[:76]}")
    print(f"       EN  : {en[:76]}")
    print(f"       JP  : {jp[:76]}")

con.close()
