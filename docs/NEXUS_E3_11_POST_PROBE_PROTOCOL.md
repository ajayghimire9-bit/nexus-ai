# E3.11 — Fresh post-probe return selection (locked development protocol)

Base3eacec07feec90c3c7d89cd39a1ed3f426ac3bbf; branch
`codex/e3-11-fresh-post-probe`. Authorized by the human's explicit E3.11
request and standing local grant. This document, executable config, tested
implementation and hash-specific allocation must be committed before any
simulator step. No historical checkpoint, evaluation split or result changes.

## Hypothesis and scope

H-evidence: a fixed small predictor using fresh current-probe prediction
residuals and candidate-specific frozen-model forecasts selects the better
192-step controller more usefully than a training-model-mean prior. Null:
forecasts/residuals do not improve held-out return selection beyond that prior.
No feature search, tuning on evaluation, new strategies, physics or network
training. Existing source-family default Pendulum/Acrobot only, two frozen
E2.9 MLP bundles per family. This is not unfamiliar-physics confirmation.

Reuse `StagedStudy`, `EpisodeContext`, `AdvantagePredictor`/ridge1,
`generated_strategies.execute`, `planner_adapter`, `ForwardCheckedStep`,
`ReservationLedger`, `full_policy_source.operation_plan`, TaskSpec/wrappers
and DecisionJournal. A post-probe host binds these; no second learning,
planning, memory or metering framework. Do not reuse the36 inspected feedback
pairs as training data or reopen E3.2/E3.4 evaluation outcomes. H17 remains
blocked and E2.17's old grant remains consumed.

## Registered episodes, probe and restoration

Config specifies families,bundles, training episodes0,1,2 and evaluation3–6.
For family index f and episode e, reset seed2121000000+10000f+1000e;
planner base2122000000+10000f+1000e, with original episode tick8–199 offsets;
uniform discrete probe RNG2123000000+10000f+1000e; evidence generation RNG
2124000000+10000f+1000e. These are common across bundles as well as controllers.
Probe seeds/control streams are separate. Check all numerical roles/ranges
against historical seed metadata, source-array seed fields and the preserved
conservative registry before collection. Any collision blocks execution.
Registry coverage is current committed records plus the historical exclusion
inventory, not a claim about unavailable external executions.

At each reset execute exactly8 uniform-policy real transitions. Use one shared
prefix and deepcopy the entire supported Gym wrapper/simulator after step8,
including simulator RNG and TimeLimit counters, for each controller. Verify
state/RNG/wrapper fingerprints at restoration. State is used by trusted host
only, never predictor input. Both continuations start at exactly that state
and use identical per-tick planner seeds. Collect both actual192-step paths
without online weights/context/selector updates. An unexpected termination,
truncation before tick199, reward mismatch or restoration mismatch invalidates
the run. Pendulum native reward and existing dense Acrobot wrapper stay fixed.

## Fixed evidence and learner

Once after each probe, evaluate the existing full successor and rank-blend
controllers' proposed first actions using their unchanged cap1536. Meter
all proposal calls. For each proposed action construct16 H16 sequences:
that first action plus15 IID actions. Share tails across both conditions
using evidence_seed+1. Score them with existing `planner_evidence`; these
are common continuation forecasts, not full-policy return predictions.

Fit no model weights. Predict all8 already observed support next states in
one charged neural batch; normalize absolute error by the model's frozen
source RMS standard deviation, averaging rows/dimensions. Fixed4-vector:
`[1, max_score_rank-max_score_successor,
mean_final_survival_rank-mean_final_survival_successor, normalized_support_mae]`.
No task ID or hidden physics enters this vector. Inferred model-specific
training priors are legitimate known-model information, not target oracle means.

Use only12 fresh TRAINING pairs (3/model) for two family-specific copies of
the existing AdvantagePredictor, unchanged ridge1 and train-only RMS scaling.
Targets are rank-minus-successor192-step observed returns, residualized by
each model's fresh training mean. Fit exactly once/family, four coefficients
each, no hyperparameter selection. Add that same model prior back at inference.
No predictor may receive future evaluation outcomes. Save coefficients and
all16 evaluation decisions **before any evaluation continuation is executed**.
Choices: rank blend iff predicted advantage>0, otherwise successor.

## Baselines, caching and resources

Methods: contextual selector, equally informed per-model training mean,
always successor, always rank blend. Same fixed two controllers, no new
generated policy. For each evaluation context execute both complete controller
continuations once. Every selector commits to one whole controller; its return
is an exact cached lookup of that paired execution, not another environment
episode or an off-policy estimate. Count physical paths once and report
logical reuse separately. No selector changes strategy during continuation.

Both controllers retain cap1536/tick (actual1491 imagined rows each, different
forward-call counts). These are the existing catalogue source controllers:
successor31 tails/root; rank blend48 flat candidates plus15 successor tails/
root. The additional common-scoring evidence uses16×H16; do not describe the
catalogue controllers as the historical16-candidate comparison.
One-time evidence/proposal/support work is extra and
charged physically once per context. Standalone mean/fixed methods do not
need it; disclose their lower actual cost. No claim of perfectly matched
FLOPs. All methods have the same upper allowance and candidate-controller
search rules; evidence cannot improve a controller's internal search budget.

28 contexts ×(8 shared+2×192) = **10976 real steps**. Training4704;
evaluation6272. Probe collection224, continuation10752; no extra diagnostic
collection. Actual planned imagined work16129288; conservative cap16615648.
Observed model-call/forward plan638596; extra probe evidence3502 imagined
rows/context includes both proposal evaluations2982, common scoring512 and
support prediction8. Exactly2 ridge fits; no neural training. Independent
resource receipts and observed top-level forward hooks must reconcile.

Expected runtime approximately1–3 minutes from earlier source-controller
clocks, with uncertainty for hook/journal overhead. **Hard wall cap300s**,
local one-thread CPU; parent kills a time-exceeded child. Scientific session
starts787.6449502930179/2812.355049706982 and includes all failed/partial time.
Exclusive consumed marker, no automatic retry. Journal receipts/partial raw
paths and active-work upper bounds survive failure. Incomplete/invalid is
different from a completed negative/inconclusive scientific outcome.

## Primary analysis and decision

Primary: contextual minus model-mean192-step return. Average four evaluation
episodes within each frozen model; report both models separately per family,
then equal model-weighted family means. Do not pool unlike family scales.
Exploratory paired95% Student-t intervals across **two models/family**, df1,
critical12.7062047364. Episodes are not extra independently pretrained models.
All intervals are unadjusted exploratory descriptions; no confirmatory or
cross-family generalization claim can follow this small source screen.

Registered development point screen: each family gain>=1 return point and
all four model gains>0. Pass label `development_point_screen_passed_not_confirmed`;
otherwise `post_probe_context_selection_not_established`. Report intervals
regardless; a point pass with intervals including zero is still inferentially
inconclusive. Secondary comparisons against both fixed controllers, paired
in-set regret, advantage MAE/sign accuracy, selector overrides, per-context
returns, feature variation, proposal first-action agreement and compute.
Probe reward is shared: adding it to each192-step return must leave every
paired difference unchanged. Do not use secondary metrics to upgrade failure.

Completeness is the exact configured family×model×role×episode×controller grid,
not a grid inferred from produced results. Every raw reward/transition, seed,
support hash, frozen coefficient/checkpoint and receipt must validate. No NaN,
missing/duplicate contexts, future-data updates or counted cache work. Preserve
prior artifacts and produce a no-inference saved-data arithmetic audit.

If negative, distinguish no forecast-feature variation, poor advantage
prediction and no improvement over strong model priors without declaring
information-theoretic impossibility. Recommend one next test from evidence;
do not automatically expand features, retrain frozen models or launch E3.12.
