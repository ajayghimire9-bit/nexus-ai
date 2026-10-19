# E3.4 — Fresh feedback coverage with a fixed quality predictor

Registered before any new source collection. Branch codex/e3-4-feedback-coverage from verified local/GitHub 2d12f5784f0020814ce93b6aa14c506ba9d23b0c. This executes the E3.3 next proposal under the standing 2026-10-16 local grant and current continue instruction. Earlier E3.2/E3.3 findings and all closed evaluation sets remain unchanged. No new physics or neural training.

## Hypothesis and alternatives

H-coverage: more paired training returns improve the existing candidate-conditioned ridge selector relative to equally informed model means on fresh resets. Competing explanations: means suffice; limited reset-conditioned features are inadequate; preferences are unstable across resets. A negative result does not identify which explanation causes failure. No feature, regularization, planner or architecture search is permitted.

Reuse generated_strategies.AdvantagePredictor/advantage_features (192 coefficients, ridge=1, training-only RMS), return_feedback.FrozenReturnSelector, original source normalization/support, full_policy_source collection, existing controllers and ReservationLedger. New feedback_coverage code only coordinates three instances of the same selector and paired analysis. No parallel memory, proposer, learner or meter stack.

## Fixed models and controller rules

Same four E2.9 frozen residual MLP(64,64) files: Pendulum/Acrobot bundles0/1. Before inference verify checkpoint bytes against evolution2_fit_clock_run.json, all eight source NPZ hashes, and parameter/normalizer fingerprints against the original full-policy capture. Do not retrain or replace files. The old fit manifest lacks an original execution SHA; retain that provenance limitation.

Same successor_anchor and rank_blend controllers, original candidate generation/action decoding/reward/rollout rules and horizons16. These SOURCE catalogue controllers are not the historical16×16 controller: the unchanged1536-transition cap gives successor31 candidate sequences per root; rank blend splits the cap into768/768, giving48 flat sequences and15 per successor root. Each uses1491 imagined rows per live decision; neural forward counts differ (51 versus67). This corrects earlier source-study prose referring to16 candidates; old protocols/results are preserved verbatim and no controller is modified. Every comparison uses paired environment reset and planner randomness; no online learner updates during evaluation. These family-default source worlds are development material, not unfamiliar physics confirmation.

## Exact executable data registration

configs/e3_4_feedback_coverage.json is validated against the host's exact coverage_feedback_v1 profile. Family order Pendulum, Acrobot. Episodes0–8 are TRAINING;9–12 are EVALUATION. Reset=2113000000+family_index*10000+bundle*100+episode. Planner=2114000000+family_index*10000+bundle*4000+episode*200+tick. Stride4000 prevents overlap for13 episodes. Audit10452 unique seed IDs against reachable historical JSON integer seed metadata, original source episode seeds and conservative H17 ranges. Do not infer coverage of unavailable external runs. No outcome-based seed or physics selection.

Collect nine paired training resets per model:72 controller episodes/14400 real steps. All four models' training completes before any evaluation environment. Fit snapshots from nested episodes[0,3),[0,6),[0,9), respectively12/24/36 pair labels. Use only each snapshot's prefix for anchor means, labels and feature scaling. Recompute its source statistics using the same original source rows; unique source observations4096 and support128 reused, no extra collection. Account for12288 normalization rows/384 support rows processed across three snapshots, not extra physical interactions.

Each snapshot fits true labels and shuffled paired labels once using the existing RNG31 permutation at its own prefix length: six ridge fits total,144 paired observations processed including both modes, numerical antisymmetric rows24/48/72 per fit. No epoch or checkpoint selection. The shuffled-label ablation retains legitimate prefix anchor means; it is not all-feedback removal. The original source observations normalize features; no target/query outcomes are used.

Save all three model manifests with labels/features/coefficients/hashes before evaluation begins. At each fresh evaluation reset persist predictions/choices from all three snapshots before either controller executes its first step. No predictor updates after that point. Four fresh paired evaluation resets per model:32 controller episodes/6400 steps. Both actual controllers are collected once; all budgets and selector baselines reuse those same returns, not additional simulated opportunities. The three prefix budgets are not independent physical experiments.

## Baselines, metrics and locked decisions

For each budget compare quality predictor, shuffled-pair-label predictor, model mean, family mean, global mean, always successor, always rank blend and the same digest-based uniform rule from E3.2 (now on fresh episode IDs). Ties choose successor. All adaptive comparisons receive exactly that prefix's legitimate training feedback. Do not fit on any old closed control/evaluation capture or E3.1 future-trajectory error.

Primary estimate: budget9 quality-predictor minus budget9 model-mean evaluation return. Average four resets inside model, then the two models within family. No pooling raw units across families. Registered primary point screen requires >=1 return point in EACH family and positive gain in BOTH models in each family. Separately report the conservative broad-baseline screen (budget9 predictor >=1 better than every named alternative and positive versus both model means). A primary pass without broad-baseline superiority is not general best-method success. No uncertainty/significance claim from n=2 existing models/family. Tasks, budgets, episodes or augmented rows are not extra model replications.

Secondary paired coverage effects: budget9 minus budget3 predictor return and (predictor-minus-model-mean at9) minus the same gap at3. Budget6 is a fixed middle learning-curve diagnostic. Report per-budget return, advantage MAE, sign accuracy, regret, per-model and per-reset results against every baseline. Do not choose the best budget using evaluation returns. Magnitude MAE is diagnostic, not a new primary threshold; E3.3's failed intersection screen remains closed. More training can improve selection without establishing better magnitude calibration; neither establishes autonomous discovery or learning-to-learn. Regret reduction equals return gain and two-arm ranking equals sign accuracy: dependent evidence.

## Resource and completeness rules

One run only, local single-thread CPU;240s hard collection/fit/analysis cap,20800 real interactions,31948800 imagined-transition upper bound. Nominal actual rows31012800 and forwards1227200. Estimated151s from E3.2, not a runtime guarantee. Carry ledger589.1500925009981 used /3010.849907499002 remaining; no budget reset or expired grant reuse. Allocation binds exact config/protocol/parent hashes. Commit tested implementation, this protocol and allocation before any collection.

Every physical model/environment operation remains reserved/settled by the original ledger. Losslessly rotate resource JSONL gzip after4000 decisions; full execution must have six ordered chunks (4000 each, last800), individually hashed and all required by the offline audit. No event sampling or omitted failed work. This is journal storage only, not a new meter or planner. Refuse pre-existing usage/results/manifests/journal parts; no retry.

Missing episodes/models/budgets/methods, nonfinite fields, wrong pairing/seeds, changed checkpoints/history, altered coefficients or cap interruption means incomplete/invalid, not a scientific negative. Preserve partial raw episodes, journals and any completed manifests; never reduce seeds or evaluation counts. Stop after the one registered study; no hyperparameter modification on these returns. Save exact source revision, code/config/data/checkpoint hashes, dependencies, real/imagined/model-call counts, CPU/wall and ledger. Offline audit adds measured time to the carried ledger and performs no new inference or fitting.

## Commands and tests

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest -o addopts='' -q tests/test_e3_4_feedback_coverage.py plus existing relevant regression tests. Test prefix exclusion and perturbation invariance, frozen manifests/pre-outcome decisions, strict budget/grid rejection, fresh seed disjointness, lossless journal rotation/tamper rejection, unchanged old-profile arithmetic, and source-only deterministic replay.

After committing the tested protocol: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_e3_2_return_feedback.py --coverage once; then --coverage --audit once for full checkpoint/source/journal/coefficient/selection replay. Keep local model binaries outside Git; publish all research JSON, predictions and journal parts. Commit results separately and push this branch, never main. Report negative/inconclusive outcomes and recommend one next question; no automatic architecture expansion.
