# -*- coding: utf-8 -*-
import io, sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
new = sqlite3.connect('app/src/main/assets/translated.db'); new.row_factory = sqlite3.Row
cur = new.cursor()
for title, album in [(r['title'], r['Album']) for r in cur.execute("select title, Album from songs")]:
    cur.execute("SELECT sa.alician_sentence, st.english, st.japanese FROM sentence_alignments sa "
                "LEFT JOIN song_translations st ON st.song_title = sa.song_title AND st.sentence = sa.alician_sentence "
                "WHERE sa.song_title=? AND sa.album=? AND TRIM(sa.alician_sentence) <> '' ORDER BY sa.song_sentence_order", (title, album))
    rs = cur.fetchall(); i = 0
    while i < len(rs):
        j = i
        while (j + 1 < len(rs) and rs[j + 1][1] and rs[j + 1][1] == rs[i][1] and rs[j + 1][2] == rs[i][2]):
            j += 1
        if j > i:
            print('%s' % title)
            for k in range(i, j + 1):
                print('    %-52s | %s' % (rs[k][0][:52], (rs[k][1] or '')[:44]))
        i = j + 1
