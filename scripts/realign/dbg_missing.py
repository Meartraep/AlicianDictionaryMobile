# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract
from map_v4 import build
from align_engine import ALIGN
E = load_extract(); STROWS = E['st']
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))
tot_missing = 0
for title in sorted(ALIGN):
    b = build(title)
    if b is None: continue
    db = set(r['sentence'] for r in STROWS.get(title, []))
    miss = [r['al'] for r in b['rows'] if r['al'].strip() and r['al'] not in db]
    if miss:
        tot_missing += len(miss)
        print('%-46s rows=%-3d st=%-3d missing=%d' % (title[:46], len(b['rows']), len(STROWS.get(title, [])), len(miss)))
print('total sentences without a DB row:', tot_missing)
