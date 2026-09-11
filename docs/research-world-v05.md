# Research world v0.5 — implementation and calibration record

This version implements the user's approved machine capabilities, bounded job
quantities, nonuniform family mix and floor-local workers. It is a synthetic
research world informed by historical reporting proxies, not a reconstruction
or a claim about industry-wide order sizes.

## Catalogue and demand

The six source-informed transition skeletons support16 synthetic multi-operation
families. Two additional single-operation families retain simple Milling and
Turning work. They receive2.5% demand each;5% combined is an engineering choice
for a small representation, not the historical32.65% single-stage share.
There are18 families and50 distinct operations. No Inspection is added.

The remaining95% follows inverse popularity rank across16 explicitly ordered
families. The rank order is in the builder and exported per family. It favours
common Milling/Turning routes while retaining rare Honing, WireEDM and return
routes. It is synthetic, not a fitted Pareto exponent or live workload balancing.

Each family has fixed relative quantity size0.5,1 or1.5. Size assignments cross
route complexity rather than automatically assigning large orders to long
routes. Means are normalized using actual family probabilities to total175:

`mu_i = 175 * relative_size_i / sum(p_j * relative_size_j)`

`Q_i = round(Triangular(0.5*mu_i, mu_i, 1.5*mu_i))`

Before rounding, class means are83.1475,166.2951 and249.4426. Across all families,
integer quantities are bounded42–374 at scale1. The exact rounded mixture mean
is174.9999966. The Batch Size slider scales the same sampled base quantity;
Arrival Scale changes only Poisson intensity. Demand streams do not depend on
algorithm, queues, utilization, resource availability or operational RNG draws.

## Processing, capability and preparation

Milling operations require either3 or4 axes. A4-axis machine can execute3-axis
work; a3-axis machine cannot execute4-axis work. Explicit eligibility is checked
when loading the world. Axis capability does not automatically confer speed.

Source median process standards provide reference unit times: Milling10,
Turning2.5, Honing4 and WireEDM12 minutes. These reported standards are proxies,
not confirmed autonomous mechanical measurements. Synthetic fixed complexity
factors and process-role modifiers create the frozen processing matrix. The
modifier is0.45 for drill/cutoff,0.8 for finish,1.1 for rough, otherwise1.0.
These are transparent engineering assumptions, not fitted technological effects.
The time for a family/operation/machine combination never resamples at runtime.

Each operation has an independent identity, setup class, owner and routing
decision. Classes A/B/C depend on role: rough A; bore/drill C; other B.
As of engine v0.5.3, only same-operation continuation has no setup. A distinct operation within the same setup class uses the lightest positive configured tier (Minor: 8/15/25 minutes in this world), an explicit engineering assumption. A↔C is Major, other changed classes Minor,
and INITIAL preparation Medium. Triangular duration parameters retain the
approved8/15/25,15/30/45 and30/50/80 minutes. Setup type is determined by the
actual transition, not randomized. Four specialists perform setup only.

## Capacity allocation adjustment

The initial processing-only allocation yielded55 Milling,9 Turning,2 Honing
and2 WireEDM machines. A12-job/day pilot showed Turning machine-busy fraction
62.65% versus35.29% in Milling, despite closer processing loads. Loading and
unloading occupy a Turning machine for a material fraction of its short cycle.

The builder was corrected to allocate general-purpose capacity using processing
PLUS on-machine manual service (11/6 minutes per unit-operation in the existing
handling model). This yields51 Milling,13 Turning,2 Honing and2 WireEDM.
The total68 map positions is unchanged. The original candidate and its completed
pilot are retained as an explicit design comparison; unfinished old-allocation
pilots were stopped after this structural issue was identified.

Four-axis count covers the required-four processing share plus20 percentage
points of flexible Milling capacity, yielding22 four-axis and29 three-axis
machines. The20-point reserve is an engineering assumption. Both total Milling
and required-four load constraints are checked; shared capacity is not counted
twice as independent pools. Source positions are preserved where possible;
six source-known positions change process family in this synthetic allocation.

## Humans and floors

The analytical staffing estimate uses expected manual service,650 productive
minutes per scheduled shift,6 days/week,75% target service utilization and20%
walking/transfer allowance. It yields24 day and12 night operators. Each floor
has12 day and6 night operators. Counts are fixed across the run. These are
engineering staffing estimates to be tested, not observed historical staffing.

Workers and setup specialists stay within their floor. Pathfinding enforces
the boundary at x=1150, including cached paths. Four setup specialists provide
one per floor per shift. Machines may continue automatic processing off-shift;
they wait for human unloading when required. Operation ownership is released
at each new operation and may be formally handed over after a shift ends.

Parts may cross floors. A source-floor operator collects the entire execution
batch at the floor landing. One shared lift serves ceil(quantity/60) serialized
cargo cycles of3 minutes each. This is aggregate travel/handling/return service,
not an explicit lift-position or door model. The destination-floor operator
collects parts after delivery. Landing nodes currently use nearest-boundary
machine service nodes; explicit floor_handoff_nodes can replace them.

An inter-floor transfer commits a destination floor, not a physical machine.
After the entire batch arrives, machine assignment is reconsidered. Transport
subloads do not become execution lots. There is no automatic lot splitting.

## Calibration and tests

Analytical candidate intensity is17.0986 jobs/day, constrained by WireEDM.
Machine occupation and human service are reported separately. Calibration
pilots use rates12,17 and22, independent replications,7 warm-up days and21
measurement days. Completed raw results contain full configurations, demand
streams, world/code hashes, worker/machine statistics and flow times.
Numerical pilot results and any final rate selection are recorded separately
when the runs finish. No stationary-performance claim follows from draining
the arrival cohort or from a single run without exceptions.

Independent tests cover integer quantity sampling and bounds, common demand
across algorithms and scales, invalid inputs,3/4 eligibility, complete matrix,
floor-local paths/skills, serialized lift service, no early destination machine
reservation, operation conservation, owner handoff and deterministic processing.

## Reproduction and inspection

Run `python tools/build_research_world.py` to reproduce the analytical candidate.
The optional `--rate` argument selects an offline scenario rate; it is not a
runtime demand controller. `--staffing-scale` changes fixed staffing for a
sensitivity scenario. Detailed tables live in research/world_v05 and are exposed
through `/api/world` and the browser's world-table panel.

Run `python run_factory.py`, then open http://127.0.0.1:8000/production/.
Use `python -m unittest discover -s tests -p 'test_*.py'` for the test suite.
The old research/world/world.json is retained for historical reproduction.

## Review correction before final calibration

Independent review found that cross-floor startability and allocation validation
contradicted each other when the destination machine was busy. Validation now
permits a transfer to its floor while keeping that machine unreserved. A test
covers a completely busy destination pool. The public calendar also now reflects
actual resource shifts rather than inherited legacy hours. Earlier pilots and
replays are retained as pre-fix evidence; final calibration uses the corrected
engine. Immutable floor landing lookups and per-snapshot service summaries are
cached to reduce repeated calculation without changing stochastic draws.

## Selected conservative baseline

The distributed world uses12 jobs/day. The analytical17.0986 candidate remains
in the configuration as provenance, not the active rate. At12, both final-engine
pilots completed, with throughput close to observed arrivals and nonpositive
weekly WIP slopes. The17-job/day pilots also completed, but mean flow increased
from77.34 to96.85 hours and mean WIP from39.40 to67.50. Twelve is selected as a
conservative research starting point, not as the maximum sustainable rate or a
formal stationarity result. Staffing remains fixed at the analytical design
capacity to permit increasing experimental load without changing resources.

The response surface is a separate exploratory experiment:5 arrival scales
by5 quantity scales,2 replications and2 algorithms (FIFO/SPT),100 complete runs.
It uses3 warm-up and3 measurement days, with cohort drain. These short-window
flow estimates are not directly interchangeable with the21-day calibration
estimand. Matched algorithm runs share identical demand hashes. No algorithm
ranking is claimed from two replications.

Operators are cross-trained across the machines on their own floor, a synthetic
skill assumption. All resources and distributions remain editable in world.json.
Reproduce the selected distributed world with
`python tools/build_research_world.py --rate 12`.

Final calibration accounting: four full runs completed (two each at12 and17).
Two planned22-job/day stress runs were interrupted before completion and have
no reported outcomes. They are excluded from the baseline decision. The selected
baseline validation and the100-run response surface are complete; the originally
planned six-run calibration sweep is not marked complete. No maximum sustainable
rate is claimed. All completed raw results are included with the release.
