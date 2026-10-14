# -*- coding: utf-8 -*-
"""Verify the corrected translations are packaged inside the debug APK."""
import io, sys, zipfile, sqlite3, hashlib
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
apk = Path('app/build/outputs/apk/debug/app-debug.apk')
print('APK:', apk.name, apk.stat().st_size, 'bytes')
zf = zipfile.ZipFile(apk)
names = [n for n in zf.namelist() if n.endswith('translated.db')]
print('db entries in APK:', names)
data = zf.read('assets/translated.db')
out = Path('.tmp-verify/translated.db'); out.parent.mkdir(exist_ok=True); out.write_bytes(data)
print('extracted db md5:', hashlib.md5(data).hexdigest())
src = Path('app/src/main/assets/translated.db').read_bytes()
print('source   db md5:', hashlib.md5(src).hexdigest())
print('identical:', hashlib.md5(data).hexdigest() == hashlib.md5(src).hexdigest())
c = sqlite3.connect(out); c.row_factory = sqlite3.Row
cur = c.cursor()
for sent in ['Olis Leste Stea Shelista', 'Ilis Leste Stea Xia Scape ah', 'Fiiani end', 'ah Leste Liz']:
    r = cur.execute("select english, japanese from song_translations where song_title='Wonder World Sketch' and sentence=?", (sent,)).fetchone()
    print('%-30s EN=%-40s JA=%s' % (sent, r['english'].replace('\n',' / '), r['japanese'].replace('\n',' / ')))
print('duplicate adjacent blocks (display join):')
cur.execute("select count(*) from sentence_alignments")
print('  align rows:', cur.fetchone()[0])
