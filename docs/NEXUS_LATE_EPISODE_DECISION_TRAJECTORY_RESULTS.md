# Late-episode decision trajectory — complete development screen

## Registered decision

The locked 30-cell development grid completed. Label: `late_error_growth_not_established`.

Student-minus-zero difference in late-versus-early executed one-step angular-velocity error growth: **+0.016 [+0.003, +0.029]**. The paired 95% lower bound is above 0, but the mean is below the registered 0.05 practical margin, so H1 does **not** pass. This is a valid complete result, not a timeout and not a control pass.

Student executed MAE did not increase late (**−0.003 [−0.014, +0.008]**). Zero-context MAE decreased late (**−0.019 [−0.037, −0.001]**). The positive growth_diff is relative: zero improved more than the student on their own paths. It is not same-state first-action quality.

This does not improve a deployed controller, demonstrate learning-to-learn, or justify a ranking-loss or architecture change. Three-action late-state forks were not collected. Confirmation physics were not used. Score-correction stays closed.

## What was tested

Three `pendulum_context_development` physics, ten independently pretrained decoders, one new phase-0 reset per decoder and task, student visitor `(d+t) mod 5` and zero. Shared per-step candidate seeds. Frozen H=16 / 16 candidates. Primary aggregation: three tasks inside each of ten decoders. Intervals are Student-t 95%, df 9.

## Secondary results (cannot upgrade the primary)

Pooled 200-step return, student minus zero: **−5.414 [−92.420, +81.592]**. Includes 0. Far below the 25-point episode screen. Student mean **−515.618**; zero **−510.204**.

First student–zero action mismatch: mean **9.6 [4.7, 14.5]** steps. Six of 30 cells mismatched at step 0. After mismatch, error comparisons are different-state.

Receding plan-inconsistency (action t+1 ≠ planned second action at t): early **0.509 [0.490, 0.529]**; late **0.525 [0.497, 0.553]**. Exploratory.

### Task growth_diff (exploratory)

- task0 (`pendulum_ctx_dev0`): **+0.047 [+0.022, +0.073]**
- task1 (`pendulum_ctx_dev1`): **−0.003 [−0.014, +0.007]**
- task2 (`pendulum_ctx_dev2`): **+0.004 [−0.026, +0.034]**

Task0's interval is above 0 and its mean is near 0.05. It cannot upgrade the pooled primary.

Executed MAE levels: student early **0.089 [0.077, 0.100]**, late **0.085 [0.076, 0.094]**; zero early **0.123 [0.107, 0.138]**, late **0.104 [0.092, 0.116]**. The student remains more accurate on executed transitions in both windows.

## Integrity

Independent reconstruction of all 30 cells reproduced growth_diff, return_gain, sequence-from-seed identity, score argmax, planned second action, finite rewards/observations/errors, and the label. Official `--results-audit` passed. Shared step seeds matched within every cell. Frozen checkpoints before and after: 120 verified, 0 missing, 0 mismatched. Exhausted-ledger hash unchanged. No world-model, encoder, or previous-capture writes. Confirmation unused. Three-action forks: 0.

## Provenance, resources and tests

Branch `cursor/late-episode-decision-trajectory`. Preparation SHA **2f81d4130a954cec67f22ce579c9115b228ffcdd**. One-run allocation SHA **1cece7e791ab0a614afac29211e7f40cb5540225**.

- Config SHA256 `472a1e460977a91acb45512185c480b4dc6689aaec3a3429286fe3c98d3d2055`
- Protocol SHA256 `a22bd269c634d47621daddd96e28fda8eaffdf4fd7fb8996c8b540de761d0a5f`
- Raw artifact SHA256 `743b545d78910f7b0df8c83d15b4eb77190798b1dd803ad4daa51434a6214939`
- Exhausted 3600-second ledger SHA256 `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`

One collection completed in **16.743 s** execute wall. Independent audit **1.249 s**. Total process under 90 s. Exactly **12,000** new real steps and **3,084,000** imagined transitions. Local CPU. Python 3.13.5. No retry.

The late-episode one-run remaining is 0. The exhausted 3,600-second standing session and prior one-runs were not modified. Further experiments are not authorized by this allocation.

## One next experiment

Do not train a decision-aware ranking loss from this sample. A later distinct question would address receding search noise or compounding state shift after early first-action mismatch, on a new protocol. That proposal is not implemented and is not authorized here.
