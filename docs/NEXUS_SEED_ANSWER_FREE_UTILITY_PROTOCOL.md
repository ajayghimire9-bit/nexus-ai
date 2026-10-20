# Answer-free next-question utility: locked source-development protocol

Base **1a6167073321d2a7241227ded4627599a63b4386**, verified GitHub tip of
codex/seed-question-utility-learning and descendant of reviewed8f404db. New branch
**codex/seed-answer-free-question-utility**. No unrelated work moved or overwritten.
[Executable configuration](../configs/seed_answer_free_utility.json).

The newer54-feature residual study failed and stays closed. This owner-requested
variant uses ten scalar features, one plain ridge and primary budgets1/2/4.
It is an additional inspected SOURCE-development analysis, never confirmation.

## Hypothesis and competing explanations

A source-trained utility predictor selects a next example with lower excluded-
task check MSE than variance, exact uniform expectation, original order and keep,
with the fixed adaptation procedure. Alternatives: the scalar representation is
uninformative, labels vary across query states, or nine source tasks cannot
support transferable estimates. Failure alone does not identify which applies.
No neural architecture change, capacity search, new collection or promotion.

## Features and one fixed fit

Pure `answer_free_utility.features` has exactly ten coordinates:
mean candidate prediction clipped to[-1,1] after dividing by4; fit-prediction
standard deviation divided by4 and capped at1; log1p(input variance)/10;
nearest anchor mean-square input distance capped at1; nearest observed-prefix
distance capped at1 (0 when empty); anchor residual MSE/4 capped at1; observed
prefix residual MSE/4 capped at1 (0 when empty); signed observed-prefix residual
mean/4 clipped to[-1,1]; cosine alignment with the anchor residual gradient
(0 for zero norm); remaining candidate fraction. Inputs use this outer fold's
frozen33-dimensional normalization. Three damping fits are averaged, not counted
as independent pretrained cores.

No task ID, action one-hot, unrevealed answer, updated proposal/theta, assessment
data or answer-dependent prefix_consistency feature enters that function. Existing
before-update theta may depend only on anchors and previously observed prefix.
The function receives those observed labels explicitly, never the future label.

For each outer fold (task index modulo4), rebuild all nine permitted training
tasks under THAT fold's frozen normalization and damping, using
question_selection.fit_path/LabelOracle and question_headroom.counterfactual.
Do not pool other own-fold caches. The old utility helper constructs the
counterfactuals; replace its temporary54-vector before the new fitter sees it.
No prior utility-predictor coefficients or action-mean tables are reused.

Training target is108-selection-row MSE before minus after one candidate update,
averaged over the three fixed damping fits. Train on all189 cases per fold,
including the singleton budget8. Center features and utility using only these
rows. Reuse nn.ridge.fit_ridge with **ridge1.0**, its training RMS and original
antisymmetric augmentation. No hyperparameter selection. Ten coefficients plus
one training mean =11 prediction parameters/fold,44 total; centering/RMS state
is additionally saved. All preprocessing excludes the three held tasks.

## Choice lock, answer reveal and assessment

For every excluded task and budget1/2/4/8, use its historical variance-order
reference prefix0/1/3/7. Construct features from inputs and observed-prefix labels
only. Fit all folds and persist ALL choices, model hashes, source/config hashes
before revealing a requested candidate answer or opening check assessment.
The evaluator owns recorded answers/check outcomes; training only gets selection
arrays for its nine tasks. One LabelOracle per method/intervention permits only
b labels (prefix plus chosen answer). Cached post-update states and scores are
reused only for the matching excluded fold, with dependency hashes and independent
scalar equation/check/retention replay. This is a logical API boundary in a
trusted offline worker, not a claim of adversarial process isolation.

Compare learned, variance, exact uniform next-candidate expectation, first
remaining original row, keep and a single featureless training-mean utility.
Ties always favor lower original row index. Thus source_mean and original_order
are mathematically identical decisions; report both without counting them as
independent support. Evaluator check oracle is a labeled upper bound, never
available to a selector. No hindsight keep decision for question policies.

## Primary endpoint and frozen screen

Average the three damping fits within each candidate, then budgets **1/2/4**
equally within each task, then12 tasks equally. The12 task means are the units
for paired exploratory95% t intervals (df11); folds overlap and all tasks share
ONE frozen core. These are conditional source-development intervals. They do
not establish independent neural replication or learning-to-learn.

Require ALL: at least5% lower primary MSE than variance, uniform, original_order
and keep; positive lower interval bounds for variance-minus-learned and keep-
minus-learned; at least8/12 keep wins; primary retention MSE no more than.01
above variance. Report all controls, per-task scores, query-utility prediction
error and selection regret. Regret subtracts the same oracle baseline and is
dependent on MSE. Budget8 is reported separately: only one question remains,
so agreement there is not evidence of ranking. These interventions are isolated
next updates, NOT a sequential questioning learning curve. No post-result tuning.

## Resources, missing results and preservation

One run: **60seconds CPU AND wall,2048MiB sampled RSS,0 new real interactions,
0 imagined transitions,0 neural forwards,0 neural/meta optimizer updates**.
Existing EXPERIMENTAL host, resource ledger, E1 journal and fixed worker route.
Carried1963.6321034559958s used /1636.3678965440042remaining, not the older
user-reviewed ledger. Debit host time conservatively; no automatic retry.
108 anchor fits,864 reference updates,2268 candidate updates,480 variance solves;
four small predictor solves.756 training/252 excluded cases,291600 training
query-row scores.900 cached assessment states.720 policy label accesses include
independently restored prefixes; no new collection or free online label budget.
Sampling uniform/oracle expectation over recorded cases is evaluator computation,
not extra agent teaching opportunity. Reused frozen/source weights never change.

Exact planned task/fold/budget/candidate/seed/method grids and finite numeric
metrics must validate before declared_complete. Missing/invalid/capped attempts
remain recorded separately from a valid FAILED or inconclusive scientific screen.
Commit tested implementation/protocol before execution. Independently replay
saved arithmetic without fitting. Preserve every prior artifact, checkpoint and
closed split; no runtime promotion or main merge. GUI is read-only saved evidence.

## Verification plan

Synthetic leakage tests poison hidden labels/check outcomes; lock choices first.
Poison/remove held task data before training extraction and require identical
training inputs, preprocessing and coefficients. Check label caps, deterministic
fit/choice, exact-grid failures, frozen fingerprints and original-order ties.
Independent scalar audit verifies fixed learner equations, ridge normal
equations, candidate variance, recorded assessment arithmetic and task intervals.
Focused plus relevant Seed/shared regression suite; no test performs this real
source study. Update current navigation/results after the one run, then push.

Pre-execution engineering:21 new focused tests passed. The broader run had
755 passes and14 setup errors in an older synthetic fixture that counted all
earlier pytest CPU time. Isolating that fixture in a subprocess changes no
scientific code, caps or historical evidence. The corrected focused/shared
regression run passed122 tests in62.08s. The final relevant suite will also be
run after saving results. No scientific execution occurred during these tests.
