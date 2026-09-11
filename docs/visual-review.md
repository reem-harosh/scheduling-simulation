## v0.6.2 — restore exclusive operation ownership

The user's clarification supersedes the v0.6.1 assistance experiment below. The
original scheduling rules in both engines are restored: when operation ownership
is retained, only that owner may load, change a cycle or unload. Another qualified
idle worker does not substitute for a busy owner. Original shift handoffs, setup
and transport rules remain intact. New traces explicitly record
`operator_assistance: false`; older assistance-enabled traces warn that a new run
is required. All material accounting and synchronized replay counter fixes remain.

Validation: 87 Python tests and the production UI regression suite pass. The new
instrumented ownership regression checks that all owner-bound dispatches use the
owner, demonstrates waiting despite another eligible idle worker, and verifies
completion and non-overlapping worker intervals. Existing shift-handoff tests pass.
The separate `mobile-review-v062` branch has an automatic Codespaces launch setup;
see the README for phone instructions. No main release is approved by this review.

# Illustrated replay review

Status: local `visual-review-v060` branch; not approved for main or published.

## Worker/cargo correction

The initial illustration pass incorrectly interpolated loading/unloading pieces
independently while leaving the worker at its service node. Its connector line
made the pieces look detached. The replacement uses one worker pose and one hand
anchor for both transport and manual service; the tote overlaps the hands rather
than sitting at the end of a connector. Direction follows the current walking
path leg. Manual service depicts approach, pickup, carrying, placement and return
within the recorded service interval. These local gestures are illustrative;
they do not add movement duration or alter the DES event times or quantities.
Cycle change unloads in the first half and loads in the second half, so a worker
never carries both the outgoing and incoming cycle simultaneously. Quantities
still commit at service completion, matching the engine.

Machine family colors are stable: Milling blue, Turning orange, Honing violet,
WireEDM pink. A separate top strip indicates activity. Gold ownership lines remain
visible for every recorded assignment of a visible worker, including an idle
owner; a solid gold line means the owner is servicing the machine. Blue lines
indicate service by another worker. Off-shift workers remain hidden.

Playback offers 14 presets from 0.25x to 7200x, a custom multiplier, half/double
buttons and a seconds-to-simulation-time explanation. The renderer retains the
30 FPS cap and existing sprite cache. Reduced-motion preferences disable gait
and bob; essential material transport continues to follow replay time.

Regression verification now samples 18 points from a small generated DES run and
30 from the saved full-world run across carrying, loading, unloading and cycle
change. It checks synchronized displacement, exact carried quantities, unique
part ranges, cycle order, repeatable backward seeks, ownership links, speed and
pause. Browser inspection checks the actual atlas rendering in successive
loading/carrying frames and custom 7.5x-to-15x speed control. The earlier 3.08 ms
measurement below belongs to the initial illustration pass, not this correction.

The floor now separates people, machines and material with distinct silhouettes.
Blue operators wear yellow helmets; violet setup technicians carry tool belts.
Metal components and filled totes replace colored material squares. Station
selection opens enlarged before-loading, inside-machine and after-unloading
quantities, family identifiers, and the current handler or assigned lot owner.

Carried material is rendered once at the recorded carrier's hands with a quantity
badge. Manual handling uses the same worker pose. Lift transfers have their own label. The activity strip
identifies the worker, task, job, machine and carried count. Solid assignment
lines indicate current work; dashed gold lines indicate operation responsibility.

The three component shapes are illustrative family symbols, assigned by numeric
NF identifier modulo three. They do not represent supplied engineering geometry
or uniquely identify every family. NF identifiers remain authoritative. Piles
contain at most four illustration sprites; the adjacent number is the exact
quantity from the replay, not the number of illustrated objects.

## Rendering and verification

- Canvas rendering is capped at 30 frames per second. The atlas is decoded once
  and eight trimmed sprites are cached in 96 by 128 canvases.
- Walking alternates two poses, with a small bob and path-based direction.
  Pausing stops the decorative clock; reduced-motion preferences disable gait
  and bob. Recorded simulation positions and material counts remain authoritative.
- `node tests/test_production_live.cjs` passes, including actual carrier/count
  association, selectable cargo, station detail, role-specific worker names,
  backward seek, material conservation display and previous UI regressions.
- In the browser fixture, the application draw/update section averaged 3.08 ms
  over 800 rendered frames. This is one test environment, not a device-wide or
  GPU performance guarantee.
- Real trace inspection at minute 1704.50: milling day worker 04 carries 60
  parts of R0-J000010 toward M61. At minute 1440, M68 shows 240 before loading,
  one inside and 97 after unloading for the 338-part job R0-J000000.
- This review changes presentation only. Simulation computation was verified
  separately before this visual revision; the static preview used saved replay
  data because it does not run the Python backend.

## Sprite asset provenance

`dist/production/assets/factory-sprites.png` is a generated RGBA atlas,
1774 by 887 pixels, 932163 bytes. `sprite-bounds.json` records alpha bounds;
the original image was not edited. One image-generation call produced the atlas.

Exact generation prompt:

```text
Use case: stylized-concept
Asset type: production sprite atlas for a lightweight industrial simulation canvas, not a UI mockup.
Generate ONE image only with a genuinely transparent alpha background. Landscape aspect ratio 2:1, ideally 2048x1024. Exactly 4 columns by 2 rows of equally sized square grid cells, no drawn grid. Each asset centered in its cell with generous transparent padding, every asset fully inside its own cell. Top row contains exactly four full-body worker sprites of the same scale, all facing right in a consistent elevated isometric three-quarter view: cell 1 blue-uniform factory operator in hardhat standing, cell 2 the same blue operator walking with clear separated arms and legs, cell 3 violet-uniform setup technician in hardhat and tool belt standing, cell 4 the same violet technician walking. Bottom row: cell 1 short machined steel cylinder with a clearly visible central bore; cell 2 machined rectangular aluminum bracket with holes; cell 3 small metal gear; cell 4 open low industrial blue-gray parts tote containing a small orderly pile of metal components. Friendly professional stylized 3D industrial-game art, low-detail polished surfaces and simple consistent lighting, strong silhouettes readable at only 40 to 60 pixels. No photorealistic faces. No text, labels, grid lines, watermark, scenery, ground plane, decorative objects, floor shadows, or anything outside the individual sprite silhouettes. Transparency is essential. Keep all top-row workers aligned at the same baseline and same height; keep all bottom-row objects centered within their respective equal cells. Avoid white or checkerboard baked background.
```

## Historical v0.6.1 — assistance policy canceled in v0.6.2

The map counters now use raw material-ledger segments, independently of manual
animation phases. Each station explicitly displays input / inside / output.
Cycle-change decoration used to subtract the carried piece from the aggregate
map marker, then return it, creating apparent oscillation. Completion events now
also have a per-machine cumulative final-operation counter: final-operation
pieces leave WIP at unloading and must not be depicted as still waiting for a
next operation. Station detail identifies the active job and operation, since
input legitimately increases when a new job/operation or delivery arrives.

Replay resource cards, entity rows and the floor now refresh at the same rendered
replay time, with unchanged DOM content reused. Independent 350/400 ms throttles
previously allowed visible disagreement at high speed. Waiting diagnostics lists
all waiting machines, the state, eligible idle worker count and already assigned
handlers, and separates idle operators, setup experts, breaks and off-shift staff.
The v0.6.1 warning about missing assistance is superseded by the v0.6.2 policy warning described above.

Scheduler rule change: the operation owner is preferred when available. If the
owner is busy or on a break, another available operator with the required machine
skill may perform the manual task while the owner retains operation responsibility.
Assistance is recorded separately from shift ownership handoffs. Setup workers do
not perform operator tasks, workers remain exclusive resources, and release rates,
batching, machine eligibility and processing times are unchanged. This is a policy
change requiring a new simulation run, not a reinterpretation of saved results.

Validation: 87 Python tests passed, including an instrumented three-machine fixture
that checks no dispatchable request is left while a qualified worker is free,
retained ownership, qualifications and non-overlapping worker intervals. UI tests
verify stable quantities across decorative cycle phases, decrement/increment at
service completion, final completions and same-time waiting counts. A new full
world run (seed 20260909, 1-day warmup, 1-day horizon, 2-day trace, 30-day drain limit)
completed 19 released jobs and recorded 604 operator assists over the full run.
This single run is functional evidence, not a statistical performance comparison.
At replay minute 2712.47, both the cards and diagnostic table show 15 waiting
machines, no idle workers and no ready batches. At minute 1440, M68 / R0-J000000 /
OP010 shows 239 input, one inside and 98 output parts (338 total).

The reported screenshot was not attached to the current message, so its exact
13-versus-1 moment could not be reproduced. The demonstrated synchronization defect
was corrected and the shared-time count was independently checked in the browser.
