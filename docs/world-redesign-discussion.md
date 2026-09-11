# World redesign discussion after v0.4 review

Status: analysis and proposed configuration only. Runtime defaults have not changed.

The user explicitly clarified that a synthetic, general research world takes precedence over historical reconstruction. v0.4 preserved empirical quantity tails, exact route patterns and order-frequency weights too literally. These are evidence inputs, not mandatory experimental settings.

## Findings and alternatives

- 343 inferred order quantities: mean 2397.708, median475, maximum50300. The largest17 orders contain46.249% of units.
- Linear rescaling to mean175 keeps a median35 and maximum3671. Square-root compression with engineering bounds25–600 gives mean175.029, median118 and maximum600. Bounds and exponent are synthetic choices, not distribution-fit findings.
- A more independent candidate uses triangular size classes Small(25,50,135), Medium(50,150,325), Large(100,240,500); means70,175,280. Fixed demand weights25%,50%,25% give mean175 before integer rounding. Distribution parameters are Engineering Baseline, not inferred from reports.
- The 19 old families were exact ordered machine-family patterns, not clusters. PF03 has50 jobs but one historical item. Five families have at most two jobs, together2.624% of demand. Only PF19 is below0.5%.
- 80.758% of the historical jobs follow routes whose operations all use one machine family. This is a structural limitation for varied routing studies.
- Proposed discussion catalogue:20 synthetic archetypes,2–5 operations, six capabilities (Milling,Turning,Grinding,WireEDM,Finishing,Inspection), including consecutive and reentrant family visits. Finishing/Inspection are added synthetic capabilities; broader Grinding is not equivalent to observed Honing. Fixed5% family probabilities are an experimental reference, not historical demand. Repeating Small/Medium/Large/Medium across20 families supplies5/10/5 size classes and overallmean175. The size–route association needs later sensitivity analysis.
- Staffing alternatives retain day:night2:1:14+7,20+10,28+14. Analytical rates10.508/15.011/19.824 at mean175 refer only to the square-root alternative with old routes/mix, excluding walking,setup,transport and local floor capacity. They are not simulation results or capacities of the new route catalogue.

## Confirmed floor defect

Independent reviewer confirmed v0.4 replaced all worker qualifications/departments with global floor pooling. Pathfinding ignores department; regular workers and setup specialists can cross the original boundary. Boundary1150 and user approximate1200 give the same40-left/28-right machine split. This is a real model defect, not a rendering artifact. The 59 former tests did not cover floor isolation.

Required correction includes explicit floor identifiers, fixed local rosters and skills, floor-constrained paths, local ownership handoff, local setup capacity in ECT, and transport conservation. Whether parts may move between floors remains a separate question for the user. If yes, use a transfer resource and separate local worker legs; if no, routes must be feasible within each floor. Do not patch movement by silently making routes impossible. No floor correction has been implemented in this discussion checkpoint.

## Grid and review

Five levels per axis already yields25 points; UI currently supports up to10 levels (100 points). Nine points was the previous pilot scope. The main study should use at least25 points with configurable replications after the world is defined.

Independent agent review checked the floor defect, grid support, quantity counterfactual arithmetic, rare-family counts, route weights and correct analytical labels. The added triangular mixture was separately checked by its exact first/second moments and candidate family demand weights. No new simulation runs were claimed.

Reproduce: `python tools/analyze_world_redesign.py` writes `research/redesign` evidence and `../outputs/Simulation_World_Design_Discussion.html`. Source world remains `research/world/world.json`; all alternatives are separate and explicitly inactive. The standalone report embeds all four figures and the full route/capacity tables.
