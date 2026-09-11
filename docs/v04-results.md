# v0.4 actual results and acceptance record

**Research candidate only. Stationary baseline and successful-world acceptance remain open.**

## Reproducibility

Current engine source SHA-256: `5d2111cddf6f84ce9e3e084afb94148f0c21e16b7cc4938e608bdd48893400c9`.
Raw records preserve exact world identity, configuration, seeds, demand streams and KPI samples.
The world builder was rebuilt independently and its world JSON matched the current version exactly.
59 automated tests passed, including 18 independent review tests. JavaScript syntax validation passed.
No real browser interaction or appearance approval was obtained: the browser could not access the local server.

## Joint-capacity calibration

Current candidate lambda = 0.9247027030846621 jobs/calendar day. Quantity distributions were held fixed.
56 warm-up days, 56 measurement days, up to 730 drain days, three replications per point.
Flow time includes drain for the measurement release cohort; resource metrics and throughput use the measurement window.

| Arrival scale | Replications | Mean flow days | Mean WIP | Throughput jobs/day | Machine busy | Operator on-duty utilization | Setup on-duty utilization | WIP slope CI95 jobs/day |
|---|---|---|---|---|---|---|---|---|
| 0.75 | 3 | 39.89 | 14.96 | 0.5655 | 16.67% | 35.45% | 1.45% | [-0.02524092795866084, 0.4436082748974365] |
| 1.25 | 3 | 47.81 | 30.83 | 0.8214 | 30.36% | 65.61% | 2.52% | [-0.12438134645589988, 0.6629300992903668] |
| 1.0 | 3 | 53.06 | 23.12 | 0.6488 | 24.45% | 52.09% | 2.06% | [-0.20606437412987222, 0.7321414716355414] |

Completed raw calibration runs at this checkpoint: 9. All point status fields must be interpreted directly; completion of a drain does not establish stability.

At scale 1, average flow is approximately 53 days. Throughput below nominal arrivals and a wide WIP-growth confidence interval prevent stable-baseline approval. Setup utilization around 2% also falls short of the requested meaningful setup bottleneck. Sparse process families and giant empirical orders remain material issues; raising demand cannot fix all resource imbalances.

## Actual response surface

`world-v04-final-grid`: 3 arrival values × 3 quantity values × 2 policies × 2 replications = 36 COMPLETE runs.
This grid deliberately retains the **original machine-only candidate lambda 2.1830489787976326/day**, with 7 warm-up and 7 measurement days. It is not the current baseline surface or a stationary study. Its retained world is `research/world/world_machine_capacity_candidate.json`.
Every policy pair received identical demand at each point/replication. All nine paired SPT-minus-FIFO confidence intervals include zero. No algorithm advantage is established.
Older folders `world-grid`, `world-calibration` and `world-v04-final-calibration` are partial or superseded pilot archives, not current acceptance evidence. The obsolete machine-only long calibration was stopped after human offered-load analysis found 177% load.

## Replay evidence and independent review

The current joint-world trace records a peak of 17 simultaneously processing machines. The selected actual interval-log frame shows 11 processing machines, 16 workers on duty, and a setup employee walking along a recorded path. It is a rendering of simulation events, not a browser screenshot and not proof of satisfactory behavior across the whole horizon.

Independent reviewer `review_v04` confirmed grid completeness, common demand, absence of a proven policy advantage, correct finite-horizon status, and honest report labels. Its final read-only review covered the first six joint calibration runs (scales 0.75 and 1); later 1.25 results are not represented as independently reviewed. No new P0 defect was found. The reviewer accepted a research candidate, not a stable baseline or an 8.5 quality gate.

Open gates: quantity/time interpretation; warm-up and long-tail sensitivity; sustained WIP and throughput balance; rare-family and setup-resource utilization; interactive visual QA. These are substantive model-validation tasks, not cosmetic cleanup.

## Delivery boundary

Code and derived world tables are committed on local branch `calibrated-world-v04`. Automatic approval review rejected pushing that branch because publishing the code and derived research artifacts to GitHub was not explicitly authorized. No bypass or later push was attempted. The report and raw run archive form the concrete reviewable evidence for the next decision.

## Next modeling decision: time interpretation before further tuning

The source does not separate automatic mechanical time from manual standard time. Two defensible interpretations remain:

1. Treat the standard as mechanical time and add measured/manual engineering service separately (current explicit candidate). This risks double counting human work.
2. Treat the standard as total work and estimate its automatic/manual components using independent time-study evidence. The current reports do not identify that split, so choosing a fraction merely to increase utilization would be unjustified.

Similarly, giant inferred order quantities can be retained as whole execution lots (current baseline), or a future explicit lot-splitting policy can be studied. The demand generator must not silently reduce quantities or split them to improve an animation. Neither ambiguity can be resolved by raising lambda alone. Future sensitivity scenarios should preserve the original fixed quantity samples and report each time/handling interpretation as a separate world.
