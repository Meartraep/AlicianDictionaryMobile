# -*- coding: utf-8 -*-
"""Extract app alignment rows + source stanzas into one JSON for analysis."""
import sqlite3, io, sys, re, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SRC = Path(r"C:\Users\meart\Desktop\alicianlabs-master\script\songs_data")
DB = Path(r"app/src/main/assets/translated.db")
WS = re.compile(r"[\s\u00a0\u2000-\u200a\u202f\u3000]+")
BT = "\x60"
def norm(t): return WS.sub(" ", t or "").strip()
def parse_song_file(path):
    content = path.read_text(encoding="utf-8")
    def g(pat):
        m = re.search(pat, content)
        return m.group(1) if m else ""
    return (g(r'title = "([^"]*)"'),
            g("original_lyrics = " + BT + "([^" + BT + "]*)" + BT),
            g("english_lyrics = " + BT + "([^" + BT + "]*)" + BT),
            g("japanese_lyrics\\s*=\\s*" + BT + "([^" + BT + "]*)" + BT))
def stanzas(text):
    out = []; cur = []
    for raw in (text or "").splitlines():
        line = norm(raw)
        if not line:
            if cur: out.append(cur); cur = []
            continue
        cur.append(line)
    if cur: out.append(cur)
    return out
src = {}
for p in sorted(SRC.glob("*.js")):
    t, o, e, j = parse_song_file(p)
    src[p.stem] = dict(title=t, original=o, english=e, japanese=j,
                       orig_st=stanzas(o), en_st=stanzas(e), ja_st=stanzas(j))
c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
songs = {}
for r in c.execute("select title, album from songs"):
    songs[r['title']] = r['album']
align = {}
for r in c.execute("select * from sentence_alignments order by song_title, song_sentence_order"):
    align.setdefault(r['song_title'], []).append(dict(order=r['song_sentence_order'], al=r['alician_sentence'], zh=r['chinese_translation'], album=r['album']))
st = {}
for r in c.execute("select id, song_title, sentence, english, japanese, korean from song_translations order by song_title, id"):
    st.setdefault(r['song_title'], []).append(dict(id=r['id'], sentence=r['sentence'], en=r['english'], ja=r['japanese'], ko=r['korean']))
out = dict(src=src, songs=songs, align=align, st=st)
Path("scripts/realign/extract.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("songs in app:", len(songs))
print("songs with alignments:", len(align))
print("songs in song_translations:", len(st))
print("app titles lacking alignments:", sorted(set(songs) - set(align)))
print()
import collections
# link app titles to source files via current st sentences
REPO_TO_APP = json.loads(Path("scripts/realign/repo_to_app.json").read_text(encoding="utf-8")) if Path("scripts/realign/repo_to_app.json").exists() else {}
print("align rows total:", sum(len(v) for v in align.values()))
print("st rows total:", sum(len(v) for v in st.values()))
print("st titles not in app songs:", sorted(set(st) - set(songs)))
print("app songs missing from st:", sorted(set(songs) - set(st)))
