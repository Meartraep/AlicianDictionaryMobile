# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build, runs_of
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))
for title in ['Lost My Savepoint']:
    b = build(title); S = b['S']
    for s in sorted(runs_of(b)):
        print('  S%02d %-50s | %-40s runs=%s' % (s, ' '.join(S['orig_st'][s])[:50], (' // '.join(S['ja_st'][s]) if s < len(S['ja_st']) else '')[:40], runs_of(b)[s]))
    print()
    db = {}
    import sqlite3
    c = sqlite3.connect('app/src/main/assets/translated.db'); c.row_factory = sqlite3.Row
    for r in c.execute("select * from song_translations where song_title=?", (title,)):
        db[r['sentence']] = r
    for ai, r in enumerate(b['rows']):
        n = NEW.get('%s|||%d' % (title, ai), {})
        row = db.get(r['al'])
        print('[%2d] %-46s -> S%-3s | DB E=%-40s J=%-30s | NEW E=%-36s J=%s' % (
            ai, r['al'][:46], b['assign'][ai], ((row['english'] if row else '') or '')[:40], ((row['japanese'] if row else '') or '')[:30],
            (n.get('en','') or '')[:36].replace('\n',' / '), (n.get('ja','') or '')[:30].replace('\n',' / ')))
