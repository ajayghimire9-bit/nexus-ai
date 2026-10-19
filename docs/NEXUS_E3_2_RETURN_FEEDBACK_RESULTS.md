# E3.2 — Fresh return-feedback predictor results

Completed, valid development execution; registered advancement screen **failed** in both families. This is a negative result for the existing feature/ridge configuration with twelve fresh paired training contexts. It is not a disproof of strategy-quality learning.

Branch: `codex/e3-2-return-feedback-predictor`. Actual starting revision: `6213c04cf1bfde47c76636f614e5747589fea663`. Protocol and implementation execution revision: `6381882b42e01860bf9779d905bed2017e854345`, committed before any collection. Locked protocol: `NEXUS_E3_2_RETURN_FEEDBACK_PROTOCOL.md`. Configuration/allocation and all source/code hashes are recorded in `artifacts/e3_2_return_feedback.json`. No post-outcome implementation or hyperparameter revision was used to produce this capture.

## Primary result

Evaluation means average four fresh resets within each frozen source model, then two models within family. Returns from different families are not pooled.

- Pendulum: predictor −477.257; model mean −445.344; **difference −31.912**. Per-model differences are 0.000 and −63.824.
- Acrobot: predictor −286.823; model mean −287.140; **difference +0.317**. Per-model differences are −1.919 and +2.553.

Both fail the registered practical screen: at least +1 against every named baseline in both families, with positive gain against model mean in each model. This is a completed scientific negative, not an incomplete run. There are only two existing pretrained models per family, no new independent models; no inferential interval or generalization claim is made. The four evaluation resets and three training resets are not extra pretrained-model replications.

## Every baseline

Pendulum predictor-minus-baseline: shuffled pair labels +19.226; family mean −133.384; global mean −133.384; always successor +69.722; always rank blend −133.384; deterministic uniform +85.909. Model mean is the primary −31.912 comparison above.

Acrobot predictor-minus-baseline: shuffled pair labels +1.205; family mean +0.231; global mean +5.330; always successor +0.231; always rank blend +5.330; deterministic uniform −0.953. Model mean is the primary +0.317 comparison above.

The predictor beat its shuffled-label ablation in both families, but did not outperform the strongest simple baseline. Shuffling retained the same legitimate training-anchor means in features, so this ablation is not total feedback removal. One deterministic uniform trajectory is not an estimate over random-policy seeds.

Advantage MAE: predictor/model mean 474.861/332.650 on Pendulum and 33.448/20.904 on Acrobot. Sign accuracy is 0.625/0.750 and 0.500/0.625 respectively. Mean selection regret is 200.222/168.310 and 7.824/8.141 respectively. Two-arm sign and ranking accuracy are mathematically dependent. Regret reduction equals selected-return gain and is not independent supporting evidence.

## What the data distinguish

Fresh full-episode outcomes discriminate these controllers, unlike the saturated earlier neutral-tail proxy. This does not make the current quality predictor reliable. Pendulum model1's training mean rank-minus-successor advantage is −44.919, while its evaluation mean is +202.944: a descriptive preference reversal across small fresh reset blocks. The reset-conditioned predictor still loses 63.824 to the model-mean selector on that model. This suggests checking feature informativeness and small-sample stability before adding capacity; it does not establish their causal role.

Only initial observations, original source-support statistics, fixed planner descriptors and newly revealed training anchor means entered fitting. Neither closed control returns nor E3.1 future-trajectory prediction errors were features or labels. Evaluation choices were recorded before the first real step for each reset, not chosen retrospectively. Both controller trajectories were collected to obtain full-feedback paired tables; all eight selectors reuse that same table. This is not a bandit interaction-efficiency or autonomous-discovery experiment.

## Integrity, costs and reproducibility

All 56 planned 200-step episodes completed: 4800 training and 6400 evaluation interactions, **11200 real steps total**. Completed imagined transitions: **16699200**; network forwards: **660800**. Both controllers use 1491 imagined rows/decision, but successor uses 51 forwards and rank blend 67. Equal imagined rows are not equal call counts. There were two ridge fits, 192 coefficients each, twelve unique training pairs with 24 antisymmetric rows per fit. Cached original source support: 128 unique rows; normalizer inputs: 4096 source-training observations. No neural or world-model training.

Pipeline wall time 81.445068s (180s cap), CPU time 81.387811s, including 0.005492s predictor preparation/fitting. Offline verification took 18.648715s with zero new interactions, learned inference or ridge fits. Carried ledger: 488.629201251 before execution; **588.722984459 used / 3011.277015541 remaining** after audit. Tests are separately reported, not silently added as scientific environment execution.

The offline audit verified 11200 decision journals and 1366400 hash-chained events, all four checkpoint file/frozen-state fingerprints, eight source-array hashes, all sixteen immutable pre-outcome selections and unchanged coefficients. Maximum published-versus-environment reward discrepancy: 4.31e−7. All 329 prior JSON artifacts remained byte-identical. Explicit checkpoint verification requires local `.pt`/`.npz` files; their documented paths/hashes are in the capture and they were not retrained or newly added to Git. The inherited E2.9 fit manifest lacks an original execution SHA.

Capture SHA256: `0ee3a3191ffde980311e9041ea34e8ec2ce910a5cf0ef7275bac091800e24b1d`.
Frozen predictor manifest SHA256: `e84d55ce4b8f3bd6dbc4cda1edcbecfe411e808ed91c63a16504b52fb3453b83`.
Pre-outcome predictions SHA256: `5fc18d1e4a6f6dfd498d665613e6b6e83ceba6523d1e16841c3bb57e38dab349`.
The separate compressed resource journal is 93392649 bytes; its hash is in the capture. It is required for full resource reconciliation. Repository-only regression tests do not require local checkpoints; explicit `--audit` fails if required files are absent or wrong.

Dependencies: Python3.13.5, NumPy2.5.4, Torch2.14.1, Gymnasium1.4.0; local single-thread CPU. Exact commands are in the protocol and `artifacts/e3_2_test_report.json`. Pre-execution focused/relevant suite: 128 passed in2.59s. Expanded post-execution source regression suite: 294 passed in5.00s before adding repository-only result checks; final **297 passed in5.04s**. This was the relevant source regression selection, not the entire historical repository suite.

## One next experiment

A separately registered, source-only leave-one-training-reset-block-out audit of this same frozen feature/ridge rule versus model means. Use only the twelve legitimate TRAINING feedback pairs; keep all sixteen just-completed evaluation contexts closed. Three folds hold out each training episode index across models, refit fixed ridge=1 on the remaining pairs, and compare paired held-out selection regret/advantage error, reporting model-level results without treating folds as independent models. No feature or hyperparameter search, simulator steps, learned-model inference or checkpoint changes. Proposed cap15s CPU, zero real/imagined transitions. This tests whether the existing observation-conditioned representation adds usable signal even within training feedback before paying for more collection. Not executed here.

No unseen-physics confirmation, historical experiment rerun, H17 execution, main merge, learning-to-learn or AGI claim.
