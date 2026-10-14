# -*- coding: utf-8 -*-
"""Repeated sentences whose differing stanzas also differ in EN/JA text."""
import io, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v2 import build
from align_engine import ALIGN
from common import norm
n_diff = 0
examples = []
for title in sorted(ALIGN):
    b = build(title)
    if b is None:
        continue
    S = b['S']
    cnt = collections.Counter(r['al'] for r in b['rows'] if r['al'].strip())
    for sent, c in cnt.items():
        if c < 2:
            continue
        idxs = [i for i, r in enumerate(b['rows']) if r['al'] == sent]
        ch = [b['diag'][i]['chosen'] for i in idxs]
        ch = [c2 for c2 in ch if c2 is not None]
        if len(set(ch)) < 2:
            continue
        texts = set()
        for si in set(ch):
            en = norm('\n'.join(S['en_st'][si])) if si < len(S['en_st']) else ''
            ja = norm('\n'.join(S['ja_st'][si])) if si < len(S['ja_st']) else ''
            texts.add((en, ja))
        if len(texts) > 1:
            n_diff += 1
            examples.append((title, sent, sorted(set(ch))))
print('repeated sentences whose stanzas carry different EN/JA text: %d' % n_diff)
for t, s, st in examples:
    print('   %-40s %-48s stanzas=%s' % (t[:40], s[:48], st))
