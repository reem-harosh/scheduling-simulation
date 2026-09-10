"""Confirm preselected load candidates using eight independent long replications.

CI units are independent replications, not correlated weekly observations.
Accepts practical finite-horizon stability; never proves infinite-horizon stability.
"""
import argparse
import json
from pathlib import Path
import statistics
import math
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from factory.experiments import confidence,atomic_json
from factory.engine import ENGINE_SOURCE_SHA256


def interval(values):
    from scipy.stats import t
    n=len(values); mean=statistics.mean(values)
    hw=float(t.ppf(.975,n-1))*statistics.stdev(values)/(n**.5)
    return [mean-hw,mean+hw]


def confirm(rows, holdout_start=100):
    reasons=[]
    if len(rows)!=8 or len({r['config']['replication'] for r in rows})!=8:
        return dict(accepted=False,reasons=['REQUIRE_EIGHT_INDEPENDENT_REPLICATIONS'])
    if {r['config']['replication'] for r in rows} != set(range(holdout_start,holdout_start+8)):reasons.append('WRONG_HOLDOUT_IDS')
    configs=[{k:v for k,v in r['config'].items() if k!='replication'} for r in rows]
    if any(c!=configs[0] for c in configs):reasons.append('MIXED_CONFIGURATIONS')
    if any(not math.isfinite(r[k]) for r in rows for k in ('mean_wip','mean_queue','bottleneck_utilization','measurement_jobs')):reasons.append('NONFINITE_METRICS')
    if any(r['status']!='FINITE_HORIZON_DIAGNOSTIC' or r['config']['horizon_days']<364 or r['config']['warmup_days']<182 for r in rows):reasons.append('INCOMPLETE_LONG_RUN')
    if any(r['engine_source_sha256']!=ENGINE_SOURCE_SHA256 for r in rows):reasons.append('SOURCE_CHANGED')
    if len({r['dataset_sha256'] for r in rows})!=1:reasons.append('MIXED_DATASETS')
    slopes=[r['assessment']['wip_slope_jobs_per_day'] for r in rows]
    if any(x is None for x in slopes):return dict(accepted=False,reasons=reasons+['MISSING_SLOPES'])
    slope_ci=interval(slopes)
    arrivals=[r['assessment']['arrivals']/r['config']['horizon_days'] for r in rows]
    differences=[(r['assessment']['completions']-r['assessment']['arrivals'])/r['config']['horizon_days'] for r in rows]
    balance_ci=interval(differences)
    rate=statistics.mean(arrivals)
    # Declared practical equivalence margins; report them with every decision.
    drift_tolerance=max(.02,.05*rate)
    if slope_ci[0]>0:reasons.append('RESIDUAL_POSITIVE_WIP_TREND')
    if slope_ci[1]>drift_tolerance:reasons.append('WIP_STABILITY_UNCERTAIN')
    if balance_ci[0]<-.1*rate or balance_ci[1]>.1*rate:reasons.append('FLOW_EQUIVALENCE_NOT_ESTABLISHED')
    if sum(r['assessment']['completions'] for r in rows)<240:reasons.append('INSUFFICIENT_COMPLETIONS')
    for r in rows:
        a=r.get('activity',{})
        if r['mean_wip']<3 or r['mean_queue']<.1 or a.get('distinct_moving_workers',0)<2 or not a.get('concurrent_machine_minutes') or min(a['concurrent_machine_minutes'].values())<=0:
            reasons.append('INSUFFICIENT_ACTIVITY');break
    return dict(accepted=not reasons,reasons=reasons,wip_slope_ci95_across_replications=slope_ci,
        completion_minus_arrival_rate_ci95=balance_ci,drift_tolerance=drift_tolerance,
        balance_tolerance=.1*rate,replications=8,
        means={k:statistics.mean(r[k] for r in rows) for k in ('measurement_jobs','mean_wip','mean_queue','machine_utilization','machine_available_utilization','active_machine_utilization','bottleneck_utilization','worker_available_utilization','throughput_jobs_per_day')})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directories',nargs='+')
    p.add_argument('--holdout-start',type=int,default=100)
    p.add_argument('--out',default='results/load-calibration/operating_point.json')
    a=p.parse_args(); groups={}
    for directory in a.directories:
        for path in Path(directory).glob('factor-*-rep-*.json'):
            r=json.loads(path.read_text());factor=r['config']['baseline_calibration_multiplier']
            groups.setdefault(factor,[]).append(r)
    if len({r['dataset_sha256'] for rows in groups.values() for r in rows})>1:raise ValueError('Mixed candidate datasets')
    assessments={str(f):confirm(rows,a.holdout_start) for f,rows in groups.items()}
    accepted=[f for f in groups if assessments[str(f)]['accepted']]
    factor=min(accepted,key=lambda f:abs(assessments[str(f)]['means']['bottleneck_utilization']-.775)) if accepted else None
    selected_rows=groups[factor] if factor is not None else next(iter(groups.values()),[])
    metadata=selected_rows[0] if selected_rows else {}
    report=dict(status='CALIBRATED' if factor is not None else 'NO_VALID_OPERATING_POINT',
        baseline_calibration_multiplier=factor,engine_source_sha256=ENGINE_SOURCE_SHA256,
        dataset_sha256=metadata.get('dataset_sha256'),
        warmup_days=metadata.get('config',{}).get('warmup_days'),measurement_days=metadata.get('config',{}).get('horizon_days'),replications=8,holdout_start=a.holdout_start,
        criterion='Independent replication mean drift and flow equivalence; see candidate CIs and margins',
        limitation='Finite-horizon practical stability; no proof of stationarity. 70-85% bottleneck is a ranking guideline only.',
        candidates=assessments)
    atomic_json(a.out,report);print(json.dumps(report,indent=2))

if __name__=='__main__':main()
