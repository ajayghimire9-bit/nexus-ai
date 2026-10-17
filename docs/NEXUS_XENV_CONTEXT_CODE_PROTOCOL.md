# Cross-environment support-inferred context-code transfer — locked protocol (rung 3)

Branch `cursor/xenv-context-code` from `9d3e5ce`. Rung 3 of the decided
cross-environment adaptation direction. Rungs 1
(+18.618 [−20.400, +57.636], one shared 64→64 layer) and 2
(+2.575 [−16.248, +21.399], full two-layer trunk) are both closed
`not_established`; their configurations and physics draws are closed and are
not retuned, rerun or reinterpreted. This rung changes the **mechanism**, not
the scale or trunk depth.

A separate uncommitted Cline draft on `cline/xenv-context-adaptation` asks
the same scientific class of question with holdout `mcc_xenv_v3`
**(0.0034, 0.001, 0.055)** and seeds `64,000,000+`. That draft is **not**
this protocol, is not copied here, and is not authorized. This lock uses a
disjoint holdout and seed block so both can exist without collision.

## Chosen direction

**C — lightweight context adaptation** (support-inferred FiLM), not A
(deeper shared trunk; already complete and not established) and not B as a
separate identity-table design. B and C collapse to the same next mechanism
once family-ID tables are disallowed: a context vector inferred from a
family's own support, never a learned per-family lookup.

## Falsifiable question (H3)

Does a **shared one-layer 64→64 tanh trunk** (the closed rung-1 architecture,
not the failed deeper trunk) conditioned by an 8-d **support-inferred FiLM
context** — pretrained jointly on CartPole, Acrobot and discrete MountainCar
(512+128 each, 15 epochs) — improve MountainCarContinuous world-model
adaptation on a NEW unused physics at matched target data, versus the
identical architecture trained on the target only?

Only the pretrained initialization differs between the two architecture-
matched arms. The target family is **absent from source pretraining**. No
learned per-family identity table exists. Prediction MAE is reported and
cannot decide the label.

## Fixed design

- `XEnvContextCodeNet`: per-family input projection (obs+one-hot-action → 64)
  and per-family state/termination heads over one shared 64→64 tanh layer,
  plus a shared context encoder (64→8, tanh) and a zero-initialized FiLM
  (8→128) applied as scale `(1+γ)` and shift `β` after the shared layer.
  Context for a family is the mean of per-transition encoder outputs on that
  family's support `(obs, action)` slice only. Both arms are the **same
  class with the same construction seed**; parameter counts are identical.
- Arms: `xenv` = pretrain source families jointly (source contexts recomputed
  each batch from each family's first 64 train transitions, with gradient
  through the encoder), then fine-tune the target pathway on the target
  prefix (20 epochs, lr 5e-4, best-val checkpoint) with a **frozen**
  support-inferred target context. `scratch` = identical class, same seed,
  **no pretraining**, same fine-tuning with its own frozen context from the
  same support slice. Reference arm (anchor only): residual 64×64
  `WorldModel`, 20 epochs, lr 1e-3.
- Target: new unused draw by locked rule `mcc_xenv_v4` —
  **(0.0027, 0.0009, 0.05)** — rejecting the default, development,
  confirmation, rung-1 (0.0025, 0.0015, 0.09), rung-2 (0.0028, 0.0013, 0.065)
  and the Cline-draft v3 (0.0034, 0.001, 0.055) physics.
- Seed blocks: resets 65,000,000+, candidate 65,100,000+, prior-collect
  65,200,000+, target-collect 65,300,000+; disjoint from every committed
  seed base (blocked ranges base..base+110,000), rung 1/2 blocks, and the
  Cline-draft block 64,000,000+.
- Everything else identical to rungs 1–2: ten seeds; target pool 1024+256 on
  the new physics; budgets 128/1024 with train+val inside the prefix;
  pretrain 15 epochs lr 1e-3; frozen H=16 × 16 dense-height control,
  200-step episodes; the simulator never enters any world model.

## Identification versus adaptation (secondary, never label-deciding)

If the pretrained machinery merely mapped the target onto a source identity,
the distance from the inferred target context to the nearest source context
would be much smaller than the mean inter-source distance
(`nearest_source_ratio` ≪ 1). A ratio near 1 with distinct target contexts
is consistent with inference on unseen data. Context inference receives only
`(obs, action)` arrays. Validation and evaluation data never enter it. A
positive primary result still stands on control return alone; the diagnostic
qualifies interpretation.

## Predeclared primary and labels

Primary: per-seed mean control return over the budgets {128, 1024}, paired
`xenv − scratch`, student-t 95% CI over ten seeds.

- `xenv_context_code_beats_scratch`: mean > 0 and CI lower bound > 0.
- `xenv_context_code_harm_established`: mean < 0 and CI upper bound < 0.
- `xenv_context_code_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune,
  no rerun on this sample, no excluded seeds.

Secondary (never label-deciding): per-budget gains, held-out prediction MAE,
reference-arm returns, `nearest_source_ratio`, per-arm parameter counts. No
learning-to-learn, cross-family weight transfer beyond the shared trunk plus
shared encoder/FiLM, or AGI claim. A negative result closes this
configuration only.

## Bounds

**600-second hard cap**, **44,000 real environment steps** (19,200 prior
collection + 12,800 target pool + 12,000 evaluation), **3,072,000 imagined
transitions**, 10 training-epoch budgets per seed inside the frozen recipe,
local CPU, one execution after a bound one-run allocation binds this
configuration, protocol and caps. Session ledger at lock: 3414.313 s of the
standing 3600 s remain. Stop and save honestly at any cap.

**Collection is not authorized.** `authorized: false`, `runs: 0`. Do not
train, collect, evaluate, or read reserved holdout outcomes until a new
explicit authorization binds this locked configuration and its caps. Do not
reset or reuse exhausted experiment budgets. Do not modify or merge `main`.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_xenv_context_code.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_xenv_context_code.py            # prep/offline audit
PYTHONPATH=src:.deps python3 scripts/run_xenv_context_code.py --execute  # one authorized run
PYTHONPATH=src:.deps python3 scripts/run_xenv_context_code.py --results-audit
```
