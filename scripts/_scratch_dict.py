"""Scratch: dump dictionary entries for function words of interest."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
cur = con.cursor()

WORDS = ["tie", "weil", "il", "ifa", "Elize", "Kulu", "Zel", "Note", "Poetklar",
         "Gout", "es", "end", "Xia", "Oli", "Olis", "Lootaria", "Aola", "ieq",
         "iequim", "Poetolt", "noa", "Eala", "Folme", "imm", "endil", "ah",
         "Ah", "Leste", "Lishe", "Hiele", "Sar", "Ord", "Qi", "ra", "Dex",
         "Bisoli", "Bis", "Oll", "Ollenes", "Oudiq", "Apnesia", "Apnesiaflea",
         "Elemie", "Foul", "Ied", "Idial", "Ail", "ail", "en", "Eist"]

for w in WORDS:
    print(f"\n===== {w} =====")
    rows = cur.execute(
        "SELECT words, explanation, class, count FROM dictionary WHERE lower(words)=lower(?)",
        (w,),
    ).fetchall()
    for r in rows:
        print(" dict:", r)
    rows2 = cur.execute(
        "SELECT words, translation, count FROM no_class WHERE lower(words)=lower(?)",
        (w,),
    ).fetchall()
    for r in rows2:
        print(" no_class:", r)

con.close()
