# E3.3 — Training-only blocked-reset feature sufficiency

Registered before fitting. Base: ded811d1f9ddaa2d907dd1a807fe06b174d9dbe9; branch codex/e3-3-training-feedback-audit. This follows the specific next proposal from E3.2, whose failed evaluation remains closed. E3.3 is an exploratory reanalysis of permitted TRAINING feedback, not new confirmation or model-family transfer.

## Question and alternatives

H-feature: the existing reset-conditioned features and ridge rule improve held-out training-reset strategy selection over per-model training means. Alternatives: means suffice; feature-conditioned prediction is unstable with eight fit pairs; preferences change across reset blocks. A failure cannot distinguish absent information from inadequate data or the particular model's limitations.

No architecture, feature search, regularization sweep, new controller, neural training, dynamics inference, environment construction, seed registration or new collection. Reuse generated_strategies.AdvantagePredictor, its existing ridge=1 antisymmetric solver and return_feedback selection semantics. The new module is an offline fold/scoring adapter, not a memory, proposer, meter or learning stack. H17 and E2.17 remain closed/blocked as before.

## Input boundary

The only parsed research input is e3_2_frozen_predictor.json, hash e84d55ce4b8f3bd6dbc4cda1edcbecfe411e808ed91c63a16504b52fb3453b83. Project only training_pairs and feature_rows into the computation. The twelve pairs are exactly Pendulum/Acrobot × model bundles0/1 × episode IDs0/1/2. Validate finite numeric fields, event receipts, identities and feature layout. Reject duplicates, missing models/episodes, booleans, numeric strings and evaluation episode IDs. Ignore stored all-training coefficients and shuffled-label models; never parse the E3.2 closed evaluation capture or prediction traces for fitting/scoring.

Original source observation normalization and support statistics were fixed independently of these reset-return labels; preserve them as cached feature coordinates. No local .pt/.npz files are needed. Hash-only preservation checks may read previous artifact bytes, including closed files, but never interpret their outcomes.

## Three locked folds and leakage prevention

Fold e holds out episode index e in all four model bundles. Eight unique training pairs fit each predictor; four query pairs are scored. All twelve contexts receive exactly one out-of-fold prediction. Folds overlap in training and are not independent experiments.

The saved 192 features are outer(task[12], candidate-minus-incumbent arm[16]), with task[0]=1. The last two task coordinates are training anchor means divided by100. Those saved means used all three reset blocks and MUST NOT be reused inside a fold. Recover the arm from the first16 coordinates; preserve the first ten rows, overwrite the final two rows with fold-only anchor means times that arm. This is mathematically equivalent to calling the existing advantage_features with fold-only means. Test equivalence at atol/rtol1e−12. Fit the existing RMS feature scaling only on the eight fold training rows. Never normalize using held-out return magnitudes or features.

True-label predictor and shuffled-pair-label predictor each fit once per fold (six fits total), with the latter's permutation from RNG(31+fold). Original ridge=1, no intercept or feature changes. Antisymmetric augmentation makes16 numerical rows/fit, not16 independent contexts. Anchor means remain legitimately revealed training information in both modes; shuffle is not total feedback removal.

Other selectors: model mean, family mean, global mean, always successor, always rank blend, and deterministic uniform by digest(('E3.3_uniform', family, bundle, episode)). Ties choose successor. Full feedback and identical held-out return tables for all selectors; no extra evaluator opportunity for a method. Persist all fold predictions/coefficients to a new exclusive-create file before scoring held-out labels. Separate prediction and scoring APIs; perturbing held-out outcomes must leave all that fold's predictions and coefficients unchanged.

## Metrics and prespecified screen

Primary contrast: quality-predictor minus model-mean selected return (equivalently model-mean regret minus predictor regret). Average three held-out resets within model, then two models within family, no pooling raw return units across families. Report model-specific gains and all baselines. Secondary: advantage MAE, sign accuracy, raw choices/returns/regret, train design ranks. Two-arm sign and ranking accuracy are dependent; regret reduction equals return gain.

Exploratory feature-signal screen requires in EACH family: mean return gain >=1; lower mean advantage MAE than model mean; positive return gain in both individual models. Otherwise label training_only_feature_signal_not_established. Passing only licenses a later proposal, not deployment, generalization, control success or learning-to-learn. With two existing models/family, no inferential confidence interval or p-value is claimed. Three folds, repeated states and numerical antisymmetric rows are not extra model replicates. Do not revise the screen after results.

## Provenance, resource and incomplete rules

One run under the human 2026-10-16 standing local grant/current continue request. Single-thread local CPU; maximum15 seconds inclusive of input/provenance checks and analysis; six ridge fits, zero real/imagined transitions, zero learned-model inference. Carry ledger588.722984459005 used /3011.277015540995 remaining; never reset. Allocation binds exact config/protocol hashes and input hash. Verify tracked implementation is clean and committed before fit. A one-run usage marker prevents retries.

Check a deadline before/after every fit/phase and use a process alarm where available. Persist partial/incomplete results on interruption or nonfinite/missing cells, never drop them. Preserve all historical artifact bytes. Save exact code/config/input/protocol hashes, dependency versions, raw folds, weights, finite complete metrics, CPU/wall time and session ledger. Results commit is separate. Offline --verify uses saved coefficients (zero fits) and checks fold-only scaling, independent ridge normal-equation residual <=1e−6, predictions <=1e−10 abs/1e−12 relative, anchor means, baseline choices, exact grid and arithmetic. An explicitly requested audit must fail if required input/artifacts are missing; checkpoint binaries are not required for this computation.

Focused command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest -o addopts='' -q tests/test_e3_3_training_feedback_audit.py.
After committing tested implementation and this protocol, execute scripts/run_e3_3_training_feedback_audit.py once with the same Python environment; --verify is an offline no-fit audit. No tuning on closed E3.2 evaluation or other historical control outcomes. Stop after the registered analysis and recommend one next evidence-based question.
