# E2.25 — Candidate-conditioned planner-quality representation

## Locked source-only development protocol

Starting GitHub/local SHA `e9a03b96921d1340a521f148cbcece3dfff368d8`.
Branch `codex/evolution2.25-planner-quality-representation`. This is
the source-only follow-up recommended by E2.24, not another scientific
controller comparison or an override of blocked experiment entry gates.

Read the master context, current state, reuse map, registry, and E2.24
report. Reuse `evidence_arbitration_bench.score_table`, existing source
helpers, `describe_support`, catalogue `features`/`plan_bound`,
`generate_candidates`, `AdaptiveProposer`, and `TrustedEvaluator` through
the existing six-receipt loop. `ObservationAwareAdaptive` and
`ContextualStrategyMemory` are not replaced or modified. No new proposer,
memory stack, evolution framework, planner, checkpoint or controller.

### Question and competing hypotheses

H-quality: permitted task/support/anchor features and explicit candidate
descriptors improve held-bundle paired planner-advantage prediction over
observation-only retrieval and a strong paired-mean baseline.

Alternative explanations: configuration alone may suffice; candidate
statistics may not represent search quality; source coverage may be too
sparse; the family-default FakeStepModel proxy may not distinguish useful
representations. E2.24's negative finding remains closed. No threshold
relaxation or post-result feature/hyperparameter search.

### Source and feedback boundaries

Use exactly the already-inspected E2.24 calibration contexts: E2.8
Pendulum/Acrobot **train bundles0/1 only**, offsets0/32/64/96,
32-row supports. Seed7 and task-ID-hashed candidate seeds exactly as
E2.24. No bundle2, validation arrays, known shifted/development task
outcomes, E2.17 arrays, reserved confirmation physics, H17 or environment
construction. Existing untracked Evolution-1 adapter files stay untouched.

Reproduce each source context's twelve proxy values once, using the
existing counted FakeStepModel scorer. Six source receipts (two anchors,
four free) are selected by the existing reset-initialized persistent
proposer per context. All four diagnostic methods train on **only those
same six receipts**, not the full oracle catalogue. Full query tables
remain evaluator-only for auditing predictions. Two anchor values are
available at query time; other query outcomes cannot enter features.

Outer validation holds out an **entire bundle** within each family,
0→1 and1→0. Fit observation normalization only on the training bundle's
observations. Train ridge feature scaling only on training pair rows.
No physics IDs/parameters, task IDs, seed integer encodings, or hidden
evaluation data enter the predictor. Candidate seeds may generate
public candidate sets; only summaries of those sets enter features.

The reused support helper has no recorded reward column and supplies
the historical synthetic `-mean(obs²)` feature. Do **not** describe that
as an observed Pendulum/Acrobot reward. Real transition changes are
available. `describe_support` is used unchanged, with this limitation.

### Fixed comparisons

1. Paired mean: mean source receipt difference for the same arm pair.
2. Observation kernel: the same paired differences, weighted by Gaussian
   observation distance. Length is the median pairwise distance among
   training-context embeddings (floor0.001). Stable normalized weights;
   no gate or missing-arm0.5 prior.
3. Context/config ridge: outer product of public task features with
   existing six arm features, trained on pairwise feature differences.
4. Candidate/context ridge: same model plus eight candidate descriptors.

Task features: intercept, source-normalized observation padded to six,
twelve unchanged support statistics, and two existing anchor receipts.
Arm features: existing E1 six features; candidate extension is three
first-action frequencies, mean/std/min/max trajectory mean centered
action, and action-switch frequency. Generate the **exact** existing
candidate arrays via `plan_bound(...,1536)` and `generate_candidates`.
This is catalogue-faithful compute, not historical sixteen-candidate
H16 control. No model rollout is used to calculate a feature.

For each observed arm pair use phi(a)−phi(b), target score(a)−score(b),
and its antisymmetric negative. Fit RMS scaling on training rows, then
closed-form ridge, sum-squared loss +1×||beta||². No intercept outside
the antisymmetric features, no clipping, training epochs or optimizer
search. This is **non-neural statistical fitting**, not decoder training.

Primary common-support domain: all catalogue arm pairs co-observed in
at least one of the four training contexts. Query outcomes do not
determine inclusion. Report unsupported pairs out of66 explicitly;
do not count missing coverage as success. Every method predicts the
same supported pairs on all four held-bundle contexts. No promotion or
controller integration in this branch, even if a screen passes.

### Metrics, aggregation and advance screen

Raw predicted and true paired advantages; absolute error; meaningful
sign loss on true |delta|>=0.01. Prediction |delta|<0.01 abstains and
costs0.5 sign loss; wrong sign costs1, correct sign0. Report abstention
coverage so silence cannot masquerade as accuracy. If a required
context has no meaningful pair, label that metric unavailable and
fail the screen rather than silently discard the context.

Average pairs within each context, four contexts within each fold,
then the two folds equally within each family; pool families equally.
Report family/fold/context results and full raw rows. No confidence
intervals: these are two inspected default-physics bundles per family,
not independent model/physics replications. Pairs and reverse folds
are mathematically dependent, not additional scientific samples.

Prespecified descriptive screen, required pooled **and in both families**:
candidate/context ridge MAE at least10% lower than **both** paired mean
and observation kernel; at least5% lower than context/config ridge;
sign loss no worse than either retrieval baseline. Complete finite
grid and unchanged historical files required. Failure is negative or
inconclusive representation evidence; a pass still supports only this
source-proxy diagnostic, not control, transfer, learning-to-learn or AGI.

### Budget, tests and provenance

Local CPU; **60-second hard dispatch cap**, zero real interactions,
zero neural training/checkpoint changes. One192-value proxy table
(292,512 fake imagined transitions expected from E2.24),96 cached
source receipt opportunities, eight ridge fits. Candidate descriptor
generation and linear algebra are separate overhead. Scientific
ledger327.869 used /3272.131 remaining stays unchanged; no scientific
allocation or E2.17 grant is created/reused. Preserve failed/partial runs.
Time checks occur between bounded source contexts/folds, so this is a
dispatch cap rather than preemptive OS termination.

Tests first: exact candidate hashes, feature independence from query
outcomes, train/query bundle separation, antisymmetry and deterministic
ridge fitting, informative toy regression, finite/missing-grid rejection,
and no artifact overwrite. No real simulator or neural fit in tests.
Commit implementation and this protocol before scoring the source audit.

Run:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_evolution2_25_planner_quality.py`.
Save `artifacts/evolution2_25_planner_quality.json`, source/config/code
hashes, execution SHA, raw source receipts and pair predictions,
candidate/support hashes, compute and wall/CPU. Never rewrite E2.24.

## Results

Pending execution of the committed protocol. No outcome inferred from
implementation or synthetic tests.
