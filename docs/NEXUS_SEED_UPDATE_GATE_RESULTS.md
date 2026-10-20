# Update-or-retain gate: damping helps; context-use screen failed

Starting revision: **96825e5d49629bc26c70e8a1be21fffa7c4ca714**. Branch:
`codex/seed-update-retain-gate`. Protocol and implementation were committed at
**0ce94d00c41e36584c33629d7c44eea5b764bf13** before the single execution.
[Locked protocol](NEXUS_SEED_UPDATE_GATE_PROTOCOL.md),
[executable configuration](../configs/seed_update_gate.json),
[raw results](../artifacts/seed_update_gate.json).
Raw SHA256: `86c31e80fda3134e69e49608b2bcb402cd61755833315423bcf07dab2618690e`.

## Question and implementation

Can an observed-context-dependent scalar decide how much of a cumulative
correction to apply better than a trained constant scalar and strong simple
references? The earlier coordinate-plasticity study failed. This test preserves
that result and holds the correction direction fixed while learning strength.

Reused the existing PlasticityController's one-output logits, source optimizer,
cumulative posterior, cross-fit preprocessing, saved-trajectory audit, bounded
reference, EXPERIMENTAL host/worker and Lab. The new rule computes
`g=clamp(.5+.25*(w@context+b),0,1)` and interpolates from the previous fit to
the unit-diagonal cumulative posterior. Exact retain/full-update endpoints are
implemented. The context contains current observed residual, anchor count,
feature novelty and fixed channel0; no query labels or task identifier.

Four folds train on nine original source tasks and assess three excluded tasks.
Scaling and the bounded reference's cap are fitted within each training fold.
Three independent update-rule seeds produce12 learned and12 constant fits,
64 Adam updates each. Paired initialization and source schedules are verified.
Only source-training task queries train the outer rule; assessment queries never
enter inner updates or fits. The source bank was previously inspected and the
feature extractor previously trained: this is reused-source development evidence,
not untouched validation, unfamiliar-task confirmation or independent core fits.

## Registered result

**Complete and finite execution. Learning/source screen FAILED. Retention PASSED.**

Mean query MSE over1/2/4/8 examples, averaging excluded tasks inside each seed:

- Learned contextual gate: **.180324117**.
- Source-trained constant gate: **.180187275**.
- Unit cumulative fit: .189456479.
- Scaled replay: .187016215.
- Bounded fixed: .184388324.
- No new-task adaptation: .200636930.

The contextual gate is **.07594% worse than the constant gate**, despite improving
over unit cumulative4.8203%, replay3.5784%, bounded fixed2.2042%, and no adaptation
10.1242%. It fails the registered5% minimum against each strong reference, and
its paired constant comparison favors the constant in all three seeds. The best
simple reference is not replaced by a weaker baseline to manufacture success.

Reference-minus-learned differences, positive favoring the contextual gate;
exploratory paired95% t intervals across three update-rule seeds (df2):

- Constant gate: **−.000136842 [−.000180296,−.000093388]**.
- Unit cumulative: +.009132362 [.009025948,.009238776].
- Replay: +.006692098 [.006585684,.006798512].
- Bounded fixed: +.004064207 [.003957794,.004170621].
- None: +.020312813 [.020206399,.020419227].

These narrow intervals describe initialization/schedule variation on one fixed
bank and ONE frozen feature extractor. They do not establish uncertainty across
new tasks, environments or pretrained models. Folds overlap in training data;
tasks/prefixes are not additional independent training seeds. Zero-width
deterministic-baseline intervals are not zero uncertainty about transfer.

Final retention MSE: learned .071710, constant .072084, unit cumulative .077707,
replay .078623, bounded fixed .066879, none .082170. Learned passes unit+.01,
but this does not substitute for a learned-rule advantage.

## Learning speed and task failures

Query MSE at1 /2 /4 /8 examples:

- Learned gate: .195091 /.179839 /.173757 /.172610.
- Constant gate: .195193 /.179183 /.173685 /.172688.
- Unit cumulative: .226568 /.176015 /.179949 /.175294.
- Replay: .196656 /.190058 /.182187 /.179164.
- Bounded fixed: .187813 /.175627 /.197112 /.177001.
- None: .200637 at each budget.

Damping removes the mean first-label increase seen under unit cumulative
fitting, but a constant gate matches this benefit. That is evidence for generic
update-strength control in this setup, not demonstrated context-dependent
learning-to-learn. No full-episode action evaluation occurred.

Fold means, learned /constant /unit /replay /bounded:

- Fold0: .205196 /.204966 /.207486 /.226886 /.220415.
- Fold1: .182833 /.183361 /.210283 /.160249 /.166542.
- Fold2: .185615 /.184469 /.175262 /.204867 /.194826.
- Fold3: .147653 /.147953 /.164794 /.156062 /.155770.

The contextual gate beats constant in two folds and seven tasks, loses in two
folds and five tasks; magnitudes favor constant overall. At task95020000 it
worsens versus constant .233467 versus .229832. Task95050000 remains a serious
negative-transfer case: learned .147036 versus no adaptation .077161 and
bounded fixed .083447. Learned also loses to no adaptation on95010000,
95030000,95060000 and95080000. No task is excluded or reweighted. The raw JSON
includes every seed/task/method/prefix and per-fold membership.

## What the gate learned

Across288 excluded-task update decisions per trained arm, learned g ranges
.362773–.479258, mean .427993. Constant gates vary across fold/seed fits,
.401720–.482942, mean .445458, but never across examples within a fitted model.
Learned mean g at1/2/4/8 is .428343/.427429/.427581/.428825. Neither arm reaches
0 or1 on assessment, so the retained-state endpoint exists but was not selected
there. No gradient-saturation failure was observed in recorded training rows.

Learned gradient norms range .00007548–.04122004; constant .00000445–.03839128,
all finite and nonzero. Parameter-change norms range .121618–.777546 learned,
.072882–.386809 constant. Functional gradients and parameter changes do not
establish usefulness or global optimality of this bounded training procedure.

## Reproducibility and costs

All1944 planned evaluation snapshots,24 new rule checkpoints and1536 training
rows passed complete-grid and arithmetic checks. Saved audits recover query/
retention MSE, observed-only gate context, gate outputs, interpolation and fixed
proposal normal equations. Frozen gate hashes match before/after assessment.
Historical network weights are not loaded or replaced. No runtime promotion.

Checkpoint files are private, outside Git:
`runs/experimental/attempts/seed-update-gate-1/rule-*.json`. Exact hashes,
provenance and weights are embedded in the raw JSON. They can be reconstructed
without training:

```sh
python3 -I -S scripts/verify_seed_update_gate.py
python3 -I -S scripts/verify_seed_update_gate.py --check-checkpoints
python3 -I -S scripts/verify_seed_update_gate.py --restore-checkpoints runs/restored-update-gates
```

Default verification works without local checkpoints or Torch. Explicit
checkpoint verification fails on missing/wrong files; restoration writes only
new files and refuses overwrites. An isolated-CLI import-path issue was corrected
after the run and covered by regression tests. Post-run schema review also
strengthened the shared saved-result validator to reject an omitted training
metric, not just missing rows or nonfinite present values. All recorded metrics
already satisfy the stricter check. The study itself was not rerun and its frozen
protocol/metrics were not edited.

Host wall **4.040320s**, worker body2.262966s, process CPU3.054846s, peak sampled
RSS321.91MiB. All within60s wall/CPU and2048MiB sampled-RSS caps; macOS sampled
memory enforcement is not kernel-hard. Conservative debit **6s**. Carried ledger
**1933.6321034559958s used /1666.3678965440042s remaining**. No second study ran.

**Zero new environment interactions, imagined transitions or world-model
forwards.** Actual counters:1536 Adam updates,12864 gate forwards (12288 training,
576 assessment),13152 cumulative solves,1788 initial solves,1728 evaluation
updates. Training:12288 teaching presentations,55296 repeated support-prefix
rows,49152 anchors,165888 query and165888 retention row scores. Evaluation:
52488 query and52488 retention row scores. Worker and host validation each
repeat those stored-vector MSE checks and576 gate/proposal traces; CLI/GUI
verification is additional arithmetic, not cached new data or neural inference.

Capacity: learned5/constant1 trainable scalars per fit;24 exports store120
scalars,72 distinct trainable scalars across all fits. The fixed channel0 gives
one contextual weight no gradient; anchor count is also constant in this bank,
so its weight is redundant with the bias. Only residual and novelty vary.
Report allocated capacity honestly. Matched
teaching and64-update budgets are not identical backpropagation cost. No new
framework or larger encoder is introduced.

## Verification performed

The [verification receipt](../artifacts/seed_update_gate_verification.json)
records18 execution-source hashes checked against the clean pre-run revision,
the hash-chained reservation/settlement journal, agreement between host/worker/
tracked results, and24 verified local checkpoint hashes. All **758 historical
artifact files** at the starting revision remain byte-identical. Main and the
two unrelated root-worktree files remain unchanged.

Pre-execution focused checks passed95 tests in17.64s; the final gate-focused
checks passed27 in1.27s. Post-execution focused saved-result/host checks passed
98 in21.01s. The initial regression suite passed424 tests in46.12s; after the
stricter missing-metric check, the final suite passed **425 tests in46.66s**:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:/Users/ajayghimire/Projects/nexus-ai/.deps \
python3 -m pytest -o addopts='' -q tests/test_seed*.py \
tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py \
tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py tests/test_factory.py
```

The explicit checkpoint command passed for all24 files. Fresh-clone tests
confirm that default verification needs no ignored files or neural runtime,
explicit checkpoint audit fails when files are absent, and restoration is exact
and refuses overwrites. Saved-result corruption tests reject missing seeds,
tasks, methods, training rows, altered checkpoints/gates/contexts/proposals/states
and unfrozen assessment. Synthetic tests also reject nonfinite/string/boolean
metrics, future-label leakage and excluded-task influence on fitted gates.

Chrome headless passed8 checks: failed-screen label, replication limitation,
all six controls, curve rendering, refresh, mobile layout, no browser errors and
unchanged raw artifact. Screenshot: private `runs/seed-update-gate-gui.png`.
The Lab replays recorded data; opening it cannot train the agent. No historical
scientific experiment or second study was executed by these checks.

## One next experiment

Run a source-only, task-blocked gate-feature informativeness audit: test whether
consistency across the observed teaching prefix predicts when updating helps,
better than the current single-row error/novelty context and a constant gate.
Use only permitted training feedback and strong controls; do not enlarge the
network or extend this failed search. This separates lack of usable context
signal from learner choice. A separate fresh validation remains necessary
before any promotion or general learning-to-learn claim. This next study is unrun.
