# Late-episode decision trajectory — locked protocol v1

Base `e2da92c521b9c69b0520b144ac43bcf68d62ab01` (`cursor/long-horizon-control-assessment`). Branch `cursor/late-episode-decision-trajectory`. Score-correction closed. Decision-aware ranking collection stays **unauthorized**. Confirmation physics stay closed. Late-state three-action first-action studies stay closed and are **not** repeated.

Frozen FiLM models, encoders, H=16, 16 candidates, published pendulum reward, 120 checkpoints read-only.

## 1. Scientific question not answered by previous experiments

On live receding 200-step episodes, does the student’s **executed-transition** one-step angular-velocity error grow after step 64 **more than zero context’s error grows on its own path**?

Return-phase showed pooled confirmation loss after step 64 but stored only rewards. PCG showed ranking at isolated states. Late-control showed same-state 16-step first-action quality was not separated. None logged per-step scores and executed one-step errors through a development episode.

## 2. Incremental evidence

New development-only paired H=16 receding traces with shared per-step candidate seeds. Primary is differential late error growth on executed actions. Same-state information is the prefix until first action mismatch. After mismatch, metrics are different-state and cannot be treated as restored-state first-action tests. 200-step return is a separate secondary.

No unevaluated-candidate 16-step actuals. No three-action forks.

## 3. Reproducibility and leakage

Development only: `pendulum_ctx_dev0/1/2`. Ten decoders. Student visitor `(d+t) mod 5` and zero. One reset per decoder×task (`11000000+`). **Shared** step seeds `11100000+` (no visitor index), so both controllers score the same 16×16 set at the same step index. Sequences are `candidate_sequences(seed,16,16)` and are reconstructed from the seed at audit; they are not an extra randomness source.

`planner_scores` does not take simulator returns. Executed one-step `model.step` uses the pre-step observation and the chosen action only; the actual next observation is compared afterwards. Context hashes must match before and after each cell. Confirmation task IDs are rejected. Closed parent hashes are locked in YAML. Complete grid: 30 decoder×task cells, 200 truncated steps, `terminated=False`. Incomplete if any cell lacks 200 steps or a finite first-mismatch encoding.

Same-state versus different-state: `first_mismatch_step` is the first index where selected first actions differ while observations still match. Prefix steps `0 … mismatch-1` are same-state shared executed transitions. Step `mismatch` is same-state disagreement. Later steps are different-state. Secondaries that mix those windows are labeled.

Statistical unit: decoder. Average three tasks inside the decoder. Student seeds are not extra replications (one visitor student per cell). Student-t 95%, df 9.

## 4. Primary hypothesis versus exploratory series

**H1 — Student late executed-error growth exceeds zero.**

Estimand: for each decoder, mean over tasks of  
`(student MAE_{64:200} − student MAE_{0:64}) − (zero MAE_{64:200} − zero MAE_{0:64})`  
where MAE is mean absolute angular-velocity error of the executed one-step prediction. Practical margin **0.05**.

- Complete, mean ≥ 0.05, lo > 0: `student_late_error_grows_faster`
- Complete, mean ≤ −0.05, hi < 0: `zero_late_error_grows_faster`
- Else: `late_error_growth_not_established`
- Incomplete grid: `incomplete`

This is **not** a 200-step control pass. Return cannot upgrade it (margin 25 is not this screen).

Exploratory, cannot upgrade: first-mismatch step; prefix-matched student-minus-zero executed MAE; disagreement rate after mismatch; receding plan-consistency (action t+1 vs planned second action at t) early vs late; selected-score traces; observation L2 after mismatch; 200-step student-minus-zero return.

## 5. Budget and authorization

Hard cap **90 seconds total process wall** (checkpoint loading, collection, validation, audit), **12,000** new real steps, **3,084,000** imagined transitions.

- Environment: 10 × 3 × 2 × 200 = **12,000**
- Imagined scoring: 10 × 3 × 2 × 200 × 16 × 16 = **3,072,000**
- Executed one-step predictions: 10 × 3 × 2 × 200 = **12,000**
- Training: **0**. Three-action forks: **0**.

Local CPU. 120 read-only checkpoints. Exhausted 3600 s ledger remaining 47.766 s is **below** 90 s and is not reused. Decision-aware 90 s ranking collection stays unauthorized.

**Collection is unauthorized.** `authorized: false`, `runs: 0`. Do not execute until a new explicit human approval binds this configuration hash and a remainder ≥ 90 s.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_late_episode_decision_trajectory.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_late_episode_decision_trajectory.py --audit
PYTHONPATH=src:.deps python3 scripts/run_late_episode_decision_trajectory.py
# Collection blocked:
PYTHONPATH=src:.deps python3 scripts/run_late_episode_decision_trajectory.py --execute
```

Not a result, not control improvement, not learning-to-learn, not AGI.
