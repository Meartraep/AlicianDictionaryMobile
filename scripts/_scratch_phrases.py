"""Scratch: check multi-word phrases containing target function words."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
rows = con.execute("SELECT words, explanation FROM dictionary WHERE words LIKE '% %'").fetchall()
targets = {"elize", "gout", "zel", "ifa", "poetklar", "end", "poet"}
hits = [(r[0], r[1]) for r in rows if targets & set(r[0].lower().split())]
print("hits:", hits)
print("total multi-word entries:", len(rows))
con.close()
