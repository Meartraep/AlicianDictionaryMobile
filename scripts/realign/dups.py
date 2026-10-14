# -*- coding: utf-8 -*-
"""How many app sentences repeat within a song, and do their source stanzas differ?"""
import io, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v2 import build
from align_engine import ALIGN
tot = 0
rows = []
for title in sorted(ALIGN):
    b = build(title)
    if b is None:
        continue
    cnt = collections.Counter(r['al'] for r in b['rows'] if r['al'].strip())
    for sent, c in cnt.items():
        if c > 1:
            tot += 1
            idxs = [i for i, r in enumerate(b['rows']) if r['al'] == sent]
            chosen = [b['diag'][i]['chosen'] for i in idxs]
            rows.append((title, sent, c, chosen))
print('repeated app sentences within a song: %d' % tot)
diff_choice = [r for r in rows if len(set(r[3])) > 1]
print('  of which map to different source stanzas: %d' % len(diff_choice))
for t, s, c, ch in diff_choice:
    print('   %-40s %-50s x%d stanzas=%s' % (t[:40], s[:50], c, ch))
