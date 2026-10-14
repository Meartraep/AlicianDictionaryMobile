# -*- coding: utf-8 -*-
import io, sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect(r'app/src/main/assets/translated.db'); c.row_factory = sqlite3.Row
for title in ['FEHLT', 'Alice Music']:
    r = c.execute("select lyric from songs where title=?", (title,)).fetchone()
    print('=' * 90); print('###', title)
    for i, line in enumerate(r['lyric'].split('\n')):
        if line.strip():
            print('%3d| %s' % (i, line[:100]))
