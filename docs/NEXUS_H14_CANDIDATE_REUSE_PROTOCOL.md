# H14 candidate-reuse protocol — locked, collection unauthorized

Branch `cursor/h14-candidate-reuse-protocol-lock` from feasibility
`1949bed`. Preparation only. `authorized: false`, `runs: 0`.

This lock does not retune H10–H13. Ranking primaries on those
holdouts stand. H12/H13 recede remains secondary and arm-confounded.
Not learning-to-learn, not AGI.

## Question (H14)

Does reusing a fixed 16×16 candidate library, instead of resampling
a fresh library at each later decision, change the relative 16-step
recede return of the frozen H10 residual recipe versus matched
scratch?

## Arms and modes

Multitask: exact H10 recipe (three sources × 512, 15 source-RMS
pretrain epochs, 128+32 target, target RMS, 20 fine-tune epochs,
residual 2×64, Adam 0.001). Scratch: same create seed, target data,
target RMS, 20 epochs.

**Fixed-library recede:** at every decision `t = 0…15`, score the
same complete matrix `L0` from the current observation and execute
the first action of `argmax` (first index). Horizon stays 16. Not
open-loop commitment. Not a shrinking suffix.

**Redraw recede:** decision 0 uses `L0`. For `t ≥ 1`, score a new
shared matrix for `(seed, state, step)` and execute its first
action.

Both modes score exactly 16 sequences of horizon 16 at every
decision. No step-zero score caching.

## Holdout

Rule `mcc_candidate_reuse_v1` rejects H10–H13, the three H10
sources, and all other occupied MCC physics. It selects
**(0.0023, 0.0019, 0.065)**. The same rule must reproduce that
tuple. H11 seeds 4 and 5 are not used to choose physics or
candidates.

## Seeds (`76,000,000+`)

- `reset_base` 76,000,000
- `state_reset_base` 76,100,000; state `+ 10s + k`
- `library_base` 76,200,000; `L0 = candidate_sequences(library_base+10s+k)`
- `collect_source_base` 76,300,000
- `collect_target_base` 76,400,000
- `redraw_base` 76,500,000; later `+ 1000s + 10k + t` for `t ≥ 1`

No arm term. `L0` is shared by both arms and both modes at `t = 0`.
Later redraws are shared by both arms. Restore is
`env.reset(seed=state_seed)` only. First reset records `obs0`; later
resets of that seed must match or the cell is invalid.

## Primary

Per seed, mean over four states of

`D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`.

Student-t 95%, df 9, n = 10. Practical margin 0.0: a test for a
nonzero interaction, not a claim of practical improvement.

- `h14_fixed_library_helps_multitask_relative`: mean > 0 and lo > 0.
- `h14_redraw_helps_multitask_relative`: mean < 0 and hi < 0.
- `h14_resampling_effect_not_established`: otherwise.
- `incomplete`: missing cell, failed reset, cap, nonfinite; no retune.

States are not extra model-training replications.

Secondaries (not label-deciding): multitask−scratch within each
mode; shared `L0` open-loop selected return and sequence regret;
initial ranking quality; later-state action disagreement; predicted
scores; one-step residuals on already-executed transitions only.
Do not call a full-horizon imagined score a one-step residual.

## Caps

Env: 15,360 source + 1,600 target + 2,560 recede
(`10×2×2×4×16`) + 10,240 shared `L0` open-loop = **29,760**.

Imagined: `10×2×2×4×16×16×16` = **655,360**. No step-zero cache.

Time **300 s**, local CPU.

## Future-runner meter invariants

Inherited H12 meters increment, then reject if the count exceeds
the cap, so one extra step or batch can run. The H14 runner, when
implemented later, must **reserve before** every simulator action
and before every imagined batch: reject if `used + n > cap`, then
add `n`, then execute. Validate batch size first. Preflight exact
collection sizes before `collect`. Check the wall-clock deadline at
those boundaries. Count reserved-but-failed operations. An
incomplete grid cannot receive a success label. Do not edit frozen
H12/H13 meters.

## Logging

Every already-budgeted controller step stores: seed, state index,
mode, arm, `state_seed`, `obs0` identity, step, candidate seed,
library fingerprint, current observation, 16 predicted scores,
selected index, first action, next observation, realized reward,
termination/truncation, running env and imagined counts. Predicted
and realized values stay distinct. Planners never receive realized
counterfactual candidate returns. No extra later-state
counterfactual rollouts.

## What D can and cannot say

Significant positive D: under this holdout and controller, fixed
reuse increases the multitask-minus-scratch return gap relative to
redraw. Significant negative D: the reverse. Shared proposals remove
the H12/H13 arm-specific library confound. They do not make
trajectories identical; later occupancy can still differ. D does
not establish general control, compounding error, exploitation,
later ranking decay, learning-to-learn, or AGI.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_h14_candidate_reuse.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_h14_candidate_reuse.py
```

`--execute` must refuse until a later one-run allocation is committed.
