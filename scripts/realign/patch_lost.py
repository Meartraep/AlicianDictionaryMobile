import json
p='scripts/realign/decisions.json'
d=json.load(open(p,encoding='utf-8'))
for x in d['decisions']:
    if x['song']=='Lost My Savepoint' and x['stanza']==5:
        x['en']=[7,0]; x['ja']=[2,0]
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print([x for x in d['decisions'] if x['song']=='Lost My Savepoint'])
