# Same-set suffix replanning — development confirmation

## Registered decision

The locked 60-cell development grid completed. Label: `same_set_advantage_not_established`.

Same-set minus equal-horizon fresh 16-step return: **+0.834 [−0.955, +2.623]**. The mean is below the registered one-point threshold and the paired 95% interval includes 0. This is a valid, complete, inconclusive primary result. It is not a timeout, not a registered same-set gain, not a registered equal-horizon-fresh gain, and not an equivalence claim.

The source retrospective same-minus-fresh **+5.442 [+3.607, +7.277]** does not replicate as a registered development primary after remaining-horizon equalization. That is consistent with H2 as a horizon-mismatch confound on the source screen. It does not prove H1.

This does not improve a deployed controller, demonstrate learning-to-learn, or justify an architecture change. Score-correction remains closed. Confirmation physics were not used.

## What was tested

Three `pendulum_context_development` physics, ten independently pretrained decoders, one new phase-0 reset per decoder and task, two visitors (student `(d+t) mod 5` and zero). At each restored `s0`, frozen H=16 scored a 16×16 candidate set and selected plan `π`. Arms from the same restored state: same-set suffix receding on remaining horizons 15…1; equal-horizon fresh draws of the same remaining lengths after the shared first action; production H=16 receding from `s0` (not yoked to `π[0]`, not remaining-horizon equalized).

Primary aggregation: equal tasks then equal visitors inside each of ten decoders. Intervals are Student-t 95%, df 9. Return is the 16-step sum of published environment rewards.

## Means and secondaries

Pooled 16-step returns: same-set **−71.365 [−90.003, −52.727]**; equal-horizon fresh **−72.199 [−91.311, −53.086]**; production H=16 **−75.844 [−96.014, −55.675]**.

Decoder same-minus-fresh point estimates: **0.91, −0.67, −1.60, −1.40, −0.04, 0.81, 6.39, 0.60, −0.56, 3.91**. Five of ten are positive. 31 of 60 cells favor same-set.

Secondaries cannot upgrade the primary label:

- Same-set minus production H=16: **+4.479 [+1.046, +7.913]**
- Equal-horizon fresh minus production H=16: **+3.646 [+0.280, +7.011]**
- Student-visitor same minus fresh: **+1.529 [−0.591, +3.649]**
- Zero-visitor same minus fresh: **+0.138 [−1.470, +1.746]**
- task0: **+1.574 [−3.055, +6.204]**
- task1: **+0.189 [−1.334, +1.712]**
- task2: **+0.738 [−0.699, +2.174]**
- Search-noise first-action switch at `s0`: **0.483 [0.379, 0.588]**
- Same-set switch at `s1`: **0.267 [0.106, 0.428]**
- Equal-horizon fresh switch at `s1`: **0.600 [0.485, 0.715]**

Both remaining-horizon methods returned more than production H=16 on this development screen, with intervals above 0. That is a secondary contrast. It does not pass the registered same-set versus equal-horizon-fresh screen. Production H=16 was not remaining-horizon equalized by design.

Do not treat these 16-step development differences as a unique cause of the closed 200-step fresh-episode gap or as a reason to enlarge the network.

## Integrity

Independent reconstruction of all 60 cells reproduced the primary interval and label. Official `--audit` passed. Frozen checkpoints before and after: 120 verified, 0 missing, 0 mismatched. Parent receding capture, protocol, results, Q completed/fit, and exhausted-ledger hashes match the locked YAML. No world-model, encoder, Q, or previous-capture writes. Confirmation unused.

## Provenance, resources and tests

Branch `cursor/same-set-planning-audit`. Preparation SHA **018230a0c16e64cfe004bd5a7462e5ad6e0677a9**. One-run allocation/execution SHA **e0cd3f940673452f5f513d56456be582582017e7**.

- Config SHA256 `f9c69eb216fd10c6f49590edfc1eefb51fe5dc1807ed9903dbc97bdf837f54d4`
- Protocol SHA256 `27a2efcce792537b20af119052c3314662e8c67e98bef343a4841c1a525eafb1`
- Allocation SHA256 `756608286589e41f99e4b6ee9876d14d4882c5cbc4c5dbd108be8ef87216d2cf`
- Raw artifact SHA256 `2aac48a16c7dbce512fdf190d5fc4694f7aed3eba2189a0a953b7a704500368d`
- Exhausted 3600-second ledger SHA256 `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`

One collection completed in **5.655 s** execute wall, **5.701 s** total process including pre-collection hash checks and independent audit, below 60. Exactly **2,880** new real steps (same 960; equal-horizon fresh 960; H=16 960) and **506,880** imagined transitions. No new support. Python 3.13.5, NumPy 2.5.4, torch 2.14.1, gymnasium 1.4.0, local CPU.

The same-set one-run remaining is 0. The exhausted 3,600-second standing session file and the receding one-run file were not modified. No retry. Further experiments are not authorized by this allocation.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_same_set_planning.py tests/test_same_set_planning_feasibility.py tests/test_same_set_planning_recorded.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_same_set_planning.py --audit
```

## One next experiment

Do not retune same-set versus equal-horizon fresh. A distinct question is whether remaining-horizon receding (either A or B) beats production H=16 because the deployed controller plans past the 16-step evaluation window. That would need a new protocol, a fresh budget, and must not reopen confirmation physics or score-correction. It is not implemented and is not authorized here.
