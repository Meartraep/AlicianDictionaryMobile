# -*- coding: utf-8 -*-
"""Render manual units for review (numbered atoms) and clean units compactly."""
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import ALIGN
units = json.load(open('scripts/realign/units.json', encoding='utf-8'))
order = {t: i for i, t in enumerate(ALIGN)}
units.sort(key=lambda u: (order.get(u['song'], 999), u['stanza']))
manual, clean = [], []
for u in units:
    k = u['n']
    en_lines = [len(x.split()) for x in u['en'] if x.strip()]
    ja_lines = [len(x.split()) for x in u['ja'] if x.strip()]
    (clean if ((not en_lines) or len(en_lines) == k) and len(ja_lines) == k else manual).append(u)

def atoms(blocks):
    idx = 0; parts = []
    for line in blocks:
        for tok in line.split():
            parts.append('%d|%s' % (idx, tok)); idx += 1
        parts.append('//')
    return ' '.join(parts) or '<none>'

out = []
for u in manual:
    rows = sorted(ALIGN[u['song']], key=lambda r: (r['order'] is None, r['order'] or 0))
    out.append('@@ %s | S%02d | K=%d' % (u['song'], u['stanza'], u['n']))
    out.append('   orig: %s' % ' | '.join(u['orig'])[:150])
    for k, ai in enumerate(u['apps']):
        r = rows[ai]
        out.append('   app%d: %s || %s' % (k, r['al'][:58], r['zh'][:68]))
    out.append('   EN: %s' % atoms(u['en']))
    out.append('   JA: %s' % atoms(u['ja']))
    out.append('')
Path('scripts/realign/review_manual.txt').write_text('\n'.join(out), encoding='utf-8')
print('manual units:', len(manual), 'lines:', len(out))

out2 = []
for u in clean:
    rows = sorted(ALIGN[u['song']], key=lambda r: (r['order'] is None, r['order'] or 0))
    out2.append('@@ %s | S%02d | K=%d' % (u['song'], u['stanza'], u['n']))
    for k, ai in enumerate(u['apps']):
        r = rows[ai]
        out2.append('   app%d: %s || %s' % (k, r['al'][:58], r['zh'][:68]))
    out2.append('   EN: %s' % atoms(u['en']))
    out2.append('   JA: %s' % atoms(u['ja']))
    out2.append('')
Path('scripts/realign/review_clean.txt').write_text('\n'.join(out2), encoding='utf-8')
print('clean units:', len(clean), 'lines:', len(out2))
