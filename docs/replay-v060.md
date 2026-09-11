# Replay visibility and run progress — v0.6.0

## User-visible changes

| Request | Behavior |
| --- | --- |
| Visible queues and parts | Counted material groups appear at their physical input/output location, in machines, with carrying workers, or in the shared pool. Loading, cycle exchange, unloading, carrying and aggregate lift movement animate against the replay clock. |
| Detailed timeline and job status | A job/resource Gantt has 2-hour, 8-hour, day and full-trace views. The full-trace view is a compact activity range (including intervening waits); clicking opens detailed intervals. A selected-job filter reduces crowding. Selecting a segment seeks to it; selecting a job shows total quantity, before/in-machine/after counts per operation and every current part range/location. |
| Active-only sidebar | Jobs must be released and unfinished; completed/split batches are hidden. Idle/off-shift/on-break workers and idle machines are absent. Seeking backwards restores entities active at that time. The physical floor still includes stationary machines and on-shift workers as context. |
| Replay state next to the floor | The resource strip now belongs to the replay map and reads the displayed time. The inspector remains alongside the map and timeline on desktop. Computation telemetry does not overwrite replay time or cards. |
| Worker–machine links | Solid lines show current service or travel to a machine. Dashed lines show continuing lot responsibility, including multiple owned machines, while the owner remains on duty or busy. Current service labels identify the worker. |
| Progress and ETA | Both the single-run area and research area display task progress, phase, event/work counters, completed/total runs, cache hits and an evolving ETA. Preparation is indeterminate. Completion reaches 100% after saving; cancellation/error does not pretend completion. |

## Data semantics

- `trace.material_version = 1` records detached material deltas at settled DES timestamps, plus final resource states for the trace boundary. Replay indexes each batch history; arbitrary backwards seeks do not reuse later state.
- Part ranges are half-open in JSON. Displayed ranges are inclusive. A visual token represents the displayed quantity, not an additional simulated part.
- Quantities change atomically at the end of manual service. The motion inside that service is illustrative; it does not introduce extra load/unload events. Loading moves only the next cycle quantity. Cycle exchange depicts outgoing and incoming quantities separately.
- During a multi-trip transfer, delivered parts, carried parts and parts left at the source remain distinct. The baseline does not split the logical production lot.
- The lift is an aggregate shipment in the engine. The replay does not claim per-part lift arrival times that the model never simulated.
- Unassigned work remains in the shared pool, or at the previous machine if that is its actual location. No fictitious machine-specific reservation/queue is created.
- The progress fraction uses completed part-operation work inside a run and completed replications across a task. ETA extrapolates observed rates and recent run durations; it is an estimate, especially across differing grid loads. Fast runs can finish before enough evidence exists for an ETA.
- Scheduling, demand, routing and random draws are unchanged by this feature. Old files remain viewable, but require a fresh run for the material ledger and complete transport timeline.

## Validation

- 86 Python tests pass, including new whole-range conservation, 60/60/5-unit transport trips, a replay beginning during warmup work, unchanged trace-on/trace-off job results and counters, final idle resource states, and 8-run grid/cache progress.
- Node UI contract tests pass: separate run/experiment exports, live compatibility, precise material counts, backwards seeking, completed-job filtering, Gantt rendering, both progress bars and 404 recovery.
- Full world, seed 20260909, one warmup day and one measurement day, two replay days, 30-day drain cap: COMPLETE. There are 7,106 material frames. All 94,510 active-job/frame checks cover exactly the original range without gaps or duplicate parts, including carrying and lift states.
- A seven-day measurement run with one warmup day (same world and seed, trace off) completed 34,710 part-operations. Observed locally: 33 telemetry updates, 29 with ETA; total about 15.9 seconds. This is a verification observation, not a runtime promise.
- Browser replay checks cover the selected-job material table (338 = 240 before + 1 in-machine + 97 after the first operation), focused Gantt, detailed timeline activation and replay-synchronized resource cards. The supervised preview serves saved replay data; backend computation/progress was checked through Python/HTTP contracts rather than that static preview.

## Running the update

Stop the previous Python server, update the checkout, restart `python run_factory.py`, and verify UI/server **0.6.0**. In Codespaces use `python run_factory.py --host 0.0.0.0 --no-browser` and open forwarded port 8000. Run a new simulation, then use the replay controls. The old hosted PrintFlow demo is a separate static demonstration and has not been redeployed by this change.
