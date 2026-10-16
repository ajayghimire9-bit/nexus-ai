# Parameter-free H=16 lookahead versus frozen H=16 — complete development screen

## Registered decision

The locked 120-episode (30 decoder×task × 2 arms) development grid completed. Label: `bellman_backup_improves_episode_return`.

Lookahead minus frozen H=16 200-step return: **155.647 [109.825, 201.469]**. The mean is above 25 and the paired 95% lower bound is above 0, so the registered improvement rule passes. This is a valid complete controller result on these development physics.

The successor value was the frozen **open-loop** H=16 score from the predicted next state, not a learned Q and not a Bellman-consistent receding-policy value. The lookahead arm also used more imagined computation per step (771 versus 256 model states). This experiment therefore does **not** isolate the benefit of Bellman consistency.

This is not a general control improvement, learning-to-learn, or AGI. Confirmation physics were not used. Score-correction, nested H=8, and fitted Q/V stay closed. Do not retune candidate counts, horizons, or reward weights from this sample.

## What was tested

Three `pendulum_context_development` physics, ten independently pretrained decoders, student visitor `(d+t) mod 5` and zero. Fresh resets `13000000+` and shared step seeds `13100000+`. Both arms saw `candidate_sequences(seed, 16, 16)` at each step. Frozen H=16 executed `seq[argmax, 0]`. Lookahead executed `argmax_a [r_pred(s,a) + max_k score_H16(s'_a, seq_k)]`. Primary aggregation: both visitors and three tasks inside each of ten decoders. Student-t 95%, df 9. Practical margin 25.

## Secondary results (cannot upgrade the primary)

Student-only lookahead minus H=16: **143.068 [70.698, 215.438]**.  
Zero-only: **168.227 [106.415, 230.038]**. Both favor lookahead; neither can change the pooled label.

Lookahead means: student **−380.579**; zero **−376.602**. Frozen H=16: student **−523.647**; zero **−544.828**.

Per-task return_gain (exploratory, ten decoder values):

- task0 (`pendulum_ctx_dev0`): **102.481 [21.891, 183.070]**
- task1 (`pendulum_ctx_dev1`): **139.746 [33.795, 245.697]**
- task2 (`pendulum_ctx_dev2`): **224.715 [82.907, 366.523]**

All ten decoder pooled means are positive: 181.3, 179.8, 107.9, 85.7, 140.8, 248.3, 210.1, 104.3, 65.4, 232.9. Student-only decoder 8 is negative (**−56.0**); the pooled cell remains positive because zero-context on that decoder gained **+186.8**.

First-action mismatch versus H=16: student **2.30 [1.52, 3.08]** steps; zero **2.00 [1.30, 2.70]**. Step-wise action disagreement is about 0.60. Executed one-step angular-velocity MAE stayed small and similar across arms (student H=16 **0.089**, lookahead **0.090**). This is not a one-step prediction pass.

## Integrity

Independent reconstruction of all 30 paired cells reproduced reward sums, shared candidate seeds, H=16 score argmax first actions, lookahead Q argmax first actions, the primary interval and the label. Official `--results-audit` passed. Frozen checkpoints before, after, and live: 120 verified, 0 missing, 0 mismatched. Exhausted 3600-second ledger SHA256 unchanged. Horizon-objective and late-episode captures unchanged. No world-model, encoder, or previous-capture writes. Confirmation unused. Three-action forks: 0. Training updates: 0.

## Provenance, resources and tests

Branch `cursor/receding-long-term-value-audit`. Preparation SHA **6e1d88f290cd563c89e56067b9442a926a72d607**. Implementation SHA **e6bbcb2660e2b28c4febd26579e22a7ff727ce8d**. One-run allocation SHA **ab8dd3bcde4ab25ac3f316f709e69da346ad6b15**.

- Config SHA256 `1a50c953ceb5a20daf3c4e876adc6a8eb855cb5f4ecd1f7d7dffece4fcad625e`
- Protocol SHA256 `6025b926475035677bcb4b7056ef7e0729275be169235f5b94bf956583c4e357`
- Raw artifact SHA256 `d9bc3a0d8cb65d49c3b94061c9079ed59268238007e724f71888cf830b86b0f6`
- Exhausted 3600-second ledger SHA256 `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`

One collection completed in **68.146 s** execute wall, **68.721 s** process including audit. Exactly **24,000** new real steps and **12,324,000** imagined transitions. Zero optimizer updates. Local CPU. No retry.

The lookahead one-run remaining is 0. The exhausted 3,600-second standing session and prior one-runs were not modified. Further experiments are not authorized by this allocation.

## One next experiment

Do not retune candidates, horizon, or reward weights on this sample. A later distinct question is whether this same frozen lookahead rule beats H=16 on disjoint confirmation physics. That would test transfer, not another development objective tweak. An alternative isolation question is whether a receding-policy successor value beats this open-loop successor value. Neither proposal is implemented or authorized here.
