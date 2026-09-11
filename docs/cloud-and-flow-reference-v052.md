# v0.5.2: repeatable launch and a flow-time lower bound

## Browser execution without ZIP updates
Open https://github.com/codespaces/new/reem-harosh/scheduling-simulation and create a Codespace on main. The checked-in devcontainer installs Python dependencies, starts the actual Python engine, and forwards port 8000 privately. If no tab opens, use Ports > 8000 > Open in Browser, then /production/.

On later updates, stop the Codespace through GitHub and reopen it. The startup script fast-forwards a clean main checkout and restarts the server. Local tracked modifications or another branch skip automatic updating; no edits are discarded. Results remain within that Codespace (do not delete it without exporting results). A running session does not hot-reload backend updates: stop/start is intentional to avoid changing an experiment midway.

Codespaces creation, account availability and quotas are controlled by GitHub. This configuration is tested locally but a user-owned cloud session has not been provisioned from this environment. It is a browser-accessible Python workspace, not an always-on deployed production server. The old static PrintFlow Site is not the production Python application.

## Version diagnosis
The header displays frontend 0.5.2, backend version and a server instance identifier. An absent backend version identifies an older server. HTML, JS and CSS are served with no-store; conditional requests do not return stale assets. A port conflict explicitly reports that an old server may be running. These changes address plausible causes of unchanged UI; the user's device was not inspected, so its exact cause is unconfirmed.

## Mathematical reference
For job j of quantity Q_j and sequential operation route O_j:

L_j = Q_j * sum over o in O_j of min over eligible m of T(family_j, o, m).

Every operation is counted, including repeated machine families. The minimum respects axes and eligibility. This relaxation gives every operation its fastest eligible machine, without queueing, setups, manual service, transport, shifts or resource contention. Since these excluded delays are nonnegative and no lot splitting/pipelining is enabled, this is a valid processing-only lower bound for the current model. It need not be attainable jointly by all jobs, and it is not a proven optimal schedule.

The mean lower bound uses exactly the measurement-release cohort used by the flow KPI, including drainage. Ratio and excess-percent are computed only when the actual mean is valid. Empty cohorts return null, not zero. Partial/censored runs do not receive an apparent optimality gap. The ratio is actual/LB, not a certified ratio to the optimum. It may overstate the improvement that any scheduling algorithm can achieve. Revisit this derivation if lot splitting or overlapping operation transfers are introduced.

Results retain per-job bounds, their mean, actual/LB, excess over LB and the complete definition. Scenario raw rows retain the reference object. Old result files display that a new run is needed, rather than inventing reference values.

## Validation
75 Python tests; JS syntax and production DOM/canvas-adapter integration tests; shell syntax; real HTTP version/cache checks. Full Codespaces and browser visual testing remain unperformed. Original calibration data are retained, not silently regenerated or relabeled.
