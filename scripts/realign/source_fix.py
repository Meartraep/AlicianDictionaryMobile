# -*- coding: utf-8 -*-
"""Normalised source layer: applies verified fixes to the alicianlabs stanza lists."""
from __future__ import annotations
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import load_extract, norm

E = load_extract()
SRC = E['src']

def fixed_song(key):
    """Return dict(orig_st, en_st, ja_st) with known source defects corrected.

    Fixes (verified against Alician original + official Japanese):
      Alice_Music : english_lyrics has one extra stanza break at "Turning the hands
                    of clock..." -> every stanza from 15 on was off by one.
      killed_by_angel : english_lyrics lines 3/4 (index 2/3) are swapped relative
                    to the Japanese and the Alician.
    """
    v = SRC[key]
    en = [list(x) for x in v['en_st']]
    if key == 'Alice_Music':
        en = en[:14] + [[en[14][0], en[15][0]]] + en[16:22] + [[]] + en[22:]
    if key == 'killed_by_angel':
        en[2], en[3] = en[3], en[2]
    if key == 'Wanderers':
        # english_lyrics re-splits one sentence across stanzas 21-23:
        #   S21 "The reason for the world," / S22 "a little light wakes up its eyes"
        #   S23 "Let's recite a spell with a sooty body to blacken our preodained destiny"
        # Restored to the Japanese/Alician stanza boundaries.
        en[21] = ['The reason for the world, a little light wakes up its eyes']
        en[22] = ["Let's recite a spell with a sooty body"]
        en[23] = ['to blacken our preodained destiny']
    bad = ('<br>', '<br/>', '<br />')

    def clean(stanzas):
        return [[' '.join(t for t in line.split() if t not in bad) for line in stanza]
                for stanza in stanzas]
    return dict(orig_st=clean([list(x) for x in v['orig_st']]), en_st=clean(en),
                ja_st=clean([list(x) for x in v['ja_st']]))

def all_songs():
    return {k: fixed_song(k) for k in SRC}

if __name__ == '__main__':
    S = fixed_song('Alice_Music')
    for i in range(12, 25):
        print('S%02d | ORIG %s' % (i, ' '.join(S['orig_st'][i])[:60]))
        print('     EN %s' % ' // '.join(S['en_st'][i])[:90])
        print('     JA %s' % ' // '.join(S['ja_st'][i])[:90])
