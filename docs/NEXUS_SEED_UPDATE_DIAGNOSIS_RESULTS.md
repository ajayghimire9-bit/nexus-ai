# Source update-magnitude diagnosis: mixed evidence, no first-update explanation

Completed once from protocol/code **9c379aa90701bb522411d80dee211cf05ca4557d**,
starting at e40539059c7076762d0699bde7998996ae8b328f. Branch:
`codex/seed-update-magnitude-diagnosis`.
[Protocol](NEXUS_SEED_UPDATE_DIAGNOSIS_PROTOCOL.md),
[configuration](../configs/seed_update_diagnosis.json),
[raw source traces](../artifacts/seed_update_diagnosis.json).
The previous nonlinear-learning failure remains unchanged.

## Finding

**Predeclared label: `pattern_not_supported`.** The median taskwise ratio of
learned/replay first-update norms was 12.5538, above the registered 2× threshold.
However, only 5/12 source tasks had worse query error after the first learned
update, below the required 8/12. Seven improved. A large step is not itself
evidence of a harmful step or an identified cause of the closed audit failure.

Mean first-step L2 norms: learned .398446, static .396467, fixed .394518,
replay .031678, none 0. The first learned update corrected 98.32% of its one
observed support residual on average. Mean support squared error fell from
.265105 to .0000726; replay left .219968. This near-interpolation did not
guarantee lower errors on other source observations.

Mean source query MSE at prefixes 0 / 1 / 2 / 4 / 8:

- Learned: .200988 / .233754 / .176085 / .226236 / .213939.
- Static: .200988 / .236376 / .177033 / .228201 / .218062.
- Fixed: .200988 / .240979 / .179640 / .233062 / .226917.
- Replay: .200988 / .196987 / .190318 / .182324 / .179223.
- None: .200988 at every prefix.

The complete nine-prefix traces show learned error peaking at .338179 at
prefix six; replay is .180310 there. The instability is not confined to prefix
one. No later-prefix hypothesis was tested prospectively in this diagnostic.

First learned update minus its own initial query error:
+.032766 [−.037982,+.103514]. Replay-minus-learned first-query MSE:
−.036768 [−.106929,+.033393]. Both exploratory intervals include zero.
Twelve reused source-task means, three controller seeds averaged within each;
one frozen world-model core. These are descriptive conditional intervals on
training data, not new independent validation.

Taskwise first-update query error changes, in registered task order:
−.020026, −.006394, −.034110, −.000237, +.034304, +.376058,
+.000373, +.006911, −.002402, −.011960, −.017004, +.067681.
Post-hoc sensitivity: removing the largest-harm task 95050000 changes the mean
to +.001558; the all-task median is −.001319. This explains sensitivity of the
aggregate, without excluding that task or changing the registered label.

Old-task MSE at prefix zero / eight: learned .082166 / .079860, static
.082166 / .080552, fixed .082166 / .082079, replay .082166 / .078978.
Retention alone does not distinguish a useful learned rule here.

## Implementation and integrity

Added one fixed source-diagnosis adapter to the existing EXPERIMENTAL host.
Reused LessonTask, scaling, initial solve, update/correction and saved
PlasticityController weights. No new optimizer, memory or resource framework.
The host extracts only training arrays, stored scale and source-fitted weights;
no development/audit/control fields or repository path enter the worker API.
The trusted host and same-user filesystem are not adversarial OS isolation.

All 1,620 planned prefix snapshots are present and finite. Independent stdlib
arithmetic recomputes query/retention MSE and update norms from saved vectors.
All restored controller weights remain identical. The 990 stored controller
parameters are frozen; zero trainable parameters or outer optimizer updates.
Historical core/readout checkpoints are not loaded or modified.

Protocol wording clarification: its shorthand "no fitting" means no outer
controller/network retraining. The explicitly specified inner corrections do
fit disposable task residual vectors and are counted below. This is not zero
algebraic adaptation. The locked protocol and its original hash are preserved.

The Lab's `/experimental` page displays a read-only **source-only diagnosis**
card with prefix curves and the registered negative label. Fresh-clone replay
needs no Torch, model binaries or simulation. This does not change live Seed
actions, select an incumbent or promote a learning rule.

## Resource accounting

One registered run: .408517 seconds worker-body wall time, **1.433732 seconds
host dispatch**, 1.001494 seconds worker process CPU, 286.08 MiB peak sampled
RSS. All within 30-second wall/CPU and 2048 MiB sampled-RSS limits. Conservative
session debit: 3 seconds, including startup and rounding.

Zero new environment interactions, zero imagined transitions, zero world-model
forwards and zero outer training. There were 576 frozen tiny-controller forward
calls, 1,440 inner update calls including 288 no-ops, 1,152 active corrections,
180 initial solves, 864 protected solves, 3,456 protected-anchor and 2,448 replay
examples processed. Support/query arrays are cached source reuse, not new data.
macOS RSS sampling is not an exact kernel memory limit.

Ledger: **1919.6321034559958 used / 1680.3678965440042 remaining seconds**.
No second study was run. Exact hashes, runtime and source revision are in the
raw artifact and its host receipt. Historical artifacts remain immutable.

## Verification performed

Before execution: 58 focused tests passed in 14.52 seconds. After recorded-data
and GUI support: 52 focused tests passed in 15.20 seconds; the relevant complete
Seed/Lab/planning/expression/factory regression selection passed **329 tests in
29.29 seconds**. Command: `python3 -m pytest -o addopts='' -q tests/test_seed*.py
tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py
tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py
tests/test_factory.py`, with source/dependency paths and single-thread settings.
The full historical scientific suite was not executed.

Chrome headless GUI: four checks passed, zero page errors. The source label,
5/12 count, curve and refresh worked. Playwright's default bundled browser was
absent; the installed Chrome channel worked without a download. Repository
verification passed 40 documents and 158 links. All 749 prior artifact blobs
match the starting revision. Execution-source hashes match their Git objects
at9c379aa, including the committed original protocol. The host ledger reconciles
exactly. [Machine-readable verification](../artifacts/seed_update_diagnosis_verification.json)
records hashes, runtime versions and costs. The original checkout's untracked
adapter files are excluded; main is unchanged.

## One next experiment

On source data only, test whether bounding the protected correction's output
change stabilizes its later prefixes, against both unchanged protection and
the existing scaled replay rule. Predeclare the bound and objective on source
data, then require a separately registered fresh validation gate before any
runtime promotion. This is a proposal, not an executed improvement or a claim
that update size explains the previous failure. Do not increase model capacity.
