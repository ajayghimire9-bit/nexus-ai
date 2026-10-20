# Teaching-prefix evidence: full-feature screen failed; decision signal uncertain

Branch: `codex/seed-prefix-consistency-audit`. Starting revision:
**0c4a3809ee12b00986fa9ddc4b9a0d2423e6a109**. Protocol and tested code locked at
**420ed2ae1e1b46ec3aa1891c4d94f30f4de6c36e** before the single execution.
[Protocol](NEXUS_SEED_PREFIX_CONSISTENCY_PROTOCOL.md),
[configuration](../configs/seed_prefix_consistency.json),
[raw results](../artifacts/seed_prefix_consistency.json).
Raw SHA256: `b5752b247f574c8168e4529329e653441d6147ac9f97ffb156ee2c367ec414af`.

## What was tested

Can observed teaching-prefix consistency predict the query benefit of applying
a cumulative correction better than the old single-row context, a constant,
or simply knowing the prefix length? This is a source-only feature audit after
the scalar gate failed. It does not replace or reopen that result.

At fixed unit-cumulative reference states, the candidate uses anchors and the
observed support prefix. Evaluator-owned query rows then label
`utility=MSE(before)-MSE(candidate)`. Positive utility means applying the full
correction helps; nonpositive means retention is preferable. Reference states,
candidate vectors and features never use query outcomes. Training predictors
use only nine source tasks per fold; three excluded tasks are scored afterward.
Four folds cover all twelve original tasks. Scaling is fitted within each fold.

Compare constant utility mean, prefix means, current context, current plus
prefix length, consistency-only, full and permuted-full representations.
The six consistency slots summarize earlier-label error/gain/conflicts,
gradient agreement, old-anchor damage and prefix length. Ridge is fixed,
including the inherited antisymmetric augmentation and training-only RMS scale.
No HPO or feature-group selection is performed by the runner.

The existing E2.25 numeric ridge solver was extracted into nn/ridge.py with
original public functions delegating to it. Exact equivalence tests passed.
Other reused components are cumulative_learning, learning_benchmark,
update_diagnosis, the EXPERIMENTAL host/worker and Lab. No parallel learning,
memory, planning or resource framework was added. The optional unused bounded
cap is omitted, saving36 unnecessary initial solves; default earlier-study
behavior remains unchanged.

## Registered decision: FAILED, complete execution

Out-of-fold utility-prediction MSE (lower is better):

- Full: **.002907894**.
- Constant: **.002250332**.
- Prefix mean: **.002084263**.
- Current context: .002527080.
- Current plus prefix: .002555661.
- Consistency only: .002224190.
- Permuted full: .002542289.

Full is29.22% worse than constant,39.52% worse than prefix mean,13.78% worse
than current-plus-prefix and14.38% worse than permuted full. It wins only2/4
folds against current-plus-prefix, below the required3/4. Local regret also
worsens versus constant. The registered5% intersection screen fails; a better
secondary group cannot replace the registered full representation afterward.

Full MSE by fold, alongside current-plus-prefix /constant /prefix mean:

- Fold0: .00314208 versus .00185149 /.00108059 /.00079247.
- Fold1: .00672961 versus .00682421 /.00639370 /.00587958.
- Fold2: .00124207 versus .00090673 /.00082927 /.00112122.
- Fold3: .00051781 versus .00064021 /.00069776 /.00054377.

Reference-minus-full MSE, exploratory conditional task-level95% intervals:

- Constant: −.00065756 [−.00147152,+.00015640].
- Prefix mean: −.00082363 [−.00174117,+.00009391].
- Current: −.00038081 [−.00104825,+.00028662].
- Current plus prefix: −.00035223 [−.00102367,+.00031920].
- Consistency only: −.00068370 [−.00133401,−.00003340].
- Permuted full: −.00036560 [−.00138547,+.00065426].

These are the existing exploratory n12 task-cluster intervals, conditional on
the saved out-of-fold fits and ONE frozen feature extractor. Training folds
overlap; the source bank was inspected previously. These intervals are not a
confidence guarantee for independent tasks/world-models or a confirmation test.
No pretrained-model replications or independent meta-training seeds were added.

## Prediction error versus decision quality

Local regret /sign accuracy /selected utility:

- Full: **.01142651 /58.33% /.00129410**.
- Constant: .00955269 /52.08% /.00316792.
- Prefix mean: .01017157 /47.92% /.00254903.
- Current: .01059938 /54.17% /.00212122.
- Current plus prefix: .01097590 /52.08% /.00174470.
- Consistency only: **.00617694 /53.13% /.00654366**.
- Permuted full: .01243241 /41.67% /.00028819.

Full predicts signs more often correctly than constant, but makes more costly
errors. Across96 assessed cases, full makes25 harmful updates and misses15
beneficial updates. Their mean regret contributions are .00646717 and .00495933.
The constant rule makes46 harmful updates, but no missed beneficial updates:
all four training utility means are positive, so it always takes the full
update. Fewer sign mistakes therefore do not guarantee lower regret.

The consistency-only secondary condition lowers mean local regret by **35.34%**
against that constant decision rule and wins on9/12 tasks. However, its MSE is
only1.16% below constant and remains worse than prefix mean. A **post-hoc,
unadjusted descriptive** interval for constant-minus-consistency regret is
.00337574 [−.00424022,+.01099171], including zero. Much of the aggregate gain
comes from task95050000 (+.03663394); task95020000 instead worsens (−.01610420).
This is an uncertain secondary lead, not advancement or fresh validation.

Regret and selected utility are mathematically dependent on this shared set:
`regret + selected utility = mean(max(utility,0)) = .01272060` for every method.
They must not be counted as two independent pieces of evidence. Counterfactual
query utility is also derived from two MSEs, not a new independent outcome.
This constant utility-sign rule is **not** the stronger trained fractional
constant gate from the previous study. This audit cannot establish superiority
over that gate or strong sequential replay.

All seven rules have negative mean selected local retention damage in this
sample (full−.00188456, consistency−.00164513, constant−.00055781), but those
are counterfactual old-task score changes at reference states, not realized
long-run forgetting estimates. Raw per-task and prefix records retain failures.

## Optimization and interpretation

Training versus excluded MSE: full .00144831 versus .00290789; consistency
.00169681 versus .00222419; constant .00226503 versus .00225033. The larger
representation fits training utility better but predicts excluded tasks worse.
This is compatible with overfitting/task-distribution sensitivity; it does not
prove that no useful information exists in the features. Normal equations
verify the exact ridge optimum, so adding optimizer iterations would not repair
this particular fixed ridge solution. This does not resolve optimization of
the different neural gate used in the previous study.

At prefixes1/2/4/8, full utility-prediction MSE is
.01011351 /.00678116 /.00081586 /.00154406; prefix mean is
.00993789 /.00383938 /.00068470 /.00048897. These measure prediction of update
benefit, **not** reward-prediction learning-curve MSE after an adaptive procedure.

No selected rule was executed sequentially here. Earlier retain decisions would
change later contexts, so a good local choice at a fixed full-update reference
need not yield a good adaptive learning curve. No controller ran, no goal-rate
or language capability was measured, and no learning-to-learn claim is supported.

## Cost, reproducibility and boundaries

Host wall **1.769373s**, worker body .523070s, process CPU1.261225s, peak sampled
RSS281.52MiB. All within30-second wall/CPU and2048MiB sampled-RSS limits. macOS
RSS monitoring is not kernel-hard enforcement. Conservative debit **3s**;
carried ledger **1936.6321034559958s used /1663.3678965440042s remaining**.

Zero new real interactions, imagined transitions or frozen-model forwards.
No neural training, checkpoint loading, replacement or runtime promotion.
The instrumented reference counters are48 initial and384 cumulative solves.
The complete fit grid accounts for20 ridge solves and8 mean/prefix baseline
fits; these counts are derived from the fixed executed loops/model grid, not
neural-forward counters. There are384 feature cases,2016 fitting-case appearances,
2880 artificially doubled ridge rows and672 held prediction cases. The
evaluator scored20736 query and20736 retention scalar rows including fold reuse
and before/candidate scoring. Cached source use is not new collection.

Worker, host and repeated verifier/GUI checks perform additional stored-vector
arithmetic; none refit models or generate scientific experience. The raw JSON
contains all predictor centers/scales/coefficients, model hashes, features,
counterfactual states, labels, predictions and source IDs. No missing .pt file
is required to reproduce saved predictions. Default verification is stdlib-only:

```sh
python3 -I -S scripts/verify_seed_prefix_consistency.py
```

One source audit ran. Its original metrics and protocol are unchanged; no
scientific retry, threshold change, architecture search or main merge occurred.
All previous negative results remain closed.

Metadata erratum: the original private worker receipt carries the generic field
`metrics.worst_error_increase=0`. This was an unused placeholder, **not a measured
zero forgetting result**. It did not enter the signal screen, GUI decision or any
promotion. The original receipt is preserved; future worker output now omits the
inapplicable field and a regression test enforces that omission. Use only the
explicit counterfactual retention scores above for what was actually measured.
The scientific run was not repeated for this metadata correction.

## Verification performed

The [verification receipt](../artifacts/seed_prefix_consistency_verification.json)
records18 execution-source hashes checked against the clean pre-run revision,
host/worker/tracked-result agreement, the verified reservation/settlement chain
and all four predictor-table hashes. All **761 historical artifact files** at
the starting revision remain byte-identical. Main and both unrelated files in
the root worktree remain unchanged. All predictor state is in tracked JSON;
no untracked binary is needed for saved-prediction verification.

Pre-execution checks passed115 tests in23.66s; the final prefix-focused checks
passed22 in3.16s. Saved-result/host/ridge checks passed82 in19.01s. The relevant
regression suite passed480 tests in51.57s, then **480 in50.40s** after the
metadata-only correction:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:/Users/ajayghimire/Projects/nexus-ai/.deps \
python3 -m pytest -o addopts='' -q tests/test_seed*.py \
tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py \
tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py \
tests/test_factory.py tests/test_evolution2_planner_quality.py
```

Tests cover independent ridge equivalence, same-prefix feature permutation,
query/future-label isolation, excluded-task poisoning, omitted cells/metrics,
altered states/coefficients/scales/hashes, finite typed predictions and actual
source arithmetic. Fresh-clone verification succeeds without local checkpoints
or neural/numeric libraries; incomplete results fail clearly. The previous
Evolution benchmark was not executed.

Chrome headless passed8 checks: failed-screen/fold label, counterfactual
qualification, all seven conditions, figure, refresh, mobile layout, no browser
errors and raw-artifact immutability. Screenshot inspected:
private `runs/seed-prefix-consistency-gui.png`. The Lab is read-only replay;
refresh performs no training, collection or scientific experiment.

## One next experiment

Test sequential replay of the source-frozen consistency-only update selector
on task-blocked source folds, comparing actual1/2/4/8-example learning curves
against trained fractional constant damping, scaled replay and bounded updates.
Recompute features from the evolving permitted fit, never query labels. The
local-regret lead is insufficient until it survives its own induced state
distribution and strong sequential baselines. Lock that separate exploratory
test before running; require genuinely fresh validation before promotion.
No further feature search or larger network is justified by this failed audit.
This next study is proposed, not executed.
