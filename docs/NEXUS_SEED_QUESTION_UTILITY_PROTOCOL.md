# Learn next-question utility on excluded source tasks

Branch `codex/seed-question-utility-learning`, base **8f404db2539c06a4ed95c8ff5758f8b24ce3af71**,
matching fetched GitHub. [Executable config](../configs/seed_question_utility.json).
Commit this protocol and tested implementation before the one bounded run.

## Hypotheses and scope

H-useful: a small task-blocked predictor can choose a more useful next teaching
example using pre-question inputs/evidence, without this task's query answers.
Competing explanations: input features lack utility information, action-level
averages already capture it, or nine training tasks cannot support reliable
contextual estimates. Do not infer which one from a failed screen alone.

The previous evaluator chose using the current task's12 selection starts.
Here this task's selection AND check outcomes are excluded from predictor
training. This is an offline SOURCE-development study on the inspected bank,
not untouched validation/confirmation or a runtime agent promotion. Neural
weights, source normalization, old teaching/support data and prior artifacts
stay unchanged. No new worlds, neural inference or scientific interactions.

## Reuse and the necessary isolation correction

Use the same12 source tasks, three frozen damping fits and four old folds
(task index modulo4): train nine, exclude three. Use `question_selection` for
variance orders/damped trajectories, `question_headroom.counterfactual` for
one-step updates, `nn.ridge.fit_ridge` for regression, and the same host/ledger.

Do NOT simply train on all cached out-of-fold theta states. A training task's
own old fold may have fitted its damping using the presently excluded tasks.
Instead rebuild each of the nine training tasks under the CURRENT outer fold's
frozen damping constants and normalization. Those constants were trained only
on this fold's nine source tasks. No retraining of historical checkpoints.
The excluded tasks use their exact old saved states, which match this fold.
This conditions all methods on the same fixed learner and avoids the indirect
held-task-feedback path through other folds' damping constants.

Use the old eight-row input-variance order to define reference states. Before
budgets1/2/4/8, prefixes0/1/3/7 have already been revealed. Independently restore
each such state and append each remaining candidate (8/7/5/1). Counterfactuals
never form an optimized sequential trajectory. All methods request ONE next
candidate, with no free candidate labels or hindsight abstention.

## Permitted features and labels

The54-vector consists of12 scalars, the33 frozen normalized candidate basis
values, and nine action indicators. Scalars: mean prediction, damping-fit
disagreement, log input variance, nearest anchor/prefix input distances,
mean cosine similarity to the eight input rows, observed anchor/prefix MSE,
signed observed prefix residual, candidate alignment with anchor/prefix
residual gradients, and prefix length/8. Fixed clipping/scaling appears in
the single executable `features` function. Damping disagreement is not claimed
to be calibrated neural uncertainty or independent model replication.

Public inference receives candidate INPUTS/actions, four known anchor labels,
only the already requested prefix labels and three current fit states. It
cannot receive the new candidate's answer, proposal/post-update fit, query
features/outcomes, retention outcomes or task ID as predictive features.
Task IDs only select source folds and provenance, never feature coordinates.

Training utility = keep query MSE minus candidate-after-update query MSE,
averaged across three frozen damping fits and108 rows from that training
task's12 SELECTION starts. Never use any CHECK row to fit, scale, select
regularization or choose a model. Excluded task selection labels are also
absent from its fitter's input API. Row prediction labels may legitimately use
OTHER source tasks' selection outcomes. Preserve all data hashes.

## One fixed predictor and strong controls

Fit an action/budget mean utility table on permitted training cases, with
budget-mean fallback for absent actions. Then regress its residual utility on
the54 features using fixed ridge1.0. Center features on training rows only,
reuse the original ridge primitive's training RMS and antisymmetric augmentation.
No grid search, architecture search, repeated seeds or tuning. There are189
training cases/fold; each case has equal loss weight (early budgets have more
candidates). Primary evaluation gives the four budgets equal weight instead.

Compare exactly:

- learned: action/budget mean plus contextual ridge correction;
- action_mean: the same source-fitted action/budget table alone;
- budget_mean: the source-fitted budget mean, no contextual ranking;
- shuffled_residual: the same legitimate action/budget table, ridge fit to
  residual labels shuffled within budget with seed8501+fold. This tests residual
  context association, not absence of all feedback;
- variance: the old input-only highest-variance candidate;
- uniform: exact mean over the remaining candidates, no Monte Carlo noise;
- keep: no additional update.

Select the largest predicted utility, even if every prediction is negative.
Exact ties favor input variance, then smaller original index. Thus budget_mean
ties to variance by construction, a dependent metric, not corroboration.
Action means are a strong label-informed but context-free reference. All have
the same allowed teaching opportunity and frozen inner learner; source fitting
and selector compute differ and must be reported.

## Lock before assessment

Train all four fold models, construct all excluded public cases, predict all
utilities and save every candidate choice before scoring ANY check outcome.
The saved model/decision manifest binds config, source pack and all models.
Assessment receives these immutable decisions, not a selector to retune.
Recompute all scores from the same hash-verified cached check/retention metrics.
No new data, choice-specific query states, posthoc model selection or live policy.

## Metrics and screen

Primary error: reward residual MSE after the single selected update on each
excluded task's108 cached CHECK rows. Three fits averaged within task/candidate;
four budgets equally inside each task;12 task means equally aggregated.
Paired exploratory df11 t intervals across source task clusters. ONE frozen
pretrained core and overlapping folds; no independent neural replication.
The previously inspected check bank remains source development.

Declare `source_question_learning_supported` only if ALL hold:

1. Learned mean check MSE at least5% below action_mean, variance, uniform AND keep.
2. Paired benefit95% lower bounds>0 versus action_mean, variance AND keep.
3. Better than keep in8/12 task means and action_mean in3/4 fold means.
4. Mean retention no worse than variance+.01.
5. Learned mean error below shuffled_residual.

Otherwise `source_question_learning_not_demonstrated`. Retention or regression
fit alone cannot establish success. Report all controls, tasks, budgets, utility
prediction MSE/sign accuracy, regret to the cached best candidate, choice rates,
retention and negative transfer. At budget8 one candidate remains: no ranking
evidence. All intervals unadjusted/exploratory; gates are conjunctive, not
independent confirmations. A passing source screen still needs fresh validation
and sequential operation before learning-to-learn or runtime promotion claims.

## Compute and integrity

CPU/wall cap **30seconds**, sampled RSS2048MiB, zero new real/imagined steps,
zero neural/outer optimizer updates. Standing human grant2026-10-16; carried
ledger **1956.6321034559958s used /1643.3678965440042s remaining**. Existing
host reserves and conservatively debits actual scientific execution; never
reset on interruption or retry. Preserve partial/invalid attempts without rerun.

Planned108 initial solves,864 reference updates,2268 counterfactual updates:
3132 cumulative posterior solves.480 variance solves (288 training orders,
192 public prefix states),1008 public candidate feature rows.756 training cases
and252 excluded cases. Eight54-coefficient ridge fits,1512 training-row
presentations/3024 antisymmetrically augmented rows. Centering756 rows, predictor
RMS1512 rows; frozen learner normalization fits zero rows.291600 training-query
row scores.900 cached check/retention states reused, not executed again.

Expected sets come from config/old registered folds, never produced results.
Reject missing tasks/folds/candidates/fits/prefixes, shortened arrays, numeric
strings/booleans, NaN/infinity, missing frozen models, changed manifests or
unreproducible arithmetic. Scalar replay2e-6 absolute float32 tolerance;
posterior normal equations2e-5, ridge normal equations1e-7, hash equality exact.
Distinguish failed scientific screen from invalid/incomplete execution.

Tests first: synthetic utility recovery, independent query/future-label poisoning,
outer-fold isolation including constants, preprocessing, question/answer boundary,
fixed learner/snapshot preservation, stronger mean baselines, shuffled controls,
normal equations, exact grid/costs, deterministic replay and saved-decision gate.
Then full relevant Seed regression. Commit before the one run. Results, raw
models/cases and verification get a separate commit; no previous result changes.

## One next decision

If the source screen passes, propose a separately locked sequential question
policy test with fresh source-development tasks and equal label budgets.
If it fails, analyze task-blocked feature/utility prediction and action-mean
behavior on these recorded cases before adding capacity. Do not repeat a search
until it passes, claim self-improvement from fitted coefficients, or enable
these models in the live GUI agent. Only this experiment runs in this branch.
