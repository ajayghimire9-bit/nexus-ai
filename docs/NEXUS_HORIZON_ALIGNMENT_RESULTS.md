# Horizon-alignment diagnostic — complete development screen

## Registered decision

The locked 60-cell development grid completed with prefix identity intact. Label: `boundary_specific_alignment`.

Remaining-horizon minus fixed H=16 **complete-episode** return: **+0.523 [−0.077, +1.123]**. The mean is far below the registered 25-point full-episode threshold and the paired 95% interval includes 0. This does **not** pass `horizon_alignment_gain` or `fixed_horizon_retained`.

The 16-step artificial-cutoff diagnostic, which cannot upgrade the primary, did pass its own margin: **+7.425 [+4.349, +10.501]**. That is a boundary-specific effect, not general control improvement.

All of the full-episode point difference sits in the last 15 steps (tail gain **+0.523 [−0.077, +1.123]**, identical to the episode contrast). Steps 0–184 matched on every cell. First action disagreement never occurred before step 185.

This does not improve a deployed controller, demonstrate learning-to-learn, or justify an architecture change. Score-correction remains closed. Confirmation physics were not used. Close the general horizon-alignment claim rather than retuning these episodes.

## What was tested

Three `pendulum_context_development` physics, ten independently pretrained decoders, one new phase-0 reset per decoder and task, two visitors (student `(d+t) mod 5` and zero). From each restored `s0`: a 16-step diagnostic cutoff and a 200-step TimeLimit episode. Both windows compared fixed H=16 with `H=min(16, remaining)` using shared per-step candidate seeds and 16 candidates. Primary aggregation: equal tasks then equal visitors inside each of ten decoders. Intervals are Student-t 95%, df 9.

## Means and secondaries

Pooled 200-step returns: fixed H=16 **−540.744 [−609.575, −471.912]**; remaining-horizon **−540.221 [−609.124, −471.318]**.

Pooled 16-step diagnostic returns: fixed H=16 **−99.798 [−112.234, −87.361]**; remaining-horizon **−92.373 [−106.619, −78.127]**.

Decoder full-episode remaining-minus-fixed: **0.60, 0.79, 1.14, −1.32, 0.37, −0.02, 0.99, 0.26, 0.53, 1.89**. Eight of ten are positive; none approach 25.

Secondaries cannot upgrade the primary label:

- Student-visitor full: **+0.344 [−1.020, +1.708]**
- Zero-visitor full: **+0.701 [−0.297, +1.699]**
- task0 full: **+0.106 [+0.036, +0.176]**
- task1 full: **+0.296 [−1.608, +2.201]**
- task2 full: **+1.165 [+0.023, +2.308]**
- Student-visitor short: **+6.972 [+3.752, +10.193]**
- Zero-visitor short: **+7.877 [+3.876, +11.878]**
- Mean tail action mismatches (steps 185–199): **8.25** of 15

Do not treat the 16-step diagnostic as a unique cause of the closed 200-step student-minus-zero gap.

## Integrity

Independent reconstruction of all 60 cells reproduced both intervals and the label. Official `--audit` passed. Prefix identity held on every cell. Frozen checkpoints before and after: 120 verified, 0 missing, 0 mismatched. Parent same-set capture/protocol/results, receding capture, and exhausted-ledger hashes match the locked YAML. No world-model, encoder, Q, or previous-capture writes. Confirmation unused.

## Provenance, resources and tests

Branch `cursor/horizon-alignment-diagnostic`. Preparation SHA **b4691dbdd3661db52399b709edf3148b8cdd0bf6**. One-run allocation/execution SHA **40617d22a99b1113e0133989ee4eb69742fd9289**.

- Config SHA256 `dc199c8241135420ad195b51fbafc41db235ef512a6dfaece45e2228b730d3f5`
- Protocol SHA256 `8a31b4e9690ed7e863fff31ae3e696e808950e70b5143d89f79b1b9e1050e71c`
- Allocation SHA256 `490d3bcc748873c9345c0de2d7870c12a4b3ec8cfcc8665cd8f34fb64a5a72cd`
- Raw artifact SHA256 `910ada43a1c0abc43ca2898bafb7e7678654a21c0e8e7806d19508a3dbd2032e`
- Exhausted 3600-second ledger SHA256 `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`

One collection completed in **32.438 s** execute wall, **32.480 s** total process including pre-collection hash checks and independent audit, below 180. Exactly **25,920** new real steps (short 960+960; full 12,000+12,000) and **6,405,120** imagined transitions. No new support. Python 3.13.5, NumPy 2.5.4, torch 2.14.1, gymnasium 1.4.0, local CPU.

The horizon-alignment one-run remaining is 0. The exhausted 3,600-second standing session file and prior one-runs were not modified. No retry. Further experiments are not authorized by this allocation.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_horizon_alignment.py tests/test_horizon_alignment_feasibility.py tests/test_horizon_alignment_recorded.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_horizon_alignment.py --audit
```

## One next experiment

Close general remaining-horizon alignment as a controller change. A later distinct question would address candidate quality, model bias, or receding search itself—not further shortening of H on these same episodes. That proposal is not implemented and is not authorized here.
