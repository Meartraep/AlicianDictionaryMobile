# -*- coding: utf-8 -*-
"""List every run containing a span participant (sentence whose own stanza is a neighbour)."""
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from map_v4 import build, runs_of
from align_engine import ALIGN
NEW = json.load(open('scripts/realign/newpos.json', encoding='utf-8'))
for title in sorted(ALIGN):
    b = build(title)
    if b is None: continue
    S = b['S']
    runs = runs_of(b)
    for si in sorted(runs):
        for run in runs[si]:
            if len(run) < 2: continue
            spans = [a for a in run if b['assign'][a] != si]
            if not spans:
                continue
            print('### %s S%02d run=%s spans=%s' % (title, si, run, [(a, b['assign'][a]) for a in spans]))
            print('    EN block: %s' % ' // '.join(S['en_st'][si] if si < len(S['en_st']) else [])[:110])
            print('    JA block: %s' % ' // '.join(S['ja_st'][si] if si < len(S['ja_st']) else [])[:110])
            for a in run:
                n = NEW.get('%s|||%d' % (title, a), {})
                print('      [%2d] %-44s -> E=%-40s J=%s' % (a, b['rows'][a]['al'][:44],
                      (n.get('en','') or '').replace('\n',' / ')[:40], (n.get('ja','') or '').replace('\n',' / ')[:40]))
