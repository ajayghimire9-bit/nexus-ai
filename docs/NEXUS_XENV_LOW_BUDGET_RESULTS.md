# Cross-environment low-budget (128) transfer — results (rung 6)

## Decision

**`xenv_low_budget_not_established`.** The predeclared primary — per-seed
control return at budget **128 only**, paired `xenv − scratch` — was
**+18.453 [−20.207, +57.113]** (student-t 95%, df 9, n = 10); the interval
includes 0, six of ten seeds positive.

This closes the 128-only question on unused holdout `mcc_xenv_v7`. Rung 5's
@128 secondary (+23.887, lo > 0 on closed `mcc_xenv_v6`) did **not**
replicate as a primary. Scarce-target-data transfer is not established at
this architecture and 2× prior. Do not promote the point estimate, retune
either holdout, or treat seed 4's +167.575 as a mechanism.

Secondary, never label-deciding: @1024 **+5.567 [−22.036, +33.170]**
(includes 0) and mean-over-budgets **+12.010 [−10.249, +34.270]** (includes
0). Mean returns @128: xenv −141.040 versus scratch −159.493 and reference
−111.334. @1024: xenv −83.420 versus scratch −88.988 and reference
−107.724. Held-out MAE gain @128 was +2.07e-04 [−4.22e-05, +4.55e-04]
(includes 0; xenv slightly worse).

Six matched xenv rungs at this architecture family are now closed
`not_established`. The established adaptation lever remains multitask
pretraining across physics variants **within** a family.

This is a valid negative result for this configuration only — not
learning-to-learn, not AGI. Target physics (0.0016, 0.0011, 0.08) and this
recipe are closed.

## Cost

**17.596 s wall** (600 s cap), **63,200 fresh real steps** (38,400 prior +
12,800 target + 12,000 evaluation), **3,072,000 imagined transitions**
exactly, local CPU, one valid execution after authorization commit
`28ad549` (no invalid attempts). Session ledger: 240.522 + 17.596 =
258.118 s of 3600 s consumed; 3341.882 s remain.

## Integrity

The independent Git-only results audit passed: saved label, 60-trace grid,
reward reconstruction, execution totals and forbidden-claim flags. Rule
`mcc_xenv_v7` reproduced **(0.0016, 0.0011, 0.08)**; seeds `68,000,000+`
are disjoint from closed blocks. Rung 5's holdout was not reused.

## Provenance

Branch `cursor/xenv-low-budget-128`: lock `2c5b697`, authorization
`28ad549`, executed once with a clean tree. Raw artifact
`artifacts/xenv_low_budget.json` SHA256
`e29308191af407b5733c613644b457717819f25abeedb38c6966684871d8f6a5`.

## One next recommendation

Six MCC-target shared-trunk rungs are closed. Do not add another FiLM
variant, do not retune `mcc_xenv_v6` or `mcc_xenv_v7`, and do not treat
the failed 128-only replication as a license to average back to rung 5.
A 5× prior scale still exceeds the 100,000 standing cap.

Leave this MCC-target line closed at this scale. The remaining cheap
discriminator, if later locked, is a **different-family target** with its
own unused physics, seeds, and protocol — not another MountainCarContinuous
draw. Nothing here pre-authorizes that run.
