# Cross-environment deep shared-trunk transfer — locked protocol (rung 2)

Branch `cline/xenv-deep-trunk` from `8553c90`. Rung 2 of the decided
cross-environment adaptation direction, preregistered in
`docs/NEXUS_NEXT_EXPERIMENT.md`. Rung 1 (one shared 64→64 layer) was
`xenv_shared_layer_not_established` (+18.618 [−20.400, +57.636]) and is
closed. This is a **new preregistered configuration**, not a retune: the
sharing is deepened.

## Falsifiable question (H2)

Does a **fully shared two-layer 64×64 tanh trunk** behind per-family
input/output projections — pretrained jointly on three other environments
(CartPole, Acrobot, discrete MountainCar source; 512+128 each, 15 epochs) —
improve MountainCarContinuous world-model adaptation on a NEW unused physics
at matched target data, versus the identical architecture trained on the
target only? Only the shared trunk's initialization differs between the two
arms. The multi-head architecture has one more hidden layer than the
reference single-family `WorldModel`; the reference arm is an anchor only,
the primary comparison is architecture-matched.

## Fixed design (differences from rung 1 only)

- `XEnvDeepNet`: per-family input projection (obs+one-hot-action → 64) and
  per-family state/termination heads over `shared1` and `shared2`
  (both 64→64, tanh) — both shared layers pretrained by the xenv arm.
- Target: new unused draw by locked rule `mcc_xenv_v2` —
  **(0.0028, 0.0013, 0.065)** — rejecting the default, development,
  confirmation and rung-1 physics.
- Seed blocks: resets 63,500,000+, candidate 63,600,000+, prior-collect
  63,700,000+, target-collect 63,800,000+; disjoint from every committed
  seed base (blocked ranges base..base+110,000) and the other live branches'
  blocks.
- Everything else identical to rung 1: ten seeds; target pool 1024+256 on the
  new physics; budgets 128/1024 with train+val inside the prefix; pretrain
  15 epochs lr 1e-3; fine-tune 20 epochs lr 5e-4 best-val; reference
  `WorldModel` (residual 64×64, 20 epochs, lr 1e-3); frozen H=16 × 16
  dense-height control, 200-step episodes; the simulator never enters any
  world model.

## Predeclared primary and labels

Primary: per-seed mean control return over the budgets {128, 1024}, paired
`xenv − scratch`, student-t 95% CI over ten seeds.

- `xenv_deep_trunk_beats_scratch`: mean > 0 and CI lower bound > 0.
- `xenv_deep_trunk_harm_established`: mean < 0 and CI upper bound < 0.
- `xenv_deep_trunk_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune,
  no rerun on this sample, no excluded seeds.

Secondary (never label-deciding): per-budget gains, held-out prediction MAE,
reference-arm returns. No learning-to-learn, cross-family weight transfer
beyond the shared trunk, or AGI claim. A negative result closes this
configuration only.

## Bounds

**600-second hard cap**, **44,000 real environment steps** (19,200 prior
collection + 12,800 target pool + 12,000 evaluation), **3,072,000 imagined
transitions**, 10 training-epoch budgets per seed inside the frozen recipe,
local CPU, one execution after a bound one-run allocation binds this
configuration, protocol and caps. Session ledger at allocation:
3432.177 s of the standing 3600 s remain. Stop and save honestly at any cap.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_xenv_deep_trunk.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_xenv_deep_trunk.py            # prep/offline audit
PYTHONPATH=src:.deps python3 scripts/run_xenv_deep_trunk.py --execute  # one authorized run
PYTHONPATH=src:.deps python3 scripts/run_xenv_deep_trunk.py --results-audit
```
