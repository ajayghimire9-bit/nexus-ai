# Larger source query-bank replication — locked before collection

Branch `codex/seed-query-utility-replication`, starting at GitHub-matched
**41b0f0990362e47ff378cd6a887a1cb89bf9de94**. Main and unrelated root-checkout
files stay unchanged. [Executable configuration](../configs/seed_query_replication.json).
One source-development execution, after committing this protocol and tests.

## Question and boundary

Does next-question utility transfer between larger independent query samples
within the SAME source tasks? The previous query-informed oracle had headroom,
but two-state selection failed on an omitted third state. Competing explanations:
the query estimate was too noisy, or candidate utility remains state-specific.
Both can contribute. Preserve both closed findings and all prior negative runs.

This evaluates an EVALUATOR'S selection using source query labels, not a
deployable questioner or a new learning algorithm. Source task identities and
supports are reused. New query starts do not create new tasks, independently
pretrained models, untouched task confirmation or learning-to-learn evidence.
No control episodes, architecture changes, neural training or live promotion.

## Frozen computation and reuse

Reuse `question_headroom`'s hash-verified756 counterfactual33-vectors and144
keep states. Reuse the eight source support labels, four anchors, reference
prefixes0/1/3/7, three damping fits and fold-specific source normalization.
Do not fit any of them again or chain selected updates into later prefixes.
The old retention metrics are reused, not re-evaluated or recollected.

Use exactly the original `SeedRSSM` checkpoint and first prespecified
`ActionReadout`6301, verified by their configured SHA256. Freeze every parameter,
the world-memory bank and normalization. Reuse `nonlinear_learning.score_basis`
and its observation-time contract. The33 features and base reward have exactly
their previous meaning. The collector uses no candidate utility to select starts.

## Registered fresh starts

The configuration lists all288 seeds explicitly: task index i uses
98200000+1000i+100..111 for selection and+200..211 for checking. No numerical
seed is chosen from an outcome. The committed inventory hashes107 existing
Seed artifacts/configurations, with a conservative identifier inventory; reject
overlap before execution. Preserve those files exactly. Read historical state
identities only from the seven listed authored-data artifacts; no historical
score chooses a new state. These are all identifiable `before`/goal records in
the current tracked Seed JSON inventory. The audit does not claim a complete
inventory of unsaved external/manual activity.

Each subset has12 starts per task with the original `fresh_world(seed,goal,i)`
rule, indices0..11. Its even indices start near the goal and odd indices use the
authored random start. Existing bounded novelty resampling changes attributes,
and may change position after32 collisions; document realized state distances.
Reject all historical or within-run repeated full object/goal identities.
No overlap of selection/check/support/anchor/closed collection seeds.
The12 source goals are unchanged; no prior development/audit task is collected.

For each start, extract features once from a fresh deterministic belief and
execute all nine actions on separate deep copies of exactly that state.
Information reward remains disabled, as in the original source collection.
Record before/after observations, reward, done/truncation, base scores, features,
residual labels, shapes/dtypes and hashes. Outcomes never enter feature inference.
There is no learning or state advance between candidate queries.

## Selection lock and checking

Collect and score ALL selection starts first. At each task/budget, average
the three damping fits inside each candidate and the12 starts equally. Choose
the candidate with lowest selection MSE, ties to the smallest original index.
Save a complete selection manifest with config, source-state, selection-data,
selection-metric hashes and every choice BEFORE generating ANY check outcome.
The check collector must require that saved manifest. No per-check-state or
per-damping-fit selection, stopping, threshold tuning or re-selection.

On the independent12 check starts compare the locked choice with the saved
variance choice, exact uniform next-candidate expectation and unchanged keep
fit. Also report the check-informed minimum strictly as an optimistic bound.
That minimum is NOT the registered selector or evidence of generalization.
At budget8 only one candidate remains, so candidate agreement is tautological.
These are isolated next-update interventions, not sequential selected curves.

## Aggregation and predeclared screen

Primary metric: check residual-reward MSE (identical squared reward error after
adding the frozen base). Average nine actions inside a start,12 starts inside
a task, three damping fits inside a candidate, and four budgets equally inside
each task. Average the12 task values equally. Reuse df11 paired task-cluster
t intervals; ONE pretrained core, overlapping source fits, reused tasks. Query
starts, actions, damping seeds and budgets are not independent model replications.
Intervals are exploratory and unadjusted, conditional on this source suite.

Label `question_utility_stability_replicated` only if ALL hold:

1. Locked-choice mean check MSE at least5% below variance, uniform AND keep.
2. Paired variance-minus-selected AND keep-minus-selected95% lower bounds>0.
3. Selected beats keep in at least8/12 task-level budget means.
4. Cached retention MSE no more than variance+.01 under those choices.

Otherwise label `question_utility_stability_not_demonstrated`. This is a
development screen, not equivalence, a task-confirmation claim or a successful
question learner. A favorable check-informed bound cannot upgrade it. Report
all task/budget values and failures, selection-to-check disagreement, retention,
realized start geometry, and leave-one-task-out sensitivity descriptively.
No additional tests selected from outcomes, hyperparameter tuning or rerun.

## Costs and failure rules

Exactly12 tasks x24 starts x9 actions = **2592 new authored interactions**.
Frozen feature inference:288 encodings/posterior updates and2592 imagined
action transitions,2880 total recurrent transition rows including posteriors.
Report neural batches separately from rows.900 cached theta states score216
new rows/task each:194400 row predictions.24300 old retention rows underlie
cached metrics; no repeated retention execution. Zero inner solves, new labels
for fitting, outer updates, normalization fits or new neural parameters.

Existing EXPERIMENTAL worker/host enforces CPU/wall **60seconds**, sampled
RSS2048MiB,2592 real steps,2592 imagined transitions and zero optimizer updates.
The collector also checks the wall/interaction limits and posterior-row cap.
Carried ledger **1951.6321034559958s used /1648.3678965440042s remaining**.
Standing human grant2026-10-16 authorizes this bounded source-development run.
Debit actual run plus established conservative whole-second dispatch accounting.
An interrupted/invalid run consumes its budget and cannot be silently retried.

Missing tasks, starts, budgets, candidates, fits, actions, metrics, hashes,
wrong numeric types, nonfinite values, changed frozen state, seed overlap,
inconsistent reward arithmetic or an absent/stale selection manifest invalidate
completion. Preserve partial progress and failure status; scientific screen
failure is different from incomplete/invalid execution. Exact numerical replays
use absolute2e-6 tolerance for float32 features/reductions, no tolerance for
checkpoint/manifest hashes. No outside permissions or evaluator rules change.

## Tests and next decision

Before collection: synthetic analytic utility/selection isolation, identical
action-state copies, reward/residual indexing, frozen core/readout/context,
fixed normalization, exact candidate/fit/task grid, manifest gating, seed
exclusion, caps, paired aggregation and preserved source artifacts. Use toy
models or synthetic records only. Run the full relevant Seed regression suite.
Afterward independently replay stored arithmetic using stdlib and inspect the
read-only GUI. Unit tests/GUI inspection must not launch this scientific runner.

If stable useful utility survives, next propose a task-blocked question-utility
learner with source-only feedback. If it does not, use the new recorded starts
to diagnose utility heterogeneity before fitting or enlarging a selector.
Only this one replication is authorized by this manifest.
