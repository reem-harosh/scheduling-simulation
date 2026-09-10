"""Discrete-event production world. Scheduler decisions use public state only.

All time is in minutes. Parts are immutable ordinal ranges; movement and machine
execution have explicit completion events. Future samples remain engine-private.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import heapq
import copy
import math
import platform
import hashlib
from pathlib import Path
import statistics
import numpy as np
from .data import InputError
from .randomness import Streams
from .policies import BaselinePolicy

ENGINE_SOURCE_SHA256 = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()
HANDLING_MEAN = 11 / 6
MANUAL = {'LOADING', 'UNLOADING', 'CYCLE_CHANGE'}
WORK = MANUAL | {'WALKING', 'CARRYING'}
MACHINE_BUSY = MANUAL | {'PROCESSING', 'SETUP'}


@dataclass
class Config:
    seed: int = 20260909
    scenario_id: str = 'baseline'
    replication: int = 0
    namespace: str = 'measurement'
    algorithm: str = 'FIFO'
    arrival_load: float = 1.0
    baseline_calibration_multiplier: float = 1.0
    batch_size: float = 1.0
    horizon_days: float = 28
    warmup_days: float = 0
    start_date: str = '2026-09-09T07:00:00'
    trace: bool = True
    trace_days: float = 7
    max_events: int = 5000000

    def validate(self):
        for name in ('baseline_calibration_multiplier', 'arrival_load', 'batch_size', 'horizon_days', 'warmup_days', 'trace_days'):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise InputError('INVALID_CONFIG_' + name)
        if self.batch_size <= 0 or self.horizon_days <= 0:
            raise InputError('Positive quantity scale and horizon required')
        if self.algorithm not in ('FIFO', 'CYCLE_TRANSFER', 'SPT'):
            raise InputError('UNKNOWN_ALGORITHM')
        datetime.fromisoformat(self.start_date)


@dataclass
class Job:
    id: str
    item: str
    quantity: int
    route: list
    release: float
    source_job_id: object = None
    complete: float | None = None
    completed: int = 0
    operation_counts: dict = field(default_factory=dict)


@dataclass
class Batch:
    id: str
    job: str
    op_index: int
    lo: int
    hi: int
    ready: float
    location: str | None = None
    target: str | None = None
    parent: str | None = None
    state: str = 'READY'
    unloaded: int = 0
    cursor: int = 0
    cycle: tuple = (0, 0)
    owner: str | None = None
    owner_shift: str | None = None
    available_output: list = field(default_factory=list)


@dataclass
class Machine:
    id: str
    department: str
    node: int
    state: str = 'IDLE_AVAILABLE'
    since: float = 0
    setup: tuple | None = None
    batch: str | None = None
    available_since: float = 0


@dataclass
class Worker:
    id: str
    department: str
    skills: set
    kind: str
    extended: bool
    node: int | None = None
    home_node: int | None = None
    state: str = 'OFF_SHIFT'
    since: float = 0
    active: bool = False
    shift: str | None = None
    busy: bool = False
    pending_break: int = 0
    break_until: float = 0


def cycle_budget(unit_time, remaining):
    k = max(1, math.ceil((3 + HANDLING_MEAN) / unit_time))
    q = min(remaining, k)
    budget = q * unit_time
    p = budget - HANDLING_MEAN if budget > HANDLING_MEAN else budget * 3 / (3 + HANDLING_MEAN)
    return q, p, max(0, p + HANDLING_MEAN - budget)


class Simulation:
    def __init__(self, calibration, config=None, manual_jobs=None, policy=None, cancel=None):
        self.data, self.config = calibration, config or Config()
        self.config.validate()
        self.policy = policy or BaselinePolicy(self.config.algorithm)
        self.cancel = cancel or (lambda: False)
        self.start = datetime.fromisoformat(self.config.start_date)
        self.streams = Streams(self.config.seed, self.config.scenario_id,
                               self.config.replication, self.config.namespace)
        self.measure_start = self.config.warmup_days * 1440
        self.arrivals_stop = self.measure_start + self.config.horizon_days * 1440
        self.trace_start = self.measure_start
        self.trace_stop = self.trace_start + self.config.trace_days * 1440
        self.snapshots = []
        self.replay_initial = {}
        self.time = 0.0
        self.events, self.sequence = [], 0
        self.jobs, self.batches, self.ready = {}, {}, []
        self.output_ids = set()
        self.transfer_groups = {}
        self.requests, self.request_seq = {}, 0
        self.samples = {}
        self.intervals, self.log = [], []
        self.counters = {'events': 0, 'splits': 0, 'relative_distance': 0.,
                         'small_cycle_adjustment_min': 0., 'rejections': {}}
        self.state_minutes = {'machine': {}, 'worker': {}}
        self.weekly, self.window_integrals = [], [0., 0., 0., 0.]
        self.measure_integrals = [0., 0., 0., 0.]
        self.concurrent_machine_minutes = {d:0. for d in self.data.rosters}
        self.peak_busy_machines = {d:0 for d in self.data.rosters}
        self.moving_workers = set()
        self.window_completions, self.last_monitor = 0, 0.
        self.measured_completions_in_window = 0
        self.machines = {m['id']: Machine(m['id'], m['department'],
                          self.data.graph['service_nodes'][m['id']]) for m in self.data.machines.values()}
        self.workers = {}
        for dept, roster in self.data.rosters.items():
            for kind in ('day', 'night'):
                for i, pid in enumerate(roster[kind + '_profiles']):
                    profile = self.data.profiles[pid]
                    wid = kind + '_' + dept + '_' + pid
                    self.workers[wid] = Worker(wid, dept, set(profile['machines']), kind,
                                               kind == 'day' and i < (4 if dept == 'milling' else 3))
        # Distinct existing service nodes, within department: no synthetic motion.
        for dept in self.data.rosters:
            nodes = sorted({m.node for m in self.machines.values() if m.department == dept})
            for kind in ('day', 'night'):
                for i, w in enumerate(w for w in self.workers.values() if w.department == dept and w.kind == kind):
                    w.home_node = nodes[i % len(nodes)] if nodes else self.data.graph['handoff_node']
        self.manual_jobs = manual_jobs
        self._calendar_day(self.start.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1))
        self._event(0, 1, 'calendar_day', self.start.replace(hour=0, minute=0, second=0, microsecond=0))
        self._event(self.arrivals_stop, 1, 'arrivals_stop')
        self._event(7 * 1440, 1, 'monitor')
        self._event(self.trace_start, 0, 'replay_start')
        if manual_jobs is not None:
            seen = set()
            for i, row in enumerate(manual_jobs):
                release = float(row.get('release', 0))
                if release < 0 or release >= self.arrivals_stop:
                    raise InputError('MANUAL_RELEASE_OUTSIDE_WINDOW')
                item, route = row['item'], row['route']
                if not route or route != sorted(set(route)) or not isinstance(row['quantity'], int) or row['quantity'] < 1:
                    raise InputError('INVALID_MANUAL_JOB')
                jid = str(row.get('id', 'manual-' + str(i)))
                if jid in seen:
                    raise InputError('DUPLICATE_JOB_ID')
                seen.add(jid)
                for op in route:
                    if not self.data.eligibility.get((item, op)) or (item, op) not in self.data.models:
                        raise InputError('INFEASIBLE_MANUAL_ROUTE')
                self._event(release, 2, 'release', {**row, 'id': jid})

    def _event(self, time, priority, kind, payload=None):
        if time < self.time - 1e-8:
            raise RuntimeError('EVENT_IN_PAST')
        self.sequence += 1
        # Payload IDs provide stable tie ordering. Sequence resolves same-entity repeats.
        key = str(payload.get('id', '') if isinstance(payload, dict) else payload)
        heapq.heappush(self.events, (float(time), priority, key, self.sequence, kind, payload))

    def _log(self, kind, **fields):
        if self.config.trace and self.trace_start <= self.time <= self.trace_stop:
            self.log.append({'time': self.time, 'kind': kind, **fields})

    def _state(self, entity, state, kind, **metadata):
        self._close_interval(entity, kind)
        entity.state, entity.since = state, self.time
        entity._metadata = metadata

    def _close_interval(self, entity, kind):
        a, b = entity.since, self.time
        overlap = max(0, min(b, self.arrivals_stop) - max(a, self.measure_start))
        states = self.state_minutes[kind].setdefault(entity.id, {})
        states[entity.state] = states.get(entity.state, 0) + overlap
        end = min(b, self.trace_stop)
        if self.config.trace and end > max(a, self.trace_start):
            self.intervals.append({'entity': entity.id, 'type': kind, 'state': entity.state,
                                   'start': a, 'end': end, **getattr(entity, '_metadata', {})})
        entity.since = b

    def _counts(self):
        wip = sum(j.complete is None for j in self.jobs.values())
        queue = len(self.ready) + sum(not r['reserved'] for r in self.requests.values())
        mb = sum(m.state in MACHINE_BUSY for m in self.machines.values()) / max(1, len(self.machines))
        wb = sum(w.state in WORK for w in self.workers.values()) / max(1, len(self.workers))
        return wip, queue, mb, wb

    def _integrate(self, until):
        counts = self._counts()
        dt = until - self.time
        measured = max(0, min(until, self.arrivals_stop) - max(self.time, self.measure_start))
        if measured:
            for dept in self.data.rosters:
                busy=sum(m.state in MACHINE_BUSY for m in self.machines.values() if m.department==dept)
                self.peak_busy_machines[dept]=max(self.peak_busy_machines[dept],busy)
                if busy>=2:self.concurrent_machine_minutes[dept]+=measured
            self.moving_workers.update(w.id for w in self.workers.values() if w.state in ('WALKING','CARRYING'))
        for i, n in enumerate(counts):
            self.window_integrals[i] += dt * n
            self.measure_integrals[i] += measured * n
        self.time = until

    def _calendar_day(self, day):
        def at(hour, minute=0):
            return (day.replace(hour=hour, minute=minute) - self.start).total_seconds() / 60
        for w in sorted(self.workers.values(), key=lambda x: x.id):
            working = day.weekday() in ((6, 0, 1, 2, 3) if w.kind == 'day' else (5, 6, 0, 1, 2, 3))
            if not working:
                continue
            begin, end = (at(7), at(19 if w.extended else 16)) if w.kind == 'day' else (at(19), at(7) + 1440)
            token = w.id + ':' + day.date().isoformat()
            for t, kind, extra in [(begin, 'shift_start', token), (end, 'shift_end', token)]:
                if t >= self.time:
                    self._event(t, 1, kind, (w.id, extra))
            breaks = [(at(10), 20), (at(13), 30)] if w.kind == 'day' else [(at(22), 20), (at(1) + 1440, 30), (at(4) + 1440, 20)]
            if w.kind == 'day' and w.extended:
                breaks.append((at(16), 20))
            for t, duration in breaks:
                if t >= self.time:
                    self._event(t, 1, 'break', (w.id, duration, token))

    def _demand_day(self, day):
        if self.manual_jobs is not None:
            return
        date = day.date().isoformat()
        counts = self.data.raw['arrival_calibration']['daily_count_samples_by_weekday_monday0'][str(day.weekday())]
        n = int(self.streams.rng('demand_day', date).choice(counts))
        n = self.streams.rounded(n * self.config.arrival_load * self.config.baseline_calibration_multiplier, 'demand_scale', date)
        templates = self.data.templates
        by_item = {}
        for j in templates:
            by_item.setdefault(j['item'], []).append(j)
        for i in range(n):
            key = [date, i]
            release = (day - self.start).total_seconds() / 60 + float(self.streams.rng('arrival_time', key).uniform(0, 1440))
            if release < 0 or release >= self.arrivals_stop:
                continue
            # Sampling a template for item supplies the empirical job-count weights.
            item = templates[int(self.streams.rng('item', key).integers(len(templates)))]['item']
            candidates = by_item[item]
            template = candidates[int(self.streams.rng('quantity', key).integers(len(candidates)))]
            q = max(1, self.streams.rounded(template['quantity_proxy'] * self.config.batch_size, 'quantity_scale', key))
            jid = f'{self.config.scenario_id}:{self.config.replication}:{date}:{i}'
            self._event(release, 2, 'release', {'id': jid, 'item': item, 'quantity': q,
                         'route': template['route'], 'source_job_id': template['source_job_id']})

    def _new_batch(self, job, oi, lo, hi, location=None, target=None, parent=None):
        bid = f'{job}/{oi}/{lo}-{hi}'
        if bid in self.batches:
            raise RuntimeError('DUPLICATE_PART_ALLOCATION')
        b = Batch(bid, job, oi, lo, hi, self.time, location, target, parent, cursor=lo)
        self.batches[bid] = b
        self.ready.append(bid)
        self._log('ready', batch=bid, job=job, operation=self.jobs[job].route[oi], lo=lo, hi=hi)
        return b

    def public_state(self):
        """Fresh plain data: released jobs, current states, known distribution means."""
        ready = []
        for bid in self.ready:
            b = self.batches[bid]
            j = self.jobs[b.job]
            key = (j.item, j.route[b.op_index])
            model = self.data.models[key]
            ready.append(dict(id=bid, job=b.job, lo=b.lo, hi=b.hi, target=b.target,
                ready_time=b.ready, release_time=j.release, operation=key[1],
                expected_processing_min=model['model']['mean']*model.get('scale_to_standard',1)*(b.hi-b.lo),
                processing_distribution=copy.deepcopy(model['model']),scale_to_standard=model.get('scale_to_standard',1),
                eligible_machines=list(self.data.eligibility[key])))
        outputs = []
        for bid in sorted(self.output_ids):
            b = self.batches[bid]
            if b.available_output:
                j = self.jobs[b.job]
                outputs.append(dict(id=b.id, state=b.state, ranges=[list(r) for r in b.available_output],
                    eligible_machines=list(self.data.eligibility[(j.item,j.route[b.op_index+1])])) )
        return dict(time=self.time, ready=ready, outputs=outputs,
            calendar=dict(start_date=self.config.start_date,day_weekdays=[6,0,1,2,3],night_start_weekdays=[5,6,0,1,2,3],
                day_hours=[7,16],extended_hours=[7,19],night_hours=[19,7],
                day_breaks=[[10,0,20],[13,0,30]],extended_breaks=[[16,0,20]],night_breaks=[[22,0,20],[1,0,30],[4,0,20]]),
            jobs=[dict(id=j.id,item=j.item,quantity=j.quantity,route=list(j.route),release=j.release,completed=j.completed)
                  for j in self.jobs.values()],
            machines=[dict(id=m.id,department=m.department,state=m.state,batch=m.batch,
                           setup=m.setup,available_since=m.available_since,elapsed_in_state=self.time-m.since) for m in self.machines.values()],
            workers=[dict(id=w.id,department=w.department,skills=sorted(w.skills),state=w.state,
                          active=w.active,node=w.node,shift=w.shift,elapsed_in_state=self.time-w.since,extended=w.extended) for w in self.workers.values()],
            ownership=[dict(batch=m.batch,worker=self.batches[m.batch].owner,shift=self.batches[m.batch].owner_shift) for m in self.machines.values() if m.batch and self.batches[m.batch].owner])

    def _allocate(self):
        if not self.ready and not self.output_ids:
            return
        if type(self.policy) is BaselinePolicy:
            movable = bool(self.output_ids) if self.policy.name=='CYCLE_TRANSFER' else any(self.batches[b].state=='COMPLETE' for b in self.output_ids)
            idle = {m.id for m in self.machines.values() if m.batch is None}
            allocatable = any((b.target in idle if b.target else bool(idle.intersection(self.data.eligibility[(self.jobs[b.job].item,self.jobs[b.job].route[b.op_index])])) ) for b in (self.batches[bid] for bid in self.ready))
            if not movable and not allocatable:
                return
        # No callback receives the engine, private RNGs, event heap or samples.
        for action in self.policy.decide(self.public_state()):
            self.apply_action(action)

    def apply_action(self, action):
        kind = action.get('kind')
        if kind == 'allocate':
            return self.accept_allocation(action.get('batch'), action.get('machine'))
        b = self.batches.get(action.get('batch'))
        reason = None
        if b is None:
            reason = 'UNKNOWN_ENTITY'
        elif kind == 'split':
            sizes = action.get('quantities', [])
            if b.state != 'READY' or b.id not in self.ready:
                reason = 'RESOURCE_BUSY'
            elif b.op_index == 0:
                reason = 'SPLIT_ONLY_BETWEEN_OPERATIONS'
            elif len(sizes)<2 or any(type(q) is not int or q<1 for q in sizes) or sum(sizes)!=b.hi-b.lo:
                reason = 'QUANTITY_NOT_CONSERVED'
            else:
                self.ready.remove(b.id)
                b.state = 'SPLIT'
                lo = b.lo
                for q in sizes:
                    self._new_batch(b.job,b.op_index,lo,lo+q,b.location,b.target,b.id)
                    lo += q
                self.counters['splits'] += len(sizes)-1
                self._log('split',batch=b.id,quantities=list(sizes))
                return None
        elif kind == 'transfer':
            lo, hi, mid = action.get('lo'), action.get('hi'), action.get('machine')
            j = self.jobs[b.job]
            if b.op_index+1 >= len(j.route) or mid not in self.data.eligibility.get((j.item,j.route[b.op_index+1]),()):
                reason = 'MACHINE_INELIGIBLE'
            elif type(lo) is not int or type(hi) is not int or lo>=hi:
                reason = 'INVALID_PART_RANGE'
            elif sum(max(0,min(hi,z)-max(lo,a)) for a,z in b.available_output) != hi-lo:
                reason = 'PRECEDENCE_NOT_MET'
            else:
                remaining=[]
                for a,z in b.available_output:
                    if z<=lo or a>=hi: remaining.append((a,z))
                    else:
                        if a<lo: remaining.append((a,lo))
                        if z>hi: remaining.append((hi,z))
                b.available_output=remaining
                if not remaining:
                    self.output_ids.discard(b.id)
                self._transfer_output(b,self.machines[b.location],lo,hi,mid,action.get('preserve_batch',False))
                return None
        else:
            reason = 'UNKNOWN_ACTION'
        self.counters['rejections'][reason] = self.counters['rejections'].get(reason,0)+1
        self._log('action_rejected',reason_code=reason,action=action)
        return reason

    def validate_allocation(self, bid, mid):
        if bid not in self.batches or mid not in self.machines:
            return 'UNKNOWN_ENTITY'
        b, m = self.batches[bid], self.machines[mid]
        j = self.jobs[b.job]
        if mid not in self.data.eligibility.get((j.item, j.route[b.op_index]), ()):
            return 'MACHINE_INELIGIBLE'
        if b.state != 'READY' or m.batch is not None:
            return 'RESOURCE_BUSY'
        if b.target is not None and b.target != mid:
            return 'PRECEDENCE_NOT_MET'
        return None

    def accept_allocation(self, bid, mid):
        reason = self.validate_allocation(bid, mid)
        if reason:
            self.counters['rejections'][reason] = self.counters['rejections'].get(reason, 0) + 1
            self._log('allocation_rejected', batch=bid, machine=mid, reason_code=reason)
            return reason
        b, m = self.batches[bid], self.machines[mid]
        j = self.jobs[b.job]
        if bid in self.ready:
            self.ready.remove(bid)
        m.batch = bid
        b.location = mid
        b.state = 'WAITING_SETUP'
        new = (j.item, j.route[b.op_index])
        old = m.setup
        self._log('allocated', batch=bid, machine=mid, job=b.job)
        if old is not None and old != new:
            mode = 5 if old[0] == new[0] else 6
            high = 6 if old[0] == new[0] else 8
            duration = float(self.streams.rng('setup', [mid, old, new, b.job, b.lo]).triangular(4, mode, high)) * 60
            self._state(m, 'SETUP', 'machine', batch=bid, job=b.job)
            self._event(self.time + duration, 0, 'setup_end', mid)
        else:
            m.setup = new
            self._request_machine(m, 'load')
        return None

    def _request_machine(self, m, kind):
        b = self.batches[m.batch]
        states = {'load': 'WAITING_FOR_WORKER_LOAD', 'change': 'WAITING_FOR_CYCLE_CHANGE', 'unload': 'WAITING_FOR_WORKER_UNLOAD'}
        self._state(m, states[kind], 'machine', batch=b.id, job=b.job)
        b.state = states[kind]
        self._request(kind, m.department, m.node, machine=m.id, batch=b.id)

    def _request(self, kind, dept, pickup, **details):
        self.request_seq += 1
        rid = self.request_seq
        self.requests[rid] = dict(id=rid, kind=kind, department=dept, pickup=pickup,
                                  ready=self.time, reserved=False, **details)

    def _worker_available(self, w):
        return w.active and not w.busy and not w.pending_break and w.break_until <= self.time

    def _rest(self, w):
        w.busy = False
        if not w.active:
            w.pending_break = 0
            self._state(w, 'OFF_SHIFT', 'worker', node=w.node)
        elif w.pending_break:
            duration, w.pending_break = w.pending_break, 0
            w.break_until = self.time + duration
            self._state(w, 'ON_BREAK', 'worker', node=w.node)
            self._event(w.break_until, 1, 'break_end', w.id)
        elif w.break_until > self.time:
            self._state(w, 'ON_BREAK', 'worker', node=w.node)
        else:
            self._state(w, 'IDLE_AT_LOCATION', 'worker', node=w.node)

    def _dispatch(self):
        order = {'change': 1, 'unload': 2, 'transport': 2, 'load': 3}
        requests = sorted(self.requests.values(), key=lambda r: (order[r['kind']], r['ready'], r['id']))
        for r in requests:
            if r['reserved']:
                continue
            candidates = []
            for w in self.workers.values():
                if w.department != r['department'] or not self._worker_available(w):
                    continue
                if r['kind'] != 'transport':
                    if r['machine'] not in w.skills:
                        continue
                    b = self.batches[r['batch']]
                    owner = self.workers.get(b.owner)
                    if owner and (owner.busy or (owner.active and owner.shift == b.owner_shift)) and owner.id != w.id:
                        continue
                distance = 0 if w.node is None else self.data.path(w.node, r['pickup'], w.department)[0]
                candidates.append((distance, w.id))
            if not candidates:
                continue
            w = self.workers[min(candidates)[1]]
            r['reserved'] = w.id
            w.busy = True
            if w.node is None:
                w.node = r['pickup']
            distance, path = self.data.path(w.node, r['pickup'], w.department)
            if distance:
                self._move(w, path, distance, 'WALKING', 'pickup', r['id'])
            else:
                self._event(self.time, 0, 'pickup', (w.id, r['id']))

    def _move(self, w, path, distance, state, event, rid):
        duration = distance * self.data.graph['seconds_per_relative_unit'] / 60
        self.counters['relative_distance'] += distance
        self._state(w, state, 'worker', path=path, node=path[0], destination=path[-1],
                    move_end=self.time + duration, request=rid)
        self._event(self.time + duration, 0, event, (w.id, rid))

    def _pickup(self, wid, rid):
        w, r = self.workers[wid], self.requests[rid]
        w.node = r['pickup']
        # Calendar events at this timestamp have precedence over starting new work.
        w.busy = False
        if not self._worker_available(w):
            r['reserved'] = False
            self._rest(w)
            return
        w.busy = True
        if r['kind'] == 'transport':
            distance, path = self.data.path(w.node, r['destination'], w.department)
            self._move(w, path, distance, 'CARRYING', 'transport_end', rid)
            self._log('carry_start', worker=wid, quantity=r['hi']-r['lo'], job=r['job'],
                      lo=r['lo'], hi=r['hi'], from_node=r['pickup'], to_node=r['destination'])
            return
        b, m = self.batches[r['batch']], self.machines[r['machine']]
        if r['machine'] not in w.skills:
            raise RuntimeError('WORKER_INELIGIBLE')
        if b.owner != wid or b.owner_shift != w.shift:
            self._log('ownership_acquire', worker=wid, batch=b.id, shift=w.shift)
            b.owner, b.owner_shift = wid, w.shift
        states = {'load': 'LOADING', 'change': 'CYCLE_CHANGE', 'unload': 'UNLOADING'}
        kind = r['kind']
        parts = [b.lo, b.hi] if kind == 'load' else list(b.cycle)
        key = [b.job, self.jobs[b.job].route[b.op_index], m.id, parts, kind]
        duration = float(self.streams.rng('handling', key).triangular(1, 1.5, 3))
        if kind != 'change':
            duration *= .5
        self._state(w, states[kind], 'worker', node=w.node, batch=b.id, job=b.job, machine=m.id)
        self._state(m, states[kind], 'machine', batch=b.id, job=b.job, worker=wid)
        b.state = states[kind]
        self._event(self.time + duration, 0, 'manual_end', (wid, rid))

    def _processing(self, m):
        b = self.batches[m.batch]
        j = self.jobs[b.job]
        key = (j.id, j.route[b.op_index])
        if key not in self.samples:
            self.samples[key] = self.streams.processing(self.data.models[(j.item, key[1])], *key)
        q, duration, adjustment = cycle_budget(self.samples[key], b.hi-b.cursor)
        self.counters['small_cycle_adjustment_min'] += adjustment
        b.cycle = (b.cursor, b.cursor + q)
        b.cursor += q
        b.state = 'PROCESSING'
        self._state(m, 'PROCESSING', 'machine', batch=b.id, job=b.job, lo=b.cycle[0], hi=b.cycle[1])
        self._event(self.time + duration, 0, 'processing_end', m.id)

    def _finished_parts(self, b, m):
        j = self.jobs[b.job]
        lo, hi = b.cycle
        op = j.route[b.op_index]
        b.unloaded += hi-lo
        j.operation_counts[op] = j.operation_counts.get(op, 0) + hi-lo
        if j.operation_counts[op] > j.quantity:
            raise RuntimeError('QUANTITY_NOT_CONSERVED')
        self._log('parts_unloaded', job=j.id, batch=b.id, operation=op, lo=lo, hi=hi)
        if b.op_index == len(j.route)-1:
            j.completed += hi-lo
            if j.completed == j.quantity:
                j.complete = self.time
                self.window_completions += 1
                if self.measure_start <= self.time < self.arrivals_stop:
                    self.measured_completions_in_window += 1
                self._log('job_complete', job=j.id, flow_time=self.time-j.release)
        else:
            self.output_ids.add(b.id)
            if b.available_output and b.available_output[-1][1] == lo:
                b.available_output[-1] = (b.available_output[-1][0], hi)
            else:
                b.available_output.append((lo, hi))

    def _transfer_output(self, b, source, lo, hi, target_id, preserve_batch=False):
        j = self.jobs[b.job]
        target = self.machines[target_id]
        portal = self.data.graph['handoff_node']
        group = f'{b.id}/transfer/{lo}-{hi}' if preserve_batch else None
        if group:
            self.transfer_groups[group] = dict(job=j.id,op_index=b.op_index+1,lo=lo,hi=hi,target=target.id,parent=b.id,received=0)
        for start in range(lo, hi, 60):
            end = min(start+60, hi)
            self.counters['splits'] += int(start > lo or end < hi or hi-lo < b.hi-b.lo)
            cross = source.department != target.department
            self._request('transport', source.department, source.node,
                          destination=portal if cross else target.node, job=j.id, op_index=b.op_index+1,
                          lo=start, hi=end, target=target.id, parent=b.id, second_leg=cross, group=group)

    def _handle(self, kind, payload):
        if kind == 'replay_start':
            self.replay_initial = dict(job_completed={j.id:j.completed for j in self.jobs.values()},
                batches={b.id:dict(state=b.state,completed=b.unloaded) for b in self.batches.values()})
        elif kind == 'calendar_day':
            day = payload
            self._calendar_day(day)
            if self.time < self.arrivals_stop:
                self._demand_day(day)
            nxt = day + timedelta(days=1)
            self._event((nxt-self.start).total_seconds()/60, 1, 'calendar_day', nxt)
        elif kind == 'shift_start':
            w = self.workers[payload[0]]
            if w.node is None:
                w.node = w.home_node
            w.active, w.shift = True, payload[1]
            w.pending_break, w.break_until = 0, 0
            if not w.busy:
                self._rest(w)
        elif kind == 'shift_end':
            w = self.workers[payload[0]]
            if w.shift == payload[1]:
                w.active = False
                self._log('shift_end', worker=w.id, shift=w.shift)
                if not w.busy:
                    self._rest(w)
        elif kind == 'break':
            w = self.workers[payload[0]]
            if w.active and w.shift == payload[2]:
                w.pending_break += payload[1]
                if not w.busy:
                    self._rest(w)
        elif kind == 'break_end':
            w = self.workers[payload]
            if not w.busy:
                self._rest(w)
        elif kind == 'release':
            row = payload
            j = Job(row['id'], row['item'], row['quantity'], row['route'], self.time, row.get('source_job_id'))
            self.jobs[j.id] = j
            self._new_batch(j.id, 0, 1, j.quantity+1)
            self._log('release', job=j.id, quantity=j.quantity, item=j.item)
        elif kind == 'setup_end':
            m = self.machines[payload]
            b = self.batches[m.batch]
            j = self.jobs[b.job]
            m.setup = (j.item, j.route[b.op_index])
            self._request_machine(m, 'load')
        elif kind == 'pickup':
            # Readiness phase: all completions/calendar/releases at time t first.
            self._event(self.time, 3, 'pickup_ready', payload)
        elif kind == 'pickup_ready':
            self._pickup(*payload)
        elif kind == 'processing_end':
            m = self.machines[payload]
            b = self.batches[m.batch]
            self._request_machine(m, 'unload' if b.cursor == b.hi else 'change')
        elif kind == 'manual_end':
            wid, rid = payload
            r = self.requests.pop(rid)
            w, m = self.workers[wid], self.machines[r['machine']]
            b = self.batches[r['batch']]
            if r['kind'] in ('change', 'unload'):
                self._finished_parts(b, m)
            self._rest(w)
            if r['kind'] == 'unload':
                b.state = 'COMPLETE'
                m.batch = None
                m.available_since = self.time
                self._state(m, 'IDLE_AVAILABLE', 'machine')
            else:
                self._processing(m)
        elif kind == 'transport_end':
            wid, rid = payload
            r = self.requests.pop(rid)
            w = self.workers[wid]
            w.node = r['destination']
            self._rest(w)
            if r['second_leg']:
                target = self.machines[r['target']]
                self._request('transport', target.department, w.node,
                              destination=target.node, job=r['job'], op_index=r['op_index'],
                              lo=r['lo'], hi=r['hi'], target=target.id, parent=r['parent'], second_leg=False, group=r.get('group'))
            elif r.get('group'):
                group = self.transfer_groups[r['group']]
                group['received'] += r['hi']-r['lo']
                if group['received'] == group['hi']-group['lo']:
                    self._new_batch(group['job'],group['op_index'],group['lo'],group['hi'],
                                    location=group['target'],target=group['target'],parent=group['parent'])
            else:
                self._new_batch(r['job'], r['op_index'], r['lo'], r['hi'],
                                location=r['target'], target=r['target'], parent=r['parent'])
        elif kind == 'monitor':
            duration = self.time - self.last_monitor
            values = [x/duration for x in self.window_integrals]
            self.weekly.append(dict(time=self.time, wip=values[0], queue=values[1],
                                   machine_utilization=values[2], worker_utilization=values[3],
                                   throughput=self.window_completions,
                                   released=sum(self.last_monitor <= j.release < self.time for j in self.jobs.values()),
                                   end_wip=sum(j.complete is None for j in self.jobs.values())))
            self.window_integrals = [0., 0., 0., 0.]
            self.window_completions, self.last_monitor = 0, self.time
            self._event(self.time + 7*1440, 1, 'monitor')
        elif kind != 'arrivals_stop':
            raise RuntimeError('UNKNOWN_EVENT_' + kind)

    def run(self, until=None):
        status = 'COMPLETE'
        last_progress = 0
        while self.events:
            if self.cancel():
                status = 'CANCELLED'
                break
            t = self.events[0][0]
            if until is not None and t > until:
                self._integrate(until)
                status = 'FINITE_HORIZON_DIAGNOSTIC'
                break
            self._integrate(t)
            while self.events and self.events[0][0] == t:
                _, _, _, _, kind, payload = heapq.heappop(self.events)
                self._handle(kind, payload)
                self.counters['events'] += 1
                if kind in ('manual_end', 'transport_end', 'processing_end', 'release'):
                    last_progress = t
            self._allocate()
            self._dispatch()
            if self.config.trace and self.trace_start <= self.time <= self.trace_stop:
                wip, queue, _, _ = self._counts()
                self.snapshots.append(dict(time=self.time,wip=wip,queue=queue,
                    released=len(self.jobs),completed=sum(j.complete is not None for j in self.jobs.values())))
            if self.counters['events'] >= self.config.max_events:
                status = 'EVENT_LIMIT'
                break
            if until is None and self.time >= self.arrivals_stop and all(j.complete is not None for j in self.jobs.values()):
                break
            # A full roster cycle without any work, no autonomous event, no future release.
            if self.time-last_progress > 8*1440 and any(j.complete is None for j in self.jobs.values()):
                productive = any(e[4] in ('manual_end', 'transport_end', 'processing_end', 'setup_end', 'release') for e in self.events)
                if not productive:
                    status = 'DEADLOCK_INFEASIBLE'
                    break
        for m in self.machines.values():
            self._close_interval(m, 'machine')
        for w in self.workers.values():
            self._close_interval(w, 'worker')
        return self.result(status)

    def result(self, status):
        measured = [j for j in self.jobs.values() if self.measure_start <= j.release < self.arrivals_stop]
        complete = [j for j in measured if j.complete is not None]
        valid = status == 'COMPLETE' and len(complete) == len(measured) and bool(measured)
        flow = [j.complete-j.release for j in complete]
        duration = max(0, min(self.time,self.arrivals_stop)-self.measure_start)
        duration = duration or 1e-12
        raw_rate = statistics.mean(statistics.mean(v) for v in self.data.raw['arrival_calibration']['daily_count_samples_by_weekday_monday0'].values())
        machine_busy = {mid:sum(v for k,v in states.items() if k in MACHINE_BUSY) for mid,states in self.state_minutes['machine'].items()}
        # Machines have no shutdown calendar in this world: autonomous processing
        # continues off shift. Available machine time therefore equals calendar time.
        worker_busy = sum(sum(v for k,v in states.items() if k in WORK) for states in self.state_minutes['worker'].values())
        worker_available = sum(sum(v for k,v in states.items() if k not in ('OFF_SHIFT','ON_BREAK')) for states in self.state_minutes['worker'].values())
        active = [v/duration for v in machine_busy.values() if v>0]
        return {
            'activity':dict(peak_busy_machines=self.peak_busy_machines,concurrent_machine_minutes=self.concurrent_machine_minutes,distinct_moving_workers=len(self.moving_workers)),
            'demand_provenance':dict(raw_empirical_arrival_rate=raw_rate,
                baseline_calibration_multiplier=self.config.baseline_calibration_multiplier,
                arrival_load=self.config.arrival_load,
                effective_arrival_rate=raw_rate*self.config.baseline_calibration_multiplier*self.config.arrival_load,
                realized_arrival_rate=len(measured)/(duration/1440),rate_unit='jobs/day',
                mode='manual' if self.manual_jobs is not None else 'empirical_mix_scaled_intensity'),
            'machine_calendar_utilization':self.measure_integrals[2]/duration,
            'machine_available_utilization':self.measure_integrals[2]/duration,
            'machine_available_definition':'24/7 autonomous machine availability; identical to calendar denominator',
            'worker_available_utilization':worker_busy/worker_available if worker_available else 0,
            'worker_available_definition':'on-duty minutes excluding actual breaks; includes non-preemptive overtime',
            'per_machine_utilization':{k:v/duration for k,v in machine_busy.items()},
            'active_machine_utilization':statistics.mean(active) if active else 0,
            'bottleneck_utilization':max(active,default=0),
            'measurement_completed_in_window':self.measured_completions_in_window,
            'status': status if measured or status != 'COMPLETE' else 'NO_MEASUREMENT_JOBS',
            'config': asdict(self.config), 'dataset_sha256': self.data.digest,
            'source_sha256': self.data.raw.get('summary', {}).get('sha256'),
            'world_version': 'v0.3', 'engine_version': '0.1.0', 'engine_source_sha256': ENGINE_SOURCE_SHA256,
            'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'rng': 'PCG64/SHA256-128'},
            'measurement': {'start_min': self.measure_start, 'stop_min': self.arrivals_stop,
                            'denominator_min': duration, 'cohort': 'release in [start,stop); drain included in flow only'},
            'end_min': self.time, 'original_jobs': len(self.jobs), 'measurement_jobs': len(measured),
            'completed_measurement_jobs': len(complete),
            'mean_flow_min': statistics.mean(flow) if valid else None,
            'median_flow_min': statistics.median(flow) if valid else None,
            'p95_flow_min': float(np.percentile(flow, 95)) if valid else None,
            'mean_wip': self.measure_integrals[0]/duration,
            'mean_queue': self.measure_integrals[1]/duration,
            'machine_utilization': self.measure_integrals[2]/duration,
            'worker_utilization': self.measure_integrals[3]/duration,
            'throughput_jobs_per_day': self.measured_completions_in_window/(duration/1440),
            'queue_definition': 'ready execution batches + unreserved manual/transport requests',
            'utilization_denominator': 'all roster resource minutes in measurement window, including off-shift',
            'weekly': self.weekly, 'counters': self.counters, 'state_minutes': self.state_minutes,
            'jobs': [asdict(j) for j in self.jobs.values()],
            'batches': [asdict(b) for b in self.batches.values()] if self.config.trace else [],
            'machines': list(self.data.machines.values()),
            'workers': [{'id': w.id, 'department': w.department, 'kind': w.kind, 'home_node':w.home_node, 'skills': sorted(w.skills)} for w in self.workers.values()],
            'trace': {'initial':self.replay_initial, 'start_min':self.trace_start, 'snapshots':self.snapshots, 'end_min': min(self.time, self.trace_stop), 'intervals': self.intervals, 'events': self.log,
                      'nodes': self.data.graph['nodes'] if self.config.trace else []},
            'protocol': 'single_run_diagnostic; use experiment runner for inferential results',
        }
