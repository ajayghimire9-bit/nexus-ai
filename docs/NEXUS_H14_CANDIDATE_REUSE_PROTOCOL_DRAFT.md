# DRAFT — NOT LOCKED — H14 candidate-reuse protocol

This is a draft for later review. It does **not** lock a holdout,
authorize collection, or consume the session ledger.

## Question

Does repeatedly resampling H=16 candidate matrices change the
relative 16-step recede return of the frozen H10 recipe versus
matched scratch, when both arms see the same proposals?

## Arms and modes

Multitask: exact H10 residual recipe. Scratch: matched data, RMS,
architecture, and budget. Modes: fixed-library recede and redraw
recede as in `NEXUS_H14_CANDIDATE_REUSE_FEASIBILITY.md`. First
matrix `L0` is shared across arms and modes. Later redraws are
shared across arms and are state-specific. No `100 * arm_index`
term.

## Primary (draft)

Seed-level `D_s` after averaging four states. Student-t 95%, df 9.
Labels `h14_fixed_library_helps_multitask_relative`,
`h14_redraw_helps_multitask_relative`,
`h14_resampling_effect_not_established`, `incomplete`.

## Draft caps

300 s / 29,760 env / 655,360 imagined, local CPU, one later run.
Physics and seeds to be chosen only at lock time, unused, disjoint
from H10–H13.

Not authorized. Not an allocation. Not a result.
