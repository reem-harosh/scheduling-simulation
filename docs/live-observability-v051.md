# Observability update v0.5.1

World parameters remain v0.5: no processing-time inflation, staffing cuts or demand changes.

## Implemented
- WorldSimulation emits detached read-only current-state snapshots at most twice per wall-clock second, plus initial/final snapshots. No observer access to future events or RNG, and no sampling in observation.
- UI polls actual task state every 900 ms. Displays warmup/measurement/drain, simulated time, wall time, achieved simulation minutes per second, event count, algorithm, replication and scales. Window progress is not reported as total-run completion: drain has an unknown duration and shows remaining jobs.
- Counts separate regular operators from setup specialists; availability uses the engine's actual availability predicate. On-shift includes breaks. Machines are separated into automatic processing, setup, manual handling, waiting and idle. These are instantaneous counts, distinct from aggregate experiment utilization.
- Live floor snapshots, selectable machine/setup metadata and active-job table. Job drilldown lists per-operation completed unload quantities, current state, owner and active cycle quantity when relevant. Whole-batch routing is unchanged.
- Replay start now records per-operation counts. New replay inspector reconstructs counts at the selected time from this initial state plus past unload events. Older files lacking an initial count report unknown rather than using final-run counts.
- Setup transitions expose from/to class and setup type in active and recorded machine intervals. Existing files retain whatever metadata they originally recorded.
- Grid points appear after each completed scenario. Loading a replay no longer clears an existing surface. Single runs can display a single point (not a fabricated response surface); algorithm choices follow the loaded data. Corrected surface alpha color syntax and invalid-value handling.
- Last-grid button loads the locally saved experiment, with the packaged v0.5 reference grid as fallback. Dataset/code identities are retained; this archival grid is not a new v0.5.1 experiment.
- Replay controls and file loading disabled during computation to avoid mixing live and recorded clocks.

## Engineering decision
Increasing processing durations solely to exceed 50% utilization is not calibration evidence. Cutting operators can increase blocked machine time while reducing productive utilization. Keep baseline frozen; study processing-speed factors and per-floor/day/night staffing separately with fixed demand, and compare processing utilization, manual-service delays, WIP, throughput and flow time. No staffing optimum or long-term stationarity claim is made by this update.

## Verification and limitations
73 Python tests pass, including observer-on/off equality of demand, jobs, flow and utilization, and immutable partial-surface snapshots. Production JavaScript syntax and a DOM/canvas-adapter integration test pass using actual simulation output and the 25-point reference grid (50 algorithm rows). Test checks grid retention after replay load and job operation details.

A full browser visual test was attempted but could not run: Chromium was absent and its download timed out. The adapter test is not browser layout/pointer validation. Live display is periodic snapshots, not smooth real-time event streaming. Setup task duration remaining is not exposed as a known exact future value. No new 100-run calibration was needed or claimed; observer neutrality is tested on a bounded deterministic fixture.

## Run
Extract the release into a new folder, then:

```
python -m pip install -r requirements.txt
python run_factory.py
```

Open http://127.0.0.1:8000/production/ . Use Run for a single run; use Grid for a Cartesian experiment. Existing server processes must be stopped and restarted to use the new backend.
