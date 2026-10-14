# -*- coding: utf-8 -*-
from pathlib import Path
p = Path('scripts/realign/assemble.py')
s = p.read_text(encoding='utf-8')
s = s.replace("            if sq(''.join(spec)) != sq(''.join(at)):",
              "            if sq(''.join(spec)) != sq(join_atoms(at)):")
p.write_text(s, encoding='utf-8')
print('ok')
