# NEXUS cross-environment test — Pendulum-v1

Branch `cursor/v089-cross-environment-test`. Parent `ef6588c`. Artifact `artifacts/cross_environment.json`.

Not AGI. Not CartPole weight transfer. Not learning-to-learn. Architecture **not** retuned on these returns.

## Hypothesis H1

The same residual 64×64 world model and H=3 / 16-candidate random-shooting MPC that plans on CartPole can improve control on **Pendulum-v1** with only interface changes (obs dim, discrete torque, published reward).

## Frozen interface (before confirmation)

| Item | Value |
| --- | --- |
| Torques | **−2, 0, +2** (Gymnasium `max_torque`) |
| Reward | Gymnasium published `-(θ² + 0.1 θ̇² + 0.001 u²)` on the **current** state and u, then the physics step |
| MPC score | that reward (not CartPole +1 / pole-angle bonus) |
| Train / val | 1024 / 256 random-policy transitions, seed-disjoint episodes |
| Epochs | 20 |
| Eval | seed **163000**, 2 episodes, all controllers share it |
| PPO reference | 16 384 steps, own budget |

CartPole tensors are 4×2; Pendulum 3×3. **Incompatible.** No weight load was attempted.

## Independently measured (n=10)

Higher (less negative) is better.

| Controller | Return | vs random (paired) |
| --- | --- | --- |
| Random | −1195.5 (deterministic under the shared eval seed) | 0 |
| Always 0 | −1237.5 | — |
| Always ±2 | −1507 / −1527 | — |
| PD heuristic (frozen gains) | −1114.4 | **+81.1** (exact) |
| **Residual H=3 MPC** | **−1052.8 [−1280, −826]** | **+142.7 [−84, +370] includes 0** |
| PPO @ 16 384 | −1461.3 | **−266 [−350, −181]** worse than random |

H1 **fails** the pre-registered rule: MPC vs random CI includes 0.

One-step val MAE **0.035 [0.026, 0.044]** (multi-step H=3 ~0.04–0.05). CartPole residual MAE was ~0.003; scale and dynamics differ.

**6/10** seeds beat random and the heuristic (~−747 to −844); **4/10** are worse than random (~−1380 to −1419). MAE does not rank those groups (best MAE seed is among the failures).

PPO at 16 384 collapsed toward constant torque. It is an under-trained reference, not a Pendulum specialist.

## Diagnosis (no architecture/horizon change)

1. **Horizon 3 × dt=0.05 s = 0.15 s** is far shorter than a swing-up; H=3 was selected on CartPole survival, not Pendulum energy.
2. **Action discretization** to three torques is a necessary interface, not proven sufficient.
3. **Learned dynamics** are usable (finite MAE) but one-step error does not predict return.
4. **Reward interface** matches Gymnasium (tested). Inconsistency is not the failure.

Do not raise H or width from this confirm.

## Learning-to-learn

Not started. H1 did not hold, so a follow-up that “Pendulum experience helps the next family” would not be measuring a working inner planner.

If a later study gets MPC vs random with a CI excluding 0 **without** retuning CartPole H/width on Pendulum returns, then a matched-budget A→Pendulum vs scratch-Pendulum sample-efficiency test would be the next L2L measurement.

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_cross_environment.py
```

Python 3.13.5, PyTorch 2.14.1, Gymnasium 1.4.0. `pytest` **238 passed**. Wall **17.0 s**. Protocol hash `402ce4151837eb0d`.
