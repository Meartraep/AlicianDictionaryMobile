import json
p='scripts/realign/decisions.json'
d=json.load(open(p,encoding='utf-8'))
d['decisions']=[x for x in d['decisions'] if not (x['song']=='Sno (_ _) oze & Sn (o_o) ze' and x['stanza']==3)]
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('decisions', len(d['decisions']))
