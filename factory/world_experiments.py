"""Cartesian experiments, full raw runs, paired comparisons, pilot calibration.
No automatic demand feedback. Baseline edits are offline, versioned world edits.
"""
import hashlib, itertools, json, math
from dataclasses import replace, asdict
from pathlib import Path
import numpy as np
from .experiments import atomic_json, confidence
from .world_engine import WorldSimulation, WorldConfig

class WorldExperimentRunner:
    def __init__(self,world,directory='results/world',progress=None,cancel=None,observer=None,surface_observer=None,run_observer=None):
        self.observer=observer;self.surface_observer=surface_observer
        self.run_observer=run_observer or (lambda event:None)
        world.refresh_identity()
        self.data=world;self.directory=Path(directory);self.progress=progress or (lambda s:None);self.cancel=cancel or (lambda:False)
        self.code_hash=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()
    def _run(self,config):
        self.data.refresh_identity()
        if self.cancel():raise InterruptedError('Cancelled; completed raw runs retained')
        key=hashlib.sha256(json.dumps([asdict(config),self.data.digest,self.code_hash],sort_keys=True).encode()).hexdigest();p=self.directory/'raw'/(key+'.json')
        self.run_observer(dict(kind='start',config=asdict(config)))
        if p.exists():
            r=json.loads(p.read_text());self.run_observer(dict(kind='complete',cached=True));return r
        r=WorldSimulation(self.data,config,cancel=self.cancel,observer=self.observer).run();r['code_sha256']=self.code_hash
        if r['status']=='CANCELLED':raise InterruptedError('Cancelled; completed raw runs retained')
        atomic_json(p,r);self.run_observer(dict(kind='complete',cached=False));return r
    def scenario(self,config=None,algorithms=('FIFO','SPT'),replications=3):
        config=config or WorldConfig(trace=False)
        if type(replications)!=int or replications<1:raise ValueError('Positive replication count required')
        point={'arrival_load':config.arrival_load,'batch_size':config.batch_size,'scenario_id':config.scenario_id,'warmup_days':config.warmup_days,'algorithms':{},'status':'FINITE_HORIZON_EXPERIMENT','dataset_sha256':self.data.digest,'code_sha256':self.code_hash,'raw_runs':[],'paired_comparisons':{}}
        vals={a:[] for a in algorithms};hashes={};rows=[]
        for rep in range(replications):
            for algorithm in algorithms:
                self.progress(f'{config.arrival_load:g} × {config.batch_size:g} · {algorithm} · {rep+1}/{replications}')
                c=replace(config,algorithm=algorithm,replication=rep,trace=False);r=self._run(c)
                if rep in hashes and hashes[rep]!=r['demand_sha256']:raise RuntimeError('COMMON_DEMAND_MISMATCH')
                hashes[rep]=r['demand_sha256'];v=r['mean_flow_min'] if r['status']=='COMPLETE' else None;vals[algorithm].append(v)
                row={k:r.get(k) for k in ['flow_reference','status','mean_flow_min','median_flow_min','p95_flow_min','mean_wip','mean_queue','machine_utilization','worker_available_utilization','setup_worker_utilization','mean_setup_wait_min','throughput_jobs_per_day','wip_slope_jobs_per_day','per_family','resource_statistics','observation_end','demand_sha256','peak_processing_machines']}
                row.update(algorithm=algorithm,seed=c.seed,replication=rep,arrival_scale=c.arrival_load,batch_scale=c.batch_size,lambda_jobs_day=r['demand_provenance']['effective_arrival_rate'],world_sha256=self.data.digest,code_sha256=self.code_hash,arrival_rate_realized=r['demand_provenance']['realized_arrival_rate']);rows.append(row)
                row.update({k:r.get(k) for k in ['machine_occupied_utilization','machine_waiting_utilization','utilization_definitions','setup_wait_sample_count','setup_wait_definition']})
        for a in algorithms:
            rr=[r for r in rows if r['algorithm']==a];valid=all(v is not None for v in vals[a]);summary=confidence(vals[a])
            if replications==1 and valid:summary.update(mean=vals[a][0])
            slopes=[r['wip_slope_jobs_per_day'] for r in rr];slope_ci=confidence(slopes)
            # Diagnostic only: finite windows do not prove stationarity. Failure not erased by drain.
            overloaded=slope_ci['ci95'] is not None and slope_ci['ci95'][0]>.1*rr[0]['lambda_jobs_day']
            summary.update(status='CENSORED_OR_NO_COMPLETIONS' if not valid else 'WIP_GROWTH_DETECTED' if overloaded else 'FINITE_HORIZON_NOT_CONFIRMED',values=vals[a],wip_slope=slope_ci,throughput=confidence([r['throughput_jobs_per_day'] for r in rr]),mean_wip=confidence([r['mean_wip'] for r in rr]),resource_diagnostics=rr)
            point['algorithms'][a]=summary
            summary['precision_status']='INSUFFICIENT_REPLICATIONS' if replications<2 else 'INCOMPLETE_COHORT' if not valid else 'REPORTED_NOT_TARGETED'
            summary['stability_evidence']='INSUFFICIENT_WEEKLY_OBSERVATIONS' if any(v is None for v in slopes) else 'FINITE_WINDOW_DIAGNOSTIC_ONLY'
        if 'FIFO' in vals:
            for a in vals:
                if a=='FIFO':continue
                pairs=[x-y if x is not None and y is not None else None for x,y in zip(vals[a],vals['FIFO'])];cmp=confidence(pairs);base=point['algorithms']['FIFO']['mean'];alt=point['algorithms'][a]['mean'];cmp.update(improvement_percent=100*(base-alt)/base if base and alt is not None else None,delta_definition='algorithm minus FIFO, paired by replication');point['paired_comparisons'][a]=cmp
        point['raw_runs']=rows
        atomic_json(self.directory/(config.scenario_id.replace('/','_')+'.json'),point)
        return point
    def grid(self,config=None,grid=(.5,.75,1.,1.25,1.5),algorithms=('FIFO','SPT'),replications=3,batch_grid=None):
        config=config or WorldConfig(trace=False);ys=grid if batch_grid is None else batch_grid
        if not grid or not ys or any(not math.isfinite(x) or x<=0 for x in list(grid)+list(ys)):raise ValueError('Positive finite grid scales required')
        surface={'grid':list(grid),'batch_grid':list(ys),'algorithms':list(algorithms),'points':[],'z_definition':'release-cohort mean flow time, drain included; not a stationary estimate','replications':replications,'dataset_sha256':self.data.digest,'code_sha256':self.code_hash}
        for a,b in itertools.product(grid,ys):
            cfg=replace(config,arrival_load=a,batch_size=b,scenario_id=f'a{a:g}_b{b:g}')
            surface['points'].append(self.scenario(cfg,algorithms,replications));atomic_json(self.directory/'surface.json',surface)
            if self.surface_observer:self.surface_observer(json.loads(json.dumps(surface)))
        expected=len(grid)*len(ys)*len(algorithms)*replications
        if sum(len(p['raw_runs']) for p in surface['points'])!=expected:raise RuntimeError('GRID_COMPLETENESS')
        return surface


def plot_surface(surface,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig=plt.figure(figsize=(12,5),layout='constrained')
    for i,a in enumerate(surface['algorithms'],1):
        ax=fig.add_subplot(1,len(surface['algorithms']),i,projection='3d');xs=surface['grid'];ys=surface.get('batch_grid',xs);z=np.full((len(ys),len(xs)),np.nan)
        for p in surface['points']:
            m=p['algorithms'][a]['mean']
            if m is not None:z[ys.index(p['batch_size']),xs.index(p['arrival_load'])]=m/60
        x,y=np.meshgrid(xs,ys);ax.plot_surface(x,y,z,cmap='viridis',alpha=.8);ax.scatter(x,y,z,c='black',s=12);ax.set(xlabel='Arrival scale',ylabel='Job size scale',zlabel='Mean flow time (hours)',title=a+' — finite horizon')
    fig.suptitle('Actual replicated simulations; stationarity not established; gaps = incomplete cohorts');fig.savefig(path,dpi=160);plt.close(fig)
