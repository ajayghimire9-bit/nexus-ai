# H15 candidate-reuse confirmation — preparation lock

Source-only same-design confirmation of H14. No collection, no
training, no imagined rollouts. `authorized: false`, `runs: 0`.

Branch `cursor/h15-candidate-reuse-confirm-prep` from H14 results
`b05f9f2`. Local and `origin/cursor/h14-candidate-reuse-execute`
both point at that SHA. Authorization parent `09c8d26` is an
ancestor. H14 stays closed. This is not a control result.

## Question

Does the exact frozen H14 fixed-versus-redraw interaction replicate
on a new unused MCC physics configuration?

## Selected unused physics

Rule `mcc_candidate_reuse_confirm_v1` on the established MCC grid
(`g ∈ [0.0015, 0.0040]`, `p ∈ [0.0008, 0.0022]`, `s ∈ [0.050, 0.090]`).
Counter 0 hashes to **(0.004, 0.0021, 0.05)** and is eligible.
Independent recomputation matches. H14 outcomes were not used.

Occupied rejection set (21 tuples): H10–H14 targets, the three frozen
H10 sources, and every other completed or reserved MCC holdout already
in that chain (native-RMS, residual-scale, xenv rungs, lookahead
development/confirmation). The selected tuple is absent from all
`configs/*.yaml` target lists except this lock.

Closed holdouts excluded by name:

- H10 `(0.0032, 0.0022, 0.06)`
- H11 `(0.0022, 0.0016, 0.07)`
- H12 `(0.0027, 0.0015, 0.075)`
- H13 `(0.0039, 0.002, 0.075)`
- H14 `(0.0023, 0.0019, 0.065)`

Sources: `(0.0025, 0.0015, 0.07)`, `(0.0038, 0.0019, 0.085)`,
`(0.0024, 0.0019, 0.09)`.

## Frozen design

Unchanged from H14: H10 residual 2×64, three sources × 512, 15
source-RMS epochs, 128+32 target, 20-epoch fine-tune versus matched
scratch, Adam 0.001, four reset states, ten model seeds, H=16×16,
three discrete actions, shared L0, fixed-library versus redraw,
shared proposals, no step-0 score cache, restore `reset_same_seed`.

Redraw stride stays `redraw_base + 1000s + 10k + t` for `t ≥ 1`.
That aliases 150 of 600 intended `(state, step)` slots (450 unique).
Repairing the stride would be a different experiment.

## Seeds (`77,000,000+`)

Same relative offsets as H14, new block. Verified disjoint from the
closed 76M H14 streams and from other registered bases.

## Primary

`D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`,
mean of four states, Student-t 95%, df 9, n = 10, margin 0.0.
H14 cells are never pooled into the H15 label. An interval that
includes 0 is failure to establish replication, not proof of no
interaction.

- `h15_fixed_library_helps_multitask_relative`
- `h15_redraw_helps_multitask_relative`
- `h15_resampling_effect_not_established`
- `incomplete`

Secondaries stay non-label-deciding.

## Caps

Recalculated: 15,360 + 1,600 + 2,560 + 10,240 = **29,760** real;
**655,360** imagined; **300 s**; local CPU. Session ledger unchanged
(299.340 s used, 3300.660 s remain). This prep used 0 experimental
seconds. The consumed H14 one-run allocation is not reused.

## Hashes

- config `bc263e69e3a57ae3bcb4c27616f0c4736deaf123dab6c0c3cb49311b3804c193`
- protocol `4e5f7a5d0f55c6f183d1c78046597a99f5dfd8f788546a1d91c8270dad0116af`
- allocation `210f3a631a3081152f63e7a6b4d53bf98a2b8e157be52e515a7c7b5a53e39362`

H14 parents remain the closed hashes recorded in the yaml.

## Tests

`tests/test_h15_candidate_reuse_confirm.py`: 5 passed. Holdout
recomputes; seeds disjoint; H14 hyperparameters frozen; labels match
the H14 three-way rule; prep stays unauthorized; `--execute` raises
`PermissionError`.

## Next engineering stage

A separate H15 guarded runner is required. Pointing the H14 runner at
this yaml without a new implementation check is not authorized.
Future execution must keep H14’s pre-operation reservation, inner
collector step guard, shared L0, reset identity, overwrite refuse,
and incomplete-run honesty.

Not learning-to-learn. Not AGI. Not a 200-step control claim.
