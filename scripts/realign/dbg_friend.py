# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build, runs_of
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))
for title in ['Friend', 'Frozen Tree']:
    b = build(title); S = b['S']; rows = b['rows']
    print('=' * 90); print('###', title)
    for s in sorted(runs_of(b)):
        print('  S%02d %-44s | %s   runs=%s' % (s, ' '.join(S['orig_st'][s])[:44], (' // '.join(S['ja_st'][s]) if s < len(S['ja_st']) else '')[:44], runs_of(b)[s]))
    print('  --- rows ---')
    for ai, r in enumerate(rows):
        n = NEW.get('%s|||%d' % (title, ai), {})
        j = (n.get('ja','') or '').replace('\n', ' / ')
        print('  [%2d] %-40s -> S%-3s | %s' % (ai, r['al'][:40], b['assign'][ai], j[:52]))
