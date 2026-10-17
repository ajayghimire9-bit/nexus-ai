# Within-family MCC residual-scale adaptation — results

## Decision

**`mcc_residual_scale_harm_established`.** The predeclared primary —
per-seed H=16 return at budget **128**, paired
`source_scale − unit_scale` — was **−54.381 [−105.776, −2.987]**
(student-t 95%, df 9, n = 10); the upper bound is below 0, eight of ten
seeds negative.

A frozen 2-d source residual scale (mean `|s′−s|` from `mcc_default`, in
target-RMS coordinates) **hurt** control relative to unit scale on unused
physics (0.0021, 0.0018, 0.055). Mean returns: source_scale −97.331
versus unit_scale −42.949. Held-out MAE gain was
+1.81e-04 [−1.25e-04, +4.86e-04] (includes 0), so this is a control
result, not a prediction-harm claim.

This closes the source residual-scale configuration on this holdout. It
does **not** reopen source-RMS, V0.6.6 CartPole RMS, or any xenv rung.
It does not license a 1-d / 3-d retune or reuse of this physics.

This is a valid negative result for this configuration only — not
learning-to-learn, not AGI, and not a general disproof of within-family
adaptation.

## Cost

**4.965 s wall** (600 s cap), **10,720 fresh real steps** (5,120 source +
1,600 target + 4,000 evaluation), **1,024,000 imagined transitions**
exactly, local CPU, one valid execution after authorization commit
`1d43bb8` (no invalid attempts). Session ledger: 273.280 + 4.965 =
278.245 s of 3600 s consumed; 3321.755 s remain.

## Integrity

The independent Git-only results audit passed: saved label, 20-trace
grid, reward reconstruction, 2-d scale identities, execution totals,
forbidden-claim flags and `cross_family_weights: false`. Rule
`mcc_residual_scale_v1` reproduced **(0.0021, 0.0018, 0.055)**; seeds
`71,000,000+` are disjoint. Native-RMS and xenv holdouts were not
reused.

## Provenance

Branch `cursor/mcc-residual-scale`: lock `94d1ef1`, authorization
`1d43bb8`, executed once with a clean tree. Raw artifact
`artifacts/mcc_residual_scale.json` SHA256
`a1970cb8f2ef544537684da5946bbd9aa9d447b480c0c3d99c9a9b9221604cc9`.

## One next recommendation

Leave transplanted source-interface statistics closed at this scale
(RMS not established; residual-scale harm established). Do not add a
scale-dimension variant and do not reopen xenv. The established levers
remain family-local residual models and family-local lookahead, without
importing a source scale. Nothing here pre-authorizes a further
interface transplant.
