"""Scratch: mine corpus stats for long-sentence phenomena."""
import io
import re
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
rows = con.execute(
    "SELECT alician_sentence, chinese_translation FROM sentence_alignments "
    "WHERE alignment_status IN ('aligned_exact','aligned_close')"
).fetchall()

# dedupe
seen = set()
data = []
for a, c in rows:
    k = (a or "").strip().casefold()
    if not k or k in seen:
        continue
    seen.add(k)
    data.append(((a or "").strip(), (c or "").strip()))
print("unique aligned:", len(data))

def stats_for(word):
    w = word.casefold()
    init = fin = mid = 0
    examples = []
    for a, c in data:
        toks = a.split()
        low = [t.casefold().strip(".,!?…") for t in toks]
        if w not in low:
            continue
        idxs = [i for i, t in enumerate(low) if t == w]
        for i in idxs:
            if i == 0:
                init += 1
            elif i == len(low) - 1:
                fin += 1
            else:
                mid += 1
        if len(examples) < 6:
            examples.append((a, c))
    print(f"\n== {word}: initial={init} mid={mid} final={fin}")
    for a, c in examples:
        print("  A:", a)
        print("  C:", c)

for w in ["end", "tie", "weil", "il", "ifa", "es", "a", "Elize", "Gout", "Poet", "Rie", "en", "sip", "sii", "Xia", "Oli", "Olis", "Kulu", "Vell", "Qleea"]:
    stats_for(w)

# sentences with leading/trailing 'end'
lead = [(a, c) for a, c in data if a.split() and a.split()[0].casefold() == "end"]
trail = [(a, c) for a, c in data if a.split() and a.split()[-1].casefold() == "end"]
print(f"\nleading end: {len(lead)}, trailing end: {len(trail)}")
for a, c in lead[:5]:
    print("  LEAD A:", a, "\n       C:", c)
for a, c in trail[:5]:
    print("  TRAIL A:", a, "\n       C:", c)
con.close()
