# H16 same-state library runner — implemented, collection unauthorized

Guarded runner on `cursor/h16-same-state-library-runner` from lock
`b577d05`. `authorized: false`, `runs: 0`. No training, no MountainCar
environment, no collection. Locked H16 science files are unchanged.
Not a result. Not learning-to-learn, not AGI.

## Runner architecture

`src/nexus/world/h16_same_state_library_runner.py` binds the locked
H16 contrast to a pre-operation meter. `execute()` calls
`load_config()` then `require_allocation()` before any environment
or training import. The current allocation keeps that path closed.

Training reuses the frozen H14/H10 recipe (`train_seed_models` and
`guarded_collect`) without editing those historical modules. Create
seeds remain `5 + 19s` and `7 + 19s`. Collection inner steps are
wrapped so dataset length alone cannot hide extra `env.step` calls.

## State restoration

For each `(seed, state)` the runner records one 12-step
model-independent prefix, then stores immutable t=8 and t=12
snapshots (observation, float32 raw state, prefix actions/rewards,
`_elapsed_steps`). Each candidate resets with the same state seed,
replays the first `t` stored actions, and must match the snapshot by
`np.array_equal` before any of its 16 actions. `.state` is never
assigned. Wrapper-stack, termination, TimeLimit, and prefix-reward
failures invalidate the cell.

Scoring uses the **recorded** later observation so it does not spend
unbudgeted reconstruction steps. Replay must still reproduce that
observation before realization.

## Scoring then realization

For each later state and library the runner scores multitask then
scratch (`16 × 16` imagined each), stores first-index `argmax`, then
realizes all 16 sequences from identical reset-plus-prefix states.
`G(x,L,j)` is computed once and shared. Realized returns are not
arguments to the scorer.

## Metering

`GuardedMeter` reserves before every reference step, replay step,
candidate step, collector inner step, and imagined batch. Caps are
**84,000** real and **81,920** imagined. The standing 16,000-step
headroom is not used. Time cap 300 s. Overwrite of an existing
result file is refused. Failures save `incomplete` with attempted /
interrupted counts. No retry.

## Statistics

`lock.mean_seed_cells` averages eight nested later states per model
seed, then student-t 95% df=9. Oracle cancellation is checked per
library. Secondaries (opportunity, regret, Spearman, first-action
regret, diversity) cannot change the label.

## Trace schema

Each later-state row stores seed, state index/seed, prefix seed,
prefix actions and rewards, t, reset and later obs/state,
elapsed_steps, L0/redraw seeds and fingerprints, per-arm scores,
selected indices/actions, shared realized returns and traces,
oracle, selected returns, and regrets.

## Tests

`tests/test_h16_same_state_library_runner.py` plus lock/feasibility
suites. Mocks only. Unauthorized `execute()` never reaches
`make_task_env` or training. Mock grid totals 84,000 / 81,920.

## Remaining empirical risk

Gymnasium float32 identity after an 8- or 12-step prefix is still a
runner-time gate. This implementation enforces the locked equality
contract; it does not claim the real MCC stack has been executed.

## Readiness

**Ready for a separate independent readiness audit.** Collection is
not authorized. `execute()` refuses. Do not treat this document as
an H16 result.
