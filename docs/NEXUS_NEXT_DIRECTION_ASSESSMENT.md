# Next-direction assessment — short-horizon ranking vs episode control

Source-only. Zero new real steps. Zero imagined transitions. Zero training. The locked decision-aware protocol is **unchanged** and **unauthorized**. Confirmation physics were not reopened for collection. Closed labels are not retuned. Not control improvement, not learning-to-learn, not AGI.

Parent: `11f56b7833dc2c7befff823617c3784656ff54eb` (`cursor/decision-aware-world-model-diagnostic`). Branch `cursor/long-horizon-control-assessment`.

## Recommendation

**Direction B.** Investigate long-term decision consistency and 200-step control failure, using recorded evidence first.

Short-horizon ranking on initial states is already strong. The unresolved control problem sits later in the episode. Running the pending 90-second development ranking diagnostic would mainly re-ask a question that source ranking, closed visited-commitment reanalysis, and the prediction-control gap have already constrained. It is preserved as a locked fallback, not the next information-maximizing step.

## Direction A — short-horizon ranking on development physics

**Question.** On fresh development states, does the frozen student make larger H=16 score errors on near-best candidates than on dominated ones?

**Archive.** Not sufficient for that exact estimand. Source `planning_value` already answers the same contrast on training physics: **+0.577 [−0.233, +1.387]**, H1 not established, Spearman **0.923**. Closed development `visited_commitment` exploratory contrast **−0.662 [−3.260, +1.936]** also includes 0. Predicted next-obs by action is still missing. The locked protocol would collect those development measurements.

**What would change engineering.** A pass (mean ≥ 1, lower bound > 0) would justify a *separately* approved ranking-loss proposal, not a controller change. A fail or inconclusive result would close short-horizon ranking diagnosis. Neither outcome would explain why one-shot ranking can improve while 200-step return falls.

**Smallest new experiment.** The already locked development diagnostic: 90 s / 19,680 real / 3,164,160 imagined. **Authorized: false.** Do not run it in this assessment.

**Safeguards.** Development physics only. Confirmation closed. Score-correction closed. Exhausted 3600 s ledger (remaining 47.766 s) is not reused.

**Information gain.** Low relative to cost. PCG already found better ranking *and* better H=16 forecast on the closed fresh split while episode return still lost to zero. Source ranking is already high. A development H1 result would still be a 16-step in-set diagnostic.

## Direction B — 200-step decision consistency, recorded evidence first

**Question.** After H=16 ranking looks adequate at shared initial states, where and how does receding student control lose complete-episode return relative to zero context?

**Archive, without new simulation.**

Published, closed, not retuned:

- Fresh-episode student-minus-zero **−30.671 [−41.540, −19.801]**, label `primarily_late`. Steps 0–15 include 0; steps 16–199 do not. Observation distance grows from **0.58** at step 16 to **2.86** at step 199.
- PCG on those physics: student ranking and forecast improved; episode return was not remeasured and stays closed (`evaluation_variance`).
- Late visited-state 16-step action quality **not separated** (**+0.031 [−0.083, +0.145]**). On those same late states, regret favored zero (**−0.340 [−0.641, −0.039]**) while forecast MAE favored the student.
- 64-step full-policy tail **−8.661 [−14.513, −2.809]**, `long_policy_tail_worse`, concentrated in rp2.
- Policy switch SS−SZ **−18.733 [−27.271, −10.195]**, `continued_student_suffix_worse`. Continuing student context after an identical student prefix is harmful on that sample; inheritance is inconclusive.
- Receding commit vs recede-fresh **−1.787 [−4.324, +0.751]**, not established. Remaining-horizon vs H=16 on 200-step development **+0.523 [−0.077, +1.123]**, boundary-specific.

Exploratory reanalysis of the **already recorded** 160 return-phase reward traces (not a new screen; does not change `primarily_late`):

- Steps 16–63: **+0.307 [−4.144, +4.759]** includes 0.
- Steps 64–127: **−11.730 [−17.965, −5.496]** excludes 0.
- Steps 128–199: **−18.018 [−26.311, −9.725]** excludes 0.

The pooled 200-step loss is not a first-horizon ranking miss. It accumulates after step 64, as trajectories diverge. Horizon-alignment cells store only aggregate returns, so they cannot refine this timing. Return-phase stores rewards, not per-step actions or planner scores, so ranking-along-the-episode cannot be reconstructed.

**What would change engineering.** If later work showed ranking remaining accurate on the student’s later visited states, the next lever is receding search / compounding state shift, not a ranking loss. If ranking degraded on those later states, a *new* decision-aware objective would have to target visited-state error, not initial-state 16-candidate ranking (Direction A). A switch-to-zero rule from the rp2 policy-switch result is not a deployable controller and is not authorized.

**Smallest new experiment, if any.** None in this assessment. The recorded traces already move the next scientific target from initial-state H=16 ranking to post-64 receding behavior. A later protocol, if approved separately, would log per-step actions and scores on **new development** episodes at a few restored phases. It must not reopen confirmation seeds, must not retune `primarily_late`, and must keep episode return separate from ranking metrics. No such protocol is authorized here. Cost of that hypothetical later run is not spent and is not estimated as an approval.

**Safeguards.** Confirmation splits remain closed. This assessment reads return-phase rewards but does not collect, overwrite, or change that label. Decision-aware YAML/protocol/allocation hashes stay `0fe69d77…` / `c66a2960…` with `authorized: false`.

**Information gain.** High. It uses the actual control failure (200-step return) rather than a 16-step proxy that already looks healthy.

## Why not A first

A can still be run later if B’s recorded synthesis is wrong about development physics. Its protocol is locked for that reason. Running A now spends 90 s and 19,680 steps on a question whose best available analogues already failed to establish H1 and whose success would still not close the episode gap. Expected information about *reliable control on unfamiliar physics* is larger for B.

## Authorization

This assessment: standing coding grant only. **`authorized: false`** for every simulation, including Direction A. Exhausted 3600 s ledger unmodified. No merge to `main`.
