"""Reproducible calibrated-world runs, offline calibration and Cartesian grid."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from factory.world import World
from factory.world_engine import WorldConfig,WorldSimulation
from factory.world_experiments import WorldExperimentRunner,plot_surface
from factory.experiments import atomic_json
p=argparse.ArgumentParser();p.add_argument('mode',choices=['run','calibrate','grid']);p.add_argument('--world',default='research/world_v05/world.json');p.add_argument('--days',type=float,default=28);p.add_argument('--warmup',type=float,default=28);p.add_argument('--replications',type=int,default=3);p.add_argument('--scales',type=float,nargs='+',default=[.5,.75,1.,1.25,1.5]);p.add_argument('--algorithms',nargs='+',default=['FIFO','SPT']);p.add_argument('--output',default='results/world');p.add_argument('--seed',type=int,default=20260909);p.add_argument('--drain-days',type=float,default=730);p.add_argument('--max-events',type=int,default=5000000);args=p.parse_args()
w=World.load(args.world);c=WorldConfig(horizon_days=args.days,warmup_days=args.warmup,seed=args.seed,trace=False,drain_days=args.drain_days,max_events=args.max_events);runner=WorldExperimentRunner(w,args.output,progress=lambda s:print(s,flush=True))
if args.mode=='run':
 c.trace=True;r=WorldSimulation(w,c).run();atomic_json(Path(args.output)/'replay.json',r);print({k:r[k] for k in ['status','mean_flow_min','machine_utilization','worker_available_utilization','setup_worker_utilization','mean_wip','peak_processing_machines']})
elif args.mode=='grid':
 r=runner.grid(c,args.scales,tuple(args.algorithms),args.replications);plot_surface(r,Path(args.output)/'response_surface.png')
else:
 points=[]
 for scale in args.scales:
  c.arrival_load=scale;c.scenario_id=f'calibration_{scale:g}';points.append(runner.scenario(c,('FIFO',),args.replications));atomic_json(Path(args.output)/'calibration.json',{'points':points,'status':'OFFLINE_PILOTS_NOT_BASELINE_CONFIRMATION','world_sha256':w.digest})
 print('Offline pilot results saved; no baseline rate mutated.',flush=True)
