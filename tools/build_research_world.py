"""Build v0.5 from explicit engineering assumptions and source-informed routes.
Never adjusts demand in response to the live simulation. Historical v0.4 is retained.
"""
import argparse, copy, csv, hashlib, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from factory.world import World

def build(out=ROOT/'research/world_v05', rate=None, staffing_scale=1.):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    old=json.loads((ROOT/'research/world/world.json').read_text())
    design=json.loads((ROOT/'research/part-family-design/family_design.json').read_text())
    ops=copy.deepcopy(design['operations'])
    ops += [dict(part_family='NF17',operation_id='OP010',position=1,name='M3 finish',machine_family='Milling',required_axes=3),dict(part_family='NF18',operation_id='OP010',position=1,name='T finish',machine_family='Turning',required_axes=None)]
    # Popularity is independent of family IDs; rare special processes are retained.
    ranks=['NF01','NF05','NF03','NF07','NF02','NF09','NF06','NF04','NF08','NF10','NF15','NF13','NF11','NF16','NF14','NF12']
    harmonic=sum(1/r for r in range(1,17))
    probs={f:.95/(i*harmonic) for i,f in enumerate(ranks,1)}|{'NF17':.025,'NF18':.025}
    # Cross size and complexity with routes, rather than making long routes large.
    size=[1,.5,1.5,1,1.5,.5,1,.5,1.5,1,.5,1,1.5,1,.5,1,1,.5]
    complexity=[1,.9,1.1,1.15,.95,1.1,.9,1.05,1.15,1,.9,1.1,1.05,1.15,.95,1.1,.85,.9]
    norm=sum(probs[f'NF{i:02}']*size[i-1] for i in range(1,19))
    base=json.loads((ROOT/'research/world/analysis.json').read_text())['processing_base']
    families=[]
    for i in range(1,19):
        fid=f'NF{i:02}';mu=175*size[i-1]/norm;oo=[]
        for source in [o for o in ops if o['part_family']==fid]:
            name=source['name'];group=source['machine_family']
            modifier=.45 if 'drill' in name or 'cutoff' in name else .8 if 'finish' in name else 1.1 if 'rough' in name else 1.
            # Distinct preparation classes by process role; same class can span families.
            cls='A' if 'rough' in name else 'C' if 'drill' in name or 'bore' in name else 'B'
            op={k:v for k,v in source.items() if k not in ('part_family','operation_id','setup_class','processing_parameters')}
            op.update(id=source['operation_id'],setup_class=f'{group}-{cls}',base_time=base[group],operation_modifier=modifier,reference_time_per_unit=base[group]*complexity[i-1]*modifier)
            oo.append(op)
        families.append(dict(id=fid,complexity=complexity[i-1],demand_probability=probs[fid],popularity_rank=ranks.index(fid)+1 if fid in ranks else None,quantity_distribution='triangular',quantity_parameters=[.5*mu,mu,1.5*mu],quantity_values=[round(mu)],quantity_relative_mean=size[i-1],quantity_mean=mu,operations=oo,provenance='Synthetic operation roles and parameters; source-informed transition skeleton'))
    work={g:sum(p['demand_probability']*p['quantity_mean']*sum(o['reference_time_per_unit'] for o in p['operations'] if o['machine_family']==g) for p in families) for g in base}
    manual_by_family={g:sum(p['demand_probability']*p['quantity_mean']*sum(o['machine_family']==g for o in p['operations'])*11/6 for p in families) for g in base}
    # Keep two specialist machines each; allocate remaining general-purpose capacity
    # by reference offered load. This is an offline world-design decision.
    counts={'Milling':2,'Turning':2,'Honing':2,'WireEDM':2}
    for _ in range(60):
        g=max(('Milling','Turning'),key=lambda g:(work[g]+manual_by_family[g])/counts[g]);counts[g]+=1
    machines=copy.deepcopy(old['machines']);audit=list(csv.DictReader((ROOT/'research/machine-mix-audit/coordinate_mapping.csv').open()))
    evidence={r['Machine']:r['Reported process family'] for r in audit}
    remaining=set(m['id'] for m in machines);assignment={}
    # Preserve source-known specialist positions first, then known turning positions.
    for group in ('Honing','WireEDM','Turning','Milling'):
        matches=sorted(m for m in remaining if evidence[m]==group)
        for mid in matches[:counts[group]]:assignment[mid]=group;remaining.remove(mid)
    for group in ('Honing','WireEDM','Turning','Milling'):
        need=counts[group]-sum(g==group for g in assignment.values())
        choices=sorted(remaining,key=lambda mid:(next(m['x'] for m in machines if m['id']==mid)<1150 if group!='Milling' else next(m['x'] for m in machines if m['id']==mid)>=1150,mid))
        for mid in choices[:need]:assignment[mid]=group;remaining.remove(mid)
    # Four-axis capacity covers required-four load plus 20% of the milling pool
    # as flexible reserve; not a claim about the historical inventory.
    req4=sum(p['demand_probability']*p['quantity_mean']*sum(o['reference_time_per_unit'] for o in p['operations'] if o.get('required_axes')==4) for p in families)
    n4=min(counts['Milling']-2,max(2,math.ceil(counts['Milling']*(req4/work['Milling']+.20))))
    milling=sorted([m for m in machines if assignment[m['id']]=='Milling'],key=lambda m:(m['x']<1150,m['id']))
    four={m['id'] for m in milling[::2][:n4]}
    four.update(m['id'] for m in milling if len(four)<n4 and m['id'] not in four)
    for g in counts:
        pool=sorted([m for m in machines if assignment[m['id']]==g],key=lambda m:m['id'])
        for i,m in enumerate(pool):
            m.update(machine_family=g,department='milling' if m['x']<1150 else 'turning',speed=math.exp(-.15+.30*i/max(1,len(pool)-1)),axis_capability=(4 if m['id'] in four else 3) if g=='Milling' else None,source_reported_family=evidence[m['id']],technology_source='Synthetic speed independent of axis capability')
    matrix=[]
    for p in families:
        for o in p['operations']:
            o['eligible_machines']=[m['id'] for m in machines if m['machine_family']==o['machine_family'] and (o.get('required_axes') is None or m['axis_capability']>=o['required_axes'])]
            for mid in o['eligible_machines']:
                m=next(m for m in machines if m['id']==mid)
                matrix.append(dict(part_family=p['id'],operation_id=o['id'],machine=mid,time_per_unit=o['reference_time_per_unit']/m['speed']))
    offered={g:sum(p['demand_probability']*p['quantity_mean']*sum(sum(r['time_per_unit'] for r in matrix if r['part_family']==p['id'] and r['operation_id']==o['id'])/len(o['eligible_machines']) for o in p['operations'] if o['machine_family']==g) for p in families) for g in counts}
    candidate=min(.70*counts[g]*1440/offered[g] for g in counts)
    candidate=min(candidate,min(.80*counts[g]*1440/(offered[g]+manual_by_family[g]) for g in counts))
    required4_actual=sum(p['demand_probability']*p['quantity_mean']*sum(sum(r['time_per_unit'] for r in matrix if r['part_family']==p['id'] and r['operation_id']==o['id'])/len(o['eligible_machines']) for o in p['operations'] if o.get('required_axes')==4) for p in families)
    candidate=min(candidate,.70*n4*1440/max(required4_actual,1e-9))
    # Service capacity: 11/6 manual minutes per unit-operation, 650min/shift,
    # 6 working days/week. Add 20% walking/transfer allowance, then pilot-check.
    manual=sum(p['demand_probability']*p['quantity_mean']*len(p['operations'])*11/6 for p in families)
    total=math.ceil(candidate*manual*1.2/(.75*650*6/7)*staffing_scale)
    night=math.ceil(total/3);day=2*night
    local_manual={d:0. for d in ('milling','turning')}
    for p in families:
        for o in p['operations']:
            for dep in local_manual:
                fraction=sum(next(m for m in machines if m['id']==mid)['department']==dep for mid in o['eligible_machines'])/len(o['eligible_machines'])
                local_manual[dep]+=p['demand_probability']*p['quantity_mean']*11/6*fraction
    share=local_manual['milling']/sum(local_manual.values());nd=max(1,min(night-1,round(night*share)))
    roster={'milling':{'day':2*nd,'night':nd},'turning':{'day':day-2*nd,'night':night-nd}}
    setups=[];dist={'None':[0,0,0],'Minor':[8,15,25],'Medium':[15,30,45],'Major':[30,50,80]}
    for g in counts:
        classes=[f'{g}-{c}' for c in 'ABC']
        for fr in ['INITIAL']+classes:
            for to in classes:
                typ='None' if fr==to else 'Medium' if fr=='INITIAL' else 'Major' if {fr[-1],to[-1]}=={'A','C'} else 'Minor'
                setups.append(dict(machine_family=g,from_class=fr,to_class=to,type=typ,triangular=dist[typ]))
    graph=copy.deepcopy(old['walking_graph']);graph['node_floor_boundary']=1150
    resources={**old['resources'],'regular_day_workers':day,'regular_night_workers':night,'regular_workers_by_floor':roster,'floor_local_workers':True,'freight_lift_trip_minutes':3.,'freight_lift_capacity_units':60}
    world=dict(version='0.5',source_sha256=old['source_sha256'],part_families=families,machines=machines,processing_matrix=matrix,setup_matrices=setups,walking_graph=graph,resources=resources,demand=dict(arrival_model='homogeneous_poisson',baseline_jobs_per_day=rate or candidate,baseline_status='OFFLINE_ANALYTICAL_CANDIDATE' if rate is None else 'OFFLINE_SELECTED_RATE_NOT_STATIONARITY_PROOF',analytical_candidate_jobs_per_day=candidate),provenance=dict(routes='Six source-informed skeletons; 16 synthetic multi-operation variants and two singles. Roles and axes are engineering choices.',mix='95% inverse-rank over explicit16-family ranking, 5% single-operation split equally. Synthetic, not fitted Pareto.',quantities='Approved bounded triangular mean175 after probability normalization; role-independent relative size classes. Not observed market quantities.',processing='Source family median standard proxies; synthetic fixed complexity and role modifiers, not isolated autonomous measurements.',machines='68 retained coordinates; two Honing/two WireEDM; remaining64 apportioned to Milling/Turning by fixed reference processing plus on-machine manual service. Source positions preserved where possible.',axes='3/4 requirement dominates eligibility; four-axis pool from required workload plus20 percentage-point flexible reserve. Extra axes not a speed factor.',setup='Three role-based synthetic setup classes per process; fixed transition type; triangular duration; four fixed setup staff.',workers='Offline manual-capacity sizing with20% transfer allowance; 2:1day/night ratio per floor; fixed employees, not demand-reactive.',floor='Workers remain on own floor; parts use finite shared freight lift. Three minutes per lift trip is engineering baseline.',arrivals='Fixed exogenous Poisson, rate chosen offline; no live balancing.',single_operation_share='5% engineering baseline, preserves small simple-work representation independently of multi-operation rank law.'))
    World(world)
    (out/'world.json').write_text(json.dumps(world,indent=2)+'\n')
    diagnostics=dict(machine_counts=counts,milling_four_axis=n4,required4_reference_min_per_job=req4,processing_min_per_job=offered,manual_min_per_job=manual,workers=roster,analytical_rate=candidate,configured_rate=world['demand']['baseline_jobs_per_day'],weighted_quantity_mean=sum(p['demand_probability']*p['quantity_mean'] for p in families),single_operation_share=.05,source_changed_machine_families=sum(m['source_reported_family'] in counts and m['source_reported_family']!=m['machine_family'] for m in machines))
    (out/'design_diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
    tables={'part_families':[{k:v for k,v in p.items() if k not in ('operations','quantity_values')} for p in families],'operations':[dict(part_family=p['id'],**o) for p in families for o in p['operations']],'machines':machines,'processing_matrix':matrix,'setup_matrices':setups}
    tables['setup_classes']=[dict(part_family=p['id'],operation_id=o['id'],machine_family=o['machine_family'],setup_class=o['setup_class']) for p in families for o in p['operations']]
    tables['worker_resources']=[dict(worker_type='operator',floor=dep,shift=shift,count=n,restrictions='floor-local; no setup') for dep,rr in roster.items() for shift,n in rr.items()]+[dict(worker_type='setup',floor=dep,shift=shift,count=1,restrictions='setup only; floor-local') for dep in roster for shift in ('day','night')]
    tables['demand_parameters']=[dict(part_family=p['id'],probability=p['demand_probability'],arrival_model='homogeneous_poisson',lambda0=world['demand']['baseline_jobs_per_day'],quantity_distribution='triangular',minimum=p['quantity_parameters'][0],mode=p['quantity_parameters'][1],maximum=p['quantity_parameters'][2],mean=p['quantity_mean']) for p in families]
    for name,rows in tables.items():
        with (out/(name+'.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));writer.writeheader();writer.writerows(rows)
    print(json.dumps(diagnostics,indent=2));return world

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'research/world_v05');p.add_argument('--rate',type=float);p.add_argument('--staffing-scale',type=float,default=1.);a=p.parse_args();build(a.out,a.rate,a.staffing_scale)
