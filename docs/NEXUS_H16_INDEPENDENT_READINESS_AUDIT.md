# H16 independent pre-execution readiness audit

Source-only adversarial review. No collection, no training, no real
MountainCar environment. Not a control result. Not learning-to-learn,
not AGI.

## Identifiers

- Audit branch `cursor/h16-same-state-independent-readiness-audit`
- Runner parent `1f5a75709cc4048cc3f7e084e17db47e3c4ec6ed`
- Locked protocol parent `b577d05c567dce5ced83979140b3c3751e2aaacd`
- Feasibility ancestor `929c93c2813db9f9d9e74639f7682439364aecf1`

Local HEAD, `origin/cursor/h16-same-state-library-runner`, and the
reported runner SHA matched before this audit. The lock commit is
the direct parent. Working tree was clean. `main` was not merged.

## Hash verification

| Object | SHA256 | Status |
|---|---|---|
| `configs/mcc_same_state_library.yaml` | `e71b0053331afa39db5b368510c8524d23e454fb490a2bde57e72ac39f32834c` | match |
| `docs/NEXUS_H16_SAME_STATE_LIBRARY_PROTOCOL.md` | `f757e8a8e1f08d0b5abeb7cffa84071a79e1c5e93ded89b6817fe25e8f7fcea7` | match |
| `configs/mcc_same_state_library_allocation.json` | `02d4680d308ad17384ecd148ce48b7e319cffa4710be8304165ebc847d7474fd` | match |

Physics `(0.0015, 0.0014, 0.055)` reproduces from
`mcc_same_state_library_v1`. Allocation remains
`authorized: false`, `runs: 0`. Closed H14/H15 parent hashes match.
H14 allocation is consumed (`authorized: true`, `runs: 1`). H15
allocation is consumed and closed. Frozen H10–H16 science files were
not edited.

Session ledger remains **303.777 s used / 3296.223 s remaining**.

## Execution path

CLI `--execute` → `runner.execute()` → `load_config()` →
`require_allocation()`. Unauthorized calls raise `PermissionError`
before `target_spec`, `make_task_env`, `collect_transitions`, or
training imports inside `train_seed_models`. Confirmed; no result
artifact is written. `lock.execute()` is independently gated the
same way. This audit did not invoke `--execute`.

After a future one-run allocation the path is: H10-recipe training
with preflight collection → four reset states → one 12-step
model-independent prefix → score L0 and redraw at t=8 and t=12 →
reset-plus-prefix reconstruction → shared candidate realization →
`summarize_experiment` → exact cap check → `complete=True` only if
the grid and totals match. Exceptions force `label=incomplete` and
`complete=False`. An existing output file is refused before any new
write.

A later one-run allocation must also update `load_allocation()` to
accept `authorized: true`, `runs: 1` with a usage record, as H14/H15
did. The current loader still rejects any authorized record. That is
an authorization-stage change, not a current execution leak.

## State restoration

This is the highest-risk component. **Empirical identity on the real
Gymnasium MCC stack has not been established.** The runner enforces
the locked contract as a fail-closed execution-time gate. A future
authorized run must verify identity while performing the registered
84,000 real operations. It must not add uncounted extra simulator
steps, write `.state`, or relax `np.array_equal`.

Static Gymnasium 1.4.0 review (no env constructed):

- `Continuous_MountainCarEnv.reset` calls `super().reset(seed=seed)`
  then samples position from `np_random`. Repeated `reset(seed=S)`
  reseeds.
- Native and gravity-patched `step` write `state` as float32 after
  the first action. Reset state may be float64; the runner compares
  float32 copies, matching the lock.
- `TimeLimit.reset` sets `_elapsed_steps = 0`. `step` increments by
  1 and truncates only at 200. The runner walks the `.env` chain and
  requires `_elapsed_steps == t`.
- `OrderEnforcing.reset` and `PassiveEnvChecker.reset` forward
  `seed`. The checker calls `env.reset` once.
- `MountainCarDenseRewardWrapper` forces wrapper `terminated=False`
  and records `gym_terminated`. Observation noise and action delay
  are forbidden. `_mcc` target specs do not enable them.

The runner never assigns `.state` or `_elapsed_steps`. Each
candidate does `reset(seed=state_seed)` plus the stored first `t`
actions, then exact observation, raw-state, reward, termination,
and elapsed-step checks before its 16 actions. Repeated mock
replays matched. Reset-time mismatch is rejected before any reserved
step. Mid-replay reward mismatch is rejected after the charged
prefix step and invalidates the cell.

## Candidate fairness and oracle isolation

Generated 16×16 matrices, not just seed arithmetic, were compared
for all 10 seeds × 4 states. L0 is `candidate_sequences(library_base
+ 10s + k)` and is identical at t=8 and t=12. Redraw uses
`redraw_base + 10_000s + 100k + t` (not the H14/H15 aliasing
stride). All 80 redraw seeds and fingerprints are unique. There is
no arm term.

Production `score_library_guarded` accepts only `(model, obs,
sequences, meter)`. Passing `realized=` raises `TypeError`.
`make_planner` / `_score_batch` unroll imagined model steps and
`mountaincar_step_reward`; they do not take simulator futures.
Scoring uses the recorded later observation, so it does not spend
unbudgeted reset-plus-prefix steps. Replay still has to reproduce
that observation before realization.

Adversarial scores that prefer index 0 while oracle prefers 15 still
select index 0. First-index `argmax` is deterministic. `G(x,L,j)` is
realized once per library and shared. Selected indices are stored
from predictions before realization and are not rewritten from `G`.

## Training fidelity

The runner reuses H14 `train_seed_models` without editing that
module. Inspected create/continue path: three sources × 512, source
RMS, 15 residual pretrain epochs, target 128+32, target RMS, 20
epochs, hidden `(64, 64)`, Adam 0.001, create seed `5+19s`, continue
seed `7+19s`. Both arms receive the same target tensors.
`guarded_collect` wraps `make_task_env` so dataset length cannot
hide extra inner steps.

## Statistics

Independent reconstruction of

`D_same = (S_mt_L0 - S_sc_L0) - (S_mt_redraw - S_sc_redraw)`

averages eight nested later states per model seed, then Student-t
95% with `n=10`, `df=9`. Synthetic grids recover all four labels,
including `lo=0` / `hi=0` `not_established` and `complete=False`
`incomplete`. Missing seeds, duplicate seeds, missing later states,
and nonfinite selected returns raise. `S_a = O - Regret_a` and
`S_mt - S_sc = Regret_sc - Regret_mt` hold; oracle opportunity
cancels. Secondaries cannot change `classify_primary`. H14/H15 cells
are never pooled.

## Budget safety

Independently reconstructed: 15,360 + 1,600 + 480 + 25,600 + 40,960
= **84,000** env and 80 × 2 × 2 × 16 × 16 = **81,920** imagined.
Wall-clock 300 s. Local CPU. The standing 16,000-step headroom is
not used.

`GuardedMeter` reserves before every reference, replay, candidate,
collector inner step, and imagined batch. Exact-cap succeeds;
cap-plus-one is refused before the extra operation. Short collection
length, extra inner collector steps, prefix timeout, candidate
timeout, scoring exceptions, overwrite, and interrupted artifacts
are fail-closed and cannot receive a success label.

## Adversarial tests

`tests/test_h16_independent_readiness_audit.py` (11 tests) covers
frozen hashes and closed parents, unauthorized CLI/`lock.execute`
denial, full L0/redraw matrix identity, 80 unique redraw libraries,
repeated reset-plus-prefix reconstruction, Gymnasium TimeLimit/MCC
reset contracts, wrapper-stack extras versus forbidden wrappers,
production scorer isolation, adversarial oracle disagreement,
first-index ties, selection algebra, label boundaries, H10 training
inspection, independent budget arithmetic, env and imagined
cap-plus-one, short and extra collector steps, production
`collect_transitions` through the guarded factory, timeouts,
scoring exceptions, overwrite refusal, and incomplete artifacts.

Full source-only suite: **30 passed**
(`test_h16_same_state_library.py` 5,
`test_h16_same_state_library_feasibility.py` 6,
`test_h16_same_state_library_runner.py` 8,
`test_h16_independent_readiness_audit.py` 11).

## Defects and fixes

No implementation defect required a code change. Frozen science was
not edited.

## Remaining risks

- **Real MCC float32 identity after an 8- or 12-step prefix is
  unverified.** It remains a mandatory fail-closed runner-time gate.
- `gym.make` also wraps `OrderEnforcing` and `PassiveEnvChecker`.
  The lock requires the named MCC wrappers and forbids noise/delay;
  it does not reject those standard Gymnasium extras. They forward
  `seed` and do not assign `.state`.
- DenseReward forces wrapper `terminated=False`. Inner
  `gym_terminated` is recorded and does not abort the cell, matching
  the published H10–H15 MCC interface.
- A custom `collect_fn` that steps a privately constructed env,
  never calling `make_task_env`, can still hide extra steps.
  Production uses `collect_transitions`, which does call it.
- Test hooks can inject an unmetered `score_fn`; the production path
  uses `score_library_guarded`.
- Residual MLP scoring has no recurrent hidden state; a future model
  family with persistent rollout state would need an extra reset.
- A later one-run allocation must update `load_allocation()` before
  `authorized: true` can be loaded.
- Timeout messages still say “H14 time cap reached” because H16
  reuses the historical H14 meter. Cosmetic only.

## Verdict

**READY_FOR_SEPARATE_ONE_RUN_AUTHORIZATION**

Real Gymnasium restoration has not been empirically verified and is
a mandatory fail-closed execution-time gate.

The next step is separately authorizing exactly one locked H16 run.
This audit does not authorize or execute that experiment.
Session ledger remains 303.777 s used, 3296.223 s remaining.
