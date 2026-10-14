# -*- coding: utf-8 -*-
"""Detailed dump of uncertain app->stanza assignments."""
import io, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from build_map import stanza_votes
from align_engine import ALIGN, SRC

CASES = [
 ('A Little Servant', 7), ('ALQ', 19), ('Apocalypse', 9), ('Apocalypse', 18),
 ('FEHLT', 2), ('FEHLT', 19), ('FEHLT', 20), ('Give Me a Nightmare', 2),
 ('KILLED BY ANGEL', 14), ('Life in a Plastic Bag', 8), ('Life in a Plastic Bag', 15),
 ('Maharajah', 11), ('Teardrop del Ray', 1), ('Teardrop del Ray', 11), ('Teardrop del Ray', 12),
 ('Thirty Million Persona', 6), ('Thirty Million Persona', 14), ('Urxbxrxs', 1), ('Urxbxrxs', 4),
 ('Urxbxrxs', 14), ('Urxbxrxs', 17),
 ('フライブルクとエンドロウル(Flyburg and the Endroll)', 8),
 ('フライブルクとエンドロウル(Flyburg and the Endroll)', 10),
 ('フライブルクとエンドロウル(Flyburg and the Endroll)', 15),
 ('フライブルクとエンドロウル(Flyburg and the Endroll)', 17),
]
for title, ai in CASES:
    sv, prob = stanza_votes(title)
    res = sv['res']; S = SRC[res['key']]
    item = sv['votes'][ai]
    print('=' * 100)
    print('### %s  app[%d] AL=%s' % (title, ai, item['al']))
    r = [x for x in ALIGN[title] if x['order'] == res['rows'][ai]['order']][0]
    print('     ZH=%s   votes=%s' % (r['zh'], item['votes']))
    # show matched token positions: first and last
    pairs = res['pairs']; src_stream, app_stream = res['src_stream'], res['app_stream']
    hits = [(i, src_stream[i]) for i, j in pairs if j is not None and app_stream[j][1] == ai and i is not None]
    if hits:
        print('     first hit: S%02d L%d %r' % (hits[0][1][1], hits[0][1][2], hits[0][1][0]))
        print('     last  hit: S%02d L%d %r' % (hits[-1][1][1], hits[-1][1][2], hits[-1][1][0]))
        sis = sorted({h[1][1] for h in hits})
        for si in sis:
            print('        S%02d orig: %s' % (si, ' | '.join(S['orig_st'][si])[:150]))
            en = S['en_st'][si] if si < len(S['en_st']) else []
            ja = S['ja_st'][si] if si < len(S['ja_st']) else []
            print('           EN: %s' % ' // '.join(en)[:140])
            print('           JA: %s' % ' // '.join(ja)[:140])
    # neighbouring app sentences
    for k in range(max(0, ai - 1), min(len(sv['votes']), ai + 2)):
        it = sv['votes'][k]
        rr = [x for x in ALIGN[title] if x['order'] == res['rows'][k]['order']][0]
        print('     %s app%-3d %-55s ZH=%s' % ('>>' if k == ai else '  ', k, it['al'][:55], rr['zh'][:60]))
