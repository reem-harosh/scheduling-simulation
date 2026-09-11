# Approved inter-floor rules and mathematical quantity design

## User decision

The user explicitly approved the proposed inter-floor transfer logic: parts may cross floors, regular workers and setup specialists stay on their assigned floor. Source and destination handling use separate local workers; a shared freight lift is the proposed initial engineering resource. Transfer has finite time/capacity and can queue. Multiple transport trips do not become independent execution lots. Full quantity reunites before the next operation; machine assignment must not lock early merely because transfer began. These rules are approved for implementation, not yet implemented.

The user wants both short/long work and meaningful routing/setup interactions. They prefer a mathematically grounded quantity design with Pareto-like concentration, without arbitrary individual quantities.

## Calculations from the retained v0.4 evidence

Using all343 inferred quantities, the largest20% contribute80.8572% of units. The boundary observation is fractionally weighted because20% of343 is68.6. Ranking instead by quantity times the sum of route reference unit times gives75.4079% of inferred processing work in the largest20% of workloads. This is a derived proxy using current route-standard interpretations, not measured autonomous work and not a fitted Pareto law.

For mean175 and top20% unit share80%, the mean within the top group must equal 0.8*175/0.2=700. A maximum500 is therefore incompatible with both targets. The previously suggested500 cap is withdrawn as a general recommendation for a strict80/20 candidate.

A reproducible candidate family is Q_new=c*Q_proxy**alpha, with c=target_mean/mean(Q_proxy**alpha). Solve alpha numerically for a requested top20% share. This defines synthetic alternatives, not statistical estimates of a uniquely correct world. With targetmean175, before integer rounding:

| Top20% unit share | alpha | Median | P95 | Maximum |
|---|---|---|---|---|
|60%|0.6003155173|93.403|572.431|1534.343|
|70%|0.7689914411|64.174|654.572|2314.577|
|80%|0.9787344377|36.849|708.146|3533.818|

Mean175 remains an engineering anchor within the user's proposed150–200 range, not an inference from the original mean2397.708. Shape/concentration and scale are separate controls. No new runtime quantity distribution or arrival baseline has been activated.

Next design recommendation: compare these controlled concentration candidates at fixed mean and a common independently defined world. Evaluate actual processing workload distributions, setup-to-processing balance, local human service, WIP stability and throughput. Do not impose a fixed percentage of setup work by randomizing transition type, and do not tune demand based on live factory state. Quantity concentration alone does not guarantee processing-work concentration after routes and times change.

## Follow-up approval

The user approved proceeding with the three concentration candidates (top20% shares60%,70%,80%) at the same mean quantity. These are candidates to compare, not a selected final distribution. The user requested grouped modeling questions and local startup instructions before the next implementation stage.
