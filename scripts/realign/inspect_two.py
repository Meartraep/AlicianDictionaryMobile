# -*- coding: utf-8 -*-
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build, runs_of
for title in ['Sno (_ _) oze & Sn (o_o) ze', 'The White Land']:
    b = build(title); S = b['S']; rows = b['rows']
    print('=' * 100); print('###', title)
    for i, st in enumerate(S['orig_st']):
        print('  S%02d %-52s | %s' % (i, ' '.join(st)[:52], (' // '.join(S['ja_st'][i])[:70] if i < len(S['ja_st']) else '')))
    print('  --- app rows ---')
    for ai, r in enumerate(rows):
        cov = b['covs'][ai]
        top = [i for i in sorted(range(len(cov)), key=lambda i: -cov[i])[:2]]
        print('  [%2d] %-50s -> S%02d (%s) top=%s' % (ai, r['al'][:50], b['assign'][ai] if b['assign'][ai] is not None else -1, b['how'][ai], [(t, cov[t]) for t in top]))
    runs = runs_of(b)
    print('  runs:', {k: v for k, v in sorted(runs.items())})
