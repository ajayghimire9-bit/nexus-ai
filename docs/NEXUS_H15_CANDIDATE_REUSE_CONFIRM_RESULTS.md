# H15 candidate-reuse confirmation — results

## Decision

**`h15_fixed_library_helps_multitask_relative`.** The predeclared
primary — per-seed mean

`D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`

over four reset states — was **+0.230 [+0.111, +0.349]**
(student-t 95%, df 9, n = 10). The lower bound is above 0. Ten of ten
seeds were positive.

Mean 16-step returns: multitask fixed **−15.061**, scratch fixed
**−15.201**, multitask redraw **−15.428**, scratch redraw **−15.338**.
The interaction is again carried by multitask losing more under redraw
than scratch does. Within-mode multitask−scratch intervals both
include 0 and do **not** decide the label.

This is a same-design confirmation of the H14 interaction on a second
unused MCC holdout. H14 cells were not pooled into this label. Shared
proposals remove the H12/H13 arm-seed confound. They do not make
trajectories identical. This does not establish general control,
compounding error, exploitation, later ranking decay, learning-to-learn,
or AGI.

## Cost

**4.437 s wall** (300 s cap), **29,760 fresh real steps**, **655,360
imagined transitions** exactly, local CPU, one valid execution after
authorization commit `0580ac5` (no invalid attempts). Session ledger:
299.340 + 4.437 = 303.777 s of 3600 s consumed; 3296.223 s remain.

The CLI `prep()` call after a successful `execute()` raised because
`prep` refuses an authorized allocation. That post-save failure is not
an extra experimental run and was not retried.

## Integrity

Saved label rebuilds from the raw cells. Ten-seed four-state grid,
execution totals, `share_step0_scores: false`,
`closed_loop_is_primary: false`, and forbidden-claim flags match.
Rule `mcc_candidate_reuse_confirm_v1` reproduced **(0.004, 0.0021, 0.05)**.
Locked config SHA256
`bc263e69e3a57ae3bcb4c27616f0c4736deaf123dab6c0c3cb49311b3804c193`
and protocol SHA256
`4e5f7a5d0f55c6f183d1c78046597a99f5dfd8f788546a1d91c8270dad0116af`
are unchanged. Raw SHA256
`440671d592c888e16f5c43d90de701c83bcae6887b9e0b83d1eb71b4312c7a15`.
Further collection on this configuration is not authorized. The one-run
allocation is consumed and closed.

## Secondaries (not label-deciding)

- Multitask−scratch fixed: **+0.140 [−0.224, +0.504]** includes 0.
- Multitask−scratch redraw: **−0.090 [−0.382, +0.201]** includes 0.
- Shared L0 open-loop selected return: **−15.635 [−15.696, −15.573]**.
- Shared L0 sequence regret: **+0.009 [+0.001, +0.016]**.
- Later-state action disagreement: **0.782 [0.634, 0.930]**.
