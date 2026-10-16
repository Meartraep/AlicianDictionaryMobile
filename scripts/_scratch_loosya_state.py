"""Scratch: confirm Loosya stays consistent across the three tables."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
print("dictionary :", [
    (r["explanation"], r["class"], r["english_gloss"], r["japanese_gloss"])
    for r in con.execute("SELECT * FROM dictionary WHERE lower(words)='loosya'")
])
print("headwords  :", [
    (r["display_explanation"], r["display_class"])
    for r in con.execute(
        "SELECT display_explanation, display_class FROM dictionary_headwords"
        " WHERE lower(words)='loosya'")
])
print("adj. table :", [
    (r["translation"], r["count"])
    for r in con.execute("SELECT translation, count FROM `adj.` WHERE lower(words)='loosya'")
])
con.close()
