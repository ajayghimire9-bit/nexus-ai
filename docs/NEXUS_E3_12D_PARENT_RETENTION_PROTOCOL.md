# E3.12D — Fresh parent-aware limited-feedback comparison, locked v1

Base verified locally and on GitHub: 32f7088824d829d36c33f41f1f8c7d3e78f8ffa9.
Branch codex/e3-12d-parent-retention-comparison. The interrupted authorization
turns started no worker and generated no experimental outcomes. Preserve both
unrelated untracked adapter files, every historical result and frozen input.
This implements the earlier proposal without changing its success thresholds.
The human explicitly authorized ONE run within300 seconds/22400 interactions.

## Hypothesis and alternatives

A simple training-average selector that can retain parent reduces harmful
changes while preserving useful query gains versus the two-child selector.
Alternatively noisy estimates can favor the wrong option, parent retention can
forgo useful changes, or the available modifications may lack stable benefits.
Do not assume which explanation is correct. C's query results stay closed; no
retrospective fitting or scoring of this new rule on them.

## Fixed mechanisms and reuse

Reuse SAME partial_feedback training statistics/parent_inclusive_decision,
StrategyGenerator mean structural credit, operator_headroom arithmetic, typed
compositions, measured_mutation, post_probe.Host/Dispatch, ForwardCheckedStep,
ReservationLedger, exact simulator/RNG restoration and chunked DecisionJournal.
parent_retention.py is selection/replay/statistics glue, not another learner.
SAME run_e3_12_mutation_control.py adds --parent-retention with isolated paths;
SAME stdlib exporter independently recomputes arithmetic. Earlier profiles and
their consumed grants remain unchanged. No parallel memory/planner/framework.

Use four unchanged frozen CPU residual MLP64x64 source models: two Pendulum,
two Acrobot, with source-only normalization and pinned source data. Inventory
artifacts/e3_9_planner_evidence_readiness.json SHA256
58a9c11758e0a13d09f68c35697374ecbad1b19c9755780436fae897a931c0f9.
Verify all four checkpoint/eight source hashes before and after and complete
model parameter/normalizer fingerprints per model. No neural training, new
physics, confirmation/H17 access, probes or support collection.

Parent is the existing successor H16 anchor; switch(parent,flat H16,.25) and
canonical rank_blend(parent,flat H16) are the only modifications. Preserve
actions, reward and candidate execution. Per-decision catalogue cap1536
imagined rows is NOT the older historical16-candidate controller's budget.

## Fresh seed registration and learning schedule

Single executable config: configs/e3_12d_parent_retention.json. For family
index f, bundle b, episode e, offset=100000*f+20000*b+1000*e. Reset seed
2181000000+offset, planner seed2182000000+offset+t for decision t=0..199.
Training e=0..7; fresh query e=8..11. Audit all9648 registered reset/planner
seeds against current artifacts/configs, original source-array metadata and
conservative historical reservations before any environment construction.
No external/unavailable historical run coverage is claimed.

Eight training resets/model. Precommitted four/four child schedules are saved
explicitly and checked against NumPy default_rng SeedSequence([73524,f,b])
permutation of [switch×4,rank_blend×4]. This stream does not depend on feedback,
query outcomes or model/planner randomness. Each reset reveals parent and
ONLY that scheduled child, each a full200-step path from identical restored
simulator states with paired planner seeds. Never execute or impute the other
child's training return. Every learning method sees precisely this same data.

Mutation credit uses its unchanged legitimate measured paired feedback:
tanh((child_return-parent_return)/100)/(1+parent_CPU_s+child_CPU_s), averaged
by operator. Logged CPU and feedback receipts are replayed exactly. Counts
are32 legitimate paired updates, no learned exploration policy.

After all eight training resets for each model, seal choices before its first
query path. Every subsequent query must reproduce that identical training-only
decision. Four fresh query resets/model execute parent and both children from
paired clones; all selectors reuse those physical paths. Query returns NEVER
update any selection statistic, credit, normalization or model weight.

Conditions: (1) primary parent-inclusive raw training mean, tie order parent,
switch,rank_blend; (2) unchanged two-child raw mean, tie switch; (3) existing
mutation-credit argmax, tie switch; (4) analytic uniform expectation over the
two children; (5) fixed parent. Also report fixed switch/blend and previously
defined paired-gain/guarded controls as exploratory diagnostics. Parent has
eight observations; each child has four. This unequal uncertainty and reset-
difficulty imbalance are disclosed. No confidence gate or outcome-based tuning.

## Outcomes, independent units and fixed decision

Primary: parent-inclusive minus two-child raw mean query return. Also report
versus uniform, fixed parent, credit and both fixed modifications, all raw
per-reset returns, parent-retention frequency, harmful-change rates relative
to parent, query win rates and training means/counts/hashes/choices.

Average four query resets WITHIN each model first. Compute paired differences
across the TWO independently pretrained models in each family, t95 df1:
mean ±12.7062047364*sample_sd/sqrt(2). No episode/path pseudo-replication;
do not pool raw family scales. These tiny-suite intervals are exploratory,
conditional on familiar physics and these source models, not confirmation.

Advancement requires in EACH family: primary mean gain≥1 and CI lower>0;
gain versus uniform≥1 and CI lower>0; fixed-parent difference CI lower>−1.
All conditions must pass, plus complete finite grid, exact frozen inputs and
meter reconciliation. This intersection screen handles the required claims
conservatively; other unadjusted exploratory intervals cannot rescue failure.
Label only exploratory_parent_retention_screen_passed if all pass; otherwise
parent_retention_not_established for a complete valid run. Degenerate intervals
from identical selected paths are dependent arithmetic, not proof of equivalent
future expected policies. Do not redefine success after outcomes.

## Resources, execution and provenance

Exact planned real work: 4 models*(8 training resets*2 paths+4 query resets*3
paths)*200=22400 interactions/112 episodes. Training12800, query9600. No cached
path is counted as a newly executed interaction. Uniform and shared selector
outcomes add no physical work. Upper34406400 imagined transitions,1120000
model calls and1120000 actual network forwards, metered separately.
Hard300-second local CPU experiment cap, no automatic retry; prior same-grid C
took154.4 seconds, so expected roughly3 minutes plus short saved-data audit.
Worker import, model loading, capture and its validation are included in the
live clock; parent kills an overrun worker and reports unknown work honestly.
Offline verification/export is separately timed and charged to the session;
if execution consumes the cap, it cannot be restarted to complete missing data.

Carry session1643.627562957004 used/1956.372437042996 remaining. Commit exact
config/protocol allocation, tested implementation and protocol BEFORE outcomes.
Allocation cites the current explicit human authorization and standing grant;
no prior consumed grant or expired allowance is reused. Record clean execution
SHA, all hashes, dependencies, raw steps, receipts, wall/CPU/RSS and ledger.
Reserve before operations, enforce all caps, preserve raw failed/partial capture.
Missing or capped cells mean incomplete; integrity failure invalid; a complete
negative/inconclusive scientific result remains complete. One run only.

Focused synthetic tests first, then relevant deterministic regression. Verify
schema-derived grid, no query leakage, exact schedule, parent tie retention,
reward/receipt sums, frozen inputs, independent arithmetic/CI and profile paths.
Post-run independent stdlib arithmetic must match the main analysis; no
resimulation for exports. Keep resources and results artifacts separate from
previous experiments. Commit results separately, push, do not merge main.

No continual-learning/E4/generalization run is authorized by this allocation.
The next scientific recommendation must follow this result; functioning
persistence and changed probabilities alone establish neither useful learning
nor learning-to-learn or AGI.
