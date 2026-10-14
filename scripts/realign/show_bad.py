# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import align_song, ALIGN, STROWS, SRC

BAD = ['A Little Servant','ALQ','Apocalypse','Chocolate Missile','Doppelgängers','End of Mythology',
       'FEHLT','Forbidden Wonderland short ver','Give Me a Nightmare','KILLED BY ANGEL',
       'Life in a Plastic Bag','Lost My Savepoint','Maharajah','Sno (_ _) oze & Sn (o_o) ze',
       'Teardrop del Ray','The White Land','Thirty Million Persona','Urxbxrxs','i am always wrong',
       '▷ NEW GAME','バッドエンド·シンドローム(Bad End Syndrome)',
       'フライブルクとエンドロウル(Flyburg and the Endroll)','地平線のアクアツォーネ','空想モダニズム -Alice Schach remix-']
for title in BAD:
    res, prob = align_song(title)
    if res is None:
        print('###', title, '-> no source'); continue
    key = res['key']; S = SRC[key]
    print('=' * 100)
    print('###', title, '(src=%s)' % key)
    # print source stanzas numbered
    for si, st in enumerate(S['orig_st']):
        print('   S%02d %s' % (si, ' | '.join(st)[:150]))
    print('   --- app sentences ---')
    rows = res['rows']
    m = res['mapping']
    for ai, r in enumerate(rows):
        mm = m[ai]
        st = mm.get('stanza')
        tag = 'S%02d' % st if st is not None else ('SPAN%s' % mm.get('stanzas'))
        print('   %3d %-6s AL=%s' % (ai, tag, r['al'][:70]))
