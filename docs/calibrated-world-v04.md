# Calibrated production world v0.4

Status: implemented research candidate; **no stationary baseline is approved yet**.
The current world must not inherit the v0.3 quality score or operating-point approval.

## What changed and why

The old release model resampled first-report daily counts and historical item templates. Item–machine eligibility was narrow, setup occupied only a machine, and each transport trip could silently become another execution lot. The new model separates route operations, capability families and physical machines. It generates demand before the simulation and pools eligible machines. The baseline retains an entire job quantity through every operation.

The new entry point is `python run_factory.py`. It loads `research/world/world.json` by default. The original engine and calibration loader remain for explicit historical reproduction. Run `python run_factory.py --calibration data/calibration/Final_Baseline_Calibration.json` for the old world, whose old demand conclusions do not apply to v0.4.

## Source analysis and family construction

Source: `production_reports.xlsx`, sheet `FTimeProductionStatistic`, SHA-256 `17164060f291c604cc8602ff6f8eb12611c097d09c59c019dbc58986a51a61d8`.

| Classification | Finding or decision |
|---|---|
| Observed | 26,222 reports, 365 production-order identifiers. All report types are labelled production. |
| Derived | Exclude all reports for the 21 serial-number jobs, retaining the prior non-serial scope; exclude one zero-quantity job. 343 usable jobs, 164 items. |
| Derived | Group item reports by ordered operation number and map each stage to its modal work center. No item-stage has conflicting work-center families in this source. |
| Derived | Four observed process families: Milling, Turning, Honing, WireEDM. No Laser or Inspection process is invented as an observation. |
| Inferred | The ordered union of reported item stages is a route proxy. It may merge order variants or omit unreported processes. It is not a certified complete technological route. |
| Derived / engineering choice | Preserve all 19 distinct route patterns as 19 synthetic product families. Six patterns cover 80.47% of jobs; ten cover 91.84%; all nineteen cover 100%. Forcing 20, 25 or 30 would introduce unsupported subdivisions. |
| Engineering choice | Keep rare patterns rather than truncate them. There are 112 single-stage jobs and 28 jobs with more than five stages. The resulting 86 distinct family-operation stages preserve repeated capability families. |

`research/world/route_coverage.csv` gives the complete rank/coverage table. `source_analysis.png` shows the full quantity histogram, ECDF and cumulative route coverage. ECDF is the fraction of observations at or below each quantity; the log x-axis makes small orders and the long right tail visible together. No distribution fitting or clustering was needed to justify an empirical model.

Quantity is the **maximum sum of good reported quantity over the operations of an order**. This is an inferred production quantity proxy, not a measured customer-order quantity. Exact selected-row duplicates are removed before this calculation. No tail trimming is applied. Across 343 jobs: mean 2,397.71; median 475; SD 5,776.19; Q1 111; Q3 2,017; P95 9,733.70; maximum 50,300. Each family retains its own empirical samples, including sparse families. Pooling into a route family intentionally discards historical item identity and its within-family quantity–time correlation; this limitation should be tested before drawing factory-specific conclusions.

## Processing matrix and physical resources

There are 68 physical machine locations from the existing map. Their IDs are replaced with M01…M68. The allocation is **an engineering design**, not the historical machine inventory by process: 44 Milling, 20 Turning, 2 Honing and 2 WireEDM. With a minimum of two machines per family, remaining machines are allocated to the currently largest expected work per machine. This is an offline capacity-pooling design based on fixed family probabilities and quantities. Demand never sees this decision during a run.

For each historical item and stage, use the median positive reported instruction standard, falling back to net reported minutes/good quantity when no standard exists. Pool stage medians across items sharing a route pattern. The source standards are not autonomous-machine measurements: across reports their median is 8.5 minutes/unit, while net/quantity has median 22.25. Human time and reporting effects may remain in either. Adopting the standard proxy as mechanical time and then adding handling is an explicitly provisional assumption that can overstate total work. `source_evidence.json` and `processing_source_evidence.png` expose this limitation.

The factorization is `base(operation family) × complexity(product family) × stage modifier / machine speed`. Complexity is the geometric mean of a family's normalized stage times; stage modifiers reproduce the pooled stage times. These factors are a transparent decomposition, not independently identified causal estimates. Synthetic speeds are evenly spaced in log space from exp(-0.15) to exp(0.15) inside each family. No machine-speed clustering is claimed.

The frozen matrix contains 2,284 eligible family–operation–machine entries. Every automatic cycle uses `units × fixed unit time`, without sampling or subtracting human handling. A default cycle processes one unit; load/unload/change handling is additive. Cycle capacity is a scenario parameter, not execution lot splitting. To change machine counts, eligibility, shifts or roster size, edit a copy of the world JSON consistently and reconstruct `World`; cache identity includes effective public parameters. Invalid eligibility and incomplete setup transitions fail validation.

## Setup and workforce

Each operation receives one of three systematic synthetic setup classes within its machine family. The class is assigned by family rank and route position; it is not a tooling inference. The full transition matrix includes INITIAL. Same class means no setup; adjacent classes use Minor, separated classes Major, INITIAL uses Medium. Triangular minutes are Minor (8,15,25), Medium (15,30,45), Major (30,50,80). Both a different operation on the same machine and a move to another machine consult the actual previous machine configuration.

Four permanent setup employees perform setup and their own walking only. Two cover day shifts and two night shifts; no dynamic staffing. Regular operators: fourteen day and seven night. These are pooled synthetic qualifications, not a claim of historical universal skills. The engineering shift calendar is six days/week, 07:00–19:00 and 19:00–07:00, with 70 break minutes/shift. Manual tasks finish nonpreemptively if a shift or break boundary occurs; no new task starts off shift. Machine processing continues off shift and can wait for unload.

Operation ownership covers job + execution batch + operation. The owner is released during automatic processing and may serve other machines. A new operation gets new ownership even on the same machine. When the old owner is no longer on the relevant shift, a logged formal handoff permits a qualified successor. No worker can perform two manual tasks at once. Transport trips carry at most 60 units, but reunite as one execution lot before setup/loading starts. Trips are counted separately from lot splits.

## Routing, dispatch and policy access

FIFO orders the pooled ready queue; SPT is an alternative dispatch rule. ECT evaluates every eligible machine using public deterministic remaining processing, expected handling/setup, transport and an approximate setup-resource delay. Earlier ready jobs create virtual queued workload within a decision call. A busy-machine preference remains a plan: there is no target reservation until an idle machine and the first real service resource can be committed. Existing human requests are served before a new allocation is revalidated.

ECT may intentionally wait for a faster busy machine when it predicts earlier completion than a slow idle machine. This is not stale machine locking. Every event opens another decision and every new operation routes independently. `WORK_CONSERVING` retains the earlier alternative that only compares immediately serviceable machines; `FIFO` and `ECT` now use the all-eligible comparison.

ECT is an estimate, not an optimal scheduling algorithm. Setup-worker delay is a workload approximation; exact future stochastic durations and full future shift-driven congestion are not known. Virtual queued workload adds expected setup contributions without solving a globally consistent setup sequence. Those approximations are visible in candidate records. The engine validates actions; policies receive detached public snapshots and cannot access RNG state or the event heap. Register a policy factory in `factory.world_policies.REGISTRY`; implement `decide(state)` returning allocate actions. Split actions are rejected by the baseline, leaving the original engine as an architectural reference for future explicit splitting policies.

## Demand and capacity calibration

Homogeneous Poisson demand uses exponential interarrival times. First-report timestamps are not accepted as evidence of an hourly or weekday customer-arrival process. A homogeneous engineering baseline is preferable to claiming a fitted NHPP from those timestamps.

Demand is generated independently before any factory events. The RNG keys contain seed, replication and namespace, not algorithm, factory state or result scenario name. Family probabilities are fixed. Quantity scaling rounds the same underlying empirical draw; arrival scaling only changes exponential time scaling. Full demand streams and SHA-256 digests are retained for cross-policy equality checks. Human randomness uses separate logical event keys.

Processing-only offered load suggests 2.18305 jobs/calendar day at approximately 75% of the largest family load. This is **not a valid joint-resource capacity result**. With one unit per cycle, expected manual work is 9,489.54 minutes/job, while scheduled regular capacity is 11,700 minutes/calendar day before walking and transport. The processing-only candidate therefore implies 177% offered manual load.

The current joint-capacity candidate is **0.92470 jobs/calendar day**, corresponding to 75% offered manual load before walking and transport. Quantities were not changed. This remains `JOINT_CAPACITY_CANDIDATE_NOT_CONFIRMED`, not a validated stationary baseline. The original machine-only candidate is retained in `world_machine_capacity_candidate.json` so overload experiments remain reproducible. Values of approximately 30–50 jobs/day would be incompatible with this quantity/time interpretation and this staffing.

## Experiments and interpretation

`python tools/run_world_experiments.py grid` runs the configured Cartesian product with multiple replications. Options include `--scales`, `--replications`, `--days`, `--warmup`, `--algorithms`, `--world` and `--output`. The browser also exposes grid values and replication count. Every run persists configuration, world/code hashes, algorithm, seed, replication, lambda, demand stream, jobs/flow times, operation processing totals, worker statistics, per-family utilization, queue integrals, setup waiting samples, WIP windows and unfinished ages. Cache keys depend on configuration and source/world identity.

Flow time is measured for the release cohort in the measurement interval and includes drain. Utilization, WIP and throughput use only the observation interval. Incomplete cohorts yield null flow summaries, not a completed-only mean. Drain does not prove stability. WIP-slope intervals are computed across independent replications; finite-window stationarity remains unconfirmed even when growth is not detected. Student-t intervals quantify replication-mean uncertainty; with two or three replications they can be very wide and are exploratory. Algorithm differences use paired replications.

The 3D response surface uses actual point estimates, Arrival × Job Size × Mean Flow Time. It is explicitly a finite-horizon cohort surface. Invalid cohorts are gaps; growth flags are preserved. Do not present it as a steady-state response surface until warm-up and stability are established. An early 3×3, two-algorithm, two-replication grid is a 36-run implementation study, not a high-precision statistical comparison.

## Validation and open gates

Independent tests cover repeated operations, exact processing totals, no transport-induced lot splitting, same-machine setup, handoff, human exclusivity, detached snapshots, all-eligible routing, CRN, service integration, grid completeness, cache identity and censoring. Current run evidence and the final review are recorded separately in `v04-results.md`.

Open acceptance gates are: a statistically supported stable operating point, trustworthy production-quantity and mechanical-time interpretation for factory-specific claims, sensitivity to rare families and giant orders, and visual replay QA. The cloud browser could not access this session's local server, so browser appearance and interactive replay have not been visually approved. Backend HTTP tests do not substitute for this.

This implementation is a research candidate. It must not be described as fully satisfying the user's successful-world criteria merely because tests pass.
