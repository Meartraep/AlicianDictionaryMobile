# -*- coding: utf-8 -*-
"""Core aligner: app sentences -> source stanzas/lines, then EN/JA fragments."""
from __future__ import annotations
import io, sys, re, json, difflib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_extract, canon, norm, song_source_key

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

E = load_extract()
ALIGN, STROWS, SRC = E['align'], E['st'], E['src']


def app_rows(title):
    return sorted(ALIGN.get(title, []), key=lambda r: (r['order'] is None, r['order'] or 0))


def sim(a, b):
    if a == b:
        return 1.0
    if abs(len(a) - len(b)) > 3:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


MATCH_MIN = 0.7
MATCH_SCORE = 1.4
MIS_SCORE = -0.9
GAP = -0.7


def nw_align(src_toks, app_toks):
    """Needleman-Wunsch alignment with fuzzy token similarity.

    Returns list of (src_idx or None, app_idx or None).
    """
    n, m = len(src_toks), len(app_toks)
    # score matrix
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    P = [[0] * (m + 1) for _ in range(n + 1)]  # 0=diag,1=up(src gap),2=left(app gap)
    for i in range(1, n + 1):
        S[i][0] = S[i - 1][0] + GAP
        P[i][0] = 1
    for j in range(1, m + 1):
        S[0][j] = S[0][j - 1] + GAP
        P[0][j] = 2
    for i in range(1, n + 1):
        si = src_toks[i - 1]
        Si, Si1 = S[i], S[i - 1]
        Pi = P[i]
        for j in range(1, m + 1):
            r = sim(si, app_toks[j - 1])
            d = Si1[j - 1] + (MATCH_SCORE if r >= MATCH_MIN else MIS_SCORE)
            u = Si1[j] + GAP
            l = Si[j - 1] + GAP
            if d >= u and d >= l:
                Si[j] = d; Pi[j] = 0
            elif u >= l:
                Si[j] = u; Pi[j] = 1
            else:
                Si[j] = l; Pi[j] = 2
    # traceback
    pairs = []
    i, j = n, m
    while i > 0 or j > 0:
        p = P[i][j]
        if i > 0 and j > 0 and p == 0:
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif i > 0 and (j == 0 or p == 1):
            pairs.append((i - 1, None)); i -= 1
        else:
            pairs.append((None, j - 1)); j -= 1
    pairs.reverse()
    return pairs


def align_song(title):
    key = song_source_key(title)
    if key is None or key not in SRC:
        return None, [('no-source', key)]
    S = SRC[key]
    rows = app_rows(title)
    src_stream = []   # (tok, stanza, line)
    for si, st_lines in enumerate(S['orig_st']):
        for li, line in enumerate(st_lines):
            for t in canon(line):
                src_stream.append((t, si, li))
    app_stream = []   # (tok, app_idx)
    for ai, r in enumerate(rows):
        for t in canon(r['al']):
            app_stream.append((t, ai))
    stoks = [t[0] for t in src_stream]
    atoks = [t[0] for t in app_stream]
    pairs = nw_align(stoks, atoks)
    app_to_src = {}
    matched = 0
    for i, j in pairs:
        if i is not None and j is not None:
            matched += 1
            app_to_src.setdefault(app_stream[j][1], []).append(src_stream[i])
    coverage = matched / max(1, min(len(stoks), len(atoks)))
    mapping = []
    problems = []
    for ai, r in enumerate(rows):
        hits = app_to_src.get(ai, [])
        stanzas = sorted({h[1] for h in hits})
        if not hits:
            mapping.append(dict(app=ai, stanza=None, lines=[]))
            problems.append(('unmapped', r['al']))
        else:
            mapping.append(dict(app=ai, stanza=stanzas[0] if len(stanzas) == 1 else None,
                                stanzas=stanzas, lines=sorted({(h[1], h[2]) for h in hits})))
            if len(stanzas) > 1:
                problems.append(('spans-stanzas', r['al'], stanzas))
    if coverage < 0.9:
        problems.append(('low-coverage', round(coverage, 3), len(stoks), len(atoks)))
    return dict(key=key, rows=rows, mapping=mapping, coverage=coverage,
                nsrc=len(stoks), napp=len(atoks), pairs=pairs,
                src_stream=src_stream, app_stream=app_stream), problems


def diag():
    ok = 0; bad = []
    covs = []
    for title in sorted(ALIGN):
        res, prob = align_song(title)
        if res:
            covs.append((res['coverage'], title))
        if prob:
            bad.append((title, prob))
        else:
            ok += 1
    print('clean songs: %d / %d' % (ok, len(ALIGN)))
    for title, prob in bad:
        print('###', title)
        for p in prob[:6]:
            print('   ', str(p)[:160])
    print()
    print('lowest coverage songs:')
    for cov, title in sorted(covs)[:15]:
        print('   %.3f  %s' % (cov, title))


if __name__ == '__main__':
    diag()
