# Within-family MCC multitask at 128 — confirmation results

## Decision

**`mcc_multitask_128_confirm_not_established`.** The predeclared
primary — per-seed H=16 return at budget **128**, paired
`multitask − scratch` — was **+18.879 [−65.988, +103.747]**
(student-t 95%, df 9, n = 10). The interval includes 0. Eight of ten
seeds were positive; seeds 4 and 5 were large losses
(−199.664 and −196.656).

The frozen H10 recipe did **not** independently replicate on unused
physics (0.0022, 0.0016, 0.07). Mean returns: multitask −65.005 versus
scratch −83.884. Held-out MAE difference (multitask − scratch) was
**−5.63e-04 [−8.25e-04, −3.00e-04]** (upper bound below 0). Prediction
still favored the pretrained init; the registered control primary did
not.

This closes the same-design confirmation on this holdout. It does
**not** retune H10, reopen source-RMS, residual-scale, or any xenv
rung, or change H10's closed label on (0.0032, 0.0022, 0.06).

This is a valid incomplete-replication result for this configuration
only — not learning-to-learn, not AGI, and not a general within-family
claim. Both arm-return intervals are below 0. The 128-transition
scratch baseline remains weak; the confirmation question was whether
the H10 relative advantage would clear the same lo>0 rule on new
physics. It did not.

## Cost

**5.428 s wall** (600 s cap), **20,960 fresh real steps** (15,360 source
+ 1,600 target + 4,000 evaluation), **1,024,000 imagined transitions**
exactly, local CPU, one valid execution after authorization commit
`ec6e2d7` (no invalid attempts). Session ledger: 283.857 + 5.428 =
289.285 s of 3600 s consumed; 3310.715 s remain.

## Integrity

The independent Git-only results audit passed: saved label, 20-trace
grid, reward reconstruction, execution totals, forbidden-claim flags
and `cross_family_weights: false`. Rule
`mcc_multitask_128_confirm_v1` reproduced **(0.0022, 0.0016, 0.07)**;
seeds `73,000,000+` are disjoint from H10. Closed H10 raw SHA256
`caca746457eb72e89c95b6f8b9cd82c7cf06cff68713ff1d9ad8a98519e4d274`
and report SHA256
`9c8f0274ed3778f4197319e74217427a1432d05658b21c59676652eb4143d480`
are unchanged.

## Provenance

Branch `cursor/mcc-multitask-128-confirm`: lock `0a076d3`,
authorization `ec6e2d7`, executed once with a clean tree. Raw artifact
`artifacts/mcc_multitask_128_confirm.json` SHA256
`e8045423ff257e2f55acbead5a3f2eafc54f5ed5f88dab99933cca5eea286950`.

## One next recommendation

Leave this confirmation closed. Do not retune physics, source count,
or budget after seeing these outcomes. H10 remains a single-holdout
positive screen; H11 shows that advantage is not yet a replicated
within-family fact. Nothing here pre-authorizes another run.
