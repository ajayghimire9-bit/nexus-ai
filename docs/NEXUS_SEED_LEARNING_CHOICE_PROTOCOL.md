# One policy-roll-in refit and learn/ask/retain advisory

Starting SHA **2f4e09a86b58b1b2dbe021cb1900790afeed992f**, matching fetched
GitHub `codex/seed-sequential-consistency`. New branch `codex/seed-learn-ask-retain`.
Executable configuration: configs/seed_learning_choice.json. Preserve all prior
failures, closed splits, historical artifacts, weights and unrelated files.

## Hypotheses and interventions

H-coverage: a single refit of the same six-feature utility ridge using states
reached by the old selector improves sequential learning versus an equal-budget
refit at always-update reference states. Competing explanations include myopic
utility targets, binary update choices and inadequate task diversity.

H-protection: a fixed, auditable learn/ask/retain rule reduces sequential query
error versus the unprotected roll-in refit without unacceptable forgetting.
This is a second, explicitly separate intervention; it cannot explain away a
failed H-coverage comparison. One roll-in pass is not converged on-policy learning.

Reuse prefix_consistency support traces/features/predictors, nn/ridge.py,
cumulative_learning posterior/folds, update_diagnosis trajectories/statistics,
and the existing EXPERIMENTAL host/worker, resource ledger and read-only Lab.
The two backwards-compatible helper options do not change old default behavior.
No new neural architecture, optimizer, memory or controller framework.

## Data and fitting boundary

Hash-verify the complete sequential parent (SHA256
10bfc72819c38d4b558d6939bb0bdcc40e48ebac9af5eedd0539ee3d46c6344f) and its original
source/predictor/damping parents. Use only the twelve saved SOURCE tasks
95000000–95110000 in10000 increments. Four modulo folds:9 source-training,
3 excluded tasks. Frozen source normalization and original feature extractor.
Do not construct environments, load neural binaries, generate new labels or use
previous validation/confirmation tasks. Baseline summaries from the verified
sequential parent are cached comparisons, never counted as new execution.

Each training condition gets72 cases (nine tasks ×eight prefixes) per fold,
same query/anchor/support arrays, same six consistency features, ridge1 with
the existing antisymmetric augmentation and source-only normalization.
Reference states always take the full cumulative proposal. Roll-in states
follow the OLD frozen consistency selector, never the just-fitted model.
Trace construction sees support/anchors only. Then permitted training query
outcomes label before-minus-proposal MSE utility. Excluded query or retention
outcomes cannot fit models, scales, thresholds or decisions. Store cases,
coefficients, normalization, residual scales and their hashes. No HPO.

## Three sequential policies

1. Reference-state refit: take full proposal iff predicted utility>0.
2. Roll-in refit: same decision, different training-state distribution only.
3. Protected roll-in: same fitted predictor, with the following fixed rule.

At each prefix the existing ridge .1 proposal uses initialization anchors plus
ALL observed teaching rows, even if previous updates were rejected. Compute
known-anchor MSE excess relative to the initialization (not a per-step drifting
bound). The error scale is the predictor's training residual RMSE, not a
calibrated uncertainty interval. No held-task errors enter this scale.

- Anchor excess>.01: ask if teaching budget remains; otherwise retain.
- Otherwise predicted utility>training RMSE: learn.
- Otherwise predicted utility<negative training RMSE: retain.
- Otherwise ask if teaching budget remains; otherwise retain.

Learn installs exactly the candidate residual fit. Retain/ask keep the previous
fit unchanged. Ask emits an explicit request for another labeled example, with
reason/evidence/budget in the trace. In this initial matched-budget comparison
it DEFERs to the next already scheduled source example. It does not select an
informative question, access an unrevealed label, collect a free answer or show
that asking improves label efficiency. All methods still receive1/2/4/8 labels.
At budget exhaustion no question is emitted. No recurrent/model weights change.

Known anchors are available memory evidence, not the held-out retention set.
Their protection cannot guarantee preservation of all old knowledge. Score
held-out retention separately. The module is an optional sandbox advisory;
there is no promotion into the live learner based on these reused source tasks.

## Metrics, independent units and locked decisions

Mean query MSE over1/2/4/8 examples, equal twelve-task weights. Three cached
constant-damping seeds were already averaged within tasks, not counted as extra
replicates. Use existing n12 paired task95% intervals, conditional on one frozen
core, selected source bank and overlapping training folds. Exploratory source
screens, not fresh confirmation; report all contrasts without claiming a family-
wise error guarantee. Old failed screens remain closed.

H-coverage screen: at least5% lower curve MSE than reference refit, paired
reference-minus-roll-in lower95% bound>0, better in at least3/4 folds.
H-protection screen: at least5% lower curve MSE than unprotected roll-in,
paired lower95% bound>0,3/4 fold wins, final retention<=constant damping+.01.
Separate strong-baseline screen: protected rule improves by5% over EACH cached
constant-damping/replay/bounded baseline, each paired lower bound>0, same
retention tolerance. All learn decisions must respect the known-anchor cap.

Report all source tasks, prefixes, folds, before/proposal/installed fits,
prediction scales, choices/reasons, support errors and separate retention.
Report comparisons with old consistency/prefix selectors, unit cumulative and
no adaptation. A protection-only pass cannot be called an overall learning-to-
learn success. Missing/nonfinite/corrupt cells mean invalid/incomplete, distinct
from a complete negative screen. No retuning or retry after reading outcomes.

## Bounded execution and integrity

Exactly one dispatch:30-second wall/CPU cap,2048MiB sampled RSS, local CPU,
zero real/imagined/world-model interactions, zero Adam updates. Eight new small
ridge fits,576 training utility cases.72 training initial/576 cumulative solves;
36 evaluation initial/288 cumulative solves;324 evaluation snapshots.
864 total teaching presentations (training576/evaluation288),39852 query row
scores and8748 retention row scores. Cached baseline trajectories108, executed0.
Fit normalization and prediction arithmetic are additional CPU work, not neural
forwards. Report actual wall/process CPU and sampled peak memory. macOS RSS
sampling is not a kernel-hard limit. Carried1939.6321034559958s used /
1660.3678965440042s remaining; conservative host debit with no ledger reset.

Add deterministic toy tests for all actions and conflict/uncertainty, knowledge
preservation, reversibility, budget exhaustion, future/query-label isolation,
source-fold isolation, training-subset equivalence, exact source hashes,
complete grids, replay and GUI immutability. Commit tested code/protocol before
the run. Save partial progress if capped; do not shrink the grid. Verify saved
normal equations and decision/score arithmetic without fitting or neural imports.
Commit results separately and push. Main and all historical evidence unchanged.
One next scientific recommendation, without a second experiment here.
