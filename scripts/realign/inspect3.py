# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract
from map_v2 import build
E = load_extract(); STROWS = E['st']
for title in ['Alice Music', 'KILLED BY ANGEL', 'The White Land']:
    b = build(title); S = b['S']
    dbrows = {}
    for r in STROWS.get(title, []):
        dbrows.setdefault(r['sentence'], []).append(r)
    print('=' * 100); print('###', title)
    for i, st in enumerate(S['orig_st']):
        en = S['en_st'][i] if i < len(S['en_st']) else []
        ja = S['ja_st'][i] if i < len(S['ja_st']) else []
        print('  S%02d ORIG %s' % (i, ' | '.join(st)[:100]))
        print('       EN %s' % ' // '.join(en)[:100])
        print('       JA %s' % ' // '.join(ja)[:100])
    print('  --- app rows (DB block shown) ---')
    for d in b['diag']:
        r = b['rows'][d['app']]
        db = dbrows.get(r['al'], [])
        dbtxt = ('EN=%r JA=%r' % (db[0]['en'][:70], db[0]['ja'][:50])) if db else '(no row)'
        print('  [%2d] chosen=S%02d cov=%s | %-52s | %s' % (d['app'], d['chosen'] if d['chosen'] is not None else -1, d['cov'][:6], r['al'][:52], dbtxt))
