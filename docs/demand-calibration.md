# Demand calibration and replay

Historical first-report counts are a demand proxy, not an observed complete
release process. The engine preserves empirical item/route/quantity distributions
and exposes an independent `baseline_calibration_multiplier`. Arrival load is
relative to that factor. Every result records nominal raw/effective jobs per day,
realized arrivals, load and factor. Manual inputs are labeled separately.

## Reproduce

```bash
python -m factory.load_calibration --factors .25 1 2 4 --days 42 --warmup 14 --workers 3
python -m factory.load_calibration --factors .25 .5 --replication-start 100 --replications 8 --days 364 --warmup 182 --out results/holdout
python tools/confirm_operating_point.py results/holdout
```

Screening never installs a baseline. The separate confirmation uses eight
independent replication slopes and completion-minus-arrival rates. It requires
source/configuration consistency, sufficient completions, real concurrent
activity in each department, moving workers, mean WIP >=3 and nonzero queues.
Practical margins are explicit: upper drift CI <= max(.02 jobs/day, 5% arrival
rate), and the flow-difference CI lies within ±10% arrival rate. These are
finite-horizon equivalence criteria, not proof of infinite-horizon stationarity.
The 70–85% bottleneck target ranks passing candidates; it is not a gate.

Within-run weekly OLS bands are heuristic diagnostics, never treated as
independent observations for baseline confirmation. Rejected points remain
rejected; missing windows and event caps are not evidence of stability.

The server loads `results/load-calibration/operating_point.json` only when status
is CALIBRATED and source/data hashes match. Otherwise the UI explicitly labels
the historical baseline as uncalibrated. Do not rename a rejected result.

## Replay and denominators

The system still starts empty. The replay records the measurement window after
burn-in, retains original interval starts for correct motion interpolation, and
captures cumulative part/batch history at its boundary. Day workers receive real
standby graph locations. Idle staff remain visible; shared-location glyphs fan
out with lines to the actual location, without changing engine positions.

Calendar machine utilization divides busy minutes by elapsed measurement time.
Machines have 24/7 autonomous availability in this world, so available-machine
and calendar-machine denominators coincide. Worker available utilization excludes
actual off-shift and break minutes and includes nonpreemptive overtime. Completion
cohort flow times include draining; throughput, queues and utilization do not.

Data, raw inputs, calibration artifacts and production replays remain outside git.
The original PrintFlow demo and published Site have not been replaced.
