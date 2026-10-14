# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build
from align_engine import ALIGN
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))
for title in ['Alice Music']:
    b = build(title); S = b['S']
    for i, st in enumerate(S['orig_st']):
        print('  S%02d %-52s | %s' % (i, ' '.join(st)[:52], (' // '.join(S['ja_st'][i]) if i < len(S['ja_st']) else '')[:56]))
    print()
    for ai, r in enumerate(b['rows']):
        n = NEW.get('%s|||%d' % (title, ai), {})
        print('[%2d] %-46s -> S%-3s | EN=%-46s | JA=%s' % (ai, r['al'][:46], b['assign'][ai], (n.get('en','') or '')[:46], (n.get('ja','') or '')[:40]))
