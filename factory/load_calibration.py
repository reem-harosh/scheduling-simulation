"""Empirical demand-mix preserving operating-point search.

No point is installed unless every replication passes the declared screening
criteria. Finite-window acceptance is evidence, not proof of stationarity.
"""
from dataclasses import replace
import argparse
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from scipy.stats import linregress, t
from .data import Calibration
from .engine import Config, Simulation, ENGINE_SOURCE_SHA256
from .experiments import atomic_json


def assess(result, minimum_completions=30):
    start=result['measurement']['start_min']
    weeks=[w for w in result['weekly'] if w['time']-7*1440>=start]
    reasons=[]
    if result['status'] not in ('COMPLETE','FINITE_HORIZON_DIAGNOSTIC'):
        reasons.append(result['status'])
    if len(weeks)<6:
        reasons.append('INSUFFICIENT_WINDOWS')
    arrivals=sum(w.get('released',0) for w in weeks)
    completions=sum(w['throughput'] for w in weeks)
    ratio=completions/arrivals if arrivals else None
    slope=upper=lower=None
    if len(weeks)>=6:
        ys=[w['wip'] for w in weeks]
        fit=linregress(np.arange(len(weeks))*7,ys)
        margin=0. if max(ys)==min(ys) else float(t.ppf(.975,len(weeks)-2))*fit.stderr
        slope=float(fit.slope); lower=slope-margin; upper=slope+margin
        # Practical equivalence: drift below 5% of arrival rate, with CI.
        tolerance=max(.02,arrivals/(len(weeks)*7)*.05)
        if lower>tolerance: reasons.append('WIP_GROWTH')
        elif upper>tolerance: reasons.append('STABILITY_UNCERTAIN')
    if completions<minimum_completions: reasons.append('INSUFFICIENT_COMPLETIONS')
    if ratio is None or not .9<=ratio<=1.1: reasons.append('FLOW_IMBALANCE')
    active=result['active_machine_utilization']
    activity=result.get('activity',{})
    concurrent=activity.get('concurrent_machine_minutes',{})
    if result['mean_wip']<3 or result['mean_queue']<.1 or not concurrent or min(concurrent.values())<=0 or activity.get('distinct_moving_workers',0)<2:
        reasons.append('LOW_ACTIVITY')
    return dict(status='ACCEPTED_SCREEN' if not reasons else 'REJECTED',reasons=reasons,
        completion_arrival_ratio=ratio,wip_slope_jobs_per_day=slope,wip_slope_ols_heuristic_interval=[lower,upper],
        arrivals=arrivals,completions=completions,weeks=len(weeks),
        bottleneck_utilization=result['bottleneck_utilization'],active_machine_utilization=active)


def replicate(task):
    path,factor,rep,days,warmup,max_events,directory=task
    data=Calibration.load(path)
    cfg=Config(baseline_calibration_multiplier=factor,replication=rep,
        horizon_days=days,warmup_days=warmup,trace=False,max_events=max_events,
        scenario_id='operating-point',namespace='calibration')
    result=Simulation(data,cfg).run(until=(days+warmup)*1440)
    assessment=assess(result)
    summary={k:v for k,v in result.items() if k not in ('jobs','batches','machines','workers','trace','state_minutes')}
    summary['assessment']=assessment
    atomic_json(Path(directory)/f'factor-{factor:g}-rep-{rep}.json',summary)
    return dict(factor=factor,replication=rep,**summary)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--calibration',default='data/calibration/Final_Baseline_Calibration.json')
    p.add_argument('--factors',type=float,nargs='+',default=[.25,1,2,4,8,16])
    p.add_argument('--replications',type=int,default=3)
    p.add_argument('--replication-start',type=int,default=0)
    p.add_argument('--days',type=float,default=84)
    p.add_argument('--warmup',type=float,default=28)
    p.add_argument('--max-events',type=int,default=5000000)
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--out',default='results/load-calibration')
    a=p.parse_args()
    if a.replications<3 or a.days<42 or a.warmup<0 or any(x<=0 for x in a.factors):
        p.error('At least 3 replications and 42 measurement days; positive factors required')
    tasks=[(a.calibration,f,r,a.days,a.warmup,a.max_events,a.out) for f in a.factors for r in range(a.replication_start,a.replication_start+a.replications)]
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for future in as_completed([pool.submit(replicate,x) for x in tasks]):
            row=future.result();rows.append(row)
            print(json.dumps({k:row[k] for k in ('factor','replication','assessment') }),flush=True)
            atomic_json(Path(a.out)/'progress.json',rows)
    eligible=[f for f in a.factors if all(r['assessment']['status']=='ACCEPTED_SCREEN' for r in rows if r['factor']==f)]
    # Rank near 77.5% bottleneck only AFTER activity and stability screening.
    selected=min(eligible,key=lambda f:abs(np.mean([r['bottleneck_utilization'] for r in rows if r['factor']==f])-.775)) if eligible else None
    report=dict(status='CANDIDATE_REQUIRES_CONFIRMATION' if selected is not None else 'NO_VALID_OPERATING_POINT',
        baseline_calibration_multiplier=selected,dataset_sha256=Calibration.load(a.calibration).digest,
        engine_source_sha256=ENGINE_SOURCE_SHA256,warmup_days=a.warmup,measurement_days=a.days,
        replications=a.replications,criteria='6+ weekly windows; heuristic OLS WIP drift upper bound <= 5% arrival rate; completion/arrival 0.9..1.1; >=30 completions; WIP>=3, queue>=0.1, concurrent busy machines in each department and >=2 moving workers in every replication',
        limitation='Finite-window screening; independent long-horizon confirmation required',results=rows)
    atomic_json(Path(a.out)/'operating_point.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='results'}),flush=True)

if __name__=='__main__':main()
