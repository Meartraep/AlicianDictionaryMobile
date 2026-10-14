# -*- coding: utf-8 -*-
"""Build app-sentence -> source-stanza mapping with per-token votes + review report."""
from __future__ import annotations
import io, sys, json, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, canon, norm, song_source_key
from align_engine import align_song, ALIGN, STROWS, SRC

E = load_extract()


def stanza_votes(title):
    """Return list per app sentence: dict(stanza, votes=Counter, uncertain=bool)."""
    res, prob = align_song(title)
    if res is None:
        return None, prob
    pairs = res['pairs']
    src_stream, app_stream = res['src_stream'], res['app_stream']
    votes = collections.defaultdict(collections.Counter)
    total = collections.Counter()
    unmatched = collections.Counter()
    for i, j in pairs:
        if j is None:
            continue
        ai = app_stream[j][1]
        total[ai] += 1
        if i is not None:
            votes[ai][src_stream[i][1]] += 1
        else:
            unmatched[ai] += 1
    out = []
    for ai, row in enumerate(res['rows']):
        v = votes.get(ai, collections.Counter())
        n_un = unmatched.get(ai, 0)
        if not v:
            out.append(dict(app=ai, al=row['al'], stanza=None, votes={}, unmatched=n_un, uncertain=True))
            continue
        ranked = v.most_common()
        best, bestn = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0
        uncertain = second > 0 and second >= max(1, 0.25 * sum(v.values()))
        out.append(dict(app=ai, al=row['al'], stanza=best, votes=dict(v), unmatched=n_un, uncertain=uncertain))
    return dict(res=res, votes=out), prob


def stanza_groups(title):
    sv, prob = stanza_votes(title)
    if sv is None:
        return None, prob
    groups = collections.OrderedDict()
    for item in sv['votes']:
        groups.setdefault(item['stanza'], []).append(item)
    return dict(sv=sv, groups=groups, res=sv['res']), prob


def main():
    lines = []
    uncertain_rows = []
    unmapped_rows = []
    for title in sorted(ALIGN):
        g, prob = stanza_groups(title)
        if g is None:
            lines.append('## %s -- NO SOURCE' % title); continue
        res = g['res']; S = SRC[res['key']]
        lines.append('# %s   [src=%s]' % (title, res['key']))
        for si in sorted([k for k in g['groups'] if k is not None]):
            items = g['groups'][si]
            st = S['orig_st'][si]
            en = S['en_st'][si] if si < len(S['en_st']) else []
            ja = S['ja_st'][si] if si < len(S['ja_st']) else []
            lines.append('  S%02d orig: %s' % (si, ' | '.join(st)))
            lines.append('      EN(%d): %s' % (len(en), ' // '.join(en)))
            lines.append('      JA(%d): %s' % (len(ja), ' // '.join(ja)))
            for it in items:
                row = next(r for r in ALIGN[title] if r['order'] == res['rows'][it['app']]['order'])
                lines.append('      -> [%d] AL=%s' % (it['app'], it['al']))
                lines.append('             ZH=%s' % row['zh'])
                if it['uncertain']:
                    uncertain_rows.append((title, it['app'], it['al'], it['votes'], it['unmatched']))
        for it in g['sv']['votes']:
            if it['stanza'] is None:
                unmapped_rows.append((title, it['app'], it['al']))
        lines.append('')
    Path('scripts/realign/review_stanzas.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('wrote review_stanzas.txt lines=%d' % len(lines))
    print()
    print('UNCERTAIN stanza assignments: %d' % len(uncertain_rows))
    for t, ai, al, v, un in uncertain_rows:
        print('   %-40s [%3d] %-60s votes=%s un=%d' % (t[:40], ai, al[:58], v, un))
    print()
    print('UNMAPPED app sentences (no source tokens): %d' % len(unmapped_rows))
    for t, ai, al in unmapped_rows:
        print('   %-40s [%3d] %r' % (t[:40], ai, al))


if __name__ == '__main__':
    main()
