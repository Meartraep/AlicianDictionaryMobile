# -*- coding: utf-8 -*-
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build, runs_of, spans_of
b = build('ALQ'); S = b['S']; rows = b['rows']
runs = runs_of(b)
for s in sorted(runs):
    print('S%02d %-45s runs=%s' % (s, ' '.join(S['orig_st'][s])[:45], runs[s]))
print()
for ai in range(17, 25):
    print('[%2d] %-30s assign=S%s spans=%s nw=%s' % (ai, rows[ai]['al'][:30], b['assign'][ai], sorted(spans_of(b, ai, b['assign'][ai])), dict(b['nw'].get(ai, {}))))
