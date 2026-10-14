# -*- coding: utf-8 -*-
"""Render the manual-review listing with numbered atoms."""
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import ALIGN, SRC
import collections
units = json.load(open('scripts/realign/units.json', encoding='utf-8'))
# order units by song appearance order in ALIGN then stanza
order = {t: i for i, t in enumerate(ALIGN)}
units.sort(key=lambda u: (order.get(u['song'], 999), u['stanza']))
out = []
for u in units:
    title = u['song']
    rowmap = {r['order']: r for r in ALIGN[title]}
    res_rows = None
    # app rows in the same order as build (align_engine uses ALIGN order)
    rows = sorted(ALIGN[title], key=lambda r: (r['order'] is None, r['order'] or 0))
    out.append('@@ %s | S%02d | K=%d | ENatoms=%d JAatoms=%d' % (
        title, u['stanza'], u['n'],
        sum(len(x.split()) for x in u['en']), sum(len(x.split()) for x in u['ja'])))
    out.append('   orig: %s' % ' | '.join(u['orig'])[:170])
    for k, ai in enumerate(u['apps']):
        r = rows[ai]
        out.append('   app%d: %s || %s' % (k, r['al'][:60], r['zh'][:70]))
    for label, blocks in (('EN', u['en']), ('JA', u['ja'])):
        if not blocks:
            out.append('   %s: <none>' % label)
            continue
        idx = 0
        parts = []
        for line in blocks:
            for tok in line.split():
                parts.append('%d|%s' % (idx, tok)); idx += 1
            parts.append('//')
        out.append('   %s: %s' % (label, ' '.join(parts)))
    out.append('')
Path('scripts/realign/review_atoms.txt').write_text('\n'.join(out), encoding='utf-8')
print('units:', len(units), 'lines:', len(out))
print('units with no EN:', sum(1 for u in units if not u['en']))
print('units with no JA:', sum(1 for u in units if not u['ja']))
