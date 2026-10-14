# -*- coding: utf-8 -*-
"""Compare current DB grouping (consecutive identical EN/JA) with source stanza grouping."""
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import align_song, ALIGN, STROWS, SRC

def db_groups(title):
    rows = sorted(STROWS.get(title, []), key=lambda r: r['id'])
    groups = []
    cur = None
    for r in rows:
        key = (r['en'], r['ja'])
        if cur is not None and cur['key'] == key:
            cur['rows'].append(r)
        else:
            cur = dict(key=key, rows=[r])
            groups.append(cur)
    return groups

report = []
for title in sorted(ALIGN):
    res, prob = align_song(title)
    if res is None:
        continue
    src_groups = {}
    for ai, m in enumerate(res['mapping']):
        s = m.get('stanza')
        src_groups.setdefault(s, []).append(ai)
    dg = db_groups(title)
    n_src = len([g for g in src_groups if g is not None])
    mism = []
    if len(dg) != n_src:
        mism.append('count %d db vs %d src' % (len(dg), n_src))
    # sizes sequence compare
    dsz = [len(g['rows']) for g in dg]
    ssz = [len(src_groups[k]) for k in sorted(k for k in src_groups if k is not None)]
    if dsz != ssz:
        mism.append('sizes db=%s src=%s' % (dsz, ssz))
    if mism or prob:
        report.append((title, mism, [p[0] for p in prob]))
print('songs where DB grouping != source stanza grouping (or problems): %d' % len(report))
for t, mism, pr in report:
    print('  %-46s %s %s' % (t[:46], '; '.join(mism)[:80], pr))
