"""Command line runner; invoke python -m factory --help."""
import argparse
import json
from pathlib import Path
from .data import Calibration
from .engine import Config, Simulation
from .experiments import ExperimentRunner, atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration', default='data/calibration/Final_Baseline_Calibration.json')
    parser.add_argument('--source', help='Optional original Excel for provenance hash verification')
    parser.add_argument('--mode', choices=['run','scenario','grid'], default='run')
    parser.add_argument('--algorithm', choices=['FIFO','CYCLE_TRANSFER','SPT'], default='FIFO')
    parser.add_argument('--days', type=float, default=28)
    parser.add_argument('--warmup', type=float, default=None)
    parser.add_argument('--load', type=float, default=1)
    parser.add_argument('--baseline-factor',type=float,default=None,help='Explicit intensity factor; use calibrated report value')
    parser.add_argument('--batch', type=float, default=1)
    parser.add_argument('--seed', type=int, default=20260909)
    parser.add_argument('--manual', help='JSON list of controlled jobs')
    parser.add_argument('--out', default='results/run.json')
    parser.add_argument('--trace-days', type=float, default=7)
    args = parser.parse_args()
    data = Calibration.load(args.calibration, args.source)
    from .engine import ENGINE_SOURCE_SHA256
    point_path=Path('results/load-calibration/operating_point.json')
    point=json.loads(point_path.read_text()) if point_path.exists() else {}
    calibrated=point.get('status')=='CALIBRATED' and point.get('dataset_sha256')==data.digest and point.get('engine_source_sha256')==ENGINE_SOURCE_SHA256
    factor=args.baseline_factor if args.baseline_factor is not None else (point['baseline_calibration_multiplier'] if calibrated else 1)
    warmup=args.warmup if args.warmup is not None else (point['warmup_days'] if calibrated else 14)
    config = Config(algorithm=args.algorithm, horizon_days=args.days, warmup_days=warmup,
                    arrival_load=args.load, baseline_calibration_multiplier=factor, batch_size=args.batch, seed=args.seed, trace_days=args.trace_days)
    if args.mode == 'run':
        jobs = json.loads(Path(args.manual).read_text()) if args.manual else None
        result = Simulation(data, config, jobs).run()
    else:
        runner = ExperimentRunner(data, str(Path(args.out).parent/'experiments'), progress=lambda x: print(x,flush=True))
        result = runner.scenario(config) if args.mode == 'scenario' else runner.grid(config)
    result['operating_point']=point if calibrated and args.baseline_factor is None else {'status':'EXPLICIT_OVERRIDE' if args.baseline_factor is not None else 'NOT_CALIBRATED'}
    atomic_json(args.out, result)
    print(json.dumps({'saved': args.out, 'status': result.get('status','GRID_COMPLETE'),
                      'mean_flow_min': result.get('mean_flow_min')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
