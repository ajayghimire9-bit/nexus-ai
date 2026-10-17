# Cross-environment shared-trunk world-model transfer — locked pilot protocol v1

Branch `cline/xenv-transfer-pilot` from `5263714`. First rung of the decided
cross-environment adaptation direction. The one established positive adaptation
lever is multitask pretraining across physics variants
(`artifacts/meta_learning_pilot.json`); first-order Reptile lost to matched-data
multitask in that configuration, and V0.8.9 sequential task transfer reduced
nothing under the MAE gate. This pilot asks the cross-FAMILY version at matched
data. Same residual-MLP architecture family — no new architecture family.

## Falsifiable question (H1)

Does one shared 64→64 tanh hidden layer — pretrained jointly on three other
environments (CartPole source, Acrobot source, discrete MountainCar source;
512+128 transitions each, 15 epochs) — improve adaptation of a
MountainCarContinuous world model on a NEW unused MCC physics at matched target
data, versus the **identical** architecture (per-family input/output heads over
the same shared layer) trained on the target only? Only the shared layer's
initialization differs between the two arms.

## Fixed design

- Ten model seeds. Target: one new unused MCC physics drawn by locked rule
  `mcc_xenv_v1` (gravity/power/max-speed grids, rejecting default, development
  and confirmation physics).
- Per seed: prior-family data (3 × 512+128, collect seeds 63200000+ block);
  target pool 1024+256 on the new physics (63300000+ block).
- Budgets: target prefixes 128 and 1024 (train+val inside the prefix); RMS
  fitted from the prefix's train observations for both arms.
- Arms: `xenv` = pretrain shared layer + all prior heads (15 epochs, lr 1e-3),
  then fine-tune target heads + shared layer on the prefix (20 epochs, lr
  5e-4, best-val checkpoint, term weight 0.25); `scratch` = same fine-tuning
  from a fresh identical net. Reference arm (not in the primary): the
  established single-family `WorldModel` (residual 64×64, 20 epochs, lr 1e-3)
  on the same prefixes.
- Evaluation: frozen H=16 × 16 receding MPC with the dense valley-height
  reward, 200-step episode on the new physics, per (seed, arm, budget) plus
  reference; candidate seeds 63100000+ block; resets 63000000+ block. The
  simulator never enters any world model or its candidate scores.

## Predeclared primary and labels

Primary: per-seed mean control return over the two budgets, paired
`xenv − scratch`, student-t 95% CI over the ten seeds.

- `xenv_shared_layer_beats_scratch`: mean > 0 and CI lower bound > 0.
- `xenv_shared_layer_harm_established`: mean < 0 and CI upper bound < 0.
- `xenv_shared_layer_not_established`: otherwise (including any interval
  that includes 0).
- `incomplete`: any missing cell, cap failure or nonfinite value. A complete
  negative/harm result is a valid finding; no retuning, no rerun on this
  sample, no exclusion of seeds.

Secondary (reported, never label-deciding): per-budget returns, held-out
target prediction MAE, reference-arm returns for anchoring against the
established single-family pipeline.

This pilot does **not** claim learning-to-learn, cross-family weight transfer
beyond the single shared layer, or AGI. A negative result closes only this
minimal-sharing configuration, not cross-environment adaptation in general.

## Bounds

**600-second hard cap**, **44,000 real environment steps** (19,200 prior
collection + 12,800 target pool + 12,000 evaluation episodes), **3,072,000
imagined transitions** (12,000 × 256), **10 training-epoch budgets per seed**
(prior 15 + target 2×20 + reference 2×20 within the pilot's frozen recipe),
local CPU, one Torch thread. Collection is unauthorized until a bound one-run
allocation sets `authorized: true` and `runs: 1` binding this configuration,
this protocol and these caps. Stop and save honestly at any cap.

## Seeds and closed-splits guard

Reset block 63000000+, candidate block 63100000+, prior-collect 63200000+,
target-collect 63300000+; disjoint from every committed seed base in
`configs/*.yaml` (highest 32,100,000) and from the other live research
branches' registered blocks (61,000,000/61,100,000 on `cline/successor-*`).
No closed development/confirmation split is reused or re-collected; the new
physics draw rejects all occupied MCC physics.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_xenv_transfer_pilot.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_xenv_transfer_pilot.py            # prep/offline audit
PYTHONPATH=src:.deps python3 scripts/run_xenv_transfer_pilot.py --execute  # one authorized run
PYTHONPATH=src:.deps python3 scripts/run_xenv_transfer_pilot.py --results-audit
```
