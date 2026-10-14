# -*- coding: utf-8 -*-
from pathlib import Path
p = Path('scripts/realign/assemble.py')
s = p.read_text(encoding='utf-8')
old = """def atoms_of(blocks):
    out = []
    for line in blocks:
        out.extend(line.split())
    return out
"""
new = """def atoms_of(blocks):
    out = []
    for li, line in enumerate(blocks):
        for tok in line.split():
            out.append((tok, li))
    return out

def join_atoms(atoms):
    \"\"\"Join tokens, keeping the source line breaks between them.\"\"\"
    parts, cur, curline = [], [], None
    for tok, li in atoms:
        if curline is None or li == curline:
            cur.append(tok)
        else:
            parts.append(' '.join(cur)); cur = [tok]
        curline = li
    if cur:
        parts.append(' '.join(cur))
    return '\\n'.join(parts)
"""
assert old in s
s = s.replace(old, new)
s = s.replace("                pieces.append(' '.join(at[i:i + c])); i += c",
              "                pieces.append(join_atoms(at[i:i + c])); i += c")
s = s.replace("                    pieces_en[key] = ['\\n'.join(x for x in en if x.strip())]",
              "                    pieces_en[key] = [join_atoms(atoms_of(en))]")
s = s.replace("                    pieces_ja[key] = ['\\n'.join(x for x in ja if x.strip())]",
              "                    pieces_ja[key] = [join_atoms(atoms_of(ja))]")
p.write_text(s, encoding='utf-8')
print('patched')
