# One-step Bellman backup of frozen H=16 value — locked protocol v1

Base `580dfb0d3e0df1c03d561339577f0a2da8f6e893`. Branch `cursor/receding-long-term-value-audit`. Score-correction closed. Nested H=8 stays closed. Confirmation physics stay closed. Three-action environment forks stay closed. No Q/V fitting.

This is a **control** test of a parameter-free first-action Bellman backup, not a prediction-loss retrain and not an H∈{4,8,16,32} sweep.

Frozen FiLM models, encoders, 16 candidates, published pendulum reward, 120 checkpoints read-only.

## 1. Scientific question

On fresh development resets, does choosing `argmax_a [r_pred(s,a) + max_k score_H16(s'_a, seq_k)]` raise 200-step return relative to frozen H=16 receding that selects the first action of the best open-loop 16-sequence?

Primary is full-episode return. Q RMSE cannot pass this screen.

## 2. Design

Development only: `pendulum_ctx_dev0/1/2`. Ten independently pretrained decoders. Student visitor `(d+t) mod 5` and zero. Fresh reset seeds `13000000+` and shared step seeds `13100000+`. Both arms see `candidate_sequences(seed, 16, 16)` at each step index.

- Arm H=16: score the 16×16 array from `s`, execute `seq[argmax, 0]`.
- Arm Bellman: for each of 3 first actions, one model step to `s'`, score the **same** 16×16 array from `s'`, take `r + max score`, execute `argmax_a Q`. Successor value is the frozen open-loop H=16 score from `s'`, not a Monte Carlo receding-policy return. That is the smallest first-action change that still uses the existing planner as V.

Do not fit a readout. Do not reuse late-episode or H=8 resets. Do not draw independent (16,8) sets.

Statistical unit: decoder. Average both visitors and three tasks inside the decoder. Student-t 95%, df 9.

## 3. Primary versus exploratory

Estimand: decoder mean of (Bellman 200-step return − H=16 200-step return). Practical margin **25**.

- Complete, mean ≥ 25, lo > 0: `bellman_backup_improves_episode_return`
- Complete, mean ≤ −25, hi < 0: `bellman_backup_hurts_episode_return`
- Else: `bellman_backup_not_established`
- Incomplete grid: `incomplete`

Exploratory, cannot upgrade: student-only; zero-only; first-action disagreement rate; executed one-step MAE. Ranking-loss training is not this experiment.

## 4. Budget and authorization

Hard cap **180 seconds total process wall**, **24,000** new real steps, **12,324,000** imagined transitions, **0** optimizer updates.

- Environment: 10 × 3 × 2 × 200 × 2 arms = **24,000**
- H=16 scoring: 10 × 3 × 2 × 200 × 16 × 16 = **3,072,000**
- Bellman: 10 × 3 × 2 × 200 × (3 + 3 × 16 × 16) = **9,252,000**

Local CPU. 120 read-only checkpoints. Previous research budgets remain exhausted or consumed and are not transferred.

**Collection is unauthorized.** `authorized: false`, `runs: 0`. Do not execute until a new explicit human approval binds this configuration hash and these caps.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_receding_long_term_value_audit.py tests/test_bellman_backup_control.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_receding_long_term_value_audit.py
PYTHONPATH=src:.deps python3 scripts/run_bellman_backup_control.py
# Collection blocked:
PYTHONPATH=src:.deps python3 scripts/run_bellman_backup_control.py --execute
```

Not a result, not control improvement, not learning-to-learn, not AGI.
