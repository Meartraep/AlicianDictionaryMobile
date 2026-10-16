"""Scratch: inspect ob / ol aspect against official JP."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\python")

from webui_backend.translation_service import TranslationService

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
svc = TranslationService(DB, enable_fallback_matching=False)

def dump(where, sql, limit=10):
    print(f"=== {where} ===")
    for r in con.execute(sql + f" LIMIT {limit}"):
        al = r["sentence"]
        print("  AL :", al[:92])
        print("  JP :", (r["japanese"] or "").replace("\n", " | ")[:92])
        print("  EN :", (r["english"] or "").replace("\n", " | ")[:92])
        print("  OUT:", svc.translate(al, "alician_to_zh")["result_text"][:92])
        print()

dump("ob rows",
     "SELECT sentence, japanese, english FROM song_translations"
     " WHERE lower(sentence) LIKE '% ob %' OR lower(sentence) LIKE 'ob %'")
dump("ol rows",
     "SELECT sentence, japanese, english FROM song_translations"
     " WHERE lower(sentence) LIKE '% ol %'")

svc.close()
con.close()
