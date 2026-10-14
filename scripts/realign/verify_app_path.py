# -*- coding: utf-8 -*-
"""Verify through the app's own query path (dictionary_core.find_song_alignments)."""
import io, sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'app/src/main/python')
import os
os.environ.setdefault('ALICIAN_DB', 'app/src/main/assets/translated.db')
c = sqlite3.connect('app/src/main/assets/translated.db'); c.row_factory = sqlite3.Row
cur = c.cursor()
def find_song_alignments(title, album):
    cur.execute(
        "SELECT sa.alician_sentence, sa.chinese_translation, st.english, st.japanese, st.korean "
        "FROM sentence_alignments sa LEFT JOIN song_translations st "
        "ON st.song_title = sa.song_title AND st.sentence = sa.alician_sentence "
        "WHERE sa.song_title = ? AND sa.album = ? AND TRIM(sa.alician_sentence) <> '' "
        "ORDER BY sa.song_sentence_order", (title.strip(), album.strip()))
    return [(r[0], r[1] or '', r[2] or '', r[3] or '', r[4] or '') for r in cur.fetchall()]
row = c.execute("select album from songs where title='Wonder World Sketch'").fetchone()
for al, zh, en, ja, ko in find_song_alignments('Wonder World Sketch', row['album']):
    print('AL: %s\n  ZH: %s\n  EN: %s\n  JA: %s' % (al, zh, en.replace('\n', ' / '), ja.replace('\n', ' / ')))
print()
# empty rows check
cur.execute("select count(*) from song_translations where trim(english)='' and trim(japanese)=''")
print('rows with no text at all:', cur.fetchone()[0])
cur.execute("select song_title, sentence from song_translations where trim(english)='' and trim(japanese)=''")
for r in cur.fetchall():
    print('   ', r[0], '|', r[1])
