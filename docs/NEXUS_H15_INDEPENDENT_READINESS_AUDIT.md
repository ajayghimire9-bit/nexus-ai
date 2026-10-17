# H15 independent pre-execution readiness audit

Source-only adversarial review. No collection, no training, no real
MountainCar environment. Not a control result. Not learning-to-learn,
not AGI.

## Identifiers

- Audit branch `cursor/h15-runner-independent-readiness-audit`
- Runner parent `f18ad85f0053be05a291a5684b1b7158214e890f`
- Locked protocol parent `ff91a940f5a4ebca18f212942e8134c5ee6c22ee`
- H14 results ancestor `b05f9f2c9f3a5bd63ce0b55655d888d7f95d57b8`

Local HEAD, `origin/cursor/h15-candidate-reuse-confirm-runner`, and the
reported runner SHA matched before this audit. Working tree was clean.
`main` was not merged.

## Hash verification

| Object | SHA256 | Status |
|---|---|---|
| `configs/mcc_candidate_reuse_confirm.yaml` | `bc263e69e3a57ae3bcb4c27616f0c4736deaf123dab6c0c3cb49311b3804c193` | match |
| `docs/NEXUS_H15_CANDIDATE_REUSE_CONFIRM_PROTOCOL.md` | `4e5f7a5d0f55c6f183d1c78046597a99f5dfd8f788546a1d91c8270dad0116af` | match |
| `configs/mcc_candidate_reuse_confirm_allocation.json` | `210f3a631a3081152f63e7a6b4d53bf98a2b8e157be52e515a7c7b5a53e39362` | match |

Physics `(0.004, 0.0021, 0.05)` reproduces from
`mcc_candidate_reuse_confirm_v1`. Allocation remains
`authorized: false`, `runs: 0`. Frozen H10–H15 science files were not
edited.

## H14-versus-H15 implementation differences

Function inventories match. Behavioral diffs are only the registered
confirmation changes:

- Target physics and holdout rule
- 77M seed block versus H14 76M
- Starting SHA / output filename / task identifiers
- H15 labels, with an extra refuse if an `h14_` label is emitted
- Helper aliasing (`h14.*` instead of `lock.*`) because the H15 lock
  module does not re-export candidate helpers

No unexpected change in model creation, collection, training,
normalization, candidate generation, planning, reward, reset,
aggregation, persistence, or resource accounting.

## Execution path

CLI `--execute` → `runner.execute()` → `load_config()` →
`require_allocation()`. Unauthorized calls raise `PermissionError`
before `target_spec`, `make_task_env`, `collect_transitions`, or
training imports inside `train_seed_models`. Confirmed; no result
artifact is written. This audit did not invoke `--execute`.

After a future one-run allocation the path is: H10-recipe training
with preflight collection → four reset states → shared L0 open-loop →
four controllers (multitask/scratch × fixed/redraw) →
`summarize_experiment` → exact cap check → `complete=True` only if
the grid and totals match. Exceptions force `label=incomplete` and
`complete=False`. An existing output file is refused before any new
write.

A later one-run allocation must also update `load_allocation()` to
accept `authorized: true`, `runs: 1` with a usage record, as H14 did.
The current loader still rejects any authorized record. That is an
authorization-stage change, not a current execution leak.

## Budget accounting

Independently reconstructed: 15,360 + 1,600 + 2,560 + 10,240 =
**29,760** env and 10×2×2×4×16×16×16 = **655,360** imagined.
Wall-clock 300 s. Local CPU.

`GuardedMeter` reserves before controller `env.step` and before each
imagined batch. Exact-cap succeeds; cap-plus-one is refused before
the extra operation. `make_planner` does not add hidden ensemble
inferences. Training forwards are not counted as imagined transitions,
matching H14.

Production `collect_transitions` calls `make_task_env`. The H15
runner wraps both `nexus.tasks.spec.make_task_env` and
`nexus.world.data.make_task_env` for the duration of collection. An
extra inner step is rejected before it runs. A dataset whose length
drifts from the reservation is refused.

## Candidate and reset fairness

Generated 16×16 matrices, not just seed arithmetic, were compared for
all 10 seeds and 4 states. At `t=0` all four controller conditions
receive identical L0. Fixed mode reuses that matrix. Redraw `t>=1`
matches `candidate_sequences(redraw_base+1000s+10k+t)` and has no arm
term. Within one state, `t=1…15` stay unique and both arms share the
same matrix.

**Locked-formula residual:** 450 unique redraw seeds for 600 intended
`(seed, state, step)` slots. Changing the stride would alter the
locked confirmation, so it was left unchanged.

Reset checks observation identity and `unwrapped.state` when present.
Controllers do not transfer visited states. Planners do not accept
realized counterfactual returns.

## Training fairness

The runner copies the frozen H10/H14 recipe: three sources × 512,
source RMS, 15 pretrain epochs, target 128+32, target RMS, 20 epochs,
residual `(64, 64)`, Adam 0.001, create seed `5+19s`, continue seed
`7+19s`. Both arms receive the same target tensors. Evaluation states
use the 77.1M block; collection uses 77.3M/77.4M. No H14 outcome
enters model selection. Source count must be exactly three.

## Statistics

Synthetic complete grids reconstruct the locked DiD, `n=10`,
Student-t 95% `df=9`, and the four H15 labels including the zero and
CI-boundary `not_established` cases. Missing, duplicated, missing-mode,
and nonfinite cells raise. Secondaries cannot change
`classify_primary`. Incomplete execute artifacts cannot be
`complete=True`. H14 cells are never pooled into an H15 label.

## Adversarial tests

`tests/test_h15_independent_readiness_audit.py` covers extra collector
steps, short collection length, production collector through the
guarded factory, oversized imagined batches, collection timeout,
control timeout, failed reset, hidden-state mismatch, nonfinite
scores, scoring exceptions, wrong redraw matrices, training-seed
inspection, missing modes, duplicate seeds, partial artifacts, and
overwrite refusal.

Full source-only suite: **26 passed**
(`test_h15_candidate_reuse_confirm.py` 5,
`test_h15_candidate_reuse_confirm_runner.py` 10,
`test_h15_independent_readiness_audit.py` 11).

## Defects and fixes

No implementation defect required a code change. The H14 collector
inner-step wrap is already present in the H15 runner. Frozen science
was not edited.

## Unresolved risks

- A custom `collect_fn` that steps a privately constructed env, never
  calling `make_task_env`, can still hide extra steps. Production uses
  `collect_transitions`, which does call `make_task_env`.
- The locked redraw stride aliases across states of one seed, as above.
- Test hooks can inject an unmetered `score_fn`; the production path
  uses `score_library_guarded`.
- Residual MLP scoring has no recurrent hidden state; a future model
  family with persistent rollout state would need an extra reset.
- A later one-run allocation must update `load_allocation()` before
  `authorized: true` can be loaded.

## Verdict

**READY_FOR_SEPARATE_ONE_RUN_AUTHORIZATION**

The next step is separately authorizing exactly one locked H15 run.
This audit does not authorize or execute that experiment.
Session ledger remains 3300.660 s unused by this review.
