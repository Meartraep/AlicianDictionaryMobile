# -*- coding: utf-8 -*-
"""Work list: every stanza overlapped by >=2 app sentences (= needs a cut), with app rows."""
import io, sys, json, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import align_song, ALIGN, SRC

def overlap_map(title):
    res, prob = align_song(title)
    if res is None:
        return None
    pairs = res['pairs']; src_stream, app_stream = res['src_stream'], res['app_stream']
    per = collections.defaultdict(list)   # stanza -> [app_idx]
    seen = collections.defaultdict(set)
    for i, j in pairs:
        if i is None or j is None:
            continue
        si = src_stream[i][1]; ai = app_stream[j][1]
        if ai not in seen[si]:
            seen[si].add(ai)
            per[si].append(ai)
    return res, per

units = []
for title in sorted(ALIGN):
    om = overlap_map(title)
    if om is None:
        continue
    res, per = om
    S = SRC[res['key']]
    rows = res['rows']
    for si, apps in sorted(per.items()):
        if len(apps) < 2:
            continue
        en = S['en_st'][si] if si < len(S['en_st']) else []
        ja = S['ja_st'][si] if si < len(S['ja_st']) else []
        units.append(dict(song=title, stanza=si, apps=apps, n=len(apps),
                          orig=S['orig_st'][si], en=en, ja=ja))
print('stanzas needing >=2 pieces (by overlap):', len(units))
print('covered app-sentence slots:', sum(u['n'] for u in units))
json.dump(units, open('scripts/realign/units.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
by_song = collections.Counter(u['song'] for u in units)
print('songs:', len(by_song))
print()
for s, c in sorted(by_song.items(), key=lambda kv: -kv[1]):
    print('   %-46s %d' % (s[:46], c))
