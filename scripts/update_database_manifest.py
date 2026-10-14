# -*- coding: utf-8 -*-
"""Add/refresh the database_metadata marker in the bundled Lite database."""
from __future__ import annotations
import io, sys, sqlite3, hashlib, json, datetime
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

DB = Path('app/src/main/assets/translated.db')
MANIFEST = Path('database-manifest.json')
RAW_URL = ('https://raw.githubusercontent.com/Meartraep/AlicianDictionaryMobile/'
           'main/app/src/main/assets/translated.db')

def read_version(conn) -> int:
    try:
        row = conn.execute("select value from database_metadata where key='db_version'").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0

def main(bump: bool, notes: str, published_at: str) -> None:
    conn = sqlite3.connect(DB)
    current = read_version(conn)
    version = current + 1 if (bump or current == 0) else current
    conn.execute("create table if not exists database_metadata (key text primary key, value text not null)")
    rows = {
        'db_version': str(version),
        'published_at': published_at,
        'notes': notes,
        'format': 'alician-lite',
    }
    for key, value in rows.items():
        conn.execute("insert into database_metadata(key, value) values(?, ?) "
                     "on conflict(key) do update set value=excluded.value", (key, value))
    conn.commit()
    conn.close()

    data = DB.read_bytes()
    manifest = {
        'db_version': version,
        'published_at': published_at,
        'notes': notes,
        'format': 'alician-lite',
        'size': len(data),
        'sha1': hashlib.sha1(data).hexdigest(),
        'url': RAW_URL,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('db_version = %d (was %d)' % (version, current))
    print('size=%d sha1=%s' % (len(data), manifest['sha1']))
    print('manifest ->', MANIFEST)

if __name__ == '__main__':
    main(bump='--bump' in sys.argv,
         notes='官方日/英译逐句对齐：修复同一段落 A/B 两句互相包含整段译文的问题',
         published_at=datetime.date.today().isoformat())
