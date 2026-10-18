# Evolution-2.6 — execution-blocker matrix

Branch `cursor/evolution2.6-execution-blockers` from
`dc6420f23b27d5a6e47fab1478cada2e932a6ea1`.
Not a scientific result. Zero new environment steps. Ledger not
debited. Frozen H16 scientific ledger remains **305.842 / 3294.158**.

## Measurement

The six n=3 bound residual files, plus the three residual-timing
identity files, are zip `.pt` payloads. Archive member names contain
no `transition`, `dataset`, `next_obs`, `train`, or `val` objects.
Sizes are 23–25 KB. **Weights only.**

`WorldModel.save` persists `state_dict`, `obs_rms`, and dims. It does
not persist source arrays. Checkpoint inspection does not recover a
fitting benchmark.

## Blocker matrix

| id | status | blocks |
|---|---|---|
| SOURCE_FITTING_UNAVAILABLE | confirmed | v2, v2-pilot |
| WEIGHTS_ONLY_PAYLOAD | confirmed | fit-from-checkpoint |
| NO_FIT_TEN_BUNDLE_UNAVAILABLE | confirmed | v2, v2-pilot |
| N3_NOT_READY_RECIPE_MISMATCH | confirmed | n3-micro |
| HOLDOUT_UNNAMED | unnamed | all screens |
| TWELVE_ARM_DISPATCH_BLOCKED | blocked | scientific dispatch |
| FULL_V2_NO_GO | NO-GO | v2 |
| V2_PILOT_NOFIT_BLOCKED | BLOCKED | v2-pilot |
| SCIENTIFIC_DISPATCH_UNAUTHORIZED | unauthorized | all screens |
| H17_BLOCKED | blocked | H17 |

**`E2_SCIENTIFIC_DISPATCH_BLOCKED`.**

v2 and n=3 hashes stay frozen.

## Next action

Do not open another worksheet shrink. Do not collect replacements.
Evolution-2 stays blocked until a separate authorization persists
matched Pendulum/Acrobot source train/val arrays.
