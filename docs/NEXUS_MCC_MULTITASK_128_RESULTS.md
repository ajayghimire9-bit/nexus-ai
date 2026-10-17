# Within-family MCC multitask at 128 — results

## Decision

**`mcc_multitask_128_beats_scratch`.** The predeclared primary —
per-seed H=16 return at budget **128**, paired
`multitask − scratch` — was **+145.785 [+106.617, +184.953]**
(student-t 95%, df 9, n = 10); the lower bound is above 0, ten of ten
seeds positive.

A residual world model pretrained on three other MCC physics (512
transitions each) and fine-tuned on 128 target transitions beat scratch
on unused physics (0.0032, 0.0022, 0.06). Both arms used the same
target RMS, so the contrast is pretrained weights, not an imported
source statistic. Mean returns: multitask +33.103 versus scratch
−112.682. Held-out MAE difference (multitask − scratch) was
**−9.01e-04 [−1.30e-03, −5.01e-04]** (upper bound below 0), so
prediction also favored the pretrained init on this holdout.

This closes the multitask-versus-scratch configuration on this holdout.
It does **not** reopen source-RMS, residual-scale, or any xenv rung.
It does not license a source-count, epoch, or budget retune of this
physics.

This is a valid positive result for this configuration only — not
learning-to-learn, not AGI, and not a general within-family claim.
The multitask absolute-return interval includes 0
(+33.103 [−5.121, +71.326]); scratch does not
(−112.682 [−153.880, −71.484]). The established claim is relative
improvement versus scratch at 128, not a reliably positive controller.

## Cost

**5.612 s wall** (600 s cap), **20,960 fresh real steps** (15,360 source
+ 1,600 target + 4,000 evaluation), **1,024,000 imagined transitions**
exactly, local CPU, one valid execution after authorization commit
`f8d2a1d` (no invalid attempts). Session ledger: 278.245 + 5.612 =
283.857 s of 3600 s consumed; 3316.143 s remain.

## Integrity

The independent Git-only results audit passed: saved label, 20-trace
grid, reward reconstruction, execution totals, forbidden-claim flags
and `cross_family_weights: false`. Rule `mcc_multitask_128_v1`
reproduced **(0.0032, 0.0022, 0.06)**; seeds `72,000,000+` are
disjoint. Source-RMS, residual-scale, and xenv holdouts were not
reused.

## Provenance

Branch `cursor/mcc-multitask-128`: lock `38469c4`, authorization
`f8d2a1d`, executed once with a clean tree. Raw artifact
`artifacts/mcc_multitask_128.json` SHA256
`caca746457eb72e89c95b6f8b9cd82c7cf06cff68713ff1d9ad8a98519e4d274`.

## One next recommendation

Confirm the same locked design on a new unused MCC holdout. Do not
retune this physics, source count, or budget. Interface transplants
and xenv remain closed. Nothing here pre-authorizes confirmation.
