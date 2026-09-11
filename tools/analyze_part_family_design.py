"""Reproducible discussion evidence; does not modify the runtime world."""
from pathlib import Path
import collections
import csv
import itertools
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/part-family-design'
OUT.mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader((ROOT / 'research/world/route_coverage.csv').open()))
groups = collections.defaultdict(lambda: {'jobs': 0, 'items': 0, 'source_families': []})
for row in rows:
    skeleton = ' / '.join(k for k, _ in itertools.groupby(row['route'].split(' → ')))
    g = groups[skeleton]
    g['jobs'] += int(row['jobs'])
    g['items'] += int(row['items'])
    g['source_families'].append(row['part_family'])
n = sum(g['jobs'] for g in groups.values())
skeletons = [{'skeleton': k, **v, 'probability': v['jobs']/n} for k,v in groups.items()]
skeletons.sort(key=lambda x: -x['jobs'])
raw = pd.read_excel(ROOT/'data/raw/production_reports.xlsx', sheet_name='FTimeProductionStatistic')
sn = raw[' מספר סידורי (S/N)']
excluded = set(raw.loc[sn.notna() & sn.astype(str).str.strip().ne(''), 'הוראת\nייצור'])
d = raw[~raw['הוראת\nייצור'].isin(excluded)].drop_duplicates()
unions = d.groupby('מספר פריט')['מספר\nפעולה'].agg(set)
incomplete = positive = 0
for _, g in d.groupby('הוראת\nייצור'):
    if g.groupby('מספר\nפעולה')['כמות\nטובים'].sum().max() <= 0:
        continue
    positive += 1
    incomplete += set(g['מספר\nפעולה']) != unions[g['מספר פריט'].iloc[0]]
assert positive == n == 343
assert sum(x['items'] for x in skeletons) == 164

# Explicit synthetic process roles; source data only supports broad skeletons.
catalogue = [
 ('Milling', ['M3 rough','M3 finish']),
 ('Milling', ['M3 rough','M3 finish','M3 drill']),
 ('Milling', ['M3 rough','M4 multi-face finish']),
 ('Milling', ['M3 rough','M4 multi-face finish','M3 drill']),
 ('Turning', ['T rough','T finish']),
 ('Turning', ['T rough','T bore','T finish']),
 ('Turning / Milling', ['T rough','M3 finish']),
 ('Turning / Milling', ['T rough','T finish','M3 drill']),
 ('Turning / Milling', ['T rough','M4 multi-face finish']),
 ('Turning / Milling', ['T rough','T finish','M4 multi-face finish','M3 drill']),
 ('Turning / Honing / Turning', ['T rough','T bore','H bore finish','T external finish']),
 ('Turning / Honing / Turning', ['T rough','T bore','H bore finish','T external finish','T cutoff']),
 ('Milling / WireEDM', ['M3 rough','M3 finish','W profile']),
 ('Milling / WireEDM', ['M3 rough','M4 multi-face finish','W profile']),
 ('Turning / Milling / Turning', ['T rough','M3 features','T finish']),
 ('Turning / Milling / Turning', ['T rough','M4 features','M3 drill','T finish']),
]
op_catalogue = []
family_rows = []
mapping = {'M3':'Milling','M4':'Milling','T':'Turning','H':'Honing','W':'WireEDM'}
for i,(sk,ops) in enumerate(catalogue, 1):
    family = f'NF{i:02}'
    family_rows.append({'id': family, 'skeleton': sk, 'operation_count': len(ops), 'route': ' / '.join(ops), 'provenance':'Synthetic candidate; broad skeleton source-informed', 'probability':None, 'quantity_class':None, 'complexity':None})
    for pos,name in enumerate(ops,1):
        prefix = name.split()[0]
        op_catalogue.append({'part_family':family,'operation_id':f'OP{pos*10:03}', 'position':pos,'name':name,'machine_family':mapping[prefix], 'required_axes':int(prefix[1]) if prefix.startswith('M') else None, 'setup_class':None,'processing_parameters':None})
assert len(family_rows) == 16
assert len({r['route'] for r in family_rows}) == 16
assert all(2 <= r['operation_count'] <= 5 for r in family_rows)
mix = []
for alpha in [.6,1.,1.4]:
    weights = [r**(-alpha) for r in range(1,17)]
    probs = [w/sum(weights) for w in weights]
    mix.append({'alpha':alpha, 'rank_probabilities':probs, 'top4_share':sum(probs[:4]), 'minimum_probability':probs[-1], 'status':'Synthetic comparison; ranks NOT assigned to family IDs'})
evidence = {'status':'DISCUSSION_NOT_ACTIVE','skeleton_collapse':'Analysis only; never collapses runtime operations','skeletons':skeletons,'jobs_missing_stages_relative_item_union':incomplete,'retained_jobs':positive,'one_operation_jobs':sum(int(r['jobs']) for r in rows if int(r['operation_count'])==1),'over5_operation_jobs':sum(int(r['jobs']) for r in rows if int(r['operation_count'])>5),'catalogue':family_rows,'operations':op_catalogue,'mix_comparisons':mix,'limitations':['Inferred source routes combine stages across jobs of each item; missing stages need not imply erroneous or optional routes.','Synthetic operation roles, axis requirements and shortened/extended routes are not empirical reconstructions.','Candidate catalogue is not an executable world. No calibrated baseline or stability result.','Rank order, size assignments, setup classes and processing parameters remain to be designed.']}
(OUT/'family_design.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
short={'Milling':'M','Turning':'T','Honing':'H','WireEDM':'W'}
labels=[' > '.join(short[s] for s in g['skeleton'].split(' / ')) for g in skeletons]
bars=axes[0].barh(labels[::-1],[100*g['probability'] for g in skeletons][::-1],color='#28799a')
axes[0].bar_label(bars,fmt='%.1f%%',padding=3)
axes[0].set(xlim=(0,62),xlabel='Share of 343 retained jobs (%)',title='Source-informed transition skeletons')
for m in mix:
    axes[1].plot(range(1,17),[100*p for p in m['rank_probabilities']],marker='o',label=f"alpha={m['alpha']:g}")
axes[1].set(xlabel='Family popularity rank (not family ID)',ylabel='Demand probability (%)',title='Synthetic mix alternatives for 16 families')
axes[1].legend();axes[1].grid(alpha=.2)
fig.savefig(OUT/'family_design.png',dpi=170)
print(json.dumps({'skeletons':skeletons,'incomplete_job_routes':incomplete,'candidate_families':len(family_rows),'candidate_operations':len(op_catalogue)},ensure_ascii=False,indent=2))
