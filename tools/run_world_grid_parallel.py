"""Run replicated Cartesian scenarios concurrently, then aggregate cached runs.

Each task uses WorldExperimentRunner's unchanged content-addressed raw cache.
Re-running this command resumes completed tasks; progress.json is diagnostic and
never decides whether a simulation can be skipped. No live baseline calibration.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factory.experiments import atomic_json
from factory.world import World
from factory.world_engine import WorldConfig
from factory.world_experiments import WorldExperimentRunner, plot_surface
from factory.world_policies import REGISTRY

_WORKER_RUNNER = None


def _initialize(raw_world, directory):
    global _WORKER_RUNNER
    _WORKER_RUNNER = WorldExperimentRunner(World(raw_world), directory)


def _cache_path(runner, config):
    key = hashlib.sha256(json.dumps([asdict(config), runner.data.digest, runner.code_hash],
                                   sort_keys=True).encode()).hexdigest()
    return runner.directory / 'raw' / (key + '.json')


def _run_task(config_values):
    config = WorldConfig(**config_values)
    runner = _WORKER_RUNNER
    path = _cache_path(runner, config)
    cached = path.exists()
    result = runner._run(config)
    return dict(scenario_id=config.scenario_id, algorithm=config.algorithm,
                replication=config.replication, status=result['status'],
                cache_reused=cached, raw_path=str(path),
                world_sha256=runner.data.digest, code_sha256=runner.code_hash)


def run_grid(world_path, out, *, scales=(.5,.75,1.,1.25,1.5), batch_scales=None,
             algorithms=('FIFO',), replications=2, workers=2, days=7., warmup=3.,
             drain=90., max_events=5_000_000, seed=20260909, namespace='measurement',
             make_plot=True):
    scales = tuple(scales)
    batch_scales = scales if batch_scales is None else tuple(batch_scales)
    algorithms = tuple(algorithms)
    if not scales or not batch_scales or any(not math.isfinite(x) or x <= 0 for x in scales + batch_scales):
        raise ValueError('Scales must be positive finite numbers')
    if len(set(scales)) != len(scales) or len(set(batch_scales)) != len(batch_scales):
        raise ValueError('Duplicate scales would schedule the same cache file concurrently')
    # The existing runner uses :g scenario names: reject distinct values whose
    # formatted names collide instead of silently replacing point summaries.
    if len({f'{x:g}' for x in scales}) != len(scales) or len({f'{x:g}' for x in batch_scales}) != len(batch_scales):
        raise ValueError('Scales must have distinct :g scenario labels')
    if not algorithms or len(set(algorithms)) != len(algorithms) or any(a not in REGISTRY for a in algorithms):
        raise ValueError('Algorithms must be distinct registered policies')
    if type(replications) is not int or replications < 1 or type(workers) is not int or workers < 1:
        raise ValueError('Replications and workers must be positive integers')
    if type(max_events) is not int or max_events < 1:
        raise ValueError('max_events must be a positive integer')
    world = World.load(world_path)
    directory = Path(out).resolve()
    runner = WorldExperimentRunner(world, directory)
    config = WorldConfig(seed=seed, namespace=namespace, horizon_days=days,
                         warmup_days=warmup, drain_days=drain, max_events=max_events,
                         trace=False)
    config.validate()
    tasks = [replace(config, arrival_load=a, batch_size=b,
                     scenario_id=f'a{a:g}_b{b:g}', algorithm=algorithm, replication=rep)
             for a,b,rep,algorithm in itertools.product(scales,batch_scales,range(replications),algorithms)]
    progress = dict(status='RUNNING', world_path=str(Path(world_path).resolve()),
                    world_sha256=world.digest, code_sha256=runner.code_hash,
                    config=asdict(config), scales=list(scales), batch_scales=list(batch_scales),
                    algorithms=list(algorithms), replications=replications, expected_runs=len(tasks),
                    completed_runs=0, cached_runs=0, runs=[])
    progress_path = directory / 'progress.json'
    atomic_json(progress_path, progress)
    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=_initialize,
                                 initargs=(world.raw, str(directory))) as pool:
            futures = {pool.submit(_run_task, asdict(c)): c for c in tasks}
            for future in as_completed(futures):
                row = future.result()
                if (row['world_sha256'],row['code_sha256']) != (world.digest,runner.code_hash):
                    raise RuntimeError('World or code changed during the experiment')
                progress['runs'].append(row)
                progress['completed_runs'] += 1
                progress['cached_runs'] += int(row['cache_reused'])
                atomic_json(progress_path, progress)
                print(f"{progress['completed_runs']}/{len(tasks)} {row['scenario_id']} "
                      f"{row['algorithm']} rep={row['replication']} {row['status']}"
                      + (' [cached]' if row['cache_reused'] else ''), flush=True)
        # Fail rather than silently recomputing if the cache disappeared between
        # the parallel stage and aggregation. grid() uses identical config keys.
        if any(not _cache_path(runner,c).exists() for c in tasks):
            raise RuntimeError('Raw cache incomplete before aggregation')
        progress['status'] = 'AGGREGATING'
        atomic_json(progress_path, progress)
        surface = runner.grid(config, grid=scales, batch_grid=batch_scales,
                              algorithms=algorithms, replications=replications)
        if make_plot:
            plot_surface(surface, directory / 'surface.png')
        progress['status'] = 'COMPLETE'
        progress['surface_path'] = str(directory / 'surface.json')
        progress['simulation_status_counts'] = {
            status:sum(r['status'] == status for r in progress['runs'])
            for status in sorted({r['status'] for r in progress['runs']})}
        atomic_json(progress_path, progress)
        return surface
    except BaseException as exc:
        progress['status'] = 'INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'FAILED'
        progress['error'] = str(exc)
        atomic_json(progress_path, progress)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, default=ROOT/'research/world_v05/world.json')
    parser.add_argument('--out', type=Path, default=ROOT/'research/world_v05/grid')
    parser.add_argument('--scales', nargs='+', type=float, default=[.5,.75,1.,1.25,1.5])
    parser.add_argument('--batch-scales', nargs='+', type=float)
    parser.add_argument('--algorithms', nargs='+', default=['FIFO'])
    parser.add_argument('--replications', type=int, default=2)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--days', type=float, default=7.)
    parser.add_argument('--warmup', type=float, default=3.)
    parser.add_argument('--drain', type=float, default=90.)
    parser.add_argument('--max-events', type=int, default=5_000_000)
    parser.add_argument('--seed', type=int, default=20260909)
    parser.add_argument('--namespace', default='measurement')
    parser.add_argument('--no-plot', action='store_true')
    args = parser.parse_args()
    run_grid(args.world,args.out,scales=args.scales,batch_scales=args.batch_scales,
             algorithms=args.algorithms,replications=args.replications,workers=args.workers,
             days=args.days,warmup=args.warmup,drain=args.drain,max_events=args.max_events,
             seed=args.seed,namespace=args.namespace,make_plot=not args.no_plot)


if __name__ == '__main__':
    main()
