"""PrintFlow: independent, synthetic print-shop discrete-event simulation.

Pure Python standard library. Also executed unchanged in a browser Web Worker
using Pyodide. The browser replays this engine's event trace; it does not choose
assignments or calculate production outcomes.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys

JOBS = [
    dict(id="A", name="חוברות ללקוח", source="הזמנה רגילה", quantity=100,
         release=0, due=25, color="#818cf8", operations=[("print", 8), ("bind", 6)]),
    dict(id="B", name="עלונים לאירוע", source="הזמנה רגילה", quantity=200,
         release=0, due=18, color="#2dd4bf", operations=[("print", 6)]),
    dict(id="C", name="עלונים למלאי", source="השלמת מלאי", quantity=500,
         release=0, due=None, color="#fbbf24", operations=[("print", 10)]),
    dict(id="D", name="חוברות דחופות", source="הזמנה דחופה", quantity=50,
         release=0, due=12, color="#fb7185", operations=[("print", 4), ("bind", 4)]),
]
MACHINES = [
    dict(id="P1", name="מדפסת 01", kind="print", position=[300, 185], dock=[300, 290]),
    dict(id="P2", name="מדפסת 02", kind="print", position=[640, 185], dock=[640, 290]),
    dict(id="F1", name="עמדת כריכה", kind="bind", position=[560, 440], dock=[560, 370]),
]
WORKERS = [
    dict(id="W1", name="עובד 01", skills=["print"], home=[125, 330], color="#38bdf8"),
    dict(id="W2", name="עובד 02", skills=["print", "bind"], home=[175, 330], color="#fb923c"),
]


def travel_path(origin, destination):
    """Walk along the central aisle; coordinates are schematic, not real meters."""
    if list(origin) == list(destination):
        return [list(origin)]
    points = [list(origin)]
    for p in ([origin[0], 330], [destination[0], 330], list(destination)):
        if p != points[-1]:
            points.append(p)
    return points


def normalized_options(raw=None):
    raw = raw or {}
    policy = raw.get("policy", "fifo")
    if policy not in ("fifo", "spt", "edd"):
        raise ValueError("Unknown dispatch policy")
    seed = int(raw.get("seed", 42))
    horizon = float(raw.get("horizon", 40))
    variation = float(raw.get("variation", 0))
    if not math.isfinite(horizon) or not 1 <= horizon <= 1000:
        raise ValueError("Run horizon must be between 1 and 1000 minutes")
    if not math.isfinite(variation) or not 0 <= variation <= 0.5:
        raise ValueError("Variation must be between 0 and 0.5")
    if not 0 <= seed <= 2**31-1:
        raise ValueError("Seed out of range")
    return dict(policy=policy, seed=seed, horizon=horizon,
                walking=bool(raw.get("walking", True)), variation=variation)


def simulate(raw=None):
    options = normalized_options(raw)
    rng = random.Random(options["seed"])
    # Sample in job/operation order, independently of scheduling decisions.
    durations = {(j["id"], i): round(d * rng.uniform(1-options["variation"],
                       1+options["variation"]), 6)
                 for j in JOBS for i, (_, d) in enumerate(j["operations"])}
    progress = {j["id"]: 0 for j in JOBS}
    positions = {w["id"]: w["home"][:] for w in WORKERS}
    pending = []
    tasks = []
    events = []
    completions = {}
    t = 0.0
    while len(completions) < len(JOBS):
        # All simultaneous completions release resources before new dispatches.
        ending = [x for x in pending if x["end"] <= t + 1e-8]
        for task in ending:
            pending.remove(task)
            progress[task["job"]] += 1
            positions[task["worker"]] = task["path"][-1][:]
            job = next(j for j in JOBS if j["id"] == task["job"])
            if progress[job["id"]] == len(job["operations"]):
                completions[job["id"]] = task["end"]
        candidates = [j for j in JOBS if j["id"] not in completions
                      and j["release"] <= t
                      and not any(x["job"] == j["id"] for x in pending)]
        if options["policy"] == "spt":
            candidates.sort(key=lambda j: (durations[j["id"], progress[j["id"]]], j["id"]))
        elif options["policy"] == "edd":
            candidates.sort(key=lambda j: (j["due"] if j["due"] is not None else math.inf, j["id"]))
        for job in candidates:
            op_index = progress[job["id"]]
            kind, _ = job["operations"][op_index]
            machine = next((m for m in MACHINES if m["kind"] == kind
                            and not any(x["machine"] == m["id"] for x in pending)), None)
            worker = next((w for w in WORKERS if kind in w["skills"]
                           and not any(x["worker"] == w["id"] for x in pending)), None)
            if machine is None or worker is None:
                continue
            path = travel_path(positions[worker["id"]], machine["dock"])
            distance = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
            walk = round(distance / 180, 6) if options["walking"] else 0.0
            start = round(t + walk, 6)
            end = round(start + durations[job["id"], op_index], 6)
            task = dict(job=job["id"], operation=kind, index=op_index,
                        machine=machine["id"], worker=worker["id"], assigned=t,
                        start=start, end=end, walking=walk,
                        duration=durations[job["id"], op_index], path=path)
            tasks.append(task)
            pending.append(task)
            if walk > 0:
                events.append(dict(time=t, type="walk", job=job["id"],
                                   machine=machine["id"], worker=worker["id"]))
            events.extend([dict(time=start, type="start", job=job["id"],
                                machine=machine["id"], worker=worker["id"]),
                           dict(time=end, type="finish", job=job["id"],
                                machine=machine["id"], worker=worker["id"])])
        if len(completions) == len(JOBS):
            break
        if not pending:
            raise RuntimeError("No feasible action: model deadlock")
        t = min(x["end"] for x in pending)
    for job in JOBS:
        events.append(dict(time=completions[job["id"]], type="complete", job=job["id"]))
    precedence = dict(finish=0, complete=1, walk=2, start=3)
    events.sort(key=lambda e: (e["time"], precedence[e["type"]], e["job"]))
    makespan = max(completions.values())
    end_time = min(makespan, options["horizon"])
    finished = [j for j in JOBS if completions[j["id"]] <= end_time + 1e-8]
    flow = [completions[j["id"]] - j["release"] for j in finished]
    complete = len(finished) == len(JOBS)
    metrics = dict(completed=len(finished), total=len(JOBS), complete=complete,
                   mean_flow=statistics.mean(flow) if complete else None,
                   completed_mean_flow=statistics.mean(flow) if flow else None,
                   makespan=makespan if complete else None,
                   observed_until=end_time,
                   total_tardiness=sum(max(0, completions[j["id"]]-j["due"])
                                       for j in finished if j["due"] is not None))
    for group, key in ((MACHINES, "machine"), (WORKERS, "worker")):
        metrics[key+"_utilization"] = {
            r["id"]: sum(max(0, min(end_time, x["end"])-x["start"])
                         for x in tasks if x[key] == r["id"])/end_time
            if end_time > 0 else 0 for r in group}
    return dict(options=options, jobs=JOBS, machines=MACHINES, workers=WORKERS,
                tasks=tasks, events=events, completions=completions,
                end_time=end_time, metrics=metrics)


def simulate_json(options_json="{}"):
    return json.dumps(simulate(json.loads(options_json)), ensure_ascii=False)


def run_replication_json(options_json, index):
    options = json.loads(options_json)
    options["seed"] = (int(options.get("seed", 42)) + int(index)) % (2**31)
    result = simulate(options)
    return json.dumps(dict(replication=int(index)+1, seed=options["seed"],
                           **result["metrics"]), ensure_ascii=False)


if __name__ == "__main__" and sys.platform != "emscripten":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=["fifo", "spt", "edd"], default="fifo")
    parser.add_argument("--no-walking", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--variation", type=float, default=0)
    parser.add_argument("--horizon", type=float, default=40)
    args = parser.parse_args()
    print(simulate_json(json.dumps(dict(policy=args.policy, walking=not args.no_walking,
                                       seed=args.seed, variation=args.variation,
                                       horizon=args.horizon))))
