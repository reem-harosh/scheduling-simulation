"""Parallel, reproducible offline pilots; each full raw result is retained."""
import argparse, concurrent.futures, json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from factory.world import World
from factory.world_engine import WorldConfig
from factory.world_experiments import WorldExperimentRunner
from factory.experiments import atomic_json

def run(task):
    path,out,rate,rep,warmup,days=task
    w=World.load(path);w.raw['demand']['baseline_jobs_per_day']=rate
    c=WorldConfig(seed=20260911,replication=rep,warmup_days=warmup,horizon_days=days,drain_days=180,trace=False,max_events=10000000,scenario_id=f'rate{rate:g}_rep{rep}')
    start=time.monotonic();r=WorldExperimentRunner(w,out)._run(c)
    keys=['status','mean_flow_min','machine_utilization','worker_available_utilization','setup_worker_utilization','mean_setup_wait_min','mean_wip','mean_queue','throughput_jobs_per_day','wip_slope_jobs_per_day','peak_processing_machines','per_family','observation_end','resource_statistics','measurement','demand_sha256']
    return dict(rate=rate,replication=rep,elapsed_seconds=time.monotonic()-start,**{k:r.get(k) for k in keys})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',default='research/world_v05/world.json');p.add_argument('--output',default='results/v05-pilots');p.add_argument('--rates',nargs='+',type=float,default=[12,17,22]);p.add_argument('--replications',type=int,default=2);p.add_argument('--warmup',type=float,default=7);p.add_argument('--days',type=float,default=21);p.add_argument('--workers',type=int,default=3);a=p.parse_args()
    tasks=[(a.world,a.output,rate,rep,a.warmup,a.days) for rate in a.rates for rep in range(a.replications)];rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,t) for t in tasks]):
            row=future.result();rows.append(row);atomic_json(Path(a.output)/'summary.json',dict(warmup_days=a.warmup,measurement_days=a.days,results=rows,expected_runs=len(tasks),complete=len(rows)==len(tasks)))
            print(json.dumps({k:v for k,v in row.items() if k not in ('per_family','resource_statistics','observation_end','measurement')}),flush=True)
