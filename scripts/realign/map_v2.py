# -*- coding: utf-8 -*-
"""Mapping v2: content-based stanza assignment (repeat-safe) + run grouping."""
from __future__ import annotations
import io, sys, json, collections, difflib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, canon, norm, song_source_key
from align_engine import align_song, ALIGN, SRC

E = load_extract()

def sim(a, b):
    if a == b:
        return 1.0
    if abs(len(a) - len(b)) > 3:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def coverage(atoks, stoks):
    """Fraction of app tokens that appear (fuzzily) in the stanza token multiset."""
    if not atoks:
        return 0.0
    pool = list(stoks)
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
    S = SRC[res['key']]
    stanzas = S['orig_st']
    stoks = [canon(' '.join(st)) for st in stanzas]
    rows = res['rows']
    # NW overlap per app sentence
    pairs = res['pairs']; src_stream, app_stream = res['src_stream'], res['app_stream']
    nw = collections.defaultdict(collections.Counter)
    for i, j in pairs:
        if i is not None and j is not None:
            nw[app_stream[j][1]][src_stream[i][1]] += 1
    assign = []
    prev = 0
    diag = []
    for ai, r in enumerate(rows):
        atoks = canon(r['al'])
        cov = [coverage(atoks, st) for st in stoks]
        best = max(range(len(cov)), key=lambda i: cov[i]) if cov else None
        bestscore = cov[best] if best is not None else 0.0
        # forward preference among near-perfect matches
        fwd = [i for i in range(prev, len(cov)) if cov[i] >= max(0.85, bestscore - 0.05)]
        if fwd:
            chosen = min(fwd)
        else:
            chosen = best
        assign.append(chosen)
        if chosen is not None:
            prev = chosen
        nw_st = nw.get(ai, collections.Counter()).most_common(1)
        diag.append(dict(app=ai, al=r['al'], chosen=chosen, best=best, bestscore=round(bestscore, 3),
                         cov=[round(c, 2) for c in cov], nw=(nw_st[0][0] if nw_st else None),
                         nwv=(nw_st[0][1] if nw_st else 0)))
    return dict(res=res, S=S, stoks=stoks, assign=assign, nw=nw, diag=diag, rows=rows)

def runs_for(title):
    b = build(title)
    if b is None:
        return None
    n = len(b['rows'])
    # participation: main assignment or adjacent-stanza overlap
    part = collections.defaultdict(set)
    for ai in range(n):
        s = b['assign'][ai]
        if s is None:
            continue
        part[s].add(ai)
        for s2, cnt in b['nw'].get(ai, {}).items():
            if abs(s2 - s) == 1 and cnt >= 1:
                part[s2].add(ai)
            if s2 == s:
                part[s].add(ai)
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
    return b, runs

if __name__ == '__main__':
    tot_runs = 0
    multi = 0
    weird = []
    for title in sorted(ALIGN):
        r = runs_for(title)
        if r is None:
            continue
        b, runs = r
        for s, rl in sorted(runs.items()):
            for run in rl:
                tot_runs += 1
                if len(run) >= 2:
                    multi += 1
        # diagnostics: chosen != nw majority and both non-null
        for d in b['diag']:
            if d['nw'] is not None and d['chosen'] is not None and d['nw'] != d['chosen'] and d['nwv'] >= 3:
                weird.append((title, d['app'], d['al'][:50], 'chosen=S%02d' % d['chosen'], 'nw=S%02d(x%d)' % (d['nw'], d['nwv']), d['bestscore']))
    print('total runs:', tot_runs, ' runs with K>=2:', multi)
    print()
    print('assignments differing from NW majority (>=3 votes): %d' % len(weird))
    for w in weird:
        print('   %-40s [%2d] %-50s %s %s score=%s' % (w[0][:40], w[1], w[2], w[3], w[4], w[5]))
