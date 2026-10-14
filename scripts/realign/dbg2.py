# -*- coding: utf-8 -*-
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract
from map_v4 import build
E = load_extract(); STROWS = E['st']
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))
title = 'ALQ'
b = build(title); rows = b['rows']
db = {}
for r in STROWS.get(title, []):
    db.setdefault(r['sentence'], r)
for ai, r in enumerate(rows):
    new = NEW.get('%s|||%d' % (title, ai), {})
    old = db.get(r['al'])
    print('[%2d] %-42s old=%s new_en=%-28s new_ja=%s' % (ai, r['al'][:42],
        ('row' if old else 'NONE'), (new.get('en') or '')[:28], (new.get('ja') or '')[:30]))
