# -*- coding: utf-8 -*-
"""Final before/after diff against the pre-change backup."""
import io, sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
old = sqlite3.connect('backups/translated.db.bak-20261014-004022'); old.row_factory = sqlite3.Row
new = sqlite3.connect('app/src/main/assets/translated.db'); new.row_factory = sqlite3.Row
o = {(r['song_title'], r['sentence']): (r['english'], r['japanese']) for r in old.execute("select * from song_translations")}
n = {(r['song_title'], r['sentence']): (r['english'], r['japanese']) for r in new.execute("select * from song_translations")}
ch_en = ch_ja = both = 0
for k, (en, ja) in n.items():
    if k not in o:
        continue
    oe, oj = o[k]
    if (oe or '').strip() != (en or '').strip(): ch_en += 1
    if (oj or '').strip() != (ja or '').strip(): ch_ja += 1
    if (oe or '').strip() != (en or '').strip() or (oj or '').strip() != (ja or '').strip(): both += 1
print('rows before: %d ; after: %d ; added: %d' % (len(o), len(n), len(n) - len(o)))
print('english changed: %d ; japanese changed: %d ; any changed: %d' % (ch_en, ch_ja, both))
# duplication before/after, measured on the display join
def dup_count(conn):
    cur = conn.cursor(); groups = 0; rows = 0
    songs = [(r['title'], r['Album']) for r in cur.execute("select title, Album from songs")]
    for title, album in songs:
        cur.execute("SELECT sa.alician_sentence, st.english, st.japanese FROM sentence_alignments sa "
                    "LEFT JOIN song_translations st ON st.song_title = sa.song_title AND st.sentence = sa.alician_sentence "
                    "WHERE sa.song_title=? AND sa.album=? AND TRIM(sa.alician_sentence) <> '' ORDER BY sa.song_sentence_order", (title, album))
        rs = cur.fetchall(); i = 0
        while i < len(rs):
            j = i
            while (j + 1 < len(rs) and rs[j + 1][1] and rs[j + 1][1] == rs[i][1] and rs[j + 1][2] == rs[i][2]):
                j += 1
            if j > i:
                groups += 1; rows += (j - i + 1)
            i = j + 1
    return groups, rows
print('duplicated display blocks before: %s ; after: %s (groups, rows)' % (dup_count(old), dup_count(new)))
