import json
p='scripts/realign/decisions.json'
d=json.load(open(p,encoding='utf-8'))
fix = {
 ('Teardrop del Ray',2): dict(en=[0,16]),
 ('Thirty Million Persona',6): dict(en=[1,16]),
 ('Thirty Million Persona',7): dict(en=[7,7]),
 ('Toys',9): dict(en=[11,7]),
 ('Toys',16): dict(en=[11,7]),
 ('Urxbxrxs',0): dict(en=[7,9]),
 ('Urxbxrxs',13): dict(en=[7,9]),
 ('Wonder World Sketch',1): dict(en=[7,10]),
 ('Wonder World Sketch',6): dict(en=[8,6]),
 ('Wonder World Sketch',12): dict(en=[8,6]),
 ('▷ NEW GAME',11): dict(en=[10,4]),
 ('九番目の迷路(Maze No.9)',12): dict(en=[8,14]),
 ('九番目の迷路(Maze No.9)',13): dict(en=[7,6]),
 ('九番目の迷路(Maze No.9)',18): dict(en=[4,6]),
 ('九番目の迷路(Maze No.9)',19): dict(en=[8,14]),
 ('九番目の迷路(Maze No.9)',20): dict(en=[7,6]),
}
n=0
for x in d['decisions']:
    k=(x['song'], x['stanza'])
    if k in fix:
        x.update(fix[k]); n+=1
        del fix[k]
json.dump(d, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('patched', n, 'leftover', list(fix))
