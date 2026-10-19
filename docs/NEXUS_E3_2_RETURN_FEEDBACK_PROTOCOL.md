# E3.2 — Fresh full-return feedback predictor

Status: registered before collection. Starting revision 6213c04cf1bfde47c76636f614e5747589fea663.

Question: can the existing AdvantagePredictor select between two fixed planners on new resets better than simple means of fresh training returns? Competing explanations are useful observation-conditioned quality inference, model-specific mean preference being sufficient, and insufficient training coverage. This is supervised full-feedback source development, not autonomous discovery, unseen-physics confirmation or learning-to-learn.

Reuse: `generated_strategies.AdvantagePredictor` and `advantage_features`, FamilyNormalizer, cached source support, the existing full_policy_source metered collector and ReservationLedger. No planner, memory, dynamics or proposer stack is replaced. No historical return or E3.1 future-trajectory error enters fitting or features.

## Locked data and controllers

Four existing E2.9 frozen residual MLP (64,64) files: Pendulum and Acrobot bundles 0/1. Verify file hashes from the original fit manifest and fingerprints against the original full-policy capture before use. Verify all eight original source NPZ hashes. All network weights remain frozen. The original fit manifest lacks an execution SHA; that inherited provenance limitation remains.

Both controllers are unchanged: successor_anchor and rank_blend. H=16, 3 actions, 16 candidate sequences, published rewards, 200-step episodes; no tuning or online adaptation. Real interactions include all training and evaluation steps.

Executable source of truth: configs/e3_2_return_feedback.json, validated against the host's exact return_feedback_v1 profile. Reset seeds: 2111000000 + family_index*10000 + bundle*100 + episode. Planner seeds: 2112000000 + family_index*10000 + bundle*2000 + episode*200 + tick. Family order is Pendulum, Acrobot. The 2000 bundle stride avoids overlapping seven-episode planner streams. Check all 5628 seed IDs against current historical artifact metadata, original source episode seeds and conservative H17 exclusions. This cannot attest unavailable external runs.

Training episodes 0,1,2: 12 paired contexts, 24 controller episodes, 4800 steps. All four models' training collection finishes before either predictor is fitted. Evaluation episodes 3,4,5,6: 16 paired contexts, 32 controller episodes, 6400 steps. These are fresh resets on known source physics; source bundles, not episodes, are model replication units (two per family). Do not pool raw return units across families.

## Features, fitting and immutable decisions

Use the existing 192-dimensional candidate-minus-incumbent descriptor features with reset observation, source-only normalized observation/support statistics, fixed planner descriptors, and fresh training anchor means divided by 100. Normalizers use 4096 original source-training observations; support features reuse 32 original rows/model (128 unique). No new support collection. Features cannot read evaluation rewards, visited trajectories, model-error diagnostics or closed outcomes.

Fit the existing ridge=1 AdvantagePredictor once on 12 raw-return differences; its antisymmetric augmentation yields 24 rows, not 24 independent contexts. A second predictor shuffles paired labels deterministically using RNG31. This ablation retains legitimate training anchor means in the features, so it is not full feedback removal. No feature/hyperparameter search.

Comparisons: quality predictor, shuffled-pair-label predictor, model-specific mean, family mean, global mean, always successor, always rank blend, deterministic uniform choice. Ties choose successor. All receive the same full training feedback. Save coefficients, normalization/support hashes, training rows and learned-state hash before the first evaluation environment. Record each choice/feature hash and completed-step count before the first evaluation step for that reset. Never update the predictor during evaluation. Evaluate both controllers on paired resets/planner streams, then reuse that table for all selectors; cached selector returns are not extra physical episodes.

## Outcomes and decision rules

Primary: mean evaluation return difference, quality predictor minus model mean, averaging four resets within model and then two models within family. Report every baseline and per-model result. Conservative advancement screen additionally requires predictor-minus-every-other-named-baseline >=1 return point in EACH family, and positive predictor-minus-model-mean in both individual models. Otherwise label screen failed, or incomplete/invalid if integrity fails. No significance or generalization claim from n=2/family. No automatic rerun or retuning.

Secondary: raw advantage absolute error, sign accuracy, selection regret and reset-level choices. Two-arm ranking accuracy and advantage-sign accuracy are the same evidence; regret reduction equals selected-return gain and is not independent confirmation. The host's pooled seven-episode fixed-controller summary is incidental, not the primary selection analysis.

## Resource and failure rules

One run, local single-thread CPU; hard 180-second pipeline cap, 11200 real interactions, 17203200 imagined-transition upper bound. Actual planned model rows are 16699200, forwards 660800 (51/67 per decision); support/preprocessing and two ridge fits are separately logged. Continuous metered execution includes training, fitting and evaluation; analysis time is included. Remaining carried session budget: 3111.3707987489893 seconds (488.6292012510106 used). No expired grant reuse. Historical checkpoint training is not repeated.

Missing episode/model/method, nonfinite metric, changed checkpoint/history, unpaired reset, altered coefficients or reward-accounting failure makes execution incomplete/invalid, never a scientific negative. Persist partial raw results and consumed usage marker; no automatic retry. Preserve all historical JSON and user files. Large compressed per-call resource journal is separate from the result capture.

Commands: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest -q tests/test_e3_2_return_feedback.py` then commit implementation, protocol, exact allocation and tests. Execute `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_e3_2_return_feedback.py` once; audit with `--audit` (zero new steps, inference or ridge fitting). Save code/config/data/checkpoint hashes, immutable predictions, dependencies, ledger and both positive and negative outcomes. Results are committed separately.
