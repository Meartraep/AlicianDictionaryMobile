# -*- coding: utf-8 -*-
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import ALIGN, STROWS
tot_a = tot_s = 0
print('%-46s %5s %5s %5s' % ('song', 'align', 'strows', 'blocked'))
for title in sorted(ALIGN):
    a = len([r for r in ALIGN[title] if (r['al'] or '').strip()])
    s = len(STROWS.get(title, []))
    tot_a += a; tot_s += s
    flag = '' if a == s else ('  <-- MISSING %d' % (a - s) if a > s else '  <-- EXTRA %d' % (s - a))
    print('%-46s %5d %5d %s' % (title[:46], a, s, flag))
print('TOTAL align=%d st=%d' % (tot_a, tot_s))
