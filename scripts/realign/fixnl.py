# -*- coding: utf-8 -*-
import io, sys
from pathlib import Path
p = Path('scripts/realign/assemble.py')
s = p.read_text(encoding='utf-8')
bad_a = "                    pieces_en[key] = ['\n'.join(x for x in en if x.strip())]\n"
bad_b = "                    pieces_ja[key] = ['\n'.join(x for x in ja if x.strip())]\n"
good_a = "                    pieces_en[key] = ['\n'.join(x for x in en if x.strip())]\n".replace("'\n'", "'\\n'")
good_b = "                    pieces_ja[key] = ['\n'.join(x for x in ja if x.strip())]\n".replace("'\n'", "'\\n'")
s = s.replace(bad_a, good_a).replace(bad_b, good_b)
p.write_text(s, encoding='utf-8')
print([l for l in s.splitlines() if 'pieces_en[key] =' in l])
