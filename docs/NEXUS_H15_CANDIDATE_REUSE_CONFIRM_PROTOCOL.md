# H15 candidate-reuse confirmation — locked, collection unauthorized

Branch `cursor/h15-candidate-reuse-confirm-prep` from H14 results
`b05f9f2`. Same-design confirmation only. `authorized: false`,
`runs: 0`.

H14 stays closed. This lock does not retune H10–H14. Not
learning-to-learn, not AGI.

## Question (H15)

Does the exact frozen H14 fixed-versus-redraw interaction replicate
on a new unused MCC physics configuration?

## Frozen design

Multitask: exact H10 residual recipe (three sources × 512, 15
source-RMS pretrain epochs, 128+32 target, target RMS, 20 fine-tune
epochs, residual 2×64, Adam 0.001). Scratch: same create seed,
target data, target RMS, 20 epochs.

**Fixed-library recede:** score the same complete `L0` from the
current observation at every decision `t = 0…15` and execute the
first action of first-index `argmax`. Horizon stays 16.

**Redraw recede:** decision 0 uses `L0`. For `t ≥ 1`, score
`candidate_sequences(redraw_base+1000s+10k+t)`. Both arms receive
that matrix. No arm term. No step-zero score cache.

The locked H14 redraw stride is preserved for replication. The
formula aliases some different `(state, step)` pairs of one seed
(450 unique seeds for 600 slots). Within one state, `t = 1…15` stay
unique. Repairing the stride would be a different experiment.

## Holdout

Rule `mcc_candidate_reuse_confirm_v1` rejects H10–H14, the three H10
sources, and all other occupied MCC physics. It selects
**(0.004, 0.0021, 0.05)**. The same rule must reproduce that tuple.
H11 seeds 4 and 5 are not used to choose physics or candidates.
H14 outcomes were not used to choose physics.

## Seeds (`77,000,000+`)

Same relative structure as H14, new block:

- `reset_base` 77,000,000
- `state_reset_base` 77,100,000; state `+ 10s + k`
- `library_base` 77,200,000; `L0 = candidate_sequences(library_base+10s+k)`
- `collect_source_base` 77,300,000
- `collect_target_base` 77,400,000
- `redraw_base` 77,500,000; later `+ 1000s + 10k + t` for `t ≥ 1`

No arm term. Restore is `env.reset(seed=state_seed)` only.

## Primary

Per seed, mean over four states of

`D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`.

Student-t 95%, df 9, n = 10. Practical margin 0.0. H14 cells are
never pooled into this label. An interval that includes 0 is
failure to establish replication, not proof of no interaction.

- `h15_fixed_library_helps_multitask_relative`: mean > 0 and lo > 0.
- `h15_redraw_helps_multitask_relative`: mean < 0 and hi < 0.
- `h15_resampling_effect_not_established`: otherwise.
- `incomplete`: missing cell, failed reset, cap, nonfinite; no retune.

States are not extra model-training replications. Secondaries stay
non-label-deciding.

## Caps

Env: 15,360 + 1,600 + 2,560 + 10,240 = **29,760**.
Imagined: `10×2×2×4×16×16×16` = **655,360**.
Time **300 s**, local CPU.

This allocation is new. The consumed H14 one-run record is not reused.

## Future-runner invariants

A later H15 runner must keep H14’s pre-operation reservation, inner
collector step guard, shared L0, reset identity, overwrite refuse,
and incomplete-run honesty. Pointing the H14 runner at this yaml
without a separate implementation check is not authorized here.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_h15_candidate_reuse_confirm.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_h15_candidate_reuse_confirm.py
```

`--execute` must refuse until a later one-run allocation is committed.
