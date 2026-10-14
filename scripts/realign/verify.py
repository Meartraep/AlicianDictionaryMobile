# -*- coding: utf-8 -*-
"""Compare old DB rows with the new per-position assembly."""
from __future__ import annotations
import io, sys, json, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, norm
from map_v4 import build
from align_engine import ALIGN
E = load_extract(); STROWS = E['st']
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))

tot = ch_en = ch_ja = 0
filled_en = filled_ja = 0
empty_before_en = empty_before_ja = 0
dup_pairs = 0
dup_examples = []
for title in sorted(ALIGN):
    b = build(title)
    if b is None:
        continue
    rows = b['rows']
    dbrows = {}
    for r in STROWS.get(title, []):
        dbrows.setdefault(r['sentence'], r)
    prev = None
    for ai, r in enumerate(rows):
        if not r['al'].strip():
            continue
        tot += 1
        new = NEW.get('%s|||%d' % (title, ai), {})
        old = dbrows.get(r['al'])
        oen = (old['en'] if old else '') or ''
        oja = (old['ja'] if old else '') or ''
        nen = new.get('en', ''); nja = new.get('ja', '')
        if not oen.strip() and nen.strip(): empty_before_en += 1
        if not oja.strip() and nja.strip(): empty_before_ja += 1
        if nen.strip(): filled_en += 1
        if nja.strip(): filled_ja += 1
        if norm(oen) != norm(nen): ch_en += 1
        if norm(oja) != norm(nja): ch_ja += 1
        if prev is not None and prev[0] != r['al']:
            if nen and norm(nen) == norm(prev[1]) and nen.strip():
                dup_pairs += 1
                if len(dup_examples) < 12:
                    dup_examples.append((title, prev[0][:40], r['al'][:40], nen[:60]))
        prev = (r['al'], nen, nja)
print('app sentences (non-empty): %d' % tot)
print('rows with EN now: %d ; with JA now: %d' % (filled_en, filled_ja))
print('EN filled where previously empty: %d ; JA filled where previously empty: %d' % (empty_before_en, empty_before_ja))
print('EN changed: %d ; JA changed: %d' % (ch_en, ch_ja))
print('adjacent rows sharing identical EN text (different Alician): %d' % dup_pairs)
for e in dup_examples:
    print('   ', e)
