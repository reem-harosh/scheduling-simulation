"""Read derived calibration without changing source files."""
from __future__ import annotations
import hashlib
import heapq
import json
from pathlib import Path


class InputError(ValueError):
    pass


class Calibration:
    def __init__(self, data, digest="manual"):
        self.raw = data
        self.digest = digest
        self.machines = {m['id']: m for m in data['machines']}
        self.models = {(m['item'], m['operation']): m for m in data['processing_models']}
        self.eligibility = {(m['item'], m['operation']): tuple(sorted(m['machines']))
                            for m in data['machine_eligibility']}
        self.templates = data['historical_jobs']
        self.profiles = {p['id']: p for p in data['worker_profiles']}
        self.rosters = data['rosters']
        self.graph = data['walking_graph']
        self.paths = {}
        self.adj = {i: [] for i in range(len(self.graph['nodes']))}
        for a, b, d in self.graph['edges_undirected']:
            if d <= 0:
                raise InputError('Graph edge length must be positive')
            self.adj[a].append((b, d))
            self.adj[b].append((a, d))
        self.validate()

    @classmethod
    def load(cls, path, source=None):
        content = Path(path).read_bytes()
        obj = cls(json.loads(content), hashlib.sha256(content).hexdigest())
        if source and hashlib.sha256(Path(source).read_bytes()).hexdigest() != obj.raw['summary']['sha256']:
            raise InputError('SOURCE_HASH_MISMATCH')
        return obj

    def validate(self):
        if not self.machines or not self.templates:
            raise InputError('Empty machines or demand templates')
        for m in self.machines.values():
            if m['id'] not in self.graph['service_nodes']:
                raise InputError('Machine service node missing')
            self.path(self.graph['service_nodes'][m['id']], self.graph['handoff_node'], m['department'])
        coverage = set()
        for dept, roster in self.rosters.items():
            for key in ('day_profiles', 'night_profiles'):
                for pid in roster[key]:
                    if pid not in self.profiles or self.profiles[pid]['department'] != dept:
                        raise InputError('WORKER_PROFILE_INVALID')
                    coverage.update(self.profiles[pid]['machines'])
        for job in self.templates:
            if job['quantity_proxy'] < 1 or not job['route'] or job['route'] != sorted(set(job['route'])):
                raise InputError('Invalid quantity/route')
            for op in job['route']:
                key = (job['item'], op)
                eligible = self.eligibility.get(key, ())
                if not eligible or key not in self.models:
                    raise InputError('INFEASIBLE_ROUTE')
                if not set(eligible) <= self.machines.keys() or not set(eligible) <= coverage:
                    raise InputError('NO_FUTURE_QUALIFIED_WORKER')

    def path(self, start, end, department):
        key = (start, end, department)
        if key in self.paths:
            return self.paths[key]
        nodes, boundary = self.graph['nodes'], self.graph.get('boundary_x', 1150)
        def allowed(n):
            return nodes[n][0] <= boundary if department == 'milling' else nodes[n][0] >= boundary
        if not allowed(start) or not allowed(end):
            raise InputError('WRONG_DEPARTMENT')
        heap, dist, prev = [(0, start)], {start: 0}, {}
        while heap:
            d, n = heapq.heappop(heap)
            if d != dist[n]:
                continue
            if n == end:
                seq = [n]
                while n != start:
                    n = prev[n]
                    seq.append(n)
                result = (d, list(reversed(seq)))
                self.paths[key] = result
                self.paths[(end, start, department)] = (d, list(reversed(result[1])))
                return result
            for nxt, length in self.adj[n]:
                if allowed(nxt) and d + length < dist.get(nxt, float('inf')):
                    dist[nxt], prev[nxt] = d + length, n
                    heapq.heappush(heap, (d + length, nxt))
        raise InputError('UNREACHABLE_PATH')
