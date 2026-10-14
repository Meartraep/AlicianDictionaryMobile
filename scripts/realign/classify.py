# -*- coding: utf-8 -*-
"""Classify units: clean (line counts == K) vs manual; emit defaults for clean ones."""
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import ALIGN
units = json.load(open('scripts/realign/units.json', encoding='utf-8'))
order = {t: i for i, t in enumerate(ALIGN)}
units.sort(key=lambda u: (order.get(u['song'], 999), u['stanza']))
clean, manual = [], []
for u in units:
    k = u['n']
    en_lines = [len(x.split()) for x in u['en'] if x.strip()]
    ja_lines = [len(x.split()) for x in u['ja'] if x.strip()]
    u['en_lines'] = en_lines; u['ja_lines'] = ja_lines
    en_ok = (not en_lines) or len(en_lines) == k
    ja_ok = len(ja_lines) == k
    if en_ok and ja_ok:
        clean.append(u)
    else:
        manual.append(u)
print('CLEAN units (line split == K): %d' % len(clean))
print('MANUAL units: %d' % len(manual))
print()
for u in clean:
    print('  %-44s S%02d K=%d en=%s ja=%s' % (u['song'][:44], u['stanza'], u['n'], u['en_lines'], u['ja_lines']))
json.dump(clean, open('scripts/realign/units_clean.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(manual, open('scripts/realign/units_manual.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
