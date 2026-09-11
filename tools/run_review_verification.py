"""Reproduce current finite-horizon review evidence; no calibration/optimality claim."""
import argparse,json,hashlib,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from factory.world import World
from factory.world_engine import WorldConfig
from factory.world_experiments import WorldExperimentRunner
from factory.experiments import atomic_json

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='research/multi_agent_review')
    parser.add_argument('--days',type=float,default=3)
    parser.add_argument('--warmup',type=float,default=3)
    parser.add_argument('--replications',type=int,default=3)
    args=parser.parse_args();out=Path(args.output)
    world=World.load('research/world_v05/world.json')
    config=WorldConfig(horizon_days=args.days,warmup_days=args.warmup,trace=False,seed=20260911,scenario_id='review-current-finite-horizon')
    runner=WorldExperimentRunner(world,out,progress=lambda s:print(s,flush=True))
    result=runner.scenario(config,replications=args.replications)
    manifest={'purpose':'Current finite-horizon implementation verification. Not a calibration, stationarity test, or reliable algorithm ranking. Warmup length is a diagnostic choice, not validated.',
      'review_baseline_commit':'653497b4a052806585b756fa30ee28ee0cd17aa4','dataset_sha256':world.digest,'code_sha256':runner.code_hash,
      'files':{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*.json')) if p.name!='manifest.json'},
      'source_files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('factory').glob('*.py'))}}
    atomic_json(out/'manifest.json',manifest)
    print(json.dumps({a:{k:v for k,v in r.items() if k in ['mean','n','ci95','status','relative_half_width']} for a,r in result['algorithms'].items()},indent=2))
if __name__=='__main__':main()
