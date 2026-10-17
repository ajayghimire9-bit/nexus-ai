# H14 independent pre-execution readiness audit

Source-only adversarial review. No collection, no training, no real
MountainCar environment. Not a control result. Not learning-to-learn,
not AGI.

## Identifiers

- Audit branch `cursor/h14-runner-independent-readiness-audit`
- Runner parent `591c2c2823f0664943b37cdbd8fe5e3832a9fc5b`
- Locked protocol parent `05542bb17da0e6f2af9075dce4ea97c135744e67`
- Feasibility ancestor `1949beda85f210521991c82294904ea415a07f39`

## Hash verification

| Object | SHA256 | Status |
|---|---|---|
| `configs/mcc_candidate_reuse.yaml` | `df155e89b8a4810bdbf04cfc121e93de7c9900235a440057dd66f7128459f81a` | match |
| `docs/NEXUS_H14_CANDIDATE_REUSE_PROTOCOL.md` | `1005e12568f3457f32638f9c7a08b0c29c7090785bf1085d097054224a012c1b` | match |
| `configs/mcc_candidate_reuse_allocation.json` | `4155621de732cdc9b9a6cda3d478c3f6aab89693be6cb430ca10a350253cff51` | match |

Physics `(0.0023, 0.0019, 0.065)` reproduces from `mcc_candidate_reuse_v1`.
Allocation remains `authorized: false`, `runs: 0`. Locked science files
were not edited.

## Execution path

CLI `--execute` → `runner.execute()` → `load_config()` →
`require_allocation()`. Unauthorized calls raise `PermissionError` before
`target_spec`, `make_task_env`, `collect_transitions`, or training imports
inside `train_seed_models`. Confirmed twice; no result artifact is written.

After a future one-run allocation the path is: H10-recipe training with
preflight collection → four reset states → shared L0 open-loop → four
controllers (multitask/scratch × fixed/redraw) → `summarize_experiment` →
exact cap check → `complete=True` only if the grid and totals match.
Exceptions force `label=incomplete` and `complete=False`. An existing
output file is refused before any new write.

## Budget accounting

Expected 15,360 + 1,600 + 2,560 + 10,240 = **29,760** env and
10×2×2×4×16×16×16 = **655,360** imagined. Wall-clock 300 s. Local CPU.

`GuardedMeter` reserves before controller `env.step` and before each
imagined batch. `make_planner` uses `uncertainty_penalty=0`, so scoring
does not add hidden ensemble inferences. Training `net` forwards are not
counted as imagined transitions, matching H12.

**Defect found:** `guarded_collect` originally reserved `n` and then
trusted `len(dataset) == n`. An extra inner `env.step` that still
returned `n` rows would have been accepted. Wall-clock was not checked
on those inner steps.

**Minimal fix on this audit branch:** wrap `make_task_env` during
collection, reject the `(n+1)`-st inner step before it runs, check the
deadline on each wrapped step, and require the inner count to be `0`
(dataset-only mock) or exactly `n`. Locked science files unchanged.

## Candidate and reset fairness

Generated 16×16 matrices, not just seed arithmetic, were compared for
all 10 seeds and 4 states. At `t=0` all four controller conditions
receive identical L0. Fixed mode reuses that matrix. Redraw `t>=1`
matches `candidate_sequences(redraw_base+1000s+10k+t)` and has no arm
term. First-decision actions match under a deterministic scorer; later
fingerprints diverge.

Reset checks observation identity and `unwrapped.state` when present.
Controllers do not transfer visited states.

**Locked-formula residual:** `redraw_base+1000s+10k+t` is not injective
across states of one seed (`10k+t` overlaps). There are 450 unique
redraw seeds for 600 intended `(seed, state, step)` slots. Within one
state, `t=1…15` stay unique, and arms still share the same matrix.
Changing the stride would alter the locked protocol, so it was left
unchanged. States are averaged and are not extra model-training
replications.

## Training fairness

The runner copies the frozen H10/H12 recipe: three sources × 512,
source RMS, 15 pretrain epochs, target 128+32, target RMS, 20 epochs,
residual `(64, 64)`, Adam 0.001, create seed `5+19s`, continue seed
`7+19s`. Both arms receive the same target tensors. Evaluation states
use the 76.1M block; collection uses 76.3M/76.4M. No holdout outcome
enters model selection. `n_actions` is hardcoded to 3, matching the
locked config. The audit added an explicit `len(priors)==3` guard.

## Statistics

Synthetic complete grids reconstruct the locked DiD, `n=10`, Student-t
95% `df=9`, and the four labels including the zero and CI-boundary
`not_established` cases. Missing, duplicated, and nonfinite cells
raise. Secondaries cannot change `classify_primary`. Incomplete execute
artifacts cannot be `complete=True`. Saved traces include the locked
`TRACE_FIELDS`, L0 actuals, and fingerprints needed to rebuild D
without resimulating.

## Adversarial tests

`tests/test_h14_independent_readiness_audit.py` covers extra collector
steps, oversized imagined batches, collection timeout, failed reset,
missing traces, wrong redraw matrices, training-seed inspection, source
count drift, duplicate seeds, partial artifacts, and overwrite refusal.

Full source-only suite: **37 passed**
(`test_h14_candidate_reuse.py` 12,
`test_h14_candidate_reuse_runner.py` 14,
`test_h14_independent_readiness_audit.py` 11).

## Unresolved risks

- A custom `collect_fn` that steps a privately constructed env, never
  calling `make_task_env`, can still hide extra steps. Production uses
  `collect_transitions`, which does call `make_task_env`.
- The locked redraw stride aliases across states of one seed, as above.
- Test hooks can inject an unmetered `score_fn`; the production path
  uses `score_library_guarded`.
- Residual MLP scoring has no recurrent hidden state; a future model
  family with persistent rollout state would need an extra reset.

## Verdict

**READY_FOR_SEPARATE_ONE_RUN_AUTHORIZATION**

The next step is separately authorizing exactly one locked H14 run.
This audit does not authorize or execute that experiment.
Session ledger remains 3304.945 s unused by this review.
