# Within-family MCC source-RMS adaptation — results

## Decision

**`mcc_native_rms_not_established`.** The predeclared primary — per-seed
H=16 return at budget **128**, paired `source_rms − scratch_rms` — was
**+2.185 [−64.564, +68.935]** (student-t 95%, df 9, n = 10); the interval
includes 0, four of ten seeds positive.

Frozen source-MCC observation RMS did **not** establish a 128-transition
control advantage over fresh target RMS on unused physics
(0.0029, 0.0022, 0.055). Mean returns: source_rms −72.164 versus
scratch_rms −74.349. Held-out MAE gain (source − scratch) was
−3.59e-04 [−9.28e-04, +2.09e-04] (includes 0). Variance is large; seed 3
is −194.7 and is not a mechanism.

This closes the source-RMS configuration on this holdout. It does not
reopen V0.6.6 CartPole RMS, and it does not license another shared-trunk
xenv rung. The CartPole RMS result stays family- and stack-specific.

This is a valid negative result for this configuration only — not
learning-to-learn, not AGI.

## Cost

**4.929 s wall** (600 s cap), **10,720 fresh real steps** (5,120 source +
1,600 target + 4,000 evaluation), **1,024,000 imagined transitions**
exactly, local CPU, one valid execution after authorization commit
`673c7bb` (no invalid attempts). Session ledger: 268.351 + 4.929 =
273.280 s of 3600 s consumed; 3326.720 s remain.

## Integrity

The independent Git-only results audit passed: saved label, 20-trace
grid, reward reconstruction, execution totals, forbidden-claim flags and
`cross_family_weights: false`. Rule `mcc_native_rms_v1` reproduced
**(0.0029, 0.0022, 0.055)**; seeds `70,000,000+` are disjoint from closed
xenv blocks. Closed MCC xenv holdouts were not reused.

## Provenance

Branch `cursor/mcc-native-rms`: lock `138bf63`, authorization `673c7bb`,
executed once with a clean tree. Raw artifact
`artifacts/mcc_native_rms.json` SHA256
`cdf80571701e78b30560fbed43aa5be77a17c58242167c9a6577ef2f7c067ac7`.

## One next recommendation

Do not retune this holdout or add a shared-trunk variant. The synthesis
named one other family-native object: a **1–3d residual-scale** inferred
from support `s′−s` in MCC coordinates. That needs its own unused
physics, protocol, and allocation. Nothing here pre-authorizes it.
