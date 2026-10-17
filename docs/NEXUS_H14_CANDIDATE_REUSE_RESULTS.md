# H14 candidate-reuse — results

## Decision

**`h14_fixed_library_helps_multitask_relative`.** The predeclared
primary — per-seed mean

`D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`

over four reset states — was **+0.178 [+0.009, +0.348]**
(student-t 95%, df 9, n = 10). The lower bound is above 0. Six of ten
seeds were positive.

Mean 16-step returns: multitask fixed **−15.024**, scratch fixed
**−15.066**, multitask redraw **−15.228**, scratch redraw **−15.092**.
The interaction is carried by multitask losing more under redraw than
scratch does. Within-mode multitask−scratch intervals both include 0
and do **not** decide the label.

This configuration only. Shared proposals remove the H12/H13 arm-seed
confound. They do not make trajectories identical. This does not
establish general control, compounding error, exploitation, later
ranking decay, learning-to-learn, or AGI.

## Cost

**4.285 s wall** (300 s cap), **29,760 fresh real steps**, **655,360
imagined transitions** exactly, local CPU, one valid execution after
authorization commit `09c8d26` (no invalid attempts). Session ledger:
295.055 + 4.285 = 299.340 s of 3600 s consumed; 3300.660 s remain.

## Integrity

Saved label rebuilds from the raw cells. Ten-seed four-state grid,
execution totals, `share_step0_scores: false`,
`closed_loop_is_primary: false`, and forbidden-claim flags match.
Rule `mcc_candidate_reuse_v1` reproduced **(0.0023, 0.0019, 0.065)**.
Locked config SHA256
`df155e89b8a4810bdbf04cfc121e93de7c9900235a440057dd66f7128459f81a`
and protocol SHA256
`1005e12568f3457f32638f9c7a08b0c29c7090785bf1085d097054224a012c1b`
are unchanged. Raw SHA256
`7e4a74ba0a8f21f735b41cc1fbceb4d5c005f68718159c0a2077caa27934959e`.
Further collection on this configuration is not authorized.

## Secondaries (not label-deciding)

- Multitask−scratch fixed: **+0.042 [−0.300, +0.383]** includes 0.
- Multitask−scratch redraw: **−0.137 [−0.410, +0.137]** includes 0.
- Shared L0 open-loop selected return: **−15.484 [−15.619, −15.349]**.
- Shared L0 sequence regret: **+0.003 [−0.001, +0.008]** includes 0.
- Later-state action disagreement: **0.695 [0.525, 0.865]**.
