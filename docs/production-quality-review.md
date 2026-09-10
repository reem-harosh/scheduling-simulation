# Production simulation — independent review record

User goal: score at least 8.5/10, with no more than three scored review rounds.

Weights: world/resource correctness 30%; data/calibration 15%; experiments/statistics 20%; visualization/usability 20%; verification/reproducibility 15%. Critical correctness failures cannot be offset by visual polish.

## Round 1 — 8.05 / 10

Independent reviewer inspected source and a completed source-calibrated controlled run, and independently ran the factory tests. Scores: world 8.4, data 8.8, experiments 8.0, UI 6.9, verification 8.2.

Prioritized notes:

1. P1: obtain rendered/interacted UI evidence.
2. P2: clear stale research charts when switching to a run.
3. P2: expose allowed calendar, distribution and elapsed-state information to policies.
4. P2: support retaining a logical batch across multiple transport trips.
5. P2: verify ownership handover across a nonpreemptive shift boundary.
6. P2: exercise the real experiment runner and make warm-up parameters inspectable/configurable.

These corrections were implemented for the next review. Single-run and experiment cancellation now remain labeled CANCELLED and cancelled replications are not cached as valid observations.

No claim of full production-grid completion is made. Public publication of internal project input files was denied by automatic approval review; this is handled through local ZIP import, not an upload workaround.
