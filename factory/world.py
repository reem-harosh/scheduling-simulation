"""Frozen synthetic production world and policy-independent demand stream."""
import copy, hashlib, heapq, json, math
from pathlib import Path
from .data import InputError
from .randomness import Streams

class World:
    def __init__(self, raw):
        self.raw=copy.deepcopy(raw)
        self.digest=hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()
        self.families={p['id']:p for p in raw['part_families']}
        self.machines={m['id']:m for m in raw['machines']}
        self.operations={(p['id'],o['id']):o for p in self.families.values() for o in p['operations']}
        self.processing={(r['part_family'],r['operation_id'],r['machine']):r['time_per_unit'] for r in raw['processing_matrix']}
        self.eligibility={k:tuple(o['eligible_machines']) for k,o in self.operations.items()}
        self.models={}
        self.setup={(r['machine_family'],r['from_class'],r['to_class']):r for r in raw['setup_matrices']}
        self.graph=raw['walking_graph']; self.paths={};self.adj={i:[] for i in range(len(self.graph['nodes']))}
        for a,b,d in self.graph['edges_undirected']:self.adj[a].append((b,d));self.adj[b].append((a,d))
        res=raw['resources'];self.profiles={};self.rosters={'floor':{}}
        if res.get('floor_local_workers'):
            self.rosters={}
            for dept,counts in res['regular_workers_by_floor'].items():
                self.rosters[dept]={}
                for kind in ('day','night'):
                    ids=[f'{dept}_{kind}{i:02}' for i in range(counts[kind])]
                    self.rosters[dept][kind+'_profiles']=ids
                    for wid in ids:self.profiles[wid]={'id':wid,'department':dept,'machines':[m for m,v in self.machines.items() if v['department']==dept]}
        else:
            for kind in ('day','night'):
                ids=[f'{kind}{i:02}' for i in range(res[f'regular_{kind}_workers'])]
                self.rosters['floor'][kind+'_profiles']=ids
                for wid in ids:self.profiles[wid]={'id':wid,'department':'floor','machines':list(self.machines)}
        # Compatibility metadata for shared diagnostic serializer, never used for demand.
        self.raw['arrival_calibration']={'daily_count_samples_by_weekday_monday0':{str(i):[raw['demand']['baseline_jobs_per_day']] for i in range(7)}}
        self.raw['summary']={'sha256':raw['source_sha256']}
        self.validate()
        self.templates=[{'item':p['id'],'route':[o['id'] for o in p['operations']],'quantity_proxy':max(1,round(sum(p['quantity_parameters'])/3)) if p.get('quantity_distribution')=='triangular' else p['quantity_values'][0]} for p in self.families.values()]
        self.models={k:{'model':{'mean':sum(self.processing[*k,m] for m in ms)/len(ms),'family':'constant'},'scale_to_standard':1} for k,ms in self.eligibility.items()}
        self.refresh_identity()
    def refresh_identity(self):
        """Hash actual public world parameters, including explicit scenario overrides.
        To change roster counts/machine layout, reconstruct World from edited JSON.
        """
        payload={k:v for k,v in self.raw.items() if k not in ('arrival_calibration','summary')}
        payload={**payload,'effective_profiles':self.profiles,'effective_rosters':self.rosters,
                 'effective_processing':sorted((list(k),v) for k,v in self.processing.items()),
                 'effective_eligibility':sorted((list(k),list(v)) for k,v in self.eligibility.items())}
        self.digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        return self.digest
    @classmethod
    def load(cls,path):return cls(json.loads(Path(path).read_text()))
    def validate(self):
        rate=self.raw['demand']['baseline_jobs_per_day']
        if not math.isfinite(rate) or rate<=0:raise InputError('INVALID_BASELINE_RATE')
        if len(self.operations)!=sum(len(p['operations']) for p in self.families.values()):raise InputError('DUPLICATE_OPERATION_ID')
        if not math.isclose(sum(p['demand_probability'] for p in self.families.values()),1,abs_tol=1e-9):raise InputError('DEMAND_PROBABILITIES')
        for p in self.families.values():
            if p.get('quantity_distribution')=='triangular':
                v=p.get('quantity_parameters',[])
                if len(v)!=3 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in v) or not 0<v[0]<=v[1]<=v[2]:raise InputError('QUANTITY_DISTRIBUTION')
            elif p.get('quantity_distribution','empirical')=='empirical':
                if not p.get('quantity_values') or any(type(q)!=int or q<=0 for q in p['quantity_values']):raise InputError('QUANTITY_DISTRIBUTION')
            else:raise InputError('QUANTITY_DISTRIBUTION')
            if not p['operations']:raise InputError('EMPTY_ROUTE')
        for k,o in self.operations.items():
            if not self.eligibility[k]:raise InputError('EMPTY_ELIGIBILITY')
            for mid in self.eligibility[k]:
                if mid not in self.machines or self.machines[mid]['machine_family']!=o['machine_family']:raise InputError('FAMILY_ELIGIBILITY')
                if o.get('required_axes') is not None and (o['required_axes'] not in (3,4) or self.machines[mid].get('axis_capability',0)<o['required_axes']):raise InputError('AXIS_ELIGIBILITY')
                if (*k,mid) not in self.processing or not math.isfinite(self.processing[*k,mid]) or self.processing[*k,mid]<=0:raise InputError('PROCESSING_MATRIX')
            classes={x['setup_class'] for x in self.operations.values() if x['machine_family']==o['machine_family']}
            for fr in classes|{'INITIAL'}:
                row=self.setup[o['machine_family'],fr,o['setup_class']];a,b,c=row['triangular']
                if not 0<=a<=b<=c:raise InputError('SETUP_DISTRIBUTION')
        for key in ['regular_day_workers','regular_night_workers','setup_workers','cycle_capacity_units','transport_capacity_units']:
            v=self.raw['resources'][key]
            if type(v)!=int or v<1:raise InputError('RESOURCE_PARAMETER_'+key)
    def path(self,start,end,department='floor'):
        local=self.raw['resources'].get('floor_local_workers') and department in ('milling','turning')
        def allowed(n):
            return not local or ('milling' if self.graph['nodes'][n][0]<self.graph.get('node_floor_boundary',1150) else 'turning')==department
        if not allowed(start) or not allowed(end):raise InputError('CROSS_FLOOR_WORKER_PATH')
        key=(start,end,department)
        if key in self.paths:return self.paths[key]
        heap=[(0,start)];dist={start:0};prev={}
        while heap:
            d,n=heapq.heappop(heap)
            if d!=dist[n]:continue
            if n==end:
                path=[n]
                while n!=start:n=prev[n];path.append(n)
                value=(d,list(reversed(path)));self.paths[key]=value;self.paths[end,start,department]=(d,list(reversed(value[1])));return value
            for v,w in self.adj[n]:
                if not allowed(v):continue
                if d+w<dist.get(v,math.inf):dist[v]=d+w;prev[v]=n;heapq.heappush(heap,(d+w,v))
        raise InputError('UNREACHABLE_PATH')
    def transition(self,mid,old,new):
        o=self.operations[new]; fr='INITIAL' if old is None else self.operations[tuple(old)]['setup_class']
        row=self.setup[o['machine_family'],fr,o['setup_class']]
        if old is not None and tuple(old)!=tuple(new) and max(row['triangular'])==0:
            # Different operations require preparation even within one setup class.
            # Reuse the world's lightest positive tier: an engineering assumption,
            # not an empirical duration estimate. Same-operation continuation is zero.
            tiers=[r for r in self.setup.values() if r['machine_family']==o['machine_family'] and min(r['triangular'])>0]
            if not tiers:raise InputError('MISSING_OPERATION_CHANGE_SETUP')
            tier=min(tiers,key=lambda r:sum(r['triangular']))
            return {**row,'type':tier['type'],'triangular':list(tier['triangular']),
                    'reason':'distinct_operation_same_class','duration_basis':'lightest positive configured setup tier'}
        return row


def demand_stream(world,config):
    """No engine argument, factory state, algorithm or result scenario ID in RNG keys."""
    streams=Streams(config.seed,'exogenous-demand',config.replication,config.namespace)
    rate=world.raw['demand']['baseline_jobs_per_day']*config.arrival_load
    stop=(config.warmup_days+config.horizon_days)*1440
    if rate<=0:return []
    families=list(world.families.values());probs=[p['demand_probability'] for p in families]
    t=0.;rows=[];i=0
    while True:
        t+=float(streams.rng('arrival',i).exponential(1440/rate))
        if t>=stop:break
        p=families[int(streams.rng('family',i).choice(len(families),p=probs))]
        if p.get('quantity_distribution')=='triangular':
            a,m,b=p['quantity_parameters']
            value=a if a==b else streams.rng('quantity',i).triangular(a,m,b)
            base=max(1,int(math.floor(value+.5)))
        else:base=int(streams.rng('quantity',i).choice(p['quantity_values']))
        rows.append({'id':f'R{config.replication}-J{i:06}','release':t,'item':p['id'],'base_quantity':base,'quantity':max(1,int(math.floor(base*config.batch_size+.5))),'route':[o['id'] for o in p['operations']]});i+=1
    return rows
