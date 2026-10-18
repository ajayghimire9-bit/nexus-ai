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

**Negative.** The candidate-conditioned representation fails every
family and pooled advancement screen. It is worse than both strong
simple baselines and the context/configuration ablation. No retuning,
controller integration, promotion or scientific execution followed.

Execution/protocol commit:
`17011ef9a07eae5d95b9e7e8ff0ebb605f103e56`. The tracked tree was
clean before scoring. The two unrelated untracked Evolution-1 files
were preserved. Artifact
`artifacts/evolution2_25_planner_quality.json`, SHA256
`2e954a219cd5bfcc9e599393b7e6a00f0950c0dc48910c526d2697d67cea398c`.
Original code/protocol hashes can be verified against this execution
revision even though this results section was added afterward.

### Pair prediction and abstention

Equal-context/fold/family pooled advantage MAE:

- Paired mean: **0.0109969**; meaningful sign loss **0.0253968**;
  abstention **5.0794%**.
- Observation kernel: **0.0122852**; sign loss **0.0253968**;
  abstention **5.0794%**.
- Context/config ridge: **0.0628861**; sign loss **0.0317956**;
  abstention **3.7996%**.
- Candidate/context ridge: **0.0814084**; sign loss **0.0776976**;
  abstention **2.5542%**.

Lower abstention is not success: candidate/context ridge makes more
confident sign mistakes. Its MAE is about **7.40×** paired mean,
**6.63×** observation kernel, and **1.29×** configuration ridge.
These are descriptive source-proxy ratios, not statistical significance.

Pendulum MAE, in the same four-method order:
**0.0109393 / 0.0117056 / 0.0669732 / 0.0858807**.
Sign loss **0.0168651 / 0.0168651 / 0.0213294 / 0.0484585**.

Acrobot MAE:
**0.0110544 / 0.0128649 / 0.0587990 / 0.0769361**.
Sign loss **0.0339286 / 0.0339286 / 0.0422619 / 0.1069368**.

All four contexts and both reverse folds remain in the results,
including poor contexts. For example, Pendulum held-bundle1/offset0
has candidate MAE0.19503 versus paired mean0.02131; Acrobot
held-bundle0/offset96 has0.17321 versus0.00656. No sample was dropped
to improve the mean. Raw per-pair predictions and per-context metrics
are saved, with independent arithmetic checks of equal-context
aggregation. Reversed folds share data and are not independent trials.

### Coverage and diagnostic interpretation

There are **260** audited query-pair rows. Training each model uses
60 pair rows formed from only four contexts × six receipts. Pendulum
held-bundle0 covers20 of66 possible pairs; the other three folds cover
15 of66. Thus46–51 pairs per fold remain unsupported, explicitly
excluded from this common-domain comparison. This cannot establish
quality over the full catalogue or an ability to select a new planner.

The arithmetic-only rank audit found configuration designs rank12
with126 columns, candidate designs rank20 with294 columns in all
four folds. Each group of15 pair differences arises from only six
scalar scores, hence at most five independent within-context
contrasts; four contexts give at most20. Adding antisymmetric rows
does not add information. This exposes a large feature/feedback
imbalance; it **does not prove** the unique reason for failure.
Candidate summaries may also omit relevant search structure. Those
explanations remain competing possibilities, and no capacity/learning
rate/regularization search was performed after scoring.

Importantly, the simple paired mean already predicts these source
differences more accurately than observation-weighted retrieval.
The evidence does not support adding the fitted representation to
`ObservationAwareAdaptive`. It also does not establish that candidate
conditioning is generally useless: this is a small, inspected,
family-default FakeStepModel suite, not a real-control target.

**Post-run leakage audit:** the inherited full-catalogue min/max unit
scale means public anchor receipts indirectly depend on unobserved
query extrema. No query truth dictionary reaches fitting/features,
but that interface property is **not** end-to-end information isolation.
A deterministic test keeps raw anchors fixed, changes an unobserved
extreme, and demonstrates changed scaled anchor feedback. This makes
the fixture transductive; it cannot be promoted as an independently
isolated real-control evaluation. Only the ridge methods explicitly
use query-anchor values, whereas both simple baselines ignore them.
The ridge methods still lose, but the comparison must retain this
information-asymmetry caveat. No historical scale or outcome was
rewritten and no experiment was rerun. A future real-control study
must freeze feedback scaling on training/revealed data before query
outcomes exist; closed proxy outcomes cannot repair that independence.

### Resource accounting and safeguards

Complete execution **0.381996s wall /0.369932s CPU**, within60s.
**Zero real interactions**; no environment construction or neural
training. There were **192** full-catalogue source proxy scores,
**292,512** fake imagined transitions,3872 fake-step calls,96 cached
source receipt opportunities and **eight** diagnostic ridge fits.
Two reverse folds ×two fitted representations ×two families =eight models.
Each model uses the same60 source pair labels (120 rows after adding
the algebraic negatives). Feature generation is additional allocation/
CPU work, not additional planner evaluation. Tests incur separate
synthetic operations; these run totals are not all session test costs.
Python3.13.5, NumPy2.5.4, local CPU.

All **304** pre-existing root JSON artifacts were verified unchanged,
including E2.24's negative result and failure record. Source bundle
episode-seed intersections are empty in both families (six recorded
episode IDs per bundle). Whole NPZ hashes, support hashes, candidate
hashes, source receipts, fit hashes and execution SHA are saved.
The rank audit reconstructs only features, with zero new model steps,
environment steps or fits. Scientific ledger remains
**327.869 used /3272.131 remaining**, H17 blocked, E2.17 grant consumed.

### Tests

Pre-execution synthetic checks: **18 passed in1.22s**. Additional
post-result tests verify aggregation, hash provenance and that
unrevealed full training tables cannot affect fitted predictions.
Focused command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution2_planner_quality.py -p no:cacheprovider -o addopts='' -q`.
Run the relevant source-only Evolution regression tests as well;
scientific/collection suites are excluded deliberately.

Final selected regression command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution2_planner_quality.py tests/test_evolution2_evidence_arbitration.py tests/test_evolution2_observation_memory.py tests/test_evolution2_observation_memory_cross.py tests/test_evolution2_planner_adapter.py tests/test_evolution1_toy_loop.py tests/test_evolution2_evolutionary_search.py tests/test_evolution1_resources.py tests/test_evolution2_cross_task_screen.py tests/test_evolution2_pendulum_acrobot_protocol_v2_pilot.py -p no:cacheprovider -o addopts='' -q`.
**159 passed in3.08s**. These include the explicit inherited-normalization
leak demonstration, not a claim that the current fixture is leakage-free.
No full repository scientific/collection suite was run. Source arrays
needed for reproduction are tracked in Git; no new checkpoint binary
is required by this diagnostic. The raw capture is mechanically complete,
but the post-run audit marks evaluation independence and scientific
advancement **false**.

### One next necessary milestone

Repair the **future evaluator's feedback-normalization boundary** so
training/revealed statistics are frozen before queries and changing
unobserved query scores cannot alter public feedback. Validate this
source-only, leaving all historical outcomes/scalers untouched. That
boundary repair is necessary before a scientifically isolated
real-control quality-label study, not evidence of better control.
Do not reopen E2.17/H17, allocate interactions, or continue this branch
with another feature/threshold sweep.
