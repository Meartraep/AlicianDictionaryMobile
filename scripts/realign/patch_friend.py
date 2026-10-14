import json
p='scripts/realign/decisions.json'
d=json.load(open(p,encoding='utf-8'))
for x in d['decisions']:
    if x['song']=='Friend' and x['stanza']==9:
        x['ja']=['"私は、','君に会うために‥"','']
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('ok')
