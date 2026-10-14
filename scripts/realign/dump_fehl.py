# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, song_source_key
from align_engine import ALIGN, SRC
E = load_extract()
def dump(title, src_key):
    S = SRC[src_key]
    print('=' * 100)
    print('### APP:', title)
    for r in sorted(ALIGN[title], key=lambda r: (r['order'] is None, r['order'] or 0)):
        print('  app order=%-3s AL=%-62s ZH=%s' % (r['order'], r['al'][:62], r['zh'][:40]))
    print('--- SOURCE stanzas (%s) ---' % src_key)
    for i, st in enumerate(S['orig_st']):
        en = S['en_st'][i] if i < len(S['en_st']) else []
        ja = S['ja_st'][i] if i < len(S['ja_st']) else []
        print('  S%02d ORIG %s' % (i, ' | '.join(st)[:110]))
        print('       EN %s' % ' // '.join(en)[:110])
        print('       JA %s' % ' // '.join(ja)[:110])
dump('FEHLT', 'Fehlt')
