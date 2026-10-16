"""Prove Loosya = Japanese すら / も using ONLY the official JP/EN lyrics.

No Chinese column, no community word list (dictionary.japanese_gloss) is used.
Evidence source: song_translations.japanese  and  song_translations.english.
"""
import io
import re
import sqlite3
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

PLURAL = None  # noqa

print("=" * 78)
print("A) 官方日文里作为【副助词】的 すら（排除 ひたすら / すらり 等词内出现）")
print("=" * 78)
rows = con.execute(
    "SELECT id, song_title, sentence, japanese, english FROM song_translations"
    " WHERE japanese LIKE '%すら%' ORDER BY id"
).fetchall()
particle_rows = []
for r in rows:
    jp = str(r["japanese"]).replace("\n", " ")
    # strip ひたすら etc.: keep only すら not preceded by ひた / た (word-internal)
    hits = [m.start() for m in re.finditer("すら", jp)]
    real = [h for h in hits if not jp[max(0, h - 2):h].endswith("ひた")]
    tag = "副助词" if real else "词内(排除)"
    ctxs = [jp[max(0, h - 6):h + 8] for h in real]
    print(f"\n  offid={r['id']} [{tag}] 上下文={ctxs}")
    print(f"     AL={r['sentence']}")
    print(f"     JP={jp}")
    print(f"     EN={(r['english'] or '').replace(chr(10), ' | ')}")
    has_loosya = "loosya" in {w.lower() for w in WORD_RE.findall(r["sentence"])}
    print(f"     含 Loosya: {has_loosya}")
    if real:
        particle_rows.append(r)

print("\n" + "=" * 78)
print("B) 反向检验：官方日文含【副助词】すら 的行中，Alician 侧出现哪些词")
print("=" * 78)
sets = []
for r in particle_rows:
    ws = {w.lower() for w in WORD_RE.findall(r["sentence"])}
    sets.append(ws)
    print(f"  offid={r['id']}: {sorted(ws)}")
if sets:
    common = set.intersection(*sets)
    print(f"\n  所有含 すら 的行共有的 Alician 词: {sorted(common)}")

print("\n" + "=" * 78)
print("C) 排除法：为 ① offid=236 的每个 Alician 词在【其它官方行】里找出日文对应")
print("=" * 78)
probe = {
    "Enebis": ("人", "人間", "ヒト"),
    "Nai": ("ない", "ません", "ぬ"),
    "iy": ("です", "だ", "は", "である"),
    "Vig": ("君", "あなた", "お前", "きみ"),
}
for word, jp_options in probe.items():
    hits = []
    for r in con.execute(
        "SELECT id, sentence, japanese FROM song_translations"
        " WHERE lower(sentence) LIKE ?", (f"%{word.lower()}%",),
    ):
        jp = str(r["japanese"] or "")
        if not any(o in jp for o in jp_options):
            continue
        ws = [w.lower() for w in WORD_RE.findall(r["sentence"])]
        if word.lower() not in ws:
            continue
        hits.append((r["id"], " ".join(ws), jp.replace("\n", " | ")))
    print(f"\n  {word}: 与 {jp_options} 共现的官方行 {len(hits)} 条（示 4 条）")
    for offid, al, jp in hits[:4]:
        print(f"    offid={offid}")
        print(f"       AL={al}")
        print(f"       JP={jp[:96]}")

print("\n" + "=" * 78)
print("D) ② offid=631 的 も 对位；以及全部 3 条 Loosya 行的精确邻接")
print("=" * 78)
for offid in (236, 631, 865):
    r = con.execute(
        "SELECT id, sentence, japanese, english FROM song_translations WHERE id=?", (offid,)
    ).fetchone()
    ws = WORD_RE.findall(r["sentence"])
    low = [w.lower() for w in ws]
    i = low.index("loosya")
    host = ws[i + 1:i + 3]
    print(f"\n  offid={offid}")
    print(f"    AL={r['sentence']}")
    print(f"    Loosya 后紧跟: {host}")
    print(f"    JP={r['japanese'].replace(chr(10), ' | ')}")
    print(f"    EN={r['english']}")

con.close()
