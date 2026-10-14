# -*- coding: utf-8 -*-
"""Assemble per-app-sentence EN/JA from stanza blocks + cut decisions. Report mode."""
from __future__ import annotations
import io, sys, json, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
from common import norm, canon
from map_v4 import build, runs_of
from align_engine import ALIGN

DEC = json.load(open('scripts/realign/decisions.json', encoding='utf-8'))['decisions']
DKEY = {}
for d in DEC:
    key = (d['song'], d['stanza'])
    if key in DKEY:
        raise SystemExit('duplicate decision for %s' % (key,))
    DKEY[key] = d

def atoms_of(blocks):
    out = []
    for li, line in enumerate(blocks):
        for tok in line.split():
            out.append((tok, li))
    return out

def join_atoms(atoms):
    """Join tokens, keeping the source line breaks between them."""
    parts, cur, curline = [], [], None
    for tok, li in atoms:
        if curline is None or li == curline:
            cur.append(tok)
        else:
            parts.append(' '.join(cur)); cur = [tok]
        curline = li
    if cur:
        parts.append(' '.join(cur))
    return '\n'.join(parts)

def cut(unit, d):
    """Return (en_pieces, ja_pieces, problems)."""
    k = unit['k']
    probs = []
    res = {}
    for lang, key in (('en', 'en'), ('ja', 'ja')):
        block = unit[lang]
        at = atoms_of(block)
        spec = d.get(key) if d else None
        if not at:
            res[lang] = [''] * k
            continue
        if spec is None:
            # auto: line split if line count == k
            lines = [x for x in block if x.strip()]
            if len(lines) == k:
                res[lang] = [x for x in lines]
            else:
                probs.append('%s: no rule (atoms=%d lines=%d)' % (lang, len(at), len(lines)))
                res[lang] = [''] * k
            continue
        if all(isinstance(x, int) for x in spec):
            if len(spec) != k:
                probs.append('%s: %d pieces for k=%d' % (lang, len(spec), k)); continue
            if sum(spec) != len(at):
                probs.append('%s: atoms %d != sum %d' % (lang, len(at), sum(spec)))
            pieces, i = [], 0
            for c in spec:
                pieces.append(join_atoms(at[i:i + c])); i += c
            res[lang] = pieces
        else:
            if len(spec) != k:
                probs.append('%s: %d string pieces for k=%d' % (lang, len(spec), k)); continue
            res[lang] = list(spec)
            sq = lambda s: ''.join(s.split())
            if sq(''.join(spec)) != sq(join_atoms(at)):
                probs.append('%s: string pieces do not rejoin the block' % lang)
    return res.get('en'), res.get('ja'), probs

def main():
    used = set(); unused = {}
    report = []
    problems = []
    newmap = {}         # (song, sentence) -> dict(en, ja, occurrences)
    per_position = {}   # (song, app_idx) -> dict(en, ja)
    for title in sorted(ALIGN):
        b = build(title)
        if b is None:
            continue
        S = b['S']; rows = b['rows']
        runs = runs_of(b)
        pieces_en = collections.defaultdict(list)   # run -> pieces
        pieces_ja = collections.defaultdict(list)
        for si in sorted(runs):
            for run in runs[si]:
                key = (title, si, tuple(run))
                d = DKEY.get((title, si))
                if d is not None and len(d['apps']) != len(run):
                    unused.setdefault((title, si), []).append(len(run))
                    d = None  # another run of this stanza may use the decision
                elif d is not None:
                    used.add((title, si))
                unit = dict(song=title, stanza=si, k=len(run), apps=run,
                            en=S['en_st'][si] if si < len(S['en_st']) else [],
                            ja=S['ja_st'][si] if si < len(S['ja_st']) else [])
                if all(not rows[a]['al'].strip() for a in run):
                    pieces_en[key] = [''] * unit['k']
                    pieces_ja[key] = [''] * unit['k']
                    continue
                if unit['k'] == 1:
                    en = unit['en']; ja = unit['ja']
                    pieces_en[key] = [join_atoms(atoms_of(en))]
                    pieces_ja[key] = [join_atoms(atoms_of(ja))]
                    continue
                en, ja, probs = cut(unit, d)
                for p in probs:
                    problems.append('%s S%02d run%s: %s' % (title, si, run, p))
                pieces_en[key] = en
                pieces_ja[key] = ja
        # assemble per app sentence
        for ai, r in enumerate(rows):
            if not r['al'].strip():
                continue
            en_parts, ja_parts = [], []
            for si in sorted(runs):
                for run in runs[si]:
                    if ai in run:
                        key = (title, si, tuple(run))
                        j = run.index(ai)
                        e = pieces_en[key][j] if j < len(pieces_en[key]) else ''
                        k2 = pieces_ja[key][j] if j < len(pieces_ja[key]) else ''
                        if e.strip():
                            en_parts.append(e.strip())
                        if k2.strip():
                            ja_parts.append(k2.strip())
            per_position[(title, ai)] = dict(en='\n'.join(en_parts), ja='\n'.join(ja_parts))
            key2 = (title, r['al'])
            rec = newmap.setdefault(key2, dict(en='\n'.join(en_parts), ja='\n'.join(ja_parts), n=0, idxs=[]))
            rec['n'] += 1; rec['idxs'].append(ai)
            if norm(rec['en']) != norm('\n'.join(en_parts)):
                rec['conflict'] = True
    conflicts = [(k, v) for k, v in newmap.items() if v.get('conflict')]
    never = sorted(set(DKEY) - used)
    print('decisions never applied:', len(never), never[:20])
    print('sentences assembled:', len(newmap))
    print('problem units:', len(problems))
    for p in problems[:60]:
        print('   !', p)
    print('conflicts (same sentence, different text):', len(conflicts))
    for (song, sent), v in conflicts[:40]:
        print('   * %-40s %-50s n=%d' % (song[:40], sent[:50], v['n']))
    json.dump({('%s|||%s' % k): v for k, v in newmap.items()}, open('scripts/realign/newmap.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({('%s|||%d' % k): v for k, v in per_position.items()}, open('scripts/realign/newpos.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('wrote newmap.json / newpos.json')

if __name__ == '__main__':
    main()
