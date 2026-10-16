# Nested H=8 versus archived H=16 — complete development screen

## Registered decision

The locked 60-episode (30 decoder×task) development grid completed. Label: `shorter_horizon_hurts_episode_return`.

H=8 minus archived H=16 200-step return: **−174.178 [−265.830, −82.527]**. The mean is below −25 and the paired 95% upper bound is below 0, so the registered hurt rule passes. This is a valid complete negative control result, not a timeout and not a prediction result.

Scoring the first eight actions of the same 16×16 candidates **lowered** complete-episode return on these development physics. One-step executed angular-velocity error stayed small (student **0.095 [0.085, 0.105]**). Better short-horizon scores did not produce better 200-step decisions.

This does not improve a deployed controller, demonstrate learning-to-learn, or justify another MPC-horizon retune. Confirmation physics were not used. Score-correction stays closed.

## What was tested

Three `pendulum_context_development` physics, ten independently pretrained decoders, student visitor `(d+t) mod 5` and zero. Paired late-episode resets `11000000+` and step seeds `11100000+`. Candidates `candidate_sequences(seed, 16, 16)`; scores used `sequences[:, :8]`. Archived H=16 returns were not re-simulated. Primary aggregation: both visitors and three tasks inside each of ten decoders. Student-t 95%, df 9. Practical margin 25.

## Secondary results (cannot upgrade the primary)

Student-only H=8 minus H=16: **−200.518 [−321.071, −79.964]**.  
Zero-only: **−147.839 [−241.949, −53.729]**. Both hurt; neither can change the pooled label.

H=8 means: student **−716.136**; zero **−658.043**. Archived H=16: student **−515.618**; zero **−510.204**.

Per-task return_gain (exploratory, ten decoder values):

- task0 (`pendulum_ctx_dev0`): **−144.135 [−371.256, +82.986]** (includes 0)
- task1 (`pendulum_ctx_dev1`): **−306.511 [−390.718, −222.304]**
- task2 (`pendulum_ctx_dev2`): **−71.889 [−170.232, +26.455]** (includes 0)

All ten decoder pooled means are negative: −56.9, −155.2, −86.8, −90.3, −95.1, −395.9, −410.8, −167.0, −194.0, −90.0.

First H=8 versus H=16 action mismatch: student **3.47 [1.89, 5.05]** steps; zero **2.83 [1.80, 3.87]**. Step-0 disagreement: student 9/30 cells, zero 6/30. Policies diverge immediately, then occupy different states. H=8 executed one-step MAE remains comparable to the archived H=16 one-step level and is not a control pass.

## Integrity

Independent reconstruction of all 30 paired cells reproduced returns, nested 16→8 candidate prefixes, score argmax, first actions, reward sums, the primary interval and the label. Official `--results-audit` passed. Shared step seeds matched the archived H=16 schedule. Initial states matched. Frozen checkpoints before and after: 120 verified, 0 missing, 0 mismatched. Late-episode capture SHA256 unchanged. Exhausted 3600-second ledger SHA256 unchanged. No world-model, encoder, or previous-capture writes. Confirmation unused. Three-action forks: 0.

## Provenance, resources and tests

Branch `cursor/multistep-rollout-control-audit`. Preparation SHA **3c278441fea8c541c52c4eacd7be3de64379f088**. Implementation SHA **1e1c4ed**. One-run allocation SHA **500c34de6bb1304d17fb3305260f81b47c8a55b7**.

- Config SHA256 `fc862b46b9ab1163e894acf4a57693282db8d0a20f9f4f35220e0f8f65999b56`
- Protocol SHA256 `76894e91fe872fe600d652691203e2f38e5b611c96d22d8df527dffb24e93317`
- Raw artifact SHA256 `bd25f642b6caab86d09d46a7af5c512ead4383f5a61e4ec68b4519935cae24cf`
- Exhausted 3600-second ledger SHA256 `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`

One collection completed in **8.542 s** execute wall. Independent audit passed. Total process under 90 s. Exactly **12,000** new real steps and **1,536,000** imagined transitions. Local CPU. No retry.

The H=8 one-run remaining is 0. The exhausted 3,600-second standing session and prior one-runs were not modified. Further experiments are not authorized by this allocation.

## One next experiment

Do not shorten the horizon further and do not treat prediction MAE as a controller success. A later distinct question should address long-term decision value under receding control, not another H∈{4,8,16,32} sweep. That proposal is not implemented and is not authorized here.
