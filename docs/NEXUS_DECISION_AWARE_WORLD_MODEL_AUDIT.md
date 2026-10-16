# Decision-aware world-model audit — source-only inventory

Offline. Zero new real steps. Zero imagined transitions. Collection unauthorized. Not a controller result, not learning-to-learn, not AGI.

## What is in the archive

| Artifact | Split | Present | Missing / limit |
| --- | --- | --- | --- |
| `planning_value.json` | source (8 tasks × 10 decoders) | 16 sequences, frozen H=16 scores, actual 16-step prefix rewards, 64-step suffixes | predicted next-obs / one-step state error by action |
| `first_action_value.json` source cells | source | three first-action 64-step returns | 16-candidate scores |
| `visited_commitment.json` | closed development | sequences, prefix rewards, first-action traces, scores | not a fresh development sample; score-correction closed |
| `prediction_control_gap.json` | closed replication/fresh confirmation | decoder-level ranking, regret, forecast, one-step error | per-candidate score/return arrays not stored |
| receding / same-set / horizon cells | source or development | selected-plan 16-step or episode returns | no per-candidate simulator returns |
| Q/V score-correction artifacts | source + development | three-action labels and closed evaluation | score-correction branch closed |

Do not invent per-action ground truth where only the executed plan was stored.

## Independently recomputed source ranking

From raw `planning_value` prefixes and scores, τ = 1, ten decoder units:

- Student Spearman vs actual 16-step return **0.923 [0.874, 0.973]**
- Student 16-step regret **0.336 [0.106, 0.566]**
- Student near-best minus dominated absolute score error **+0.577 [−0.233, +1.387]**
- Zero-context contrast **+0.750 [+0.505, +0.995]**
- Student H=16 reward MAE **4.882 [3.838, 5.925]** versus zero **4.094 [3.376, 4.812]**
- Observational decoder-level Pearson of student MAE vs 16-step regret **0.698** (not causal)

Label: `source_h1_not_established`. Ranking of the measured 16-step set is already strong. Remaining score error is not established as larger on near-best candidates for the student. Zero context’s contrast interval is above 0 on this suite; that is not a student-context H1 pass and is not a training warrant.

Published exact-16 64-step regret **34.685 [22.677, 46.694]** stays closed (short objective mismatch).

Source first-action 64-return spread **30.260 [20.998, 39.523]**. First action matters under that intervention. Those cells have no model ranking scores.

Closed development `visited_commitment` exploratory contrast **−0.662 [−3.260, +1.936]** includes 0. Not retuned. Not a new screen.

Published prediction-control-gap on closed fresh physics: student ranking and H=16 forecast improved while episode return still lost to zero (`evaluation_variance`). That rejects “better prediction, worse ranking” as the explanation of that control gap. Confirmation splits stay closed.

## Competing hypotheses after the audit

H1 (decision-relevant prediction errors) is **not established** on source. H2 (search/objective/receding) remains consistent with later failed controller screens. H3 (shift, context, sampling) remains open, including negative transfer on disjoint physics.

Decision-aware training is **not** justified from this inventory. Phase C stays a proposal.

## Smallest useful next experiment

Locked in `docs/NEXUS_DECISION_AWARE_WORLD_MODEL_PROTOCOL.md`: development-only, fresh seeds, near-best minus dominated H=16 score error, ten decoders, frozen models, H=16 / 16 candidates, 200-step return as a separate secondary. Budget **90 s / 19,680 / 3,164,160**. **Authorized: false**. Exhausted 3,600 s ledger remaining 47.766 s is below the cap and is not reused.
