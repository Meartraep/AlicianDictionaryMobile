"""Scratch: exhaustive investigation of the Alician word Elize."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== SCHEMA sentence_alignments ===")
for row in con.execute("PRAGMA table_info(sentence_alignments)"):
    print("  ", row["name"], row["type"])

print()
print("=== SCHEMA dictionary ===")
for row in con.execute("PRAGMA table_info(dictionary)"):
    print("  ", row["name"], row["type"])

print()
print("=== SCHEMA no_class ===")
for row in con.execute("PRAGMA table_info(no_class)"):
    print("  ", row["name"], row["type"])

print()
print("=== ALL dictionary rows mentioning elize/eliz/element ===")
for row in con.execute(
    "SELECT * FROM dictionary WHERE lower(words) LIKE '%eliz%' "
    "OR explanation LIKE '%所以%' OR explanation LIKE '%因为%' OR explanation LIKE '%因此%' "
    "OR explanation LIKE '%正因%' OR explanation LIKE '%由于%'"
):
    print("  words=%r explanation=%r class=%r count=%r sense/variety=%r/%r" % (
        row["words"], row["explanation"], row["class"], row["count"],
        row["variety"] if "variety" in row.keys() else "?",
        row["sense_order"] if "sense_order" in row.keys() else "?"))

print()
print("=== no_class rows mentioning so/cause words ===")
for row in con.execute(
    "SELECT * FROM no_class WHERE lower(words) LIKE '%eliz%' OR translation LIKE '%所以%' "
    "OR translation LIKE '%因为%' OR translation LIKE '%因此%' OR translation LIKE '%正因%'"
):
    print("  ", dict(row))

con.close()
