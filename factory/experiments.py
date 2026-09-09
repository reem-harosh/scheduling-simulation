"""Adaptive warm-up, common-random-number experiments and durable resumable runs."""
from __future__ import annotations
from dataclasses import dataclass, replace, asdict
import hashlib
import json
from pathlib import Path
import statistics
import math
from scipy.stats import t as student_t
from .engine import Simulation, Config


@dataclass(frozen=True)
class WarmupProtocol:
    pilots: int = 5
    window_days: int = 7
    minimum_days: int = 28
    maximum_days: int = 182
    consecutive_windows: int = 3
    relative_tolerance: float = .05
    utilization_tolerance: float = .02

    def validate(self):
        if self.pilots<1 or self.window_days!=7 or self.minimum_days<self.window_days or self.maximum_days<self.minimum_days:
            raise ValueError('Invalid warm-up protocol; this engine monitors weekly windows')
        if self.consecutive_windows<1 or not 0<=self.relative_tolerance<=1 or not 0<=self.utilization_tolerance<=1:
            raise ValueError('Invalid stability tolerances')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    temp.replace(path)


def confidence(values):
    if len(values) < 2 or any(v is None or not math.isfinite(v) for v in values):
        return {'n': len(values), 'mean': None, 'half_width': None, 'relative_half_width': None, 'ci95': None}
    mean = statistics.mean(values)
    half = float(student_t.ppf(.975, len(values)-1)) * statistics.stdev(values)/math.sqrt(len(values))
    return {'n': len(values), 'mean': mean, 'half_width': half,
            'relative_half_width': half/abs(mean) if mean else None, 'ci95': [mean-half, mean+half]}


def stability(windows, min_days=28, max_days=182, consecutive_required=3, relative_tolerance=.05, utilization_tolerance=.02):
    consecutive, completed = 0, 0
    diagnostics = []
    for i, current in enumerate(windows):
        completed += current['throughput']
        if not i:
            continue
        previous = windows[i-1]
        changes = {k: abs(current[k]-previous[k])/max(1, current[k], previous[k])
                   for k in ('wip', 'queue', 'throughput')}
        changes.update({k: abs(current[k]-previous[k]) for k in ('machine_utilization', 'worker_utilization')})
        passed = all(v <= (utilization_tolerance if 'utilization' in k else relative_tolerance) for k,v in changes.items())
        consecutive = consecutive+1 if passed else 0
        days = current['time']/1440
        diagnostics.append({'day': days, 'changes': changes, 'passed': passed, 'consecutive': consecutive})
        if days >= min_days and consecutive >= consecutive_required and completed > 0:
            return {'status': 'STABILIZED', 'warmup_days': days, 'diagnostics': diagnostics}
        if days >= max_days:
            break
    return {'status': 'NOT_STABILIZED', 'warmup_days': None, 'diagnostics': diagnostics,
            'interpretation': 'Protocol did not establish stabilization; not proof of mathematical instability'}


class ExperimentRunner:
    def __init__(self, calibration, directory='results/experiments', progress=None, cancel=None, warmup_protocol=None):
        self.data = calibration
        self.warmup = warmup_protocol or WarmupProtocol()
        self.warmup.validate()
        self.directory = Path(directory)
        self.progress = progress or (lambda message: None)
        self.cancel = cancel or (lambda: False)
        self.code_hash = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()

    def _run(self, config, until=None):
        if self.cancel():
            raise InterruptedError('Experiment cancelled; completed replications retained')
        key = hashlib.sha256(json.dumps([asdict(config), self.data.digest, self.code_hash, until],
                                       sort_keys=True).encode()).hexdigest()
        path = self.directory / 'cache' / (key + '.json')
        if path.exists():
            return json.loads(path.read_text())
        result = Simulation(self.data, config, cancel=self.cancel).run(until=until)
        if result['status'] == 'CANCELLED':
            raise InterruptedError('Experiment cancelled; completed replications retained')
        # Summary cache deliberately omits entity traces and source IDs.
        result = {k: v for k,v in result.items() if k not in ('trace','jobs','batches','machines','workers','state_minutes')}
        result['code_sha256'] = self.code_hash
        atomic_json(path, result)
        return result

    def scenario(self, config=None, algorithms=('FIFO', 'CYCLE_TRANSFER'), minimum=30, maximum=100):
        config = config or Config()
        if minimum != 30 or maximum != 100:
            raise ValueError('Research protocol requires n=30..100, checked in increments of 10')
        algorithms = tuple(dict.fromkeys(algorithms))
        if not algorithms or 'FIFO' not in algorithms:
            raise ValueError('Comparisons require FIFO baseline')
        point = {'arrival_load': config.arrival_load, 'batch_size': config.batch_size,
                 'scenario_id': config.scenario_id, 'world_version': 'v0.3',
                 'dataset_sha256': self.data.digest, 'code_sha256': self.code_hash,
                 'seed': config.seed, 'pilot_namespace': 'pilot', 'pilots': {}, 'algorithms': {},
                 'status': 'RUNNING_PILOTS', 'warmup_protocol': asdict(self.warmup), 'protocol': '5 pilots; weekly stability; n30..100; nominal Student-t 95% CI'}
        point_path = self.directory / (config.scenario_id.replace('/', '_').replace(':', '_') + '.json')
        warmups = []
        failed = False
        for algorithm in algorithms:
            point['pilots'][algorithm] = []
            for i in range(self.warmup.pilots):
                self.progress(f'{config.scenario_id} · {algorithm} · pilot {i+1}/{self.warmup.pilots}')
                cfg = replace(config, algorithm=algorithm, namespace='pilot', replication=i,
                              warmup_days=0, horizon_days=self.warmup.maximum_days, trace=False)
                result = self._run(cfg, until=self.warmup.maximum_days*1440)
                assessment = stability(result['weekly'],self.warmup.minimum_days,self.warmup.maximum_days,
                    self.warmup.consecutive_windows,self.warmup.relative_tolerance,self.warmup.utilization_tolerance)
                assessment['run_status'] = result['status']
                assessment['replication_index'] = i
                if result['status'] not in ('FINITE_HORIZON_DIAGNOSTIC', 'COMPLETE'):
                    assessment['status'] = 'PILOT_FAILED'
                point['pilots'][algorithm].append(assessment)
                if assessment['status'] == 'STABILIZED':
                    warmups.append(assessment['warmup_days'])
                else:
                    failed = True
                atomic_json(point_path, point)
        if failed:
            point['status'] = 'NOT_STABILIZED'
            point['warmup_days'] = None
            for algorithm in algorithms:
                point['algorithms'][algorithm] = {'status': 'NOT_STABILIZED', 'n': 0, 'mean': None, 'ci95': None}
            atomic_json(point_path, point)
            return point
        warmup = max(warmups)
        point['warmup_days'] = warmup
        point['status'] = 'RUNNING_REPLICATIONS'
        values = {a: [] for a in algorithms}
        for i in range(100):
            for algorithm in algorithms:
                self.progress(f'{config.scenario_id} · {algorithm} · replication {i+1}/100')
                cfg = replace(config, algorithm=algorithm, namespace='measurement', replication=i,
                              warmup_days=warmup, trace=False)
                result = self._run(cfg)
                values[algorithm].append(result['mean_flow_min'] if result['status']=='COMPLETE' else None)
            if (i+1) >= 30 and (i+1) % 10 == 0:
                point['algorithms'] = {a: {**confidence(v), 'values': v, 'replication_indices': list(range(i+1))} for a,v in values.items()}
                if any(s['mean'] is None for s in point['algorithms'].values()):
                    point['status'] = 'INVALID_REPLICATIONS'
                    break
                reached = all(s['relative_half_width'] is not None and s['relative_half_width'] <= .05 for s in point['algorithms'].values())
                atomic_json(point_path, point)
                if reached:
                    point['status'] = 'PRECISION_MET'
                    break
        if point['status'] == 'RUNNING_REPLICATIONS':
            point['status'] = 'PRECISION_NOT_MET'
        for summary in point['algorithms'].values():
            summary['status'] = point['status']
        point['paired_comparisons'] = {}
        for a in algorithms:
            if a == 'FIFO':
                continue
            pairs = list(zip(values['FIFO'], values[a]))
            differences = [alt-base if alt is not None and base is not None else None for base,alt in pairs]
            base = point['algorithms']['FIFO']['mean']
            alt = point['algorithms'][a]['mean']
            point['paired_comparisons'][a] = {**confidence(differences),
                'delta_definition': 'algorithm minus FIFO; negative is improvement',
                'improvement_percent': 100*(base-alt)/base if base and alt is not None else None}
        atomic_json(point_path, point)
        return point

    def grid(self, config=None, grid=(.5,.75,1.,1.25,1.5), algorithms=('FIFO','CYCLE_TRANSFER')):
        config = config or Config()
        surface = {'grid': list(grid), 'algorithms': list(algorithms), 'points': [],
                   'z_definition': 'mean of replication means of Original Job Flow Time (minutes)',
                   'dataset_sha256': self.data.digest, 'code_sha256': self.code_hash}
        for a in grid:
            for b in grid:
                cfg = replace(config, arrival_load=a, batch_size=b, scenario_id=f'a{a:g}_b{b:g}')
                surface['points'].append(self.scenario(cfg, algorithms))
                atomic_json(self.directory/'surface.json', surface)
        return surface
