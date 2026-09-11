"""Analyze source reports and build a frozen, auditable synthetic world (v0.4).
Run from repository root; raw inputs stay in ignored data/. No source IDs exported.
"""
from pathlib import Path
import argparse, collections, hashlib, json, math, re, sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def write_json(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))

def build(source, calibration, out):
    d=pd.read_excel(source,sheet_name='FTimeProductionStatistic')
    names={'הוראת\nייצור':'job','מספר פריט':'item','מספר\nפעולה':'op','מרכז עבודה':'center','תאור פעולה':'description','תחנה...':'station','זמן\nהתחלת\nדיווח':'start','זמן\nסיום\nדיווח':'end','כמות\nטובים':'qty','זמן עבודה נטו (דקות)':'net',' מספר סידורי (S/N)':'sn','זמן תקן\nהוראת\nייצור':'standard'}
    a=d[list(names)].rename(columns=names); sn=a.sn.notna() & a.sn.astype(str).str.strip().ne(''); excluded=set(a.loc[sn,'job'])
    a=a[~a.job.isin(excluded)].drop_duplicates().copy()
    mapping={'כרסום':'Milling','חריטה':'Turning','הונינג':'Honing','חיתוך בחוט':'WireEDM'}
    a['family']=a.center.map(mapping)
    if a.family.isna().any():raise ValueError('Unmapped process center; review mapping explicitly')
    route_by_item={}; opdata={}; ambiguous=0
    for item,g in a.groupby('item'):
        route=[]
        for pos,(op,h) in enumerate(g.groupby('op',sort=True)):
            ambiguous+=int(h.family.nunique()>1); family=h.family.mode().iloc[0];route.append(family)
            v=h.loc[(h.standard>0)&np.isfinite(h.standard),'standard']
            fallback=False
            if v.empty:
                v=(h.loc[(h.qty>0)&(h.net>0),'net']/h.loc[(h.qty>0)&(h.net>0),'qty']);fallback=True
            opdata[item,pos]={'time':float(v.median()),'source':'reported net/quantity proxy' if fallback else 'reported standard proxy','names':sorted(h.description.dropna().unique().tolist())}
        route_by_item[item]=tuple(route)
    jobs=[];zeros=0
    for job,g in a.groupby('job'):
        if g.item.nunique()!=1:raise ValueError('Multiple items within job')
        q=float(g.groupby('op').qty.sum().max())
        if q<=0:zeros+=1;continue
        item=g.item.iloc[0];jobs.append({'item':item,'quantity':int(math.floor(q+.5)),'route':route_by_item[item]})
    grouped=collections.defaultdict(list)
    for j in jobs:grouped[j['route']].append(j)
    patterns=sorted(grouped,key=lambda rt:(-len(grouped[rt]),rt))
    base={f:float(np.median([v['time'] for (it,pos),v in opdata.items() if route_by_item[it][pos]==f])) for f in mapping.values()}
    families=[]; operations=[]; route_table=[]; coverage=[]; cum=0
    for i,rt in enumerate(patterns,1):
        pf=f'PF{i:02}';jj=grouped[rt];items=sorted({j['item'] for j in jj});q=[j['quantity'] for j in jj]
        times=[float(np.median([opdata[it,pos]['time'] for it in items])) for pos in range(len(rt))]
        complexity=float(np.exp(np.mean(np.log([t/base[f] for t,f in zip(times,rt)]))))
        fam={'id':pf,'complexity':complexity,'demand_probability':len(jj)/len(jobs),'quantity_values':q,'quantity_distribution':'empirical','operations':[],'historical_job_count':len(jj),'historical_item_count':len(items)}
        for pos,(f,t) in enumerate(zip(rt,times)):
            oid=f'OP{(pos+1)*10:03}'; cls=f'{f}-{(i+pos)%3+1}'
            op={'id':oid,'name':f'{f} stage {pos+1}','machine_family':f,'position':pos+1,'setup_class':cls,'base_time':base[f],'operation_modifier':t/(base[f]*complexity),'reference_time_per_unit':t}
            fam['operations'].append(op);operations.append({'part_family':pf,**op})
        families.append(fam);cum+=len(jj)
        coverage.append({'rank':i,'part_family':pf,'route':' → '.join(rt),'jobs':len(jj),'items':len(items),'cumulative_coverage':cum/len(jobs),'repeated_family':len(set(rt))<len(rt),'operation_count':len(rt)})
    old=json.loads(Path(calibration).read_text());graph=old['walking_graph'];oldmachines=sorted(old['machines'],key=lambda m:m['id'])
    work={f:sum(p['demand_probability']*np.mean(p['quantity_values'])*sum(o['reference_time_per_unit'] for o in p['operations'] if o['machine_family']==f) for p in families) for f in base}
    # Capacity pooling design: retain 68 physical locations, apportion by expected load.
    # Minimum two parallel machines per family. No runtime balancing.
    n=len(oldmachines); counts={f:2 for f in base}
    for _ in range(n-2*len(base)):
        f=max(base,key=lambda f:work[f]/counts[f]);counts[f]+=1
    machines=[];service={};index=0
    for f,count in counts.items():
        for k in range(count):
            original=oldmachines[index];index+=1;mid=f'M{index:02}'
            speed=float(np.exp(np.linspace(-.15,.15,count)[k]))
            machines.append({**{key:original[key] for key in ['x','y','w','h']},'id':mid,'department':'floor','machine_family':f,'speed':speed,'technology_source':'Synthetic log-spaced speed factors, not estimated machine effects'})
            service[mid]=graph['service_nodes'][original['id']]
    graph={**graph,'service_nodes':service};matrix=[]
    for p in families:
        for op in p['operations']:
            op['eligible_machines']=[m['id'] for m in machines if m['machine_family']==op['machine_family']]
            for m in machines:
                if m['id'] in op['eligible_machines']:
                    matrix.append({'part_family':p['id'],'operation_id':op['id'],'machine':m['id'],'time_per_unit':op['base_time']*p['complexity']*op['operation_modifier']/m['speed']})
    setups=[];dist={'None':[0,0,0],'Minor':[8,15,25],'Medium':[15,30,45],'Major':[30,50,80]}
    for f in base:
        classes=[f'{f}-{i}' for i in range(1,4)]
        for fr in ['INITIAL']+classes:
            for to in classes:
                typ='None' if fr==to else 'Medium' if fr=='INITIAL' else 'Minor' if abs(int(fr[-1])-int(to[-1]))==1 else 'Major'
                setups.append({'machine_family':f,'from_class':fr,'to_class':to,'type':typ,'triangular':dist[typ]})
    offered={f:sum(p['demand_probability']*float(np.mean(p['quantity_values']))*sum(float(np.mean([r['time_per_unit'] for r in matrix if r['part_family']==p['id'] and r['operation_id']==op['id']])) for op in p['operations'] if op['machine_family']==f) for p in families) for f in base}
    capacity=[{'machine_family':f,'machines':counts[f],'processing_minutes_per_job':offered[f],'calendar_capacity_min_per_day':counts[f]*1440,'jobs_per_day_at_processing_rho_075':.75*counts[f]*1440/offered[f]} for f in base]
    rate=min(x['jobs_per_day_at_processing_rho_075'] for x in capacity)
    world={'version':'0.4','source_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),'part_families':families,'machines':machines,'processing_matrix':matrix,'setup_matrices':setups,'walking_graph':graph,'demand':{'arrival_model':'homogeneous_poisson','baseline_jobs_per_day':rate,'baseline_status':'ANALYTICAL_CANDIDATE_NOT_CONFIRMED'},'resources':{'regular_day_workers':14,'regular_night_workers':7,'setup_workers':4,'cycle_capacity_units':1,'transport_capacity_units':60,'working_weekdays':[6,0,1,2,3,5],'day_start_hour':7,'day_end_hour':19},'provenance':{'routes':'Derived: ordered source operation numbers mapped to modal work center; not certified complete technological routes','quantities':'Inferred: maximum cumulative good quantity across reported operations; possible report accumulation; not customer order sizes','processing':'Inferred: median reported instruction standard per historical item/stage, pooled by route stage; standard may include human time. Adopted as mechanical baseline pending measurement','machine_count':'Observed 68 map locations; family allocation Engineering Baseline proportional to fixed expected offered processing load with >=2 each','speed':'Synthetic symmetric log-spaced factors exp(-0.15)..exp(0.15); no causal machine-speed inference','setup':'Synthetic three operation-specific classes per family; transition matrix and triangular minutes Engineering Baseline','arrivals':'Engineering Baseline homogeneous Poisson; first-report timestamps do not identify exogenous arrival seasonality','workers':'Engineering Baseline 14 day + 7 night pooled qualified operators; 4 fixed setup employees split 2 day/2 night, no overtime hiring','cycles':'Engineering Baseline one unit per automatic processing cycle; human handling additive; one execution lot throughout','geometry':'Existing derived corridor graph retained; physical department constraints replaced with pooled floor skills','family_selection':'All observed route patterns; no forced 20–30 count and no route truncation to 2–5 stages'}}
    unitops=sum(p['demand_probability']*float(np.mean(p['quantity_values']))*len(p['operations']) for p in families)
    manual=unitops*11/6
    human_capacity=21*650*6/7
    world['demand']['machine_only_candidate_jobs_per_day']=rate
    rate=min(rate,.75*human_capacity/manual)
    world['demand'].update(baseline_jobs_per_day=rate,baseline_status='JOINT_CAPACITY_CANDIDATE_NOT_CONFIRMED')
    world['human_offered_load']={'unit_operations_per_job':unitops,'expected_manual_min_per_job':manual,'operator_calendar_capacity_min_per_day':human_capacity,'excludes':'walking and transport; nonpreemptive overtime not credited','target_manual_rho':.75}
    out=Path(out);out.mkdir(parents=True,exist_ok=True);write_json(out/'world.json',world)
    for name,rows in [('route_coverage',coverage),('operations',operations),('processing_matrix',matrix),('setup_matrices',[{**r,'triangular':str(r['triangular'])} for r in setups]),('machines',machines),('offered_load',capacity),('part_families',[{k:v for k,v in p.items() if k not in ('operations','quantity_values')}|{'quantity_mean':float(np.mean(p['quantity_values'])),'quantity_median':float(np.median(p['quantity_values'])),'quantity_n':len(p['quantity_values'])} for p in families]),('quantities',[{'part_family':p['id'],'quantity':q} for p in families for q in p['quantity_values']])]:pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False)
    q=np.array([j['quantity'] for j in jobs]);stats={'raw_rows':len(d),'raw_jobs':int(d[names and 'הוראת\nייצור'].nunique()),'excluded_serial_jobs':len(excluded),'retained_jobs':len(jobs),'zero_quantity_jobs_excluded':zeros,'retained_items':len({j['item'] for j in jobs}),'patterns':len(patterns),'ambiguous_item_operations':ambiguous,'quantity':{'mean':float(q.mean()),'median':float(np.median(q)),'std':float(q.std(ddof=1)),'quantiles':dict(zip(['min','p25','p50','p75','p90','p95','p99','max'],map(float,np.quantile(q,[0,.25,.5,.75,.9,.95,.99,1]))))},'long_routes_over5':sum(len(grouped[rt]) for rt in patterns if len(rt)>5),'one_operation_jobs':sum(len(grouped[rt]) for rt in patterns if len(rt)==1),'processing_base':base,'analytical_candidate_jobs_day':rate}
    write_json(out/'analysis.json',stats)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,3,figsize=(15,4),layout='constrained');ax[0].hist(q,bins=35);ax[0].set(xlabel='Quantity proxy',ylabel='Jobs',title='Full empirical tail (no trimming)');ax[1].plot(np.sort(q),np.arange(1,len(q)+1)/len(q));ax[1].set(xscale='log',xlabel='Quantity proxy (log axis)',ylabel='ECDF');ax[2].plot(range(1,len(coverage)+1),[x['cumulative_coverage'] for x in coverage],marker='o');ax[2].set(xlabel='Route patterns retained',ylabel='Job coverage',ylim=(0,1.03));fig.savefig(out/'source_analysis.png',dpi=160);plt.close(fig)
    print(json.dumps(stats,indent=2));print('Machine allocation',counts)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='data/raw/production_reports.xlsx');p.add_argument('--calibration',default='data/calibration/Final_Baseline_Calibration.json');p.add_argument('--out',default='research/world');args=p.parse_args();build(args.source,args.calibration,args.out)
