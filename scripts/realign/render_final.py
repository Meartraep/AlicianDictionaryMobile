# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build
from align_engine import ALIGN
units = json.load(open('scripts/realign/units_final.json', encoding='utf-8'))
def atoms(blocks):
    idx = 0; parts = []
    for line in blocks:
        for tok in line.split():
            parts.append('%d|%s' % (idx, tok)); idx += 1
        parts.append('//')
    return ' '.join(parts) or '<none>'
out = []
for u in [x for x in units if x['k'] >= 2 and not x['auto']]:
    b = build(u['song']); rows = b['rows']
    out.append('@@ %s | S%02d | K=%d' % (u['song'], u['stanza'], u['k']))
    out.append('   orig: %s' % ' | '.join(b['S']['orig_st'][u['stanza']])[:140])
    for j, ai in enumerate(u['apps']):
        out.append('   p%d: %s || %s' % (j, rows[ai]['al'][:56], rows[ai]['zh'][:66]))
    out.append('   EN: %s' % atoms(u['en']))
    out.append('   JA: %s' % atoms(u['ja']))
    out.append('')
Path('scripts/realign/review_final.txt').write_text('\n'.join(out), encoding='utf-8')
print('lines:', len(out))
