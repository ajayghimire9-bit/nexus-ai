# Sequential replay of the frozen consistency selector

Starting revision: **fb0ae7457a04bd06db801bb2c2af71a3a201b1a1**, matching GitHub
after fetch. Branch: `codex/seed-sequential-consistency`. Preserve the failed
full-feature audit and the uncertain consistency-only local-regret lead. This
new exploratory source test is not a relabeling of either result.

## Hypothesis and scope

H-sequential: the frozen consistency-only utility predictor can choose update
versus retain in a changing learning state, improving actual1/2/4/8-example
query-prediction curves over trained fractional constant damping, scaled replay
and bounded fixed protection. Alternative: its local counterfactual advantage
disappears under its induced fit distribution or strong sequential baselines.

No refitting, new teaching collection, neural training, architecture changes,
threshold search, control episodes or runtime promotion. Even a source-screen
pass would require genuinely fresh validation before learning-to-learn claims.

## Frozen inputs and reuse

The executable source of truth is configs/seed_sequential_consistency.json.
Hash-verify the source plan and both tracked parents before loading:

- Predictor parent artifacts/seed_prefix_consistency.json:
  b5752b247f574c8168e4529329e653441d6147ac9f97ffb156ee2c367ec414af.
- Damping parent artifacts/seed_update_gate.json:
  86c31e80fda3134e69e49608b2bcb402cd61755833315423bcf07dab2618690e.

Keep the original twelve source tasks95000000–95110000 at10000 spacing. Four
source folds exclude indices modulo4, three tasks per fold. Each predictor and
each damping coefficient was fitted only on its fold's nine training tasks.
Verify training IDs, normalization, source hashes and constant checkpoint hashes.
Pass only original source arrays and permitted frozen fold state to the worker;
do not pass previous assessment scores, diagnostic query tables, old training
logs or development/control payloads as learner inputs.

Reuse cumulative_learning.posterior/prepare_fold, prefix_consistency.features/
predict, update_diagnosis.trajectory/saved-math/paired and bounded_correction.
Use the same EXPERIMENTAL host/worker/shared runner and Lab. No parallel learner,
memory, planner or meter is introduced. All needed state is small tracked JSON.
No historical binary is required or loaded, replaced or retrained.

Reproduce the frozen fold scale using source training support/anchor arithmetic
and require exact equality with the saved scale. Do not fit a new bounded cap;
use the source-fitted tau saved by the damping parent. Parent predictor means,
centers, scales, coefficients and threshold0 remain frozen.

## Sequential adaptation

Start from the existing four-anchor initial fit. Observe eight teaching labels
in their original order, retaining all observed labels even if an update is
rejected. At each prefix form the existing ridge .1 unit-diagonal cumulative
proposal centered on the initial fit. Recompute consistency features using the
CURRENT fit and only the observed prefix/anchors. Predict utility using the
saved six-feature consistency ridge. If prediction>0, take the full proposal;
otherwise retain the current fit. Ties retain. Query/retention labels are only
scored after each decision and cannot enter future decisions.

Seven methods, identical teaching prefixes and evaluator rows:

1. Frozen consistency selector, features recomputed on its evolving fit.
2. Frozen prefix-mean utility selector, threshold0 at each prefix.
3. Frozen trained fractional constant damping; three saved seeds7201/7202/7203.
4. Existing feature-scaled replay update.
5. Existing bounded fixed protection with saved source-only tau.
6. Unit cumulative proposal on every step.
7. No new-task adaptation, retaining the same old-anchor initialization.

Recompute all trajectories rather than report cached baseline executions.
For constant damping, execute each saved rule separately and average metrics
inside each task; do not average coefficients before the sequential update.
The deterministic selector is executed once/task, not triplicated to manufacture
three training replications. Logical teaching budgets match; solve/inference
costs differ and are reported. Stored parent query scores are not inputs.

## Primary screen and statistics

Primary metric: mean query MSE over budgets1,2,4,8. Average damping seed metrics
within each task first; give all twelve tasks equal weight. Require at least5%
lower mean MSE than EACH trained damping/replay/bounded reference, with each
reference-minus-selector paired task95% interval lower bound>0. Require selector
better than damping in at least3/4 fold means, and final retention MSE no more
than damping+.01. The conjunction is the source screen; do not weaken it later.

Report all0–8 prefixes, per-task/fold results, update/retain counts, negative
transfer versus no adaptation, support/retention errors, and source predictor
immutability. Use the existing n12 task-cluster exploratory interval helper.
These are conditional on one frozen feature extractor, selected source-trained
models and a repeatedly inspected source bank. Fold training overlaps. They are
not twelve independent pretrained models or a fresh confirmation. The three
damping seeds are not extra statistical units. Intervals are descriptive and
do not remove selection bias from the preceding exploratory feature audit.

A complete failed screen is a scientific negative result. Missing cells,
incorrect provenance or nonfinite values mean incomplete/invalid execution.
Do not shrink the grid, select another feature group, refit coefficients or run
another scientific retry after reading these outcomes.

## Accounting, completeness and verification

One dispatch under30-second wall/CPU caps,2048MiB sampled RSS, CPU only.
Zero new real/imagined/frozen-world-model interactions; zero predictor fits,
zero outer optimizer updates. Carried ledger: **1936.6321034559958s used /
1663.3678965440042s remaining**. macOS RSS sampling is not kernel-hard memory
enforcement. Use the existing host's durable reservation and conservative debit.

Expected108 executed trajectories,972 snapshots,864 inner updates,108 anchor
initial solves,576 cumulative solves,96 consistency predictions,96 prefix
predictions,96 feature constructions and36 constant-scalar reads. Existing
replay/protection counters are recorded separately. Query/retention each have
26244 executed row scores. These are cached source arrays, not new collection;
repeated saved-vector verification is separate arithmetic work.
Normalization arithmetic uses432 source row appearances. Across108 trajectories
there are864 teaching presentations and432 initial-anchor rows; cumulative
solves use2592 repeated prefix-support rows and2304 anchors. Exact retain and
full-update decisions return their endpoint tensors directly; fractional
damping preserves the original interpolation arithmetic.

Record clean execution SHA, config/protocol/input hashes, parent hashes and
frozen-state hashes before/after. Save every trajectory and decision: current
fit, proposal, features, predicted utility, gate, query/retention scores and
support residual. Exact expected task/method/replica/prefix sets come from the
locked config. Validate required finite typed fields; independently recover
proposal normal equations, feature/prediction/interpolation math, score and norm
arithmetic without fitting or neural imports. Verify complete frozen parent
state, not just an unchanged Boolean flag. No fabricated forgetting field.

Run source-only correctness tests, commit implementation/protocol before the
single scientific run, then commit results separately and push without merging.
Keep main, unrelated files, previous artifacts and closed evaluations unchanged.
Recommend one evidence-grounded next study; no second experiment in this run.
