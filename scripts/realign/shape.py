# -*- coding: utf-8 -*-
"""Shape analysis of current DB blocks: how many need a split, and how clean the split is."""
import io, sys, json, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import ALIGN, STROWS

def blocks(title):
    rows = sorted(STROWS.get(title, []), key=lambda r: r['id'])
    out = []
    for r in rows:
        if out and out[-1]['en'] == r['en'] and out[-1]['ja'] == r['ja']:
            out[-1]['rows'].append(r)
        else:
            out.append(dict(en=r['en'], ja=r['ja'], rows=[r]))
    return out

shape = collections.Counter()
need = 0
single_multi = []   # N==1 but block has >1 line
total_rows = 0
for title in sorted(STROWS):
    for b in blocks(title):
        n = len(b['rows'])
        total_rows += n
        le = len([x for x in (b['en'] or '').split('\n') if x.strip()])
        lj = len([x for x in (b['ja'] or '').split('\n') if x.strip()])
        if n == 1:
            if le > 1 or lj > 1:
                single_multi.append((title, b['rows'][0]['sentence'], le, lj, b['rows'][0]['id']))
        else:
            shape[(n, le, lj)] += 1
            need += 1
print('rows total:', total_rows)
print('multi-row blocks (N>=2):', need, ' covering rows:', sum(k[0] * v for k, v in shape.items()))
print('distinct (N, en_lines, ja_lines) shapes:')
for k, v in sorted(shape.items()):
    print('   N=%d en_lines=%d ja_lines=%d  -> %d blocks   %s' % (k[0], k[1], k[2], v,
          'CLEAN' if (k[1] == k[0] and k[2] == k[0]) else ('en-clean' if k[1] == k[0] else ('ja-clean' if k[2] == k[0] else 'needs-work'))))
print()
print('N==1 blocks whose text still spans several lines: %d' % len(single_multi))
for t, s, le, lj, i in single_multi:
    print('   %-40s id=%-5d en=%d ja=%d  %s' % (t[:40], i, le, lj, s[:60]))
