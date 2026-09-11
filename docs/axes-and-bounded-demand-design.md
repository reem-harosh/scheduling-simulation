# Capability pools and bounded quantities — 2026-09-11

Status: design and mathematical checks only. The runtime world has NOT changed.

## User direction

Keep Milling, Turning, Honing and WireEDM; exclude Inspection. Do not adopt the previous Dedicated Finishing suggestion. Split Milling eligibility into 3-axis and 4-axis capabilities. Four-axis machines may serve three-axis operations; the reverse is prohibited. Keep unequal part-family demand probabilities. Replace historical quantities of thousands with bounded quantities suitable for the intended simulation scope.

## Evidence and interpretation

The accompanying source_axis_labels.json contains 39 reported Milling station labels: 2 explicitly x3, 18 x4, 9 x5 and 10 without an explicit suffix. Among the 36 mapped stations these counts are 2, 18, 7 and 9. These are literal label observations, not a verified machine inventory. Unspecified labels must not be classified as three-axis by default. Historical five-axis labels must not be relabeled as physical four-axis facts.

A synthetic 3-axis / 4-axis-capable benchmark is a deliberate simplification. Five-axis source resources could inform the latter pool only if their extra capability is explicitly abstracted away and no five-axis-required operation is introduced. Machine counts remain to be designed. Haas identifies the UMC-500 as five-axis: https://www.haascnc.com/machines/vertical-mills/universal-machine/models/umc-500.html

Represent process family, required operation axes, physical machine capability and explicit eligibility separately. Axis dominance is a scenario assumption conditional on compatible tooling and work envelope. Extra axes do not imply higher speed. Shared four-axis capacity must not be counted twice when estimating loads. Map coordinates remain physical locations; their capabilities need an explicit assignment table.

## Quantity recommendation and its provenance

Family occurrence skew and within-family quantity variation are separate model dimensions. A Pareto-like mix does not require a Pareto quantity tail. Previous quantity-tail proposals are superseded by the latest request for much smaller jobs.

Law (2012), section 5, discusses triangular distributions specified through minimum, mode and maximum when suitable data are absent. This supports an input-modeling method, not a market mean, three size classes or particular numeric bounds. Rounding its continuous distribution to integer quantities is our modeling adaptation.

Source: https://www.informs-sim.org/wsc12papers/includes/files/inv225.pdf

Protolabs advertises CNC production across widely varying order volumes. This is supplier capability information, not a representative sample of market order sizes. It cannot establish a universal mean of 175, nor show that large orders are inherently unrealistic.

Source: https://www.protolabs.com/services/cnc-machining/production-capabilities/

Engineering candidate: target mean 175, reflecting the user's earlier 150–200 range; relative size levels r in {0.5, 1, 1.5}; common spread delta=0.5. Three classes provide a parsimonious short/medium/large size comparison; they are not empirical clusters. Neither the levels nor the spread is a literature estimate.

Given actual fixed family probabilities p_i, define mu_i = 175*r_i / sum_j(p_j*r_j). Sample Tri((1-delta)*mu_i, mu_i, (1+delta)*mu_i), then round to positive integers. This normalization fixes the continuous overall mean independently of the skewed family mix. Verify the rounded mixture mean too. Family-to-size assignments and probabilities are still pending.

The companion bounded_quantity_candidate.json checks an ILLUSTRATIVE class probability mass of 25%/50%/25%, not a selected family mix. It yields means 87.5/175/262.5 and rounded supports 44–131, 88–262 and 131–394. Exact discrete CDF bin probabilities give overall rounded mean 175. Other class masses require recomputing these bounds. The example maximum 394 is not a universal cap under arbitrary mixtures.

## Validation still required

Quantity is not duration: processing matrix, route length, setup transitions and transport determine service demands. Smaller jobs reduce processing per job but can increase setup share when arrival intensity is raised. Do not claim stability from the quantity calculation. Fix quantities first; then estimate and simulate arrival candidates, machine pools, floor-local human capacity and four setup workers. Preserve independent demand random streams across policies.

Planned sensitivity should separate target mean, spread and demand mix from capacity and arrival intensity. Sanchez and Wan (2012) discuss designed experiments and the problems of confounded ad hoc changes; this motivates the experiment structure, not the selected quantity values.

Source: https://www.informs-sim.org/wsc12papers/includes/files/inv260.pdf

All sources accessed 2026-09-11. No calibration simulations were run for this candidate. No deployment or remote git push was performed.
