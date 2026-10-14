# -*- coding: utf-8 -*-
"""Master table: app sentence -> current DB row/block + content-based stanza match."""
from __future__ import annotations
import io, sys, json, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, canon, norm
from map_v2 import build, coverage
from align_engine import ALIGN, SRC

E = load_extract()
STROWS = E['st']

def master(title):
    b = build(title)
    if b is None:
        return None
    S = b['S']; rows = b['rows']
    dbrows = {r['sentence']: r for r in STROWS.get(title, [])}
    out = []
    for ai, r in enumerate(rows):
        d = b['diag'][ai]
        db = dbrows.get(r['al'])
        out.append(dict(ai=ai, order=r['order'], al=r['al'], zh=r['zh'],
                        db_id=(db['id'] if db else None),
                        db_en=(db['en'] if db else None), db_ja=(db['ja'] if db else None),
                        chosen=d['chosen'], cov=d['cov'], bestscore=d['bestscore'], nw=d['nw']))
    return b, out

if __name__ == '__main__':
    # Consistency: does the block text equal the source block of the assigned stanza?
    bad = []
    for title in sorted(ALIGN):
        m = master(title)
        if m is None:
            continue
        b, out = m
        S = b['S']
        seen = set()
        for rec in out:
            if rec['db_en'] is None and rec['db_ja'] is None:
                continue
            key = (rec['db_en'], rec['db_ja'])
            if key in seen:
                continue
            seen.add(key)
            si = rec['chosen']
            en = '\n'.join(S['en_st'][si]) if si is not None and si < len(S['en_st']) else ''
            ja = '\n'.join(S['ja_st'][si]) if si is not None and si < len(S['ja_st']) else ''
            if norm(en) != norm(rec['db_en'] or '') or norm(ja) != norm(rec['db_ja'] or ''):
                bad.append((title, rec['al'][:50], si, rec['db_en'] or '', en, rec['db_ja'] or '', ja))
    print('blocks whose text differs from the content-matched source stanza: %d' % len(bad))
    for t, al, si, den, sen, dja, sja in bad[:60]:
        print(' * %s | %s | chosen S%s' % (t[:38], al, si))
        print('     DB EN: %s' % den.replace(chr(10), ' // ')[:100])
        print('     SRC EN: %s' % sen.replace(chr(10), ' // ')[:100])
        if norm(dja) != norm(sja):
            print('     DB JA: %s' % dja.replace(chr(10), ' // ')[:100])
            print('     SRC JA: %s' % sja.replace(chr(10), ' // ')[:100])
