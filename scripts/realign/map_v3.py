# -*- coding: utf-8 -*-
"""map_v3: content assignment (repeat-aware) over the fixed source + run grouping."""
from __future__ import annotations
import io, sys, json, collections, difflib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, canon, norm, song_source_key
from align_engine import align_song, ALIGN
from source_fix import all_songs

E = load_extract()
FIXED = all_songs()

def sim(a, b):
    if a == b:
        return 1.0
    if abs(len(a) - len(b)) > 3:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def coverage(atoks, pool):
    if not atoks:
        return 0.0
    pool = list(pool)
    hit = 0
    for t in atoks:
        for i, u in enumerate(pool):
            if sim(t, u) >= 0.72:
                hit += 1
                pool.pop(i)
                break
    return hit / len(atoks)

def build(title):
    res, prob = align_song(title)
    if res is None:
        return None
    key = res['key']
    S = FIXED[key]
    stoks = [canon(' '.join(st)) for st in S['orig_st']]
    rows = res['rows']
    pairs = res['pairs']; src_stream, app_stream = res['src_stream'], res['app_stream']
    nw = collections.defaultdict(collections.Counter)
    for i, j in pairs:
        if i is not None and j is not None:
            nw[app_stream[j][1]][src_stream[i][1]] += 1
    assign, covs = [], []
    prev = 0
    for ai, r in enumerate(rows):
        atoks = canon(r['al'])
        cov = [round(coverage(atoks, st), 3) for st in stoks]
        best = max(range(len(cov)), key=lambda i: cov[i]) if cov else None
        bs = cov[best] if best is not None else 0.0
        fwd = [i for i in range(prev, len(cov)) if cov[i] >= max(0.85, bs - 0.05)]
        chosen = min(fwd) if fwd else best
        assign.append(chosen); covs.append(cov)
        if chosen is not None:
            prev = chosen
    return dict(key=key, S=S, stoks=stoks, assign=assign, covs=covs, nw=nw, rows=rows, res=res)

def runs_of(b):
    n = len(b['rows'])
    part = collections.defaultdict(set)
    for ai in range(n):
        s = b['assign'][ai]
        if s is None:
            continue
        part[s].add(ai)
        for s2 in b['nw'].get(ai, {}):
            if abs(s2 - s) == 1:
                part[s2].add(ai)
    runs = collections.defaultdict(list)
    for s, appset in part.items():
        apps = sorted(appset)
        cur = [apps[0]]
        for a in apps[1:]:
            if a == cur[-1] + 1:
                cur.append(a)
            else:
                runs[s].append(cur); cur = [a]
        runs[s].append(cur)
    return runs

if __name__ == '__main__':
    jumps = []
    for title in sorted(ALIGN):
        b = build(title)
        if b is None:
            continue
        prev = 0
        for ai, s in enumerate(b['assign']):
            if s is None:
                continue
            if ai and s < prev:
                jumps.append((title, ai, b['rows'][ai]['al'][:52], prev, s, b['covs'][ai]))
            prev = max(prev, s)
    print('backward assignments: %d' % len(jumps))
    for t, ai, al, prev, s, cov in jumps:
        print('   %-40s [%2d] %-52s prev=S%02d chosen=S%02d cov[chosen]=%s cov[prev:prev+4]=%s' % (
            t[:40], ai, al, prev, s, cov[s], cov[prev:prev+4]))
