# Teaching-prefix consistency: source feature informativeness audit

Starting revision: **0c4a3809ee12b00986fa9ddc4b9a0d2423e6a109**, matching
GitHub after fetch. Branch: `codex/seed-prefix-consistency-audit`. The preceding
gate's failure is preserved. No live learner, historical checkpoint, closed
evaluation, main or unrelated root-worktree file is modified by this study.

## Question

H-prefix: observed teaching-prefix consistency contains useful information
about the query benefit of a proposed cumulative update, beyond the present
single-row context and the number of examples. Alternatives: update usefulness
is adequately predicted by a constant/prefix mean, or this small representation/
linear learner cannot extract transferable signal. A failed audit cannot prove
that no usable information or better nonlinear predictor exists.

This is a predictive feature diagnosis, not another gate training search.
It cannot establish realized learning curves, control improvement or general
learning-to-learn. No policy or checkpoint is promoted even if the screen passes.

## Reuse and fixed reference

Reuse cumulative_learning.prepare_fold/posterior, learning_benchmark.initial,
update_diagnosis.source_pack/paired and the existing EXPERIMENTAL host/worker/
shared runner. The existing E2.25 fit_ridge/predict_ridge arithmetic is extracted
to the small numeric nn/ridge.py helper, with the original public functions
delegating to it. Antisymmetric augmentation, RMS normalization, ridge1 and
results are unchanged; source-only equivalence tests guard this extraction.
Do not run any old Evolution benchmark or source collection.

For each task and prefix1–8, construct a fixed reference using observed support
and old anchors only. Start with the existing old-anchor initial fit (ridge .01).
The candidate is the unit-diagonal cumulative posterior (ridge .1), centered at
that initial fit, using four anchors and the observed prefix. After each prefix
the reference takes the complete candidate. It never follows predicted gates.

At each such reference state, evaluator-owned query rows label:

`utility = query_MSE(before) - query_MSE(candidate)`.

Positive means the full update helps. The counterfactual retain action uses
the unchanged before-fit. Features and the reference trajectory are computed
before evaluator labels and accept no query argument. Query labels train the
predictor only on permitted training tasks. Excluded-task queries are scored
after all fold predictors are frozen. Do not sum these local utilities and
call them a realized adaptive-policy learning curve or episode return.

## Predeclared representations

Existing four context slots: clipped absolute current residual/4, anchor
count/16, clipped minimum mean-squared feature novelty to an anchor, channel0.
Anchor count and channel are constant here; report that limitation.

Six new support-only slots, with definitions fixed before outcomes:

1. Previous-fit MSE on earlier prefix rows, clipped at4 and divided by4; zero
   when there are no earlier rows.
2. Before-minus-candidate MSE on those earlier rows, clipped to[-4,4]/4.
3. Fraction of earlier rows whose squared error increases under the candidate;
   zero on the first example.
4. Cosine agreement between the new-row residual gradient and mean earlier-row
   residual gradient, zero when their norm product is at most1e-12.
5. Candidate-minus-before anchor MSE, clipped to[-4,4]/4.
6. Observed prefix length/8.

Seven conditions: training utility mean; training prefix-specific means;
current four slots; current plus prefix length; six consistency slots; full ten
slots; full slots with training task blocks permuted. Permutation is one locked
nonidentity cyclic task shift per fold, seed7301+fold, same shift across prefixes.
It preserves feature distributions and prefix association while breaking the
training task-feature/label association. Excluded features stay unpermuted.
One permutation is a diagnostic ablation, not a formal permutation p-value.

Ridge input/target centering uses training rows only. Keep the inherited
antisymmetric augmentation (x,y and −x,−y), RMS scaling and ridge1. This is
equivalent to ridge .5 on the original centered rows; do not call it ridge1
without disclosing augmentation. No regularization, feature or checkpoint
selection. Keep all groups, including failures. Full is the registered primary
representation; a better secondary group cannot replace it after outcomes.

## Data and exclusion

Executable source of truth: configs/seed_prefix_consistency.json. Verify the
source-plan SHA256
788d2df3ae49cdd71a91068fc0a4fd04b7a65790a475c16635bccd6135c4866b and its
bound source-artifact/array hashes. Only twelve original source tasks cross the
worker boundary, without globally fitted scales, old rules, development/audit
or control payloads. IDs95000000–95110000 at10000 spacing.

Four folds exclude task indices modulo4: nine training tasks, three assessed
tasks. Feature scale is fitted on108 training support/anchor rows per fold.
Predictor statistics use only72 training prefix cases. Each assessed task is
predicted in exactly one fold. The source bank is reused and already inspected;
these exclusions are not untouched confirmation or independent world-model fits.

## Metrics and decision

Primary: out-of-fold utility-prediction MSE, first average eight prefixes within
each task, then twelve tasks with equal weight. Required metrics are MSE,
sign accuracy, selected utility and local selection regret. Regret is
`max(utility,0) - utility*I(prediction>0)`.
Report every task/fold, retention counterfactuals and positive/negative utilities.
Keep examples1/2/4/8 separately readable, but the feature audit covers all1–8.

Signal screen requires all of:

- Full MSE at least5% below constant, prefix mean and current-plus-prefix.
- Full MSE below the full-permuted control.
- Full beats current-plus-prefix in at least3/4 folds.
- Full mean local regret no greater than the training-mean decision baseline.
- Complete finite results, intact source provenance and arithmetic checks.

Show paired task-level MSE contrasts using the existing n12 exploratory interval
helper, alongside fold sensitivity. These describe this fixed bank conditional
on saved out-of-fold fits. Correlated prefixes are aggregated inside tasks;
overlapping fold training and one frozen core limit inference. They are not
independent meta-training seeds or a confidence guarantee for unseen worlds.
The screen is a development diagnostic, not a confirmatory statistical claim.

## Resource budget and integrity

One dispatch, **30-second wall/CPU cap**,2048MiB sampled RSS, CPU only, zero Adam
updates, zero new real/imagined/world-model interactions. No neural model is
loaded or inferred. The existing host enforces process CPU/wall; macOS RSS
sampling is not a kernel-hard bound. Carried ledger:
**1933.6321034559958s used /1666.3678965440042s remaining**.

Expected counts:48 old-anchor initial solves,384 cumulative solves,20 predictor
ridge solves and8 baseline fits;384 feature cases,2016 fitting case appearances,
2880 artificially doubled ridge rows,672 held prediction cases. Evaluator scores
20736 query and20736 retention scalar rows, including fold reuse and both
counterfactuals. The unused bounded-reference cap is not fitted. Report actual
work separately from repeated saved-vector verification and GUI arithmetic.

Store complete fold/case/method/prefix grids, source IDs/hashes, features,
before/candidate vectors, query/retention scores, utility labels, predictions,
coefficients/centers/scales and model hashes. All predictor state is small JSON,
not an unavailable binary. Independent stdlib checks must verify normal
equations, input/label isolation, source scaling, predictions and aggregation;
they must not refit a learner. Missing/nonfinite fields or inconsistent counts
are invalid, not a negative scientific result. Save incomplete dispatches and
never shrink the grid or retry scientifically in this study.

Commit protocol/tested implementation before scoring source outcomes; results
separately. Preserve previous artifacts, update research status, push without
merging and recommend exactly one next study. No second experiment in this run.
