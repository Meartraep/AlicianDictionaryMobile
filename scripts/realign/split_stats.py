# -*- coding: utf-8 -*-
"""Statistics: how many stanzas need a split and how mechanical it is."""
import io, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from build_map import stanza_groups
from align_engine import ALIGN, SRC

def lines_of(block):
    return [x for x in (block or '').split('\n') if x.strip()]

stat = collections.Counter()
detail = []
for title in sorted(ALIGN):
    g, prob = stanza_groups(title)
    if g is None: continue
    res = g['res']; S = SRC[res['key']]
    for si, items in sorted([kv for kv in g['groups'].items() if kv[0] is not None]):
        if si is None: continue
        n = len(items)
        en = S['en_st'][si] if si < len(S['en_st']) else []
        ja = S['ja_st'][si] if si < len(S['ja_st']) else []
        for i in range(len(en)):
            en[i] = ' '.join(x for x in en[i].split('\n'))
        le, lj = len(en), len(ja)
        key = ('N>=2' if n >= 2 else 'N==1',
               'en=%s' % ('ok' if le == n else ('none' if le == 0 else 'diff')),
               'ja=%s' % ('ok' if lj == n else ('none' if lj == 0 else 'diff')))
        stat[key] += 1
        if n >= 2:
            detail.append((title, si, n, le, lj, en, ja, [it['al'] for it in items]))
for k, v in sorted(stat.items()):
    print('%-6s %-6s %-6s -> %d stanzas' % (k[0], k[1], k[2], v))
print()
need_manual = [d for d in detail if not (d[3] == d[2] and d[4] == d[2])]
print('stanzas with N>=2: %d ; of which mechanical-clean both: %d ; needing judgment: %d'
      % (len(detail), len(detail) - len(need_manual), len(need_manual)))
import json
Path('scripts/realign/split_needed.json').write_text(json.dumps(
    [dict(song=t, stanza=si, n=n, le=le, lj=lj, en=en, ja=ja, app=apps) for t, si, n, le, lj, en, ja, apps in need_manual],
    ensure_ascii=False, indent=1), encoding='utf-8')
Path('scripts/realign/all_groups.json').write_text(json.dumps(
    [dict(song=t, stanza=si, n=n, le=le, lj=lj, en=en, ja=ja, app=apps) for t, si, n, le, lj, en, ja, apps in detail],
    ensure_ascii=False, indent=1), encoding='utf-8')
print()
for t, si, n, le, lj, en, ja, apps in need_manual:
    print('%-38s S%02d N=%d en=%d ja=%d' % (t[:38], si, n, le, lj))
    print('     EN: %s' % ' // '.join(en)[:170])
    print('     JA: %s' % ' // '.join(ja)[:170])
