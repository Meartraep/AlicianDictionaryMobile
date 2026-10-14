# -*- coding: utf-8 -*-
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v3 import build
for title in ['EAT YOU UP', 'Sno (_ _) oze & Sn (o_o) ze', 'i am always wrong']:
    b = build(title); S = b['S']
    print('=' * 100); print('###', title, ' stanzas=%d apps=%d' % (len(S['orig_st']), len(b['rows'])))
    for i, st in enumerate(S['orig_st']):
        print('  S%02d %-58s | %s' % (i, ' '.join(st)[:58], ' // '.join(S['ja_st'][i])[:60] if i < len(S['ja_st']) else ''))
    print('  --- assignment ---')
    for ai, r in enumerate(b['rows']):
        cov = b['covs'][ai]
        top = sorted(range(len(cov)), key=lambda i: -cov[i])[:3]
        print('  [%2d] %-52s -> S%02d  top=%s' % (ai, r['al'][:52], b['assign'][ai] if b['assign'][ai] is not None else -1,
              [(t, cov[t]) for t in top]))
