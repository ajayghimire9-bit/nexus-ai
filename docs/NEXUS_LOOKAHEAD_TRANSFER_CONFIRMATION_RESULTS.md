# Frozen lookahead versus H=16 — complete transfer screen

## Registered decision

The locked 120-episode holdout grid completed. Label: `lookahead_transfer_established`.

Lookahead minus frozen H=16 200-step return: **98.608 [43.258, 153.957]**. The mean is above 25 and the paired 95% lower bound is above 0, so the registered transfer-improvement rule passes on this new Pendulum holdout.

This is transfer of the **same frozen development controller**, not a retune. Successor value remained the frozen **open-loop** H=16 score from `s'`, not Bellman-consistent receding-policy value. Lookahead used 771 imagined states per step versus 256 for H=16. Historically closed confirmation physics were not reused.

This is **not** learning-to-learn, **not** cross-family generalization, and **not** AGI. Student-versus-zero is a separate estimand and was **not** established. Do not retune this controller from these confirmation outcomes.

## What was tested

Holdout rule `lookahead_transfer_holdout_v1`, split hash `73844661addfa11b`:

- `pendulum_look_tf0` (17.1, 1.5, 0.8)
- `pendulum_look_tf1` (12.5, 0.65, 0.9)
- `pendulum_look_tf2` (4.2, 3.2, 1.7)

Ten independently pretrained decoders. Student visitor `(d+t) mod 5` with frozen-encoder inference on 128 random-policy support rows. Zero visitor `z = 0`. Fresh resets `14000000+`, step seeds `14100000+`, support seeds `14200000+`. Both arms saw `candidate_sequences(seed, 16, 16)` at each step. Primary aggregation: both visitors and three tasks inside each of ten decoders. Student-t 95%, df 9. Practical margin 25.

## Secondary results (cannot upgrade or replace the primary)

Student-only lookahead minus H=16: **83.622 [25.758, 141.485]**.  
Zero-only: **113.594 [42.433, 184.755]**. Both favor lookahead; neither can change the pooled label.

Estimand B, student minus zero, **includes 0** on both arms and cannot be inferred from A:

- H=16 student−zero: **38.862 [−12.099, 89.822]**
- Lookahead student−zero: **8.890 [−42.430, 60.209]**

Lookahead means: student **−713.555**; zero **−722.445**. Frozen H=16: student **−797.177**; zero **−836.038**.

Per-task return_gain (exploratory, ten decoder values):

- task0 (`pendulum_look_tf0`): **42.478 [27.090, 57.866]**
- task1 (`pendulum_look_tf1`): **196.809 [50.686, 342.932]**
- task2 (`pendulum_look_tf2`): **56.536 [−27.743, 140.815]** (includes 0)

Ten decoder pooled means: 157.6, 41.1, 116.2, 138.4, 109.1, 24.2, **−17.3**, 69.4, 257.4, 90.2. Decoder 6 is negative; the registered unit remains the ten-decoder mean.

First-action mismatch versus H=16: student **1.13 [0.42, 1.85]** steps; zero **1.50 [0.94, 2.06]**. Step-wise action disagreement is about 0.60. Executed one-step angular-velocity MAE stayed similar across arms (student H=16 **0.189**, lookahead **0.209**). This is not a one-step prediction pass.

## Integrity

Independent reconstruction of all 30 paired cells reproduced reward sums, shared candidate seeds, H=16 score argmax first actions, lookahead Q argmax first actions, the primary interval and the label. Official `--results-audit` passed. Frozen checkpoints before and after: 120 verified, 0 missing, 0 mismatched. Exhausted 3600-second ledger SHA256 unchanged. Development lookahead capture unchanged. No world-model, encoder, or previous-capture writes. Closed confirmation physics unused. Reserved amortized hash `d1fa621351d286cf` unused. Three-action forks: 0. Training updates: 0. Compute-matched control: 0. Retries: 0.

## Provenance, resources and tests

Branch `cursor/lookahead-transfer-confirmation-prep`. Preparation SHA **c464a962e80854882b0fbddef20af993849a8608**. One-run allocation SHA **29c4f9826f6d4073d80694d15277182674199224**.

- Config SHA256 `385285edca761d60c1759bf8ef951c2682794e7b3d6066e9223aad5236c9cae8`
- Protocol SHA256 `5c2e0d7300e497c65c0564990aa2a86ab4d08e79979c40d8ce7d2ea51735c942`
- Raw artifact SHA256 `226e649ea34b8b7ada752143e797d43853076863a76a123f8f88de6d75298019`
- Exhausted 3600-second ledger SHA256 `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`

One collection completed in **61.312 s** execute wall, **62.495 s** process including audit. Exactly **27,840** new real steps and **12,324,000** imagined transitions. Zero optimizer updates. Local CPU. No retry.

The transfer one-run remaining is 0. The exhausted 3,600-second standing session and prior one-runs were not modified. Further experiments are not authorized by this allocation.

## One next experiment

Do not retune candidates, horizon, reward weights, or the lookahead backup from this confirmation sample. The registered transfer question is closed on this Pendulum holdout.

The next distinct question is whether the **same frozen lookahead-versus-H=16 package** beats H=16 on a **different environment family**. That is cross-family replication, not another Pendulum physics draw and not learning-to-learn. Student-versus-zero remains a separate estimand and stays unestablished here. That proposal is not implemented and is not authorized here.
