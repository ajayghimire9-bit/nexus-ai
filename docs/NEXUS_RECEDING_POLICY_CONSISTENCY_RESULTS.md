# Receding-horizon policy consistency — complete source screen

## Registered decision

The locked 160-cell source grid completed. Label: `replan_consistency_not_established`.

Commit-16 minus recede-fresh 16-step return: **−1.787 [−4.324, +0.751]**. The mean is below the registered one-point commitment threshold. The paired 95% interval includes 0, so it also fails the receding-replanning screen (mean ≤ −1 and upper bound < 0). This is a valid, complete, inconclusive primary result. It is not a timeout, not a registered open-loop gain, not a registered receding gain, and not an equivalence claim.

This does not improve a deployed controller, demonstrate learning-to-learn, or justify an architecture change. Score-correction remains closed. Confirmation physics were not used.

## What was tested

Eight `pendulum_context_train` physics, ten independently pretrained decoders, one new phase-0 reset per decoder and task, two visitors (student `(d+t) mod 5` and zero). At each restored `s0`, frozen H=16 scored a 16×16 candidate set and selected plan `π`. Arms from the same restored state: execute `π` open-loop; recede on remaining suffixes of that same set; recede with fresh candidate draws after the shared first action; continue with the decoder's zero-context receding planner on the same continuation seeds (copied, not re-collected, when the visitor is already zero).

Primary aggregation: equal tasks then equal visitors inside each of ten decoders. Intervals are Student-t 95%, df 9. Return is the 16-step sum of published environment rewards.

## Means and secondaries

Pooled 16-step returns: commit **−92.747 [−105.259, −80.235]**; recede-fresh **−90.960 [−105.190, −76.731]**; recede-same-set **−85.518 [−99.639, −71.398]**; common-zero **−90.939 [−105.254, −76.624]**.

Decoder commit-minus-recede-fresh point estimates: **−9.76, −2.09, 0.98, 1.82, −1.76, −5.17, −2.16, 1.18, 1.11, −2.02**. Four of ten are positive.

Secondaries cannot upgrade the primary label:

- Commit minus recede-same-set: **−7.229 [−9.718, −4.739]**
- Recede-fresh minus recede-same-set: **−5.442 [−7.277, −3.607]**
- Recede-fresh minus common-zero: **−0.022 [−0.631, +0.587]**
- Student-visitor commit minus recede-fresh: **−2.045 [−4.851, +0.760]**
- Zero-visitor commit minus recede-fresh: **−1.528 [−4.019, +0.963]**
- Search-noise first-action switch at `s0`: **0.500 [0.430, 0.570]**
- State-driven suffix switch at `s1`: **0.200 [0.122, 0.278]**
- Recede-fresh switch at `s1`: **0.450 [0.331, 0.569]**

Same-set receding returned more than both open-loop commitment and fresh-candidate receding on this source screen. That is a secondary contrast. It does not pass H-commit-beats-replan or H-replan-beats-commit, and it was not the registered primary. Search-noise disagreement at `s0` is at least as large as recede-fresh disagreement after the state changes; that does not identify harm.

Do not treat these 16-step source differences as a unique cause of the closed 200-step fresh-episode gap or of Q/V failure.

## Integrity

Independent reconstruction of all 160 cells reproduced the primary interval and label. Official `--audit` passed. Frozen checkpoints before and after: 120 verified, 0 missing, 0 mismatched. Parent Q, fit, incomplete capture, resume-results, visited-commitment, commitment-value, receding-horizon, and exhausted-ledger hashes match the locked YAML. No world-model, encoder, Q, or previous-capture writes. Confirmation unused.

## Provenance, resources and tests

Branch `cursor/receding-policy-consistency`. Preparation SHA **7b4637d423e64aac29305bf188f6d35b1d058563**. One-run allocation SHA **872e81fba04566d15e0bb4a4605634619de93b3d**.

- Config SHA256 `251d83d14791d416dcdbd30c9a6f2985ce039475f8a43d453fbe8806f661531e`
- Protocol SHA256 `69e50a8409167ff64de64afd55ddc136273498740d8c5cfad04d281acbb6f85e`
- Allocation SHA256 `9d661c77fbd35ce46dd396a51fe7752d92049cb3b22dc58fb5109c7ee8e182e8`
- Raw artifact SHA256 `48736a499e0d650dbf8138cc29e03cdbb623f0e3b413dec7b2b6b552adc2e149`
- Exhausted 3600-second ledger SHA256 `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`

One collection completed in **17.838 s** execute wall, **17.927 s** total process including pre-collection hash checks and independent audit, below 120. Exactly **8,960** new real steps (commit 2,560; recede-same 2,560; recede-fresh 2,560; common-zero 1,280) and **1,515,520** imagined transitions. No new support. Python 3.13.5, NumPy 2.5.4, torch 2.14.1, gymnasium 1.4.0, local CPU.

The receding one-run remaining is 0. The exhausted 3,600-second standing session file was not modified. No retry. Further experiments are not authorized by this allocation.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_receding_policy_consistency.py tests/test_receding_policy_consistency_feasibility.py tests/test_receding_policy_consistency_recorded.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_receding_policy_consistency.py --audit
```

## One next experiment

Same-set suffix receding beat both open-loop commitment and fresh-candidate receding here, but only as a secondary. A new protocol would need to make remaining-suffix receding versus deployed recede-fresh the primary on a locked held-out source or development split, with a fresh budget, and without reopening confirmation physics or score-correction. That proposal is not implemented and is not authorized here.
