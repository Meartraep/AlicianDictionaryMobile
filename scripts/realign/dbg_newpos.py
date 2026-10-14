# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))
ks = list(NEW.keys())
print('newpos entries:', len(ks))
print('sample keys:', ks[:5])
from map_v4 import build
b = build('Wonder World Sketch')
rows = b['rows']
for ai, r in enumerate(rows[:6]):
    k = 'Wonder World Sketch|||%d' % ai
    print(ai, r['al'][:40], '->', repr(NEW.get(k, 'MISSING')))
print()
import collections
c = collections.Counter(k.split('|||')[0] for k in ks)
print('songs in newpos:', len(c))
print(sorted(c.items(), key=lambda kv: -kv[1])[:8])
