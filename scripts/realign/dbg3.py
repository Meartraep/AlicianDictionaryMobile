# -*- coding: utf-8 -*-
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build, runs_of
for title in ['Sno (_ _) oze & Sn (o_o) ze', 'バッドエンド·シンドローム(Bad End Syndrome)', 'Apocalypse']:
    b = build(title); S = b['S']; rows = b['rows']
    print('=' * 90); print('###', title)
    for s in sorted(runs_of(b)):
        print('  S%02d %-46s | %-40s runs=%s' % (s, ' '.join(S['orig_st'][s])[:46], (' // '.join(S['ja_st'][s]) if s < len(S['ja_st']) else '')[:40], runs_of(b)[s]))
    print('  --- rows ---')
    for ai, r in enumerate(rows):
        if title.startswith('Sno') and ai > 20: break
        print('  [%2d] %-44s -> S%s (%s)' % (ai, r['al'][:44], b['assign'][ai], b['how'][ai]))
