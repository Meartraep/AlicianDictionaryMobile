# -*- coding: utf-8 -*-
"""Write per-batch stanza listings for independent EN-vs-JA review."""
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from source_fix import all_songs
from common import REPO_TO_APP
S = all_songs()
songs = sorted([k for k in S if S[k]['ja_st']], key=lambda k: -len(S[k]['orig_st']))
batches = [[] for _ in range(4)]
load = [0] * 4
for k in songs:
    n = len(S[k]['orig_st'])
    i = load.index(min(load))
    batches[i].append(k); load[i] += n
for i, b in enumerate(batches):
    out = []
    for k in b:
        app = REPO_TO_APP.get(k, k)
        out.append('=' * 90)
        out.append('### SONG %s   (app title: %s)   stanzas=%d' % (k, app, len(S[k]['orig_st'])))
        for si in range(len(S[k]['orig_st'])):
            out.append('S%02d ORIG: %s' % (si, ' | '.join(S[k]['orig_st'][si])))
            en = S[k]['en_st'][si] if si < len(S[k]['en_st']) else []
            ja = S[k]['ja_st'][si] if si < len(S[k]['ja_st']) else []
            out.append('    EN  : %s' % (' // '.join(en) if en else '<none>'))
            out.append('    JA  : %s' % (' // '.join(ja) if ja else '<none>'))
        out.append('')
    Path('scripts/realign/batch_%d.txt' % (i + 1)).write_text('\n'.join(out), encoding='utf-8')
    print('batch %d: %d songs, %d stanzas -> scripts/realign/batch_%d.txt' % (i + 1, len(b), load[i], i + 1))
    print('   ', ', '.join(b))
