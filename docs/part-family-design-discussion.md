# Part-family design discussion — 2026-09-11

User approved the preceding 3/4-axis capability model and bounded-quantity construction for implementation. These are approved design inputs, not active runtime features. Family design is the current discussion focus.

## Source analysis

The 19 existing families are exact ordered machine-family sequences, not technological clusters. Source routes are inferred from the union of each item's operation numbers across jobs. Of 343 positive-quantity retained jobs, 118 lack at least one stage from that item-level union; this does not establish that the missing stages were optional or wrongly inferred. 112 jobs have one inferred operation and 28 more than five.

Consecutive-family compression is exclusively an analytical projection. Runtime operations must never be collapsed by it.

| Transition skeleton | Jobs | Share | Source families |
|---|---:|---:|---|
| Milling | 178 | 51.90% | PF01, PF02, PF05, PF19 |
| Turning | 99 | 28.86% | PF03, PF04, PF07, PF18 |
| Turning / Milling | 33 | 9.62% | PF08, PF10, PF11, PF12, PF15, PF16 |
| Turning / Honing / Turning | 20 | 5.83% | PF06, PF13 |
| Milling / WireEDM | 11 | 3.21% | PF09, PF14 |
| Turning / Milling / Turning | 2 | 0.58% | PF17 |

## Synthetic catalogue candidate

Six source-informed transition skeletons become 16 proposed technological route variants with 48 operations. This is an engineering design, not a statistically selected optimal cluster count. Four Milling and four Turning-to-Milling variants explore capability restrictions and consecutive operations; two variants in each other group retain simpler alternatives without multiplying every combination. A 2–5-operation candidate deliberately adds stages to some single-stage archetypes and shortens long source routes. It is not historical reconstruction.

M3/M4 denote required Milling axes; T Turning, H Honing, W WireEDM. Rough, finish, drill and feature roles below are synthetic. Bore honing and subsequent external turning describe different surfaces; product geometry and tolerances are abstracted. All capabilities assume compatible fixtures/envelopes.

| Candidate ID | Synthetic operation sequence |
|---|---|
| NF01 | M3 rough / M3 finish |
| NF02 | M3 rough / M3 finish / M3 drill |
| NF03 | M3 rough / M4 multi-face finish |
| NF04 | M3 rough / M4 multi-face finish / M3 drill |
| NF05 | T rough / T finish |
| NF06 | T rough / T bore / T finish |
| NF07 | T rough / M3 finish |
| NF08 | T rough / T finish / M3 drill |
| NF09 | T rough / M4 multi-face finish |
| NF10 | T rough / T finish / M4 multi-face finish / M3 drill |
| NF11 | T rough / T bore / H bore finish / T external finish |
| NF12 | T rough / T bore / H bore finish / T external finish / T cutoff |
| NF13 | M3 rough / M3 finish / W profile |
| NF14 | M3 rough / M4 multi-face finish / W profile |
| NF15 | T rough / M3 features / T finish |
| NF16 | T rough / M4 features / M3 drill / T finish |

Each operation gets its own route position and ID. Eligibility, setup class and deterministic processing are operation-specific, including adjacent Milling operations. Physical machine choice remains a scheduler decision. Setup class is not a family ID. Quantity class is not automatically determined by route length or popularity.

## Demand mix proposal

Do not copy source skeleton shares and split them uniformly: two T-M-T families would each have only0.2915% probability. A synthetic popularity-rank law p(r)=r^(-alpha)/sum(k^(-alpha)) provides a transparent nonuniform alternative. This is not a fitted Pareto distribution or an empirical exponent estimate. Rank is not the candidate family ID.

| alpha | Top4 share among16 | Least frequent share |
|---|---:|---:|
| 0.6 | 45.67% | 3.31% |
| 1.0 | 61.62% | 1.85% |
| 1.4 | 75.83% | 0.90% |

Recommend alpha1 as a discussion candidate, not a calibrated probability assignment. Top4 then receive61.62%, least frequent1.85%. Assigning ranks to concrete families must be shown explicitly and evaluated against operation-level offered loads, especially the small Honing/Wire pools and shared four-axis capacity. No probabilities are active in the new catalogue yet. Rare does not mean useless, but rarity should be intentional and enough occurrences should be obtained across experimental replications.

## Remaining parameter decisions

After route catalogue agreement, provide a complete per-family table: fixed demand probability, quantity class and normalized triangular parameters, complexity, operation modifiers, operation-specific setup classes and eligibility. Derive reference times from reviewed source evidence; label new role-specific assumptions. Complexity must be an independent fixed factor if used for sensitivity; recomputing its modifier inversely would cancel the intended effect.

Then evaluate processing and human loads independently before choosing arrival rate. No claim of stability follows from16 families, bounded quantities or nonuniform frequencies alone.

## Verification

Analysis script: tools/analyze_part_family_design.py. Assertions check source totals,16 unique candidate routes and2–5 operations each. Independent review verified the six skeleton counts and identified route-union and synthetic-count limitations, incorporated above. This was a data/design audit, not a runtime integration test.
