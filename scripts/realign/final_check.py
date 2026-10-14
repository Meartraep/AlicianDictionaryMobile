# -*- coding: utf-8 -*-
"""Final verification: app query path, duplicate scan, coverage."""
import io, sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect('app/src/main/assets/translated.db'); c.row_factory = sqlite3.Row
cur = c.cursor()
songs = [(r['title'], r['Album']) for r in cur.execute("select title, Album from songs")]
tot = dup_en = dup_ja = 0
filled_en = filled_ja = 0
examples = []
for title, album in songs:
    cur.execute(
        "SELECT sa.alician_sentence, sa.chinese_translation, st.english, st.japanese "
        "FROM sentence_alignments sa LEFT JOIN song_translations st "
        "ON st.song_title = sa.song_title AND st.sentence = sa.alician_sentence "
        "WHERE sa.song_title = ? AND sa.album = ? AND TRIM(sa.alician_sentence) <> '' "
        "ORDER BY sa.song_sentence_order", (title, album))
    prev = None
    for al, zh, en, ja in cur.fetchall():
        en = (en or '').strip(); ja = (ja or '').strip()
        tot += 1
        if en: filled_en += 1
        if ja: filled_ja += 1
        if prev and prev[0] != al:
            if en and en == prev[1]:
                dup_en += 1
                if len(examples) < 10: examples.append((title, prev[0][:30], al[:30], 'EN', en[:40]))
            if ja and ja == prev[2]:
                dup_ja += 1
                if len(examples) < 10: examples.append((title, prev[0][:30], al[:30], 'JA', ja[:40]))
        prev = (al, en, ja)
print('displayed lines: %d ; with EN: %d ; with JA: %d' % (tot, filled_en, filled_ja))
print('adjacent lines sharing identical EN (different Alician): %d' % dup_en)
print('adjacent lines sharing identical JA (different Alician): %d' % dup_ja)
for e in examples:
    print('   ', e)
