# Nested H=8 versus archived H=16 receding — locked protocol v1

Base `a9ada15ac3ae758b75187074aaae98eab089d2a9`. Branch `cursor/multistep-rollout-control-audit`. Score-correction closed. Decision-aware ranking collection stays unauthorized. Confirmation physics stay closed. Three-action forks stay closed.

This protocol is a **control** test of scoring horizon, not a prediction-loss retrain. Offline teacher-forced H=16 angular-velocity MAE is ~1.93–2.03 on recorded live actions. Nested H=8 scoring uses the same 16×16 candidate arrays as the archived H=16 traces.

Frozen FiLM models, encoders, 16 candidates, published pendulum reward, 120 checkpoints read-only.

## 1. Scientific question

On the same development resets as the late-episode H=16 receding traces, does scoring the first 8 actions of each shared candidate improve 200-step return relative to the archived H=16 controller?

Primary is full-episode return. Prediction MAE cannot pass this screen.

## 2. Design

Development only: `pendulum_ctx_dev0/1/2`. Ten independently pretrained decoders. Student visitor `(d+t) mod 5` and zero. **Paired reuse** of late-episode reset seeds `11000000+` and step seeds `11100000+` so candidate arrays equal `candidate_sequences(seed, 16, 16)`. Score `sequences[:, :8]` with `RandomShootingMPC(horizon=8, n_candidates=16)`. Do not draw independent `(16, 8)` integers; that would confound horizon with a new candidate set.

H=16 returns are **not** re-simulated. They are read from the frozen late-episode capture. H=8 episodes are newly collected. Do not overwrite `artifacts/late_episode_decision_trajectory.json`.

Statistical unit: decoder. Average both visitors and three tasks inside the decoder. Student-t 95%, df 9.

## 3. Primary versus exploratory

Estimand: decoder mean of (H=8 200-step return − archived H=16 200-step return). Practical margin **25**.

- Complete, mean ≥ 25, lo > 0: `shorter_horizon_improves_episode_return`
- Complete, mean ≤ −25, hi < 0: `shorter_horizon_hurts_episode_return`
- Else: `shorter_horizon_not_established`
- Incomplete grid: `incomplete`

Exploratory, cannot upgrade: student-only contrast; zero-only contrast; first-mismatch of H=8 versus H=16; H=8 executed one-step MAE. Ranking-loss training is not this experiment.

## 4. Budget and authorization

Hard cap **90 seconds total process wall**, **12,000** new real steps, **1,536,000** imagined transitions.

- Environment: 10 × 3 × 2 × 200 = **12,000**
- Imagined scoring: 10 × 3 × 2 × 200 × 16 × 8 = **1,536,000**
- Training: **0**

Local CPU. 120 read-only checkpoints. Previous research budgets remain exhausted or consumed and are not transferred.

**Collection is unauthorized.** `authorized: false`, `runs: 0`. Do not execute until a new explicit human approval binds this configuration hash and these caps.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_multistep_rollout_control_audit.py tests/test_horizon_objective_control.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_horizon_objective_control.py
# Collection blocked:
PYTHONPATH=src:.deps python3 scripts/run_horizon_objective_control.py --execute
```

Not a result, not control improvement, not learning-to-learn, not AGI.
