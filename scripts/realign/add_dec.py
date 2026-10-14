import json
p = 'scripts/realign/decisions.json'
d = json.load(open(p, encoding='utf-8'))
d['decisions'].extend([
  {"song":"Give Me a Nightmare","stanza":9,"apps":[12,13],"en":[1,4],"ja":["「幸福」は","人間とは話してくれない"]},
  {"song":"Sno (_ _) oze & Sn (o_o) ze","stanza":3,"apps":[5,6,7],"ja":[2,1,0]},
  {"song":"Sno (_ _) oze & Sn (o_o) ze","stanza":8,"apps":[14,15,16],"ja":[2,1,0]},
])
json.dump(d, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('decisions now', len(d['decisions']))
