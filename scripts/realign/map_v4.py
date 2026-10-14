# -*- coding: utf-8 -*-
"""map_v4: NW-monotonic assignment as primary, content fallback when NW stanza mismatches."""
from __future__ import annotations
import io, sys, json, collections, difflib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import canon, norm, load_extract
from align_engine import align_song, ALIGN
from source_fix import all_songs
from overrides import ASSIGN_OVERRIDE

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
    S = FIXED[res['key']]
    stoks = [canon(' '.join(st)) for st in S['orig_st']]
    rows = res['rows']
    pairs = res['pairs']; src_stream, app_stream = res['src_stream'], res['app_stream']
    nw = collections.defaultdict(collections.Counter)
    for i, j in pairs:
        if i is not None and j is not None:
            nw[app_stream[j][1]][src_stream[i][1]] += 1
    assign, covs, source = [], [], []
    prev = 0
    used = set()
    for ai, r in enumerate(rows):
        atoks = canon(r['al'])
        cov = [round(coverage(atoks, st), 3) for st in stoks]
        nwm = nw.get(ai, collections.Counter()).most_common(1)
        nws = nwm[0][0] if nwm else None
        best = max(range(len(cov)), key=lambda i: cov[i]) if cov else None
        bs = cov[best] if best is not None else 0.0
        # candidate stanzas at/after the previous one that match as well as the
        # best match and that no earlier line has been assigned to yet
        fwd = [i for i in range(prev, len(cov))
               if cov[i] >= max(0.85, bs - 0.05) and i not in used]
        if nws is not None and cov[nws] >= 0.55 and (nws in used or not fwd):
            chosen = nws; how = 'nw'
        elif fwd:
            chosen = min(fwd); how = 'fwd'
        elif nws is not None and cov[nws] >= 0.55:
            chosen = nws; how = 'nw'
        elif best is not None:
            chosen = best; how = 'content'
        else:
            chosen = None; how = 'none'
        ov = ASSIGN_OVERRIDE.get((title, ai), 'missing')
        if ov != 'missing':
            chosen = ov; how = 'override'
        assign.append(chosen); covs.append(cov); source.append(how)
        if chosen is not None:
            prev = chosen
            used.add(chosen)
    localpos = {}
    cnt = collections.Counter()
    for idx, (tok, si, li) in enumerate(res['src_stream']):
        localpos[idx] = cnt[si]; cnt[si] += 1
    return dict(key=res['key'], S=S, stoks=stoks, assign=assign, covs=covs, nw=nw,
                rows=rows, res=res, how=source, _localpos=localpos)

def spans_of(b, ai, s):
    """Stanzas adjacent to s that this sentence actually overruns into.

    A sentence belongs to the neighbouring stanza only when its matched tokens
    there form a contiguous prefix (next stanza) or suffix (previous stanza).
    """
    out = set()
    S = b['S']
    for s2, cnt in b['nw'].get(ai, {}).items():
        if s2 == s or abs(s2 - s) != 1:
            continue
        # positions of this sentence's matched tokens inside s2
        pos = sorted({b['_localpos'][i] for i, j in b['res']['pairs']
                      if i is not None and j is not None
                      and b['res']['src_stream'][i][1] == s2
                      and b['res']['app_stream'][j][1] == ai})
        if not pos:
            continue
        n = len(b['stoks'][s2])
        if s2 == s + 1 and pos == list(range(len(pos))):
            out.add(s2)
        elif s2 == s - 1 and pos == list(range(n - len(pos), n)):
            out.add(s2)
    return out

def runs_of(b):
    n = len(b['rows'])
    part = collections.defaultdict(set)
    for ai in range(n):
        s = b['assign'][ai]
        if s is None:
            continue
        part[s].add(ai)
        for s2 in spans_of(b, ai, s):
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
    n_fb = 0
    for title in sorted(ALIGN):
        b = build(title)
        if b is None:
            continue
        fbs = [(ai, b['rows'][ai]['al'][:46], b['assign'][ai], b['covs'][ai][b['assign'][ai]] if b['assign'][ai] is not None else None)
               for ai in range(len(b['rows'])) if b['how'][ai] == 'content']
        if fbs:
            print('### %s' % title)
            for ai, al, s, c in fbs:
                print('    [%2d] %-46s -> S%02d cov=%s' % (ai, al, s if s is not None else -1, c))
            n_fb += len(fbs)
    print()
    print('content-fallback assignments: %d' % n_fb)
