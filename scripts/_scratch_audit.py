"""Audit: translator hard-coded glosses vs dictionary's JP/EN glosses.

The dictionary carries japanese_gloss / english_gloss built from the official
lyrics, so they outrank the Chinese explanation column.
"""
import io
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(r"c:\Users\meart\Desktop\AlicianDictionaryMobile")
SRC = ROOT / "app/src/main/python/webui_backend"
DB = ROOT / "app/src/main/assets/translated.db"

# 1) Harvest translator hard-coded function-word glosses
pattern = re.compile(
    r'_alician_grammar_token\(\s*part,\s*part,\s*"([^"]*)",\s*"([^"]*)"',
)
gloss = {}
text = (SRC / "translation_alician.py").read_text(encoding="utf-8")
# capture the enclosing `if lower_part == "x":` or `in {...}` guard
blocks = re.split(r"\n            if ", text)
for b in blocks:
    m = re.match(r'lower_part == "([^"]+)"', b) or re.match(r'lower_part in \{([^}]+)\}', b)
    g = pattern.search(b)
    if not m or not g:
        continue
    words = re.findall(r'"([^"]+)"', m.group(1))
    for w in words:
        gloss[w.lower()] = (g.group(1), g.group(2))
print(f"translator hard-coded glosses harvested: {len(gloss)}")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("\n=== word | translator gloss | dict explanation | dict EN | dict JP ===")
for w, (g, role) in sorted(gloss.items()):
    rows = con.execute(
        "SELECT explanation, english_gloss, japanese_gloss, class, count FROM dictionary"
        " WHERE lower(words)=? ORDER BY sense_order", (w,),
    ).fetchall()
    if not rows:
        print(f"  {w:<10} {g:<8} ({role})   ** 词典无此词 **")
        continue
    expl = " / ".join(dict.fromkeys(str(r["explanation"]) for r in rows))
    en = " / ".join(dict.fromkeys(str(r["english_gloss"] or "") for r in rows))
    jp = " / ".join(dict.fromkeys(str(r["japanese_gloss"] or "") for r in rows))
    print(f"  {w:<10} {g:<8} ({role})")
    print(f"        expl={expl[:70]}")
    print(f"        EN  ={en[:70]}")
    print(f"        JP  ={jp[:70]}")

con.close()
