# -*- coding: utf-8 -*-
import io, sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect('app/src/main/assets/translated.db'); c.row_factory = sqlite3.Row
cur = c.cursor()
for title in ['FEHLT', 'Friend']:
    album = cur.execute("select Album from songs where title=?", (title,)).fetchone()['Album']
    print('=' * 80); print('###', title)
    cur.execute(
        "SELECT sa.alician_sentence, sa.chinese_translation, st.english, st.japanese "
        "FROM sentence_alignments sa LEFT JOIN song_translations st "
        "ON st.song_title = sa.song_title AND st.sentence = sa.alician_sentence "
        "WHERE sa.song_title = ? AND sa.album = ? AND TRIM(sa.alician_sentence) <> '' "
        "ORDER BY sa.song_sentence_order", (title, album))
    for al, zh, en, ja in cur.fetchall():
        print('%-52s | %s' % (al[:52], (ja or '').replace('\n', ' / ')[:44]))
