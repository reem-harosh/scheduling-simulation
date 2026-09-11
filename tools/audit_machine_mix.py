from pathlib import Path
import json,pandas as pd,numpy as np,collections
root=Path(__file__).resolve().parents[1];out=root/'research/machine-mix-audit';out.mkdir(parents=True,exist_ok=True)
d=pd.read_excel(root/'data/raw/production_reports.xlsx',sheet_name='FTimeProductionStatistic')
sn=d[' מספר סידורי (S/N)'].notna()&d[' מספר סידורי (S/N)'].astype(str).str.strip().ne('');exc=set(d.loc[sn,'הוראת\nייצור']);a=d[~d['הוראת\nייצור'].isin(exc)].copy()
a['mid']=a['תחנה...'].astype(str).str.extract(r'^\s*(\d+)',expand=False)
mp={'כרסום':'Milling','חריטה':'Turning','הונינג':'Honing','חיתוך בחוט':'WireEDM'};a['family']=a['מרכז עבודה'].map(mp)
c=json.loads((root/'data/calibration/Final_Baseline_Calibration.json').read_text());w=json.loads((root/'research/world/world.json').read_text());mapids={m['id'] for m in c['machines']};machfamilies={mid:set(g.family) for mid,g in a.groupby('mid')};print('conflicts',{k:list(v) for k,v in machfamilies.items() if len(v)!=1})
rows=[]
for f,g in a.groupby('family'):
 ids=set(g.mid);rows.append({'Family':f,'Reports':len(g),'Report share %':100*len(g)/len(a),'Reported station IDs':len(ids),'Reported IDs in map':len(ids&mapids),'Reported IDs outside map':len(ids-mapids),'Reported net minutes':float(g['זמן עבודה נטו (דקות)'].sum()),'Mapped stations left':sum(m['id'] in ids and m['x']<1150 for m in c['machines']),'Mapped stations right':sum(m['id'] in ids and m['x']>=1150 for m in c['machines'])})
reconciliation={'report_rows':len(a),'reported_jobs':a['הוראת\nייצור'].nunique(),'mapped_machines':len(mapids),'mapped_and_reported':len(mapids&set(a.mid)),'map_without_reports':len(mapids-set(a.mid)),'reported_without_map':len(set(a.mid)-mapids),'note':'All non-serial reports (344 orders), including the zero-quantity order; route-demand comparison below uses343 positive-quantity orders.'}
# Trace physical coordinate mapping, not numerical IDs (renamed in v0.4).
oldxy={(m['x'],m['y']):m for m in c['machines']};mapping=[]
for m in w['machines']:
 old=oldxy[m['x'],m['y']];hist=machfamilies.get(old['id'],set());mapping.append({'Machine':m['id'],'x':m['x'],'y':m['y'],'Floor':'Left' if m['x']<1150 else 'Right','Source-map department':old['department'],'Reported process family':'/'.join(sorted(hist)) or 'No reports','v04 synthetic family':m['machine_family']})
confusion=collections.Counter((r['Reported process family'],r['v04 synthetic family']) for r in mapping)
ps=w['part_families'];probs=np.array([p['demand_probability'] for p in ps]);equal=np.ones(len(ps))/len(ps);mix=.5*probs+.5*equal
strategies={'Historical jobs':probs,'Uniform':equal,'50% historical + 50% uniform':mix}
means=np.array([np.mean(p['quantity_values']) for p in ps]);counts=np.array([len(p['operations']) for p in ps]);groups=sorted({o['machine_family'] for p in ps for o in p['operations']})
visits=np.array([[sum(o['machine_family']==f for o in p['operations']) for f in groups] for p in ps]);reach=(visits>0).astype(float)
strategystats=[];perfamily=[]
for label,pr in strategies.items():
 strategystats.append({'Mix':label,'Most frequent family %':float(pr.max()*100),'Least frequent family %':float(pr.min()*100),'Top3 share %':float(np.sort(pr)[-3:].sum()*100),'Mean operations/job':float(pr@counts),'Mean quantity if old family sizes retained':float(pr@means),'Expected families seen in100 jobs':float(sum(1-(1-pr)**100)),'Effective family count (1/sum p^2)':float(1/sum(pr**2))})
 for f,reachval,visitval in zip(groups,pr@reach,pr@visits):perfamily.append({'Mix':label,'Machine family':f,'Jobs visiting family %':float(reachval*100),'Mean visits/job':float(visitval)})
probtable=[{'Family':p['id'],'Historical jobs':p['historical_job_count'],'Historical items':p['historical_item_count'],'Historical %':float(probs[i]*100),'Uniform %':float(equal[i]*100),'Mixed %':float(mix[i]*100),'Operations':len(p['operations'])} for i,p in enumerate(ps)]
result={'source_machine_statistics':rows,'reconciliation':reconciliation,'mapping':mapping,'confusion':[{'Source process':a,'v04 family':b,'Count':n} for (a,b),n in sorted(confusion.items())],'mix_comparison':strategystats,'machine_reach':perfamily,'probabilities':probtable,'scope':'Diagnostic comparison on the SAME19 old families; not a calibrated proposed-world mix or runtime change.'}
(out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
for name,rs in [('source_machine_statistics',rows),('coordinate_mapping',mapping),('mix_comparison',strategystats),('machine_reach',perfamily),('probabilities',probtable)]:pd.DataFrame(rs).to_csv(out/(name+'.csv'),index=False)
print(json.dumps({k:v for k,v in result.items() if k not in ['mapping','probabilities']},ensure_ascii=False,indent=2))
