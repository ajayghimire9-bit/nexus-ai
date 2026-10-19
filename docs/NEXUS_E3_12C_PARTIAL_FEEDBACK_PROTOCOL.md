# E3.12C — Single-child explore-then-commit selection, protocol v1

Base GitHub/local76310669855e2dbbe0bb32f44d6dec447a40bc8a verified after fetch.
Separate branch codex/e3-12c-limited-feedback-selection. Preserve all historical
results, protocols, seeds, frozen checkpoints and unrelated untracked adapter files.

## Question and alternatives

Does learning a fixed operator preference improve fresh-episode returns when
each training reset reveals only one child? Stable source-model preferences may
be learnable with four observed outcomes/operator; alternatively small samples,
reset difficulty or credit normalization may prevent reliable selection. Keeping
an unchanged parent may be preferable even when an operator wins its comparison.
These are competing explanations, not conclusions. E3.12/B stay closed.

## Immutable mechanism and reuse

Same four CPU residual MLP64x64 source models (two/family), pinned source data,
normalization, family-default physics and reward definitions from E3.9 inventory.
No neural fitting, new physics, probes, support collection, confirmation/H17
access or checkpoint replacement. All four checkpoints and eight source arrays
must hash-match before/after. No generated code or model architecture changes.

Reuse StrategyGenerator mean structural credit, measured_mutation, existing
typed switch/rank_blend operators and successor/flat anchors, Host/Dispatch,
ForwardCheckedStep, TaskSpec/restoration, ReservationLedger and DecisionJournal.
SAME runner adds --partial-feedback; partial_feedback only provides schedule,
selection and replay glue over operator_headroom. No parallel learner, memory,
meter or planner framework. Original profiles/results remain unchanged.

Parent successor H16; children switch(parent,flat H16,.25) and canonical
rank_blend(parent,flat H16), with1536 imagined-row per-decision upper cap.
These catalogue-budget planners are not historical16-candidate parity. All
paths use the unchanged existing execution/candidate/reward/action logic.

## Fixed exploration and permitted feedback

Eight training resets/model. Before outcomes, permute [switch x4,rank_blend x4]
using NumPy default_rng(SeedSequence([73514,family_index,model_bundle])). At
registration, the resulting four schedules are explicitly saved in the config
and validated against that RNG derivation, so independent schema checks do not
derive expected labels from produced results. At
each reset execute parent and ONLY the registered child, full200-step episodes
from exact simulator/RNG/time-limit clones with paired planner seeds. Never
execute, score or impute the unobserved other child's episode outcome.

The existing generator receives one legitimate matched parent/child update per
training reset: tanh((child_return-parent_return)/100)/(1+parent_CPU_s+child_CPU_s),
mean by operator. All32 updates are logged; CPU includes receipt/capture work.
Exact replay uses saved costs. Exploration is fixed and balanced, not learned.
The learned adaptation occurs in the subsequent frozen exploitation choice.

Every selector uses the same8 revealed children/parents, four observations/type:

1. Primary: larger mean raw child training return.
2. Existing credit: argmax final structural-credit probability.
3. Strong paired-gain baseline: larger mean child-minus-parent training return.
4. Incumbent guard: use paired-gain winner only if its estimated gain>0; else parent.

Exact ties choose switch; zero estimated gain retains parent. No new update
rule, temperature, penalty, validation search or hyperparameter tuning. Record
all choices, counts, means, gain estimates, probabilities and training hash
BEFORE evaluating any query path. Query outcomes never enter training/update.

## Fresh query and comparisons

Four fresh query resets/model, each executes parent and both operators, paired
from identical initial simulator state/RNG and per-tick planner seeds. Selector
returns reuse these actual paths: no free extra physical episode is claimed.
Compare all selectors against fixed parent, fixed switch, fixed rank_blend and
uniform-expected choice. The latter is the arithmetic mean of two measured
operator returns: operator chosen once/episode with probability.5, not random
per-action switching and not another physically executed policy. Hindsight
best of the two is diagnostic only, unavailable to selectors.

All controllers get identical opportunity caps. Actual inference and CPU work
may differ by operator; matched opportunities are not equal FLOPs. No online
weight/context fitting or query-time preference updates. Training raw-return
means may be confounded by reset difficulty because operators were observed
on different resets; paired-gain baseline explicitly addresses that concern.

## Registered seeds and bounds

Executable source of truth configs/e3_12c_partial_feedback.json. Same four source
models; train episode IDs0..7, query8..11. Offset=family_index*100000+bundle*20000+
episode*1000. Reset=2171000000+offset; planner=2172000000+offset+tick0..199.
The schedule RNG stream is isolated from reset/planner streams and feedback.
Audit9648 identifiers against available artifact/config seed metadata, original
source-array seeds and conservative reservations. Unavailable external history
is not asserted covered. Never reuse any earlier closed episode sample.

Training:4 models*8 resets*2 paths*200=12800 real steps. Query:4*4*3*200=9600.
Total112 physical episodes/22400 real steps. No additional support/validation/
probe collection. Cap34406400 imagined rows,1120000 calls/forwards. Reserve
before every physical operation; partial/unknown work must never be called zero.

One local single-thread run, estimated120–180s, hard300s cap. Standing local
grant2026-10-16; carried ledger1485.650493707012s used/2114.349506292988s remaining.
Enforce smaller applicable cap, no automatic retry. Allocation pins exact
protocol/config hashes and one clean implementation commit before collection.

## Primary estimand and decision

Per model average four query episode returns, then primary training-mean minus
uniform-expected. Average the two independent pretrained models INSIDE each
family; exploratory paired95% t interval df1, critical12.7062047364. Never pool
families as interchangeable models or count episodes/operator paths as replicates.
Report each model/reset and all unadjusted exploratory intervals.

Screen requires BOTH families: mean primary gain>=1, both model gains>0 and
95% interval lower>0. Label exploratory_partial_feedback_selection_screen_passed
only if all hold; otherwise partial_feedback_selection_not_established. Secondary
credit/paired-gain/guard results cannot upgrade a failed primary screen. Any claim
that credit outperforms simple baselines additionally requires its own positive
paired interval; responsive preferences alone are insufficient.

Report primary and all fixed-baseline comparisons, credit-minus-training-mean,
credit-minus-paired-gain, credit-minus-guard, training-mean-minus-guard, and each
selector versus uniform. Report individual model losses against parent, query
winner counts, regret and hindsight headroom. Best-minus-uniform, regret
reductions and winner diagnostics are dependent, not separate replications.

This new reset sample is not a paired comparison with E3.12B. Do not interpret
cross-study point changes or ratios as proof of retained performance, feedback
efficiency or causation. A passing screen supports only this limited-feedback
source-development procedure. No new-physics, continual-learning, L2L or AGI claim.

## Integrity and stopping

Require full config-derived model/seed/phase grid; exact scheduled training
parent+single-child conditions and complete query panels;200 finite contiguous
transitions/path; correct rewards, actions, seeds, termination and restoration.
Reject hidden-child training fields, missing/duplicate cells, nonfinite metrics,
stale choices, query updates or changed frozen parameters. Raw path counts must
agree with physical caps, forward hooks and journals. Scientific inconclusive/
negative is distinct from incomplete/invalid execution.

Source-only tests first, then commit tested implementation/protocol/allocation.
One execution only. Preserve all previous artifact JSON byte hashes. Save raw
paths, chronological credit events, source hashes, runtime/dependencies, peaks
and resource accounting. Independent saved-data verification, then results
commit and push without merging main. If unsuccessful, diagnose small-feedback
selection failure and incumbent safety before adding capacity or more variants.
