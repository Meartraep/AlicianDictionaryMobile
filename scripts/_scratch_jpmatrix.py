"""Scratch: Alician function word x Japanese marker co-occurrence / lift matrix.

Uses song_translations (official japanese original + english) as the reference
instead of the Chinese localization column.
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

ALICIAN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

JP_MARKERS = [
    # conjunctive particles / connectives
    "から", "ながら", "ので", "だから", "でも", "けど", "けれど", "しかし",
    "そして", "それから", "すると", "ゆえに", "つまり",
    # case particles
    "と", "で", "に", "の", "は", "が", "を", "へ", "も", "より", "や",
    # clause-final / auxiliaries
    "ている", "てる", "たい", "ない", "ません", "なかった", "ましょう",
    "ください", "なさい", "だろ", "でしょ", "よう", "みたい", "らしい", "そう",
    "なら", "たら", "れば", "ば", "つつ",
    # adverbs / quantifiers
    "もう", "まだ", "ずっと", "きっと", "いつも", "とても", "すべて", "みんな",
    "また", "今", "ここ", "そこ", "どこ", "これ", "それ", "あれ", "この",
    "その", "あの", "どんな", "どう", "なぜ", "もし", "たとえ", "だけ",
    "しか", "ほど", "まで", "くらい", "ばかり", "何",
]

# Candidate Alician function words: closed classes + no_class + known particles
cands = set()
for cls in ("conj.", "prep.", "pron.", "art.", "num.", "interj.", "adv."):
    for r in con.execute("SELECT DISTINCT words FROM dictionary WHERE class = ?", (cls,)):
        cands.add(r["words"])
for r in con.execute("SELECT words FROM no_class"):
    cands.add(r["words"])
extra = {
    "end", "iera", "ra", "iy", "a", "es", "en", "ta", "sii", "sip", "wei",
    "weiy", "dou", "endil", "iqyur", "noa", "ieq", "iequim", "og", "amiy",
    "laiz", "vell", "qleea", "nai", "ol", "ob", "ord", "yien", "ifa", "imm",
    "tie", "weil", "il", "folme", "arch", "arche", "lim", "alfloul", "pllia",
    "uleim", "forle", "winde", "lid", "elied", "tozlom", "ijlim", "mols",
    "osa", "baly", "poutie", "imeila", "quim", "elize", "gout", "poet",
    "poetklar", "poetolt", "zel", "note", "hiele", "lishe", "leste", "kulu",
    "phim", "foul", "crain", "lend", "erikes", "fevla", "phier", "yiela",
    "yiep", "lqll", "dis", "shai",
}
cands |= extra
cands = {c for c in cands if c and ALICIAN_WORD_RE.fullmatch(c)}

rows = con.execute(
    "SELECT sentence, japanese FROM song_translations"
    " WHERE japanese IS NOT NULL AND japanese <> ''"
).fetchall()
docs = []
for r in rows:
    jp = str(r["japanese"]).replace("\n", " ")
    words = {w.lower() for w in ALICIAN_WORD_RE.findall(str(r["sentence"]))}
    docs.append((words, jp))
print(f"official JP rows: {len(docs)}")

marker_base = Counter()
for _, jp in docs:
    for m in JP_MARKERS:
        if m in jp:
            marker_base[m] += 1
N = len(docs)

word_docs = defaultdict(list)
for words, jp in docs:
    for w in words:
        if w in cands:
            word_docs[w].append(jp)

print("\n=== Alician function word  ->  top Japanese markers (lift, N>=5) ===")
results = []
for w, jps in word_docs.items():
    if len(jps) < 5:
        continue
    cnt = Counter()
    for jp in jps:
        for m in JP_MARKERS:
            if m in jp:
                cnt[m] += 1
    scored = []
    for m, c in cnt.items():
        if c < 3:
            continue
        precision = c / len(jps)
        lift = precision / (marker_base[m] / N) if marker_base[m] else 0
        scored.append((lift, m, c, precision))
    scored.sort(reverse=True)
    if scored:
        results.append((w, len(jps), scored[:4]))

results.sort(key=lambda x: x[1], reverse=True)
for w, n, top in results:
    desc = "  ".join(f"{m}({c}/{n},{lift:.1f}x)" for lift, m, c, prec in top)
    print(f"  {w:<12} n={n:<4} {desc}")

con.close()
