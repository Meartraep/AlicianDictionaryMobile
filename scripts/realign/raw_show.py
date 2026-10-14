# -*- coding: utf-8 -*-
import io, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
BT = "\x60"
SRC = Path(r"C:\Users\meart\Desktop\alicianlabs-master\script\songs_data")
def show(name, which):
    t = (SRC / (name + '.js')).read_text(encoding='utf-8')
    m = re.search(which + r"\s*=\s*" + BT + "([^" + BT + "]*)" + BT, t)
    if not m:
        print('NO MATCH', name, which); return
    print('=' * 80); print('###', name, which)
    for i, line in enumerate(m.group(1).split('\n')):
        print('%3d|%s' % (i, line.rstrip()))
show('Alice_Music', 'english_lyrics')
show('Alice_Music', 'japanese_lyrics')
