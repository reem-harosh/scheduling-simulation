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

from pathlib import Path
import copy
import re


def validate_scenario(scenario):
    """Validate the small print-shop model before scheduling or rendering it."""
    model = copy.deepcopy(scenario)
    for group in ("jobs", "machines", "workers"):
        rows = model.get(group)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"Scenario requires a nonempty {group} list")
        ids = [row.get("id", "") for row in rows]
        if any(not isinstance(i, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", i) for i in ids) or len(set(ids)) != len(ids):
            raise ValueError(f"Invalid or duplicate IDs in {group}")
        for row in rows:
            if not isinstance(row.get("name"), str):
                raise ValueError(f"Missing name in {group}")
    if set(m["id"] for m in model["machines"]) & set(w["id"] for w in model["workers"]):
        raise ValueError("Machine and worker IDs must be distinct")
    for row in model["machines"] + model["workers"]:
        for field in (("position", "dock") if "kind" in row else ("home",)):
            point = row.get(field, [])
            if len(point) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in point):
                raise ValueError(f"Invalid coordinates: {field}")
    for row in model["jobs"] + model["workers"]:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", row.get("color", "")):
            raise ValueError("Colors must use #RRGGBB")
    for m in model["machines"]:
        if m.get("kind") not in ("print", "bind"):
            raise ValueError("This print-shop version supports print and bind operations")
    for w in model["workers"]:
        if not w.get("skills") or any(k not in ("print", "bind") for k in w["skills"]):
            raise ValueError("Invalid worker skills")
    for j in model["jobs"]:
        if j.get("release") != 0:
            raise ValueError("This initial scenario requires every job to be available at time 0")
        if not isinstance(j.get("source"), str) or not isinstance(j.get("quantity"), int) or j["quantity"] <= 0:
            raise ValueError("Each job needs a source and positive integer quantity")
        due = j.get("due")
        j["due"] = due
        if due is not None and (not isinstance(due, (int, float)) or not math.isfinite(due) or due < 0):
            raise ValueError("Invalid due date")
        if not j.get("operations"):
            raise ValueError("Every job needs at least one operation")
        for operation in j["operations"]:
            if not isinstance(operation, (list, tuple)) or len(operation) != 2:
                raise ValueError("Operations must contain kind and duration")
            kind, duration = operation
            if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
                raise ValueError("Operation duration must be finite and positive")
            if not any(m["kind"] == kind for m in model["machines"]) or not any(kind in w["skills"] for w in model["workers"]):
                raise ValueError(f"No feasible machine and worker for {kind}")
    return model


def load_scenario(path=None):
    return validate_scenario(json.loads(Path(path or Path(__file__).with_name("scenario.json")).read_text(encoding="utf-8")))


DEFAULT_SCENARIO = load_scenario()


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


def simulate(raw=None, scenario=None):
    model = validate_scenario(DEFAULT_SCENARIO if scenario is None else scenario)
    JOBS, MACHINES, WORKERS = model["jobs"], model["machines"], model["workers"]
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
    return dict(options=options, scenario_name=model.get("name", "בית הדפוס"), jobs=JOBS, machines=MACHINES, workers=WORKERS,
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
