"""Independently anchor the co-elements of the Loosya clauses in official lyrics."""
import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

TARGETS = {
    "Enebis": ("人", "人間"),
    "Selti": ("意味",),
    "Spay": ("鏡", "镜"),
    "Liiquip": ("独裁者",),
    "Hewvews": ("ナルシスト",),
    "Mazy": ("迷路",),
}
for word, jp_opts in TARGETS.items():
    print(f"\n########## {word}  （官方日文含 {jp_opts}）")
    found = 0
    for r in con.execute(
        "SELECT id, song_title, sentence, japanese, english FROM song_translations"
        " WHERE lower(sentence) LIKE ?", (f"%{word.lower()}%",),
    ):
        jp = str(r["japanese"] or "")
        if not any(o in jp for o in jp_opts):
            continue
        found += 1
        ws = WORD_RE.findall(r["sentence"])
        low = [w.lower() for w in ws]
        i = low.index(word.lower())
        print(f"  offid={r['id']}  位置 {i+1}/{len(low)}  邻: "
              f"{' '.join(ws[max(0,i-2):i])} >>> {ws[i]} <<< {' '.join(ws[i+1:i+3])}")
        print(f"     JP={jp.replace(chr(10), ' | ')[:110]}")
        if r["english"]:
            print(f"     EN={r['english'].replace(chr(10), ' | ')[:110]}")
        if found >= 4:
            break
    if not found:
        print("  （无官方行同时满足）")

print("\n########## 关键：3 条 Loosya 行的日文里是否出现疑问词（何/誰/どこ）")
for offid in (236, 631, 865):
    r = con.execute("SELECT japanese FROM song_translations WHERE id=?", (offid,)).fetchone()
    jp = r["japanese"].replace("\n", " ")
    q = [w for w in ("何", "誰", "ど", "いつ") if w in jp]
    print(f"  offid={offid} 疑问词={q or '无'}   JP={jp}")

print("\n########## 官方英文里 even / too / also 的出现（对 Loosya 行的支持）")
for offid in (236, 631, 865):
    r = con.execute("SELECT english FROM song_translations WHERE id=?", (offid,)).fetchone()
    en = str(r["english"] or "").replace("\n", " ")
    marks = [w for w in ("even", "too", "also", "nothing but") if w in en.lower()]
    print(f"  offid={offid} 英文标记={marks or '无'}   EN={en or '(空)'}")

con.close()
