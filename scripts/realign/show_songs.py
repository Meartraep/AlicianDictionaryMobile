# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from build_map import stanza_groups
from align_engine import ALIGN, SRC

def show(title):
    g, prob = stanza_groups(title)
    res = g['res']; S = SRC[res['key']]
    rows = {r['order']: r for r in ALIGN[title]}
    print('#' * 90)
    print('# SONG:', title)
    for si, items in sorted([kv for kv in g['groups'].items() if kv[0] is not None]):
        n = len(items)
        st = S['orig_st'][si]
        en = S['en_st'][si] if si < len(S['en_st']) else []
        ja = S['ja_st'][si] if si < len(S['ja_st']) else []
        mark = '  <<< SPLIT NEEDED' if n >= 2 else ''
        print('-- S%02d (N=%d)%s' % (si, n, mark))
        print('   orig : %s' % ' | '.join(st))
        print('   EN   : %s' % ' // '.join(en))
        print('   JA   : %s' % ' // '.join(ja))
        for it in items:
            r = res['rows'][it['app']]
            print('   app%-3d AL=%-58s ZH=%s' % (it['app'], it['al'][:58], r['zh']))
for t in ['A Little Servant', 'Wonder World Sketch', 'Lost My Savepoint', '三十 Million Persona'.replace('三十','Thirty')]:
    show(t)
