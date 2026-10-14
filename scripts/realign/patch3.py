import json, re
# 1) Snooze overrides: the app's alarm-clock verse maps to S08
p = 'scripts/realign/overrides.py'
s = open(p, encoding='utf-8').read()
s = s.replace("    ('Sno (_ _) oze & Sn (o_o) ze', 6): 3,\n    ('Sno (_ _) oze & Sn (o_o) ze', 7): 3,\n",
              "    ('Sno (_ _) oze & Sn (o_o) ze', 6): 8,\n    ('Sno (_ _) oze & Sn (o_o) ze', 7): 8,\n")
open(p, 'w', encoding='utf-8').write(s)
# 2) decisions: drop Apocalypse S07 / Bad End S15, add Bad End S16
p2 = 'scripts/realign/decisions.json'
d = json.load(open(p2, encoding='utf-8'))
drop = {('Apocalypse', 7), ('バッドエンド·シンドローム(Bad End Syndrome)', 15)}
d['decisions'] = [x for x in d['decisions'] if (x['song'], x['stanza']) not in drop]
d['decisions'].append({"song":"バッドエンド·シンドローム(Bad End Syndrome)","stanza":16,"apps":[16,17],"ja":[3,2]})
json.dump(d, open(p2, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ok', len(d['decisions']))
