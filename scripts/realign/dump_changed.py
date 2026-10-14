# -*- coding: utf-8 -*-
"""Dump every changed row for proofreading."""
from __future__ import annotations
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, norm
from map_v4 import build
from align_engine import ALIGN
E = load_extract(); STROWS = E['st']
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))
out = []
for title in sorted(ALIGN):
    b = build(title)
    if b is None:
        continue
    dbrows = {}
    for r in STROWS.get(title, []):
        dbrows.setdefault(r['sentence'], r)
    block = []
    for ai, r in enumerate(b['rows']):
        if not r['al'].strip():
            continue
        new = NEW.get('%s|||%d' % (title, ai), {})
        old = dbrows.get(r['al'])
        oen = (old['en'] if old else '') or ''
        oja = (old['ja'] if old else '') or ''
        nen = new.get('en', ''); nja = new.get('ja', '')
        if norm(oen) == norm(nen) and norm(oja) == norm(nja):
            continue
        block.append('  [%2d] AL: %s\n       ZH: %s\n     OLD : %s | %s\n     NEW : %s | %s' % (
            ai, r['al'], r['zh'], oen.replace('\n', ' / '), oja.replace('\n', ' / '),
            nen.replace('\n', ' / '), nja.replace('\n', ' / ')))
    if block:
        out.append('=' * 100)
        out.append('### %s   (%d changed rows)' % (title, len(block)))
        out.extend(block)
Path('scripts/realign/changed_rows.txt').write_text('\n'.join(out), encoding='utf-8')
print('changed row lines:', len(out))
