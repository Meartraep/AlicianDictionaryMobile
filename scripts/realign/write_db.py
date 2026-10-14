# -*- coding: utf-8 -*-
"""Write the corrected per-sentence official translations into translated.db."""
from __future__ import annotations
import io, sys, json, sqlite3, shutil, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, norm
from map_v4 import build
from align_engine import ALIGN

DB = Path('app/src/main/assets/translated.db')
E = load_extract(); STROWS = E['st']
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))

def main(apply=False):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    updates, inserts, skipped = [], [], []
    for title in sorted(ALIGN):
        b = build(title)
        if b is None:
            skipped.append(title); continue
        cur.execute("SELECT id, sentence, english, japanese, korean FROM song_translations WHERE song_title=?", (title,))
        existing = {}
        for r in cur.fetchall():
            existing.setdefault(r['sentence'], r)
        seen = {}
        for ai, row in enumerate(b['rows']):
            sent = row['al']
            if not sent.strip():
                continue
            new = NEW.get('%s|||%d' % (title, ai), {})
            # first occurrence wins for repeated sentences
            if sent not in seen:
                seen[sent] = new
        for sent, new in seen.items():
            en = new.get('en', ''); ja = new.get('ja', '')
            old = existing.get(sent)
            if old is None:
                if en.strip() or ja.strip():
                    inserts.append((title, sent, en, ja))
            elif norm(old['english'] or '') != norm(en) or norm(old['japanese'] or '') != norm(ja):
                updates.append((old['id'], title, sent, en, ja, old['english'], old['japanese']))
    print('rows to update: %d ; to insert: %d ; songs skipped (no source): %s' % (len(updates), len(inserts), skipped))
    for u in updates[:3]:
        print('   upd id=%s %s' % (u[0], u[2][:40]))
    for i in inserts:
        print('   ins %s | %s' % (i[0][:30], i[1][:40]))
    if not apply:
        print('(dry run)')
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = DB.with_suffix('.db.bak-%s' % stamp)
    shutil.copy2(DB, backup)
    print('backup:', backup)
    for uid, title, sent, en, ja, oe, oj in updates:
        cur.execute("UPDATE song_translations SET english=?, japanese=? WHERE id=?", (en, ja, uid))
    for title, sent, en, ja in inserts:
        cur.execute("INSERT OR IGNORE INTO song_translations (song_title, sentence, english, japanese, korean) VALUES (?,?,?,?, '')",
                    (title, sent, en, ja))
    conn.commit()
    print('updated %d rows, inserted %d rows' % (len(updates), len(inserts)))
    conn.close()

if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
