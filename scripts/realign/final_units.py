# -*- coding: utf-8 -*-
"""Final units: runs of app sentences per stanza, with auto/needs-judgement classification."""
import io, sys, json, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build, runs_of
from align_engine import ALIGN

units = []
for title in sorted(ALIGN):
    b = build(title)
    if b is None:
        continue
    S = b['S']
    runs = runs_of(b)
    for si in sorted(runs):
        for run in runs[si]:
            en = S['en_st'][si] if si < len(S['en_st']) else []
            ja = S['ja_st'][si] if si < len(S['ja_st']) else []
            k = len(run)
            en_lines = [len(x.split()) for x in en if x.strip()]
            ja_lines = [len(x.split()) for x in ja if x.strip()]
            auto = None
            if k >= 2:
                if (not en_lines or len(en_lines) == k) and len(ja_lines) == k:
                    auto = dict(en=en_lines if en_lines else None, ja=ja_lines)
            units.append(dict(song=title, stanza=si, k=k, apps=run, en=en, ja=ja,
                              en_lines=en_lines, ja_lines=ja_lines, auto=auto))
json.dump(units, open('scripts/realign/units_final.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
multi = [u for u in units if u['k'] >= 2]
print('total runs: %d ; runs with K>=2: %d' % (len(units), len(multi)))
print('  auto (line split clean): %d' % sum(1 for u in multi if u['auto']))
print('  needs judgement: %d' % sum(1 for u in multi if not u['auto']))
by = collections.Counter(u['song'] for u in multi if not u['auto'])
print('songs with judgement units:', len(by))
for s, c in sorted(by.items(), key=lambda kv: -kv[1]):
    print('   %-46s %d' % (s[:46], c))
