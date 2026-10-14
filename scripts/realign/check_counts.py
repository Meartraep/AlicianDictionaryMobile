# -*- coding: utf-8 -*-
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from align_engine import SRC
from common import REPO_TO_APP
print('%-34s %5s %5s %5s' % ('source', 'orig', 'en', 'ja'))
bad = []
for k, v in sorted(SRC.items()):
    o, e, j = len(v['orig_st']), len(v['en_st']), len(v['ja_st'])
    tag = ''
    if not (o == e == j):
        tag = '   <-- MISMATCH'
        bad.append(k)
    print('%-34s %5d %5d %5d%s' % (k[:34], o, e, j, tag))
print()
print('songs with stanza-count mismatch:', len(bad), bad)
