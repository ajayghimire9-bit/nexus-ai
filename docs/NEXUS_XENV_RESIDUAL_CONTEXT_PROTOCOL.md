# Cross-environment residual-aware context-code transfer — locked protocol (rung 4)

Branch `cursor/xenv-residual-context` from `c129c62`. Rung 4 of the decided
cross-environment adaptation direction. Rungs 1–3 are closed
`not_established` (shared layer +18.618, deep trunk +2.575, occupancy-only
context-code −2.300). Their configurations and physics draws are closed.
This rung changes **what the support encoder may see**, not trunk depth or
scale.

## Falsifiable question (H4)

Does a shared one-layer 64→64 tanh trunk conditioned by an 8-d **residual-
aware** support-inferred FiLM context — pretrained jointly on CartPole,
Acrobot and discrete MountainCar (512+128 each, 15 epochs) — improve
MountainCarContinuous world-model adaptation on a NEW unused physics at
matched target data, versus the identical architecture trained on the
target only?

The encoder reads each support transition's normalized residual `s'−s`
(padded to length 6) concatenated with the `(obs, action)` embedding.
Validation and evaluation data never enter context inference. No family-ID
table. Prediction MAE cannot decide the label.

This is the mechanism the rung-3 source audit said occupancy-only FiLM did
not test. It is still not the Pendulum support-latent line (no per-task
latent optimization on a frozen decoder).

## Fixed design

- `XEnvResidualContextNet`: same per-family projections and one shared
  64→64 tanh layer as rung 3, plus shared context encoder
  (`Linear(70, 8)` + tanh) and zero-initialized FiLM (8→128). Residual is
  family observation-dim, zero-padded to 6 (Acrobot). Both arms are the
  same class with the same construction seed.
- Arms, budgets, pretrain/fine-tune/reference recipe, H=16 × 16 control
  and the 44,000 / 3,072,000 allocation are identical to rung 3 except
  the encoder input.
- Target: new unused draw by locked rule `mcc_xenv_v5` —
  **(0.0019, 0.0013, 0.065)** — rejecting default, development,
  confirmation, rungs 1–3 and the Cline v3 draft.
- Seeds: resets 66,000,000+, candidate 66,100,000+, prior-collect
  66,200,000+, target-collect 66,300,000+.

## Predeclared primary and labels

Primary: per-seed mean control return over {128, 1024}, paired
`xenv − scratch`, student-t 95% CI over ten seeds.

- `xenv_residual_context_beats_scratch`: mean > 0 and CI lower bound > 0.
- `xenv_residual_context_harm_established`: mean < 0 and CI upper bound < 0.
- `xenv_residual_context_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune.

## Bounds

**600-second hard cap**, **44,000 real environment steps**, **3,072,000
imagined transitions**, 135 locked epoch-loops per seed, local CPU, one
execution after a bound one-run allocation. Session ledger at lock:
3395.797 s of 3600 s remain.

**Collection is not authorized on this protocol text alone.** A separate
allocation must bind this exact configuration.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_xenv_residual_context.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_xenv_residual_context.py
PYTHONPATH=src:.deps python3 scripts/run_xenv_residual_context.py --execute
```
