# Cumulative learning-rule test: practical screen failed

Protocol/code **52355993fbf8dc39bbf7d868c86f1b2e913908b7**, starting at
12a2b2ca306737efa8412f3df288d32dc9f2d128. Branch:
`codex/seed-cumulative-learning`.
[Protocol](NEXUS_SEED_CUMULATIVE_LEARNING_PROTOCOL.md),
[configuration](../configs/seed_cumulative_learning.json),
[raw results](../artifacts/seed_cumulative_learning.json).
Raw SHA256: `fca453f103f94cf96ede04f3c935f5ce27fd9632699578bb94c0c13dc0d04930`.

## What was tested

This is an implemented meta-training comparison of an update procedure, using
only previously permitted source arrays. Four folds each trained fresh small
rules on nine tasks, then assessed three tasks excluded from that fit. Each of
three independent update-rule seeds produced four fold fits. Learned and static
rules had paired initializations, source schedules and 64 Adam updates per fit.
No checkpoint selection, HPO, old-rule replacement or world-model training.

Fold-specific normalization and the bounded reference's cap used training tasks
only. No legacy globally fitted rule weights or scale entered the worker. A new
cumulative posterior fitted all permitted old anchors and observed teaching
prefix rows; excluded query outcomes never entered inner updates or outer fits.
The existing optimizer, controller, trace helpers and metered host were reused.
All six controls were recomputed using each fold's training-only scale and cap.
Their values therefore differ slightly from the preceding globally normalized
source study; they are not silently substituted cached comparisons.

This is still reused-source development evidence. The source bank and feature
extractor were previously inspected/trained. Excluded tasks are not newly
collected validation, unfamiliar physics or independent world-model replications.

## Registered outcome

**Complete execution; learned-learning screen FAILED. Retention PASSED.**

Mean excluded-task curve MSE, averaging budgets 1,2,4,8:

- Learned cumulative: **.187597**.
- Source-trained static cumulative: .188183.
- Fixed cumulative: .189456.
- Scaled replay: **.187016**.
- Bounded fixed: **.184388**.
- No new-task correction: .200637.

The learned rule improved on static by **.31%** and fixed cumulative by **.98%**,
below the registered 5% minimum. It was .31% worse than replay and 1.74% worse
than bounded fixed. Generic cumulative fitting did not beat the strong simple
references. Ordinary evidence reuse therefore cannot be counted as success for
the learned update procedure.

Positive paired differences favor learned cumulative. Conditional 95% intervals
across three update-rule initialization/schedule seeds (df2):

- Static minus learned: +.0005863 [.0005523,.0006203].
- Fixed cumulative minus learned: +.0018595 [.0017690,.0019500].
- Replay minus learned: −.0005808 [−.0006713,−.0004903].
- Bounded fixed minus learned: −.0032087 [−.0032992,−.0031182].
- None minus learned: +.0130399 [.0129494,.0131304].

These narrow intervals measure only optimizer-seed variability on this fixed
bank and ONE frozen core. They do not measure uncertainty across new tasks or
pretrained worlds. Folds overlap in training tasks and are not extra replicates.
The fixed-cumulative-minus-replay interval has zero width because both methods
are deterministic here, not because transfer uncertainty is zero. Practical
thresholds were preserved despite positive small static/fixed contrasts.

Final retention MSE: learned .075461, static .076090, fixed cumulative .077707,
replay .078623, bounded fixed .066879, none .082170. The fixed+.01 retention
requirement passes, but cannot substitute for the learning improvement screen.

## Learning speed and sensitivity

MSE at 1 / 2 / 4 / 8 observed new-task labels:

- Learned cumulative: .225404 / .175136 / .177905 / .171943.
- Static cumulative: .225994 / .175406 / .178522 / .172810.
- Fixed cumulative: .226568 / .176015 / .179949 / .175294.
- Replay: .196656 / .190058 / .182187 / .179164.
- Bounded fixed: .187813 / .175627 / .197112 / .177001.
- None: .200637 at every budget.

The learned rule has a better final-budget point estimate than replay but a
worse budget-one estimate. Final accuracy does not establish faster learning
over the registered curve.

Fold means, learned / static / fixed cumulative / replay / bounded fixed:

- Fold 0, tasks 95000000/95040000/95080000:
  .206127 / .206491 / .207486 / .226886 / .220415.
- Fold 1, tasks 95010000/95050000/95090000:
  .206793 / .207859 / .210283 / .160249 / .166542.
- Fold 2, tasks 95020000/95060000/95100000:
  .173449 / .173945 / .175262 / .204867 / .194826.
- Fold 3, tasks 95030000/95070000/95110000:
  .164018 / .164438 / .164794 / .156062 / .155770.

Learned cumulative beat static/fixed cumulative in every fold, but its transfer
against replay/bounded fixed was mixed. The raw artifact records all twelve
task results. Task 95050000 is a conspicuous negative-transfer case: learned
.217790 versus no adaptation .077161 and bounded fixed .083447. No task was
excluded or reweighted. The next experiment must allow learning to retain a
useful current fit rather than assuming every new label warrants a large edit.

## Integrity, checkpoints and cost

All 1944 planned evaluation snapshots, 24 trained rules and 1536 optimizer rows
are complete and finite. Source schedules match between learned/static arms;
source training IDs and excluded IDs are disjoint in every fold. Independent
arithmetic checks recover held-task errors and update norms from recorded
vectors. Model state stays fixed during assessment. All historical checkpoints,
closed outcomes and result artifacts are preserved; no live policy is promoted.

The 24 NEW small JSON checkpoints live outside Git at
`runs/experimental/attempts/seed-cumulative-learning-1/rule-*.json` in the execution
worktree. Their exact hashes, provenance and weights are embedded in the raw
artifact. Reproducibility does not require rerunning training:

```sh
python3 -I -S scripts/verify_seed_cumulative_learning.py
python3 -I -S scripts/verify_seed_cumulative_learning.py --check-checkpoints
python3 -I -S scripts/verify_seed_cumulative_learning.py --restore-checkpoints runs/restored-cumulative-rules
```

Default audit is repository-only. Explicit checkpoint audit fails if any binary
is missing/wrong; restoration writes new files and refuses overwrites. All 24
original local checkpoints passed verification. They are new rule versions,
not replacements for historical frozen weights.

Host wall **3.508188 seconds**, worker body 2.050243 seconds, worker process CPU
2.863614 seconds, peak sampled RSS 308.39 MiB. All within 60-second wall/CPU and
2048 MiB sampled-RSS caps. macOS sampling is not kernel-hard memory enforcement.
Conservative debit: **5 seconds**. Ledger **1927.6321034559958 seconds used /
1672.3678965440042 remaining**. No second experiment ran.

Zero new real interactions, imagined transitions or world-model forwards.
There were 1536 outer Adam updates, 12864 tiny-controller forwards, 13152
cumulative solves, 1788 initialization solves, and 1728 evaluation update calls.
Training used 12288 source teaching presentations, 55296 repeated prefix-support
row appearances, 49152 old-anchor appearances, and 165888 query plus 165888
retention row scores. Evaluation produced 52488 query and 52488 retention row
scores; worker and host verification each repeated 52488 stored-vector query
and retention checks (104976 extra arithmetic checks per role). Source arrays
are cached reuse, not new collection. Compute is not equal across methods.

Learned/static capacity: 165/33 trainable parameters per fit, matched 64-update
budgets. The 24 checkpoints contain 3960 stored scalars; total distinct trainable
scalars across fits are 2376. Gradient norms and parameter changes are finite
and nonzero, which establishes functional training, not useful meta-learning.

The Lab shows all six source curves, conditional seed intervals and the failed
screen through read-only replay. Opening or refreshing it cannot train a model.

## Verification performed

The [verification receipt](../artifacts/seed_cumulative_verification.json) records
the clean execution reservation, 17 execution-source hashes checked against
commit 52355993fbf8dc39bbf7d868c86f1b2e913908b7, the host/worker/raw metric
agreement, exact hashes of 24 reconstructed/local rule checkpoints and the
verified journal chain. All **755 historical artifact files** at the starting
revision remain byte-identical. Main and the unrelated root-worktree files were
preserved.

Focused checks passed: **58 tests in 16.76 seconds**. The relevant regression
suite passed: **384 tests in 42.19 seconds**, using:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:/Users/ajayghimire/Projects/nexus-ai/.deps \
python3 -m pytest -o addopts='' -q tests/test_seed*.py \
tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py \
tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py tests/test_factory.py
```

The explicit checkpoint command above passed for all 24 files. Chrome headless
GUI checks passed for the correct failed-screen label, replication limitation,
learning-curve rendering, reload, mobile overflow, absence of browser errors
and raw-artifact immutability. Screenshot: private
`runs/seed-cumulative-learning-gui.png`. These were read-only replay checks,
not a second scientific execution. No historical controller study was rerun.

## One next experiment

Test a small learned scalar update/retain gate against a source-trained constant
gate and the same strong replay/bounded references, using task-blocked source
fitting. It should learn how much of a proposed correction to apply, including
zero, rather than changing only coordinate plasticity. The first-label loss and
negative-transfer task justify testing this specific limitation. Do not add
capacity broadly, retune the closed audit, or claim general learning-to-learn
without a separate genuinely fresh validation stage. This proposal is unrun.
