# NEXUS V0.8.4 — Fair Adaptation Verification

Branch `cursor/v084-fair-adaptation-verification`. Parent `93a08bd` (V0.8.3). Artifact `artifacts/v084_verification.json`. Prior V0.8.x JSON files were not overwritten.

This is **not** AGI, not a trading system, and **not** measured adaptation success.

## Question

Can NEXUS accept beneficial model updates and improve H=3 MPC return versus a frozen (never-adapt) agent under the same target-interaction cap?

## Frozen protocol (development, then confirmation)

- Source: CartPole default physics, residual MLP (64, 64), V0.7 H=3 / 16-candidate MPC, objective `both`.
- Identity belief in the planner. GRU is not used.
- Policies: never / always / MAE / repaired `control_fair`.
- `control_fair`: one matched pair of frozen MPC rollouts, horizon **32**, same reset seed, both charged to `online_val` (64 steps reserved before adapt collect). Accept iff candidate mean return ≥ incumbent + **MIN_IMPROVE=2**. `|diff|<2` is inconclusive (reject, not accept). Not reward-per-step.
- Confirmation eval seed **116000**. New unused physics (`dev_v084` / `confirm_v084`). n=10 source-training seeds. Budgets 0 / 128 / 256. Not retuned after confirmation.
- Development selected **MAE** (mean return 298.85 vs never 230.05 vs always 276.9 vs control_fair 230.05). Tie-break unused.

## Commands and provenance

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v084_benchmarks.py
```

- Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0
- Wall clock **267.2 s** (local CPU)
- Artifact written by `run_v084_benchmark`
- Replication unit: source-training seed (Student-t 95%)

## Engineering fixes

1. V0.8.3 control compared a short candidate rollout to mean **collection** returns of different length. V0.8.4 uses matched H=32 MPC returns.
2. Action disagreement (if reported) is H=3 MPC under matched planner RNG; diagnostic only.
3. Estimators observe **once** per env step, with the previously executed action. Prediction error uses raw `next_obs`, not a second `observe`.
4. Collected transitions keep real `episode_id`, reset `seed`, `terminated`, `truncated`, and stop reason (`natural` / `budget` / `adapt_cut`).
5. `split_by_episodes` with one episode returns empty val (disjoint), not a duplicated overlapping set.
6. Validation clones both models; incumbent weights are unchanged.
7. Zero target cap does not construct or step an environment.
8. Proposal traces record scores, decision, reason, and bucket usage. Harm **conditional on acceptance** is `not_applicable` if nothing was accepted.
9. Confirmation episodes are not inputs to the gate.

## Confirmation results (noisy tasks, n=10)

Paired deltas use budget **128** as the pre-registered comparison (also reported at 256 from the same frozen runs).

| Budget | Policy | Mean return [95% t] | Mean accepts / proposals | Acc. rate | Insuff. rate | Paired vs never |
| --- | --- | --- | --- | --- | --- | --- |
| 128 | never | 230.7 [198.3, 263.1] | 0 / 0 | 0 | 0 | — |
| 128 | always | 233.2 [190.5, 275.8] | 3.0 / 3.0 | 1.00 | 0 | **+2.5 [−57, +62]** |
| 128 | mae (selected) | 231.4 [206.7, 256.2] | 0.7 / 1.0 | 0.70 | 0 | **+0.7 [−31, +33]** |
| 128 | control_fair | 230.7 [198.3, 263.1] | 0 / 1.0 | 0 | 0 | **+0.0 [0, 0]** |
| 256 | never | 230.7 [198.3, 263.1] | 0 / 0 | 0 | 0 | — |
| 256 | always | 263.7 [191.1, 336.3] | 3.0 / 3.0 | 1.00 | 0 | **+33.0 [−54, +120]** |
| 256 | mae | 247.1 [211.1, 283.2] | 0.7 / 1.0 | 0.70 | 0 | **+16.4 [−39, +72]** |
| 256 | control_fair | 230.7 [198.3, 263.1] | 0 / 1.0 | 0 | 0 | **+0.0 [0, 0]** |

Clean shifted confirm (no observation noise): all methods **500** (ceiling; regression control only).

Target used equals the cap on every noisy run (128 or 256). Mean pretrain **1328** interactions (source train/val + detector calibration; not in the target cap). Confirmation planning eval is `eval_only` and does not feed the gate. Accepted-update audits are also `eval_only`.

### Harm and benefit

- **control_fair:** 0 accepts. Conditional harm **not applicable**. All 20 noisy@128 proposals were `tie_or_small_diff` (inconclusive). Final return identical to never-adapt.
- **mae:** 14 accepts across noisy tasks at each listed budget. Audit-conditional harm mean **0** (H=32 matched audit vs immediate incumbent). Final vs never CI includes 0.
- **always:** 60 accepts. Audit-conditional harm mean **0**. Final vs never CI includes 0. Continual A→B→C→A naive shared **147** vs snapshot **247**.

Audit harm is not the same as final-model degradation versus never-adapt. The latter is the paired table above.

## Does V0.8.4 support useful adaptation?

**Engineering:** yes. Comparisons are matched, accounting holds, tests cover accept/reject/tie/budget/observe-once/splits, and decisions are traced.

**Scientific:** **no.** The frozen development winner (MAE) does not improve noisy confirmation return versus never-adapt (CI includes 0). The repaired control gate **never accepted** an update: every noisy proposal was an honest tie on H=32. Rejection-only behavior is not adaptation success.

### Evidence vs hypothesis

- **Measured:** H=32 paired MPC returns did not separate candidate from incumbent (`tie_or_small_diff` × 20). Caps 128 and 256 can reserve 64 val steps and still collect; the limitation is discriminative power of a 32-step return on noisy CartPole (≈1 reward per live step), not inability to fit validation in the cap.
- **Hypothesis (not shown):** candidates may be too weak (always@256 paired CI still includes 0), observation noise may swamp H=32 survival differences, or MIN_IMPROVE=2 plus a single paired episode is too conservative for this scale. Do not treat these as results.

## Tests

`PYTHONPATH=src:.deps python3 -m pytest tests -q` → **175 passed**.

## Next step (evidence-based)

Pre-register a **longer matched control horizon** (e.g. H=64 or several paired episodes) at a **fixed equal cap for all methods**, chosen before seeing new confirmation numbers. The V0.8.4 traces already show the gate is not blocked by `insufficient_budget`; it is blocked by ties. Do not start V0.9, finance, or a new environment family on the back of this negative result.
