# E3.12F — Public reset-blocked exploration: preparation only

Status: **PREPARED_NOT_REGISTERED; no scientific execution authorized.**
Starting revision: `015d5fcfb13a1d5ca86197d7a41727cafde4db70`, branch
`codex/e3-12f-reset-blocked-preparation`. GitHub was fetched before branching;
the base was already pushed. Unrelated untracked Evolution-1 adapter files
are preserved and excluded. No historical artifacts are rewritten.

## Evidence and question

E3.12D failed its parent-retention screen. E3.12E's training-only audit found
stable raw choices but Pendulum raw-versus-matched parent sign disagreements.
The observed parent-group offsets explain that algebraic discrepancy; they do
not prove a causal explanation of query performance or systematic randomization
bias. No D query results are used to choose a new rule here.

Hypothesis: blocking child exploration by **pre-decision public reset
observations** improves held-out selection relative to random balanced
exploration, at the same revealed training-feedback budget. Competing nulls:
observation proximity does not balance relevant difficulty; treatment effects
vary within blocks; eight trials remain too noisy; or the frozen raw selector
is the limiting factor. These possibilities remain untested.

## Fixed comparison

Use the same four frozen source MLPs: two Pendulum and two Acrobot models,
family-default dynamics, existing parent/switch/rank-blend operators, reward,
200-step paths and 1536 imagined-row per-decision reservation. This is not the
historical H16/16-candidate parity claim. No model fitting, new architecture,
physics input or modified operator. Reverify the E3.9 inventory and all four
checkpoint/source-data hashes before any later collection.

Per model, register eight new training resets and four new query resets.
Before any training action or return, obtain only the eight public initial
observations. Verify exact reset-observation reproduction when paths start.
Freeze and hash both schedules before revealing training feedback.

* Random balanced: a dedicated local seeded RNG uniformly permutes four
  switch/four rank-blend assignments. This is a fresh randomized baseline,
  not a reuse of D's consumed schedule or its NumPy stream.
* Public blocked: enumerate all 105 perfect matchings of the eight reset IDs;
  choose minimum total squared normalized observation distance, breaking
  ties lexicographically by IDs. Assign one child to each endpoint of every
  pair using a separate local RNG. No rejection sampling or outcome-based
  rerandomization.

Distances use existing public observation coordinates, including sine/cosine
coordinates: Pendulum scales `(1,1,8)`; Acrobot scales
`(1,1,1,1,4π,9π)`. These are fixed schema bounds, not fitted task statistics.
Do not infer hidden angles/physics or fit a difficulty predictor. Coordinates
are divided by these scales; their values are not clipped or centered.
Pairing is across all eight available resets, so this is batch-design
preparation, not an online exploration algorithm.

## Feedback boundary and actual costs

Collect a **shared physical union**: parent once/reset, plus each child
required by either schedule. Each method receives only its scheduled child's
return and the paired parent return: eight parent and four returns per child,
16 revealed training returns/model/method. Unrevealed child outcomes and all
query outcomes must remain evaluator-only. The pure projection rejects query
rows, extra metadata, missing union cells and nonfinite values before masking.
Projection tests establish a data interface, not operating-system secrecy;
the future trusted host must enforce access boundaries.

Freeze each selector using the existing
`partial_feedback.parent_inclusive_decision` (parent-first exact ties).
The only scientific intervention is schedule assignment. No new update rule
is selected. Existing two-child mean and mutation-credit replay may be
reported as secondary, with their existing algorithms unchanged; the current
adapter implements the primary selector only. Do not choose among secondary
selectors on these query outcomes.

For every query reset, execute parent and both children on paired resets and
planner streams. Both selectors are scored by their frozen choice on these
same complete query panels. Shared panel paths are charged once physically,
not once per selector. This measures masked-feedback selection quality, not
the real-interaction savings of a deployed online learner.

Per model: 8 parent + 8–16 union-child training paths + 12 query paths = 28–36
paths. Across four models at 200 steps: **22,400–28,800 real interactions**.
Proposed conservative caps: **44,236,800 imagined rows**, **1,440,000 model
calls and network forwards**, **300 seconds**. The latter limits reuse D's
reservation ratios (1536 rows and 50 calls/step); they are ceilings, not FLOP
equivalence or measured costs. Future Host binding must enforce them before
calls. All reset collection, hashing and validation time counts toward cap.
Using D's 159-second/22,400-step runtime gives a rough 204-second upper-panel
planning estimate; runtime variability could produce an honest partial run.
No timing benchmark or model inference was performed in this preparation.

## Proposed statistics and decision rules

Primary: blocked-selector minus random-balanced-selector actual query return.
Average four query resets **inside each independent pretrained model**, then
report family-specific paired means and Student-t 95% intervals across the
two models/family (df=1). Episodes, blocks, shared panel paths and repeated
choices are not additional independent models. Do not pool raw reward scales
across families. These are exploratory intervals on family-default dynamics.

Proposed practical screen: in **both** families, mean advantage at least
1 return point, lower paired interval above zero and both model differences
positive. This intersection screen must be frozen before collecting any
outcomes. Secondary intervals are unadjusted descriptive diagnostics, not
extra confirmations. A zero-width [0,0] from identical choices fails the
screen. Report each model/task, parent choices, harmful selected queries,
reset-group parent offsets, observation distances and all fixed baselines.
Offsets are descriptive, not additional evidence independent of their raw
and paired gain decomposition. Hypothetical replay permutations cannot
be promoted as independent experiments.

Incomplete/missing paths, wrong hashes, reused closed seeds, schedule changes
after feedback, hidden-feedback exposure, nonfinite metrics or reservation
failures yield INCOMPLETE/INVALID, never a scientific negative. Valid results
with intervals crossing zero are inconclusive. Valid evidence of harm is
retained; neither outcome automatically justifies architecture expansion.
Equal observation-distance blocks may still have unequal return difficulty.

## Implementation and remaining execution prerequisites

`reset_blocks.py` is a pure schedule/mask adapter over the existing E1
`Work`, catalogue `digest`, and E3 partial-feedback selector. No replacement
learner, memory, planner, meter or runner. `partial_feedback` adds an explicit
optional balanced schedule argument; its historical default path is unchanged.
Config `configs/e3_12f_reset_blocked_proposal.json` is validated exactly by
`reset_blocks.validate_proposal`; it has no seeds/allocation/authorization.

Tests use authored observations/rewards only: known optimal pairing, exact
balance, RNG isolation, reproducibility, invalid/missing cell rejection,
unrevealed-return invariance, immutable plans, equal logical budgets and
separate physical union accounting. These establish mechanics, not usefulness.

Before later execution: authorize collection within this concrete scope;
register fresh environment/planner/schedule seeds against the full closed
registry; bind/test this adapter in the SAME
`scripts/run_e3_12_mutation_control.py` / `Host` / `ReservationLedger` path;
preserve complete per-step receipts and masked feedback journals; add paired
query aggregation/independent export; record immutable schedules before
feedback and a clean protocol/config/allocation revision before collection.
Fail closed if any prerequisite is missing. No new simulation entry point is
added here; engineering preparation is **not** scientific protocol lock.

## Scope and next decision

No environments constructed, steps collected, neural models trained/inferred,
new numerical scientific seeds registered or allocations created. Carried
ledger is unchanged: **1808.9990201649957 used / 1791.0009798350043 remaining**.
All previous results remain closed. Continual learning, E4 update-rule utility
and unfamiliar-model transfer still require their separate measured studies.

One next scientific action: complete fresh registration and trusted-host
binding for this reset-blocked versus random-balanced comparison, then run
only under an explicit scope permitting new collection. Do not infer success
from the authored tests or start another feature/rule search on D queries.
