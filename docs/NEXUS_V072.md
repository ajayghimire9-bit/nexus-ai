# NEXUS V0.7.2 — Planning reliability and model exploitation

Branch `cursor/v072-planning-reliability`. Not merged. Measured 2026-10-11, CPU.

Parent `b8d4bb0`. `pytest` **130 passed**. Prior `v07` / `v071` artifacts were not overwritten.

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v072_benchmarks.py`

Not AGI. Simulator is an eval oracle. Geometric termination uses thresholds on the **predicted** next state, not `env.step`. Temperature calibration is fit on **val Brier** only.

## What V0.7.1 got wrong

`RandomShootingMPC.act` re-seeded `default_rng(self.seed)` on **every** decision, so every step scored the **same** candidate sequences. Under absorbing termination that is a repeatable, exploitable shooting pattern—not a fair multi-step planner.

V0.7.2 keeps a persistent RNG and calls `reset_episode(seed)` at episode start. Consecutive steps draw new sequences. The same seed reproduces the full action list.

Scoring is matched to one-step greedy: predicted CartPole reward **+1** while imagined-alive, plus `-(|θ| + 0.25|ω|)`. Candidate-eval budget **48** ≈ `n_candidates × horizon`.

## Prediction (n=5 model seeds)

| Model | test MAE [t 95%] |
| --- | --- |
| Ridge residual | 0.000125 [0.000115, 0.000135] |
| Residual MLP | 0.00915 [0.00673, 0.0116] |

Learning env steps: **1280**/seed (1024+256). Wall **228 s**.

## Task 2 — Termination vs the ridge collapse

Horizon 6, 8 candidates (budget 48). Returns:

| Planner | mean [t 95%] |
| --- | --- |
| Ridge + learned p_term | **446 [387, 505]** |
| Ridge + always-nonterminal | 389 |
| Ridge + val-calibrated p_term | 431 [399, 462] |
| Ridge + geometric (diagnostic) | 397 |
| Residual + learned | 439 [417, 461] |
| Residual + always-live | 441 [390, 492] |
| Ridge one-step greedy | 317 [242, 392] |
| Residual one-step greedy | 361 [331, 391] |
| Random / heuristic | 17 / 500 |

Ridge learned − greedy **+129 [60, 198]** (excludes 0). The V0.7.1 ridge MPC return of **9** does **not** replicate once candidates change every step.

Always-live − learned (ridge) **−57 [−116, +2]** includes 0. **Incorrect p_term is not sufficient to explain the old collapse.** Learned ridge terminate Brier is still bad (0.077 vs always-live 0.007, recall 0); calibrated Brier matches always-live (~0.007). Geometric recall is 1.0 on the random-policy test set (fail labels are the CartPole fail-set).

## Task 3 — Horizon with matched compute

`n_candidates = max(2, 48 // H)`:

| H | cand | ridge learned | residual learned | residual always-live |
| --- | --- | --- | --- | --- |
| 1 | 48 | 379 | 366 [312, 419] | 366 |
| 3 | 16 | **486 [449, 524]** | **500** | **500** |
| 6 | 8 | 446 [387, 505] | 439 [417, 461] | 441 |
| 10 | 4 | 249 [195, 303] | 132 [82, 182] | 119 |
| 20 | 2 | 96 [81, 110] | 76 [53, 99] | 65 |

**Short multi-step planning helps** (H=3 vs H=1 and vs greedy). **Long horizons with the same eval budget hurt** because the shooter has 2–4 sequences, not because H=20 is intrinsically worse physics.

Residual H=6 − greedy **+78 [47, 108]** (excludes 0) under this RNG and matched objective.

## Task 4 — Exploitation

When control works, on-policy MAE is **not** worse than off-policy test MAE (ridge ~7e-5 on-policy vs 1.3e-4 test). Imagined shooting scores are not episode returns (different units: summed 1−|θ| along a horizon). Failed long-horizon runs are explained by **candidate starvation**, not a measured on-policy MAE blow-up in this setup.

## Task 5 — Uncertainty

Ensemble always-live H=6: zero penalty **464 [435, 493]** vs penalty 2 **458 [439, 478]**. Paired **−5.6 [−33, +22]** includes 0. **Do not call uncertainty beneficial.**

## Answers

1. **Ridge MPC failure (V0.7.1):** primarily **non-persistent candidate RNG** (same sequences every timestep), not one-step MAE and not uniquely the terminate head. Terminate Brier is still miscalibrated; it did not recreate return=9 after the RNG fix.
2. **Does multi-step planning help?** **Yes at H=3–6** with a fixed eval budget and persistent RNG, vs H=1 and vs greedy (residual +78, ridge +129 at H=6). **No at H=10–20** under the same budget.
3. Remaining uncertainty: whether H=20 would help with **more** candidates (unmatched compute); whether a better terminate model would beat always-live (CI includes 0 here).

Do not start V0.8 until any new planner is tested with persistent RNG, matched H=1, and a recorded eval budget.
