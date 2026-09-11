# Multi-agent review — Scheduling Simulation v0.5.3

Review date: 11 September 2026. Baseline: `653497b4a052806585b756fa30ee28ee0cd17aa4` on `main`.

Five independently executing specialist agents reviewed the same checkout. A separate team lead reproduced findings, implemented changes, reconciled evidence, and retained responsibility for acceptance. Scores are expert judgments on the inspected research prototype, not statistical estimates, certifications, or a claim of full real-factory validation.

## Scope and stopping rule

The default `research/world_v05/world.json`, Python `WorldSimulation`, browser production interface and their research runner were reviewed. Legacy PrintFlow/v0.3 functionality was distinguished from the current default. The world has 18 part families, 50 operations, 68 physical machines, 36 regular employees and four setup specialists. Original source spreadsheets and the complete approved master specification were not available in this checkout. Visible user requirements and current implementation documents supplied the acceptance context.

The user requested at most three evaluation rounds, stopping at a weighted score of 8.5. Weights were fixed before review: logic 30%, data 20%, QA 20%, visualization 15%, UX 15%. These user-facing weights take precedence over the different legacy reviewer rubric in `reviewer-instructions.md`.

| Specialist | Weight | Iteration 1 | Iteration 2 | Iteration 3 |
|---|---:|---:|---:|---:|
| Logic and operations research | 30% | 7.6 | 8.7 | 8.7 |
| Data and analytics | 20% | 7.3 | 8.4 | 8.6 |
| QA and requirements | 20% | 7.4 | 8.6 | 8.6 |
| Visualization | 15% | 6.7 | 8.1 | 8.3 |
| UX/UI | 15% | 6.0 | 8.0 | 8.4 |
| **Team lead weighted result** | **100%** | **7.13** | **8.43** | **8.56** |

The threshold was reached in the third and final round. Approval is limited to the reviewed research-prototype scope. Missing live-browser, Codespaces and master-specification evidence remains open; it is not converted into an implied pass.

## Iteration 1: findings and prioritized actions

The baseline passed all 75 Python tests. Passing those tests did not establish absence of defects: the specialists reproduced behaviors outside their coverage.

### Visualization — 6.7

Strengths: coherent dark palette, retained machine geometry, trace-derived worker motion, selection, zoom and seeking. Current Chrome replay inspection confirmed populated machines and worker dots.

Priority order: P1 missing visible queues; P1 chart diamonds conflated precision and stability; P2 tiny family subtitles, indistinguishable worker roles, incomplete legend, missing numeric chart scales. A bounded screenshot was not used as evidence of system-wide loading or stationarity.

### Logic and operations research — 7.6

Strengths: policy-independent demand, sequential route conservation, physical eligibility, exclusive manual workers, floor-local paths and a valid processing-only lower bound for the unsplit model.

Priority order: P1 different operations sharing a setup class could skip setup; P1 a simulation starting during a shift initialized no active workers; P2 validation occurred after demand generation; P2 research evidence was too short for stationary-performance claims.

The unchanged default NF12 route contains OP040 and OP050 in Turning-B. The quantity-one diagnostic finished at 119.7863 minutes with no setup between these distinct operations. At an 08:00 start the baseline initialized zero regular workers and zero setup specialists instead of 24 and two. Midnight had the corresponding missing prior-night shift.

### Data and analytics — 7.3

Strengths: matched demand hashes, clearly separated measurement-window resource integrals and drained release-cohort flow, explicit synthetic provenance, and no silent completed-only cohort average.

Priority order: P1 single-replication descriptive means disappeared from secondary summaries; P1 service utilization was described ambiguously as occupancy; P1 historical code identities and missing raw evidence needed explicit disclosure; P2 short-window stability diagnostics, uncertainty and setup-wait censoring needed clarification.

The historical grid contains 25 points × two algorithms × two replications = 100 completed runs. Mean relative CI half-width is approximately 55%; all weekly WIP slopes are unavailable in the three-day measurement window. These results cannot establish general algorithm superiority. World identity matches the current world, but the historical code identity differs.

### UX/UI — 6.0

Strengths: Hebrew controls, run/replay distinction, version status, warmup/replications, cancellation and explanatory caveats.

Priority order: P1 export selected a summary instead of the complete replay; P1 live sidebar could be empty or stale; P1 imported settings differed from displayed controls and first-result seeking remained disabled; P1 cancellation/error mixed live and replay state; P2 inaccessible file input and unclear grid cost.

Actual JavaScript execution in a DOM adapter reproduced the export, seek and configuration mismatches. These were not presented as full browser end-to-end tests.

### QA and requirements — 7.4

Strengths: meaningful controlled tests for part conservation, manual exclusivity, floor paths, axis capability, shared lift, demand reproducibility, censoring and cache identity.

Priority order: P1 actual NF12 setup requirement failure; P1 invalid configuration reached demand generation before rejection; P2 malformed API container types and preparation bounds; P2 unverified cloud access and incomplete original-spec traceability. No P0 defect was identified in the bounded review.

## Iteration 2: implemented corrections and independent rechecks

1. **Operation-change setup:** a distinct operation with a zero class transition now receives the world's lightest strictly positive configured setup tier. In this world it is Minor, triangular (8, 15, 25) minutes. This is a documented engineering assumption, not an empirical fit. Repeating the same operation retains zero continuation setup. The full NF12 diagnostic now includes the fifth setup and completes at 135.9913 minutes, with quantity conserved.
2. **Calendar startup:** workers, including specialists, are established before initial calendar events. Already-active day/night shifts and residual breaks are initialized at time zero. Tests cover 08:00, midnight, 10:10 and the world's actual Friday shutdown. The working-weekday convention is preserved.
3. **Validation:** configuration is validated before generation; finite numeric fields and integer seed/replication/event limits are checked. API request/config objects and service warmup/scales bounds receive structured rejection.
4. **Statistics:** one finite replication retains its descriptive mean with an unavailable CI. Machine automatic processing, service, occupied time and waiting are distinguished. Setup-wait count and its service-start cohort are documented. Short-window stability and insufficient replication evidence are explicit.
5. **Provenance:** the saved-surface API compares code/world identities and the UI warns about incompatible historical results. Historical experiments remain unchanged.
6. **UX and visualization:** separate replay/experiment downloads, synchronized controls, live entity lists, consistent terminal-state handling, actual family ready-queue counts, specialist squares, readable labels, a complete state legend, numeric vertical chart ticks, accessible upload and predicted grid run count.

All 83 Python tests passed, including eight new behavioral regression tests. Logic and QA independently repeated key setup, calendar, validation and HTTP cases. Data independently reconciled the occupancy and one-replication examples.

The team lead's second-round result was 8.43. Remaining actionable UX defects were hidden live-job details and endless retry after a task ceased to exist. These led to the final round.

## Iteration 3: final corrections and verification

Live-job selection now displays identity, family, quantity, elapsed time and per-operation unload counts directly in the inspector. HTTP 404 ends recovery and releases controls; transient connection errors continue retrying the existing task. Chart points have a keyboard selector, tabs support arrow/Home/End keys, and horizontal 3D scales have numeric labels.

The extended `tests/test_production_live.cjs` invokes the actual export handlers and round-trips the serialized event replay while a grid is loaded. It also verifies separate experiment export, synchronized controls, live workers/jobs, ready-queue display and terminal-404 recovery. It passed independently under the UX reviewer. This is genuine JavaScript handler verification with a DOM/canvas adapter, not a claim that a browser download completed.

## Fresh current-code evidence

Reproduce with `python tools/run_review_verification.py`. Default configuration: 3 days warmup, 3 measurement days, baseline arrival/quantity scales, seed 20260911, three paired replications, FIFO and SPT. The warmup is a diagnostic choice; it was not statistically validated.

All six runs completed their measurement-release cohorts. The repository includes their raw results and summary in `research/multi_agent_review/`, with SHA-256 identities in `manifest.json`. The data reviewer verified all seven result-file hashes and twelve factory source-file hashes; recomputed per-job flow; checked matched demand; and reconciled service plus waiting with occupied utilization.

| Finite-horizon diagnostic | FIFO | SPT |
|---|---:|---:|
| Independent replications | 3 | 3 |
| Mean flow, hours | 60.72 | 60.65 |
| Nominal 95% CI, hours | 48.63–72.80 | 50.17–71.13 |
| Mean WIP, jobs | 34.80 | 34.73 |

The paired SPT-minus-FIFO difference is −3.98 minutes, with nominal 95% CI −103.93 to +95.97 minutes. **There is no established algorithm superiority.** These new outputs provide current implementation evidence, not a capacity calibration, a stationary estimate or an optimal schedule. Earlier numerical evidence cannot be relabeled as current after the setup-rule correction.

## Browser evidence and limits

- A real Chrome browser rendered the baseline and updated production replay; screenshots are [baseline](review-images/baseline-replay.jpg) and [iteration 2](review-images/iteration2-replay.jpg).
- The updated screenshot is cropped to the lower map and controls. The last chart changes were source-reviewed, without a new final browser capture.
- The supervised browser-preview runtime lacks a Python executable. An attempted backend integration reported `spawn python ENOENT`; the unverified integration was removed. The original normal Python launcher is retained.
- Browser download-event verification timed out and the browser connection subsequently became unavailable. No successful browser download roundtrip, complete live-browser workflow, phone rendering or user-owned Codespaces access is claimed.
- Python simulation behavior and real localhost HTTP cases were checked separately. Adapter tests cover actual JavaScript data paths, but cannot replace layout, pointer, browser-download or full live end-to-end verification.

## Remaining work, ordered by importance

1. Complete live-browser run/cancel/reconnect and actual user Codespaces acceptance; reconcile the full approved specification against this implementation.
2. Perform a prespecified warmup sensitivity/longer-window/precision study before stationarity, sustainable load or algorithm-ranking claims.
3. Improve preparation-stage cancellation and stricter manual-job validation.
4. Export separate pending/censored setup waits; recover historical calibration raw records if those historical conclusions are needed.
5. Add live worker machine/skills/shift details, selected-job resource highlighting, a chart color legend, and final mobile/rotated-chart visual QA.

No cosmetic activity was invented and no demand or processing-time parameter was changed to increase visible utilization or the score. The processing-only reference remains a lower bound, never a claimed attainable optimum.

## Literature used by the logic reviewer

- Mäcker et al., [Non-Preemptive Scheduling on Machines with Setup Times](https://arxiv.org/abs/1504.07066): class-based setups are legitimate modeling choices; applicability still depends on this project's explicit operation-change rule.
- Lamothe et al., [Scheduling rules to minimize total tardiness in a parallel machine problem with setup and calendar constraints](https://arxiv.org/abs/1509.02099): setup, operator and calendar constraints are relevant scheduling dimensions. Its objective/system differ; no performance result is transferred to this simulator.
- Law, [Statistical Analysis of Simulation Output Data](https://pubsonline.informs.org/doi/10.1287/opre.31.6.983): initialization bias and estimator accuracy require explicit treatment.
- Little, [A Proof for the Queuing Formula: L = λW](https://pubsonline.informs.org/doi/10.1287/opre.9.3.383): use consistent accounting boundaries before comparing finite-window WIP with drained release-cohort flow.
