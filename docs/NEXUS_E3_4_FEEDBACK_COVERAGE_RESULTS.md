# E3.4 — More return feedback does not establish reliable selection

Complete, valid source-development execution. **Both the registered primary point screen and the broad-baseline screen failed.** Increasing training feedback improves Acrobot selection in this finite comparison but does not fix Pendulum. Do not select the middle budget after observing these results or extend collection to force a positive outcome.

Branch `codex/e3-4-feedback-coverage`; actual starting local/GitHub revision `2d12f5784f0020814ce93b6aa14c506ba9d23b0c`. Protocol/configuration/allocation, tested implementation and exact seed schedule were committed before collection at **ea9a9a8a584c8b93fd9109686123d46e65427d0a**. The existing selector, ridge, generated strategies, source environment wrappers and reservation ledger were reused. No new learner, memory, proposer or controller stack was introduced.

## Primary result: nine training reset pairs per model

Average four evaluation reset pairs inside each frozen model, then two models inside each family. No pooled raw return across families, no episodes counted as independent model replications.

- Pendulum predictor −286.140 versus model mean −174.198: **−111.942 return points**. Model-specific differences: −94.941 and −128.943. Model means select the better controller on all eight evaluation contexts; the predictor selects the worse on all eight. Mean predictor/model-mean in-set regret:111.942/0.000.
- Acrobot predictor −293.561 versus model mean −297.059: **+3.498 points**. Model-specific differences: −0.090 and +7.086. This fails the required positive gain in both models. Predictor/model-mean regret:3.648/7.146.

Thus Pendulum fails the >=1-point family and per-model criteria; Acrobot passes the family threshold but fails the both-model criterion. The broad-baseline screen also fails: Pendulum loses to every named alternative; Acrobot beats the deterministic uniform rule by only0.251, below1. These are point-estimate screens, not statistical significance or general control improvement. There are two existing independently trained source models/family and no new model replications or unfamiliar physics. No inferential interval was preregistered for this n=2 development study.

## Fixed learning curve, not posthoc checkpoint selection

On the SAME four fresh evaluation reset pairs/model, predictor-minus-equally-informed model mean at budgets3/6/9:

- Pendulum: **−47.471 / −0.743 / −111.942**. Predictor returns −286.140/−239.413/−286.140; model-mean returns −238.670/−238.670/−174.198.
- Acrobot: **−1.666 / +3.498 / +3.498**. Predictor returns −298.725/−293.561/−293.561; model mean stays −297.059.

Nine versus three feedback pairs change predictor return by0.000 on Pendulum and+5.164 on Acrobot. Relative advantage over the model-mean baseline changes by−64.471 and+5.164, respectively. Pendulum's mean baseline improves with more feedback, while the contextual selector does not. Budget6's better Pendulum point estimate is a secondary diagnostic; budget9 remains primary. Budget9 does not add Acrobot return over6. These nested comparisons share outcomes and are not independent experiments.

Advantage MAE (predictor/model mean), budgets3/6/9: Pendulum588.321/229.935,173.068/161.667,204.524/107.973; Acrobot33.068/17.084,15.650/16.355,15.002/15.523. Nine-budget sign accuracy: Pendulum0/8 versus8/8; Acrobot5/8 versus3/8. Lower magnitude error and better choices remain distinct. Choosing a stronger baseline after seeing outcomes is not a new confirmed method; every registered baseline is reported below and in raw metrics.

## Every nine-budget baseline

Pendulum predictor-minus-baseline: shuffled labels−61.602; family mean−47.471; global mean−47.471; always successor−64.471; always rank blend−47.471; deterministic uniform−33.984. Primary model-mean difference−111.942.

Acrobot predictor-minus-baseline: shuffled labels+9.884; family mean+3.198; global mean+4.797; always successor+3.198; always rank blend+4.797; deterministic uniform+0.251. Primary model-mean difference+3.498.

All per-budget/per-model/per-reset forecasts, choices, realized returns, sign correctness and regret are in coverage_analysis. The shuffled-label mode retains legitimate prefix anchor means; it is not total feedback removal. Uniform uses one fixed digest rule, not a replicated random-selector population. Two-arm ranking/sign accuracy are dependent, and regret reduction equals selected-return gain. The host's pooled13-episode fixed-policy summary is incidental, not the primary analysis.

## Interpretation and boundaries

More paired feedback alone did not establish reliable contextual selection under this representation/ridge rule. It helps Acrobot on this sample and strengthens a simple model-mean baseline on Pendulum. It does not prove that features contain no useful information, that more data can never help, or that a larger model is required. Sparse-data instability and extrapolation remain possible explanations; this study does not isolate their cause.

All training prefixes were fresh, nested and isolated. Anchor means and feature scaling were recomputed using only each prefix. All six ridge fits and three immutable manifests completed before any evaluation environment. All48 budget-specific choices were persisted before outcomes; both actual controller returns were collected once per reset and reused by eight selectors and all three budgets. No old closed return labels, confirmation outcomes or future-trajectory model errors entered fitting. Historical seed/checkpoint metadata was inspected for exclusion/provenance only. This is full-feedback supervised selector development, not online bandit efficiency, strategy invention or learning-to-learn.

Source inspection corrected a documentation error BEFORE execution: these catalogue controllers use the unchanged1536 imagined-transition budget, not the historical16×16 controller. Successor has31 sequences/root; rank blend has48 flat sequences and15/root for its successor component. Both horizons are16, both use1491 imagined rows/decision, but forward counts differ51/67. Earlier protocols/results are preserved verbatim. No planning rule or candidate budget was changed.

## Integrity, resources and reproduction

All104 complete200-step episodes finished:14400 training interactions and6400 evaluation interactions, **20800 total**. Imagined transitions **31012800**; network forwards/model calls **1227200**. Each actual controller consumed10400 real steps and15506400 imagined transitions; successor530400 forwards, rank blend696800. Upper imagined cap31948800; wall cap240s.

Measured pipeline: **148.174886s wall /148.140279s CPU**, within the cap. Offline complete checkpoint/source/journal/coefficient audit: **35.543887s**, zero new real/imagined transitions, learned inference or ridge fits. Carried ledger **772.868865293001 used /2827.131134706999 remaining**, from589.150092500998 before execution. Tests are recorded separately from experiment execution.

Six ridge fits; unique physical training pairs36. Prefix observations processed per mode12+24+36=72 (144 across both modes), with24/48/72 antisymmetric numerical rows per fit; these are not extra independent model replicates. Unique cached original-source normalization observations4096/support transitions128, with12288/384 rows processed across snapshots and zero extra collection.

Audit passed:20800 decision journals,2537600 hash-chained events, all six ordered lossless journal chunks, four unchanged checkpoint/parameter/normalizer fingerprints, eight source-array hashes,48 pre-outcome choices and six prefix coefficient models. Maximum published-versus-environment reward difference4.32e−7. All339 previous JSON artifacts remained byte-identical. Chunked storage preserves every event; it does not reduce model compute or environment cost. The six compressed chunks total173621948 bytes and are individually hashed in the capture. Original binaries/NPZs were not added to Git; explicit audit fails if any required checkpoint/source/journal file is absent or has a wrong hash. Repository-only tests need no model binaries. E2.9's inherited missing original fit execution SHA remains a limitation.

Capture SHA256 **23aeeb335363ec420bd5a162a102fe7897daba77ce2c5dd285f20e33fe31a9bc**. Configuration, allocation, checkpoint/source-array, manifest, prediction, journal-part and execution-code hashes are in artifacts/e3_4_feedback_coverage.json. Six fits are verified by prefix labels/scaling and the ridge normal equations without refitting. This was one locked run, no retry or post-outcome hyperparameter change.

Execution: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_e3_2_return_feedback.py --coverage`; verification adds `--audit`. Dependencies and CPU-thread count are captured. Before collection350 relevant regressions passed in7.24s, including20 new focused tests; final **353 passed in7.98s**, including repository-only saved-prefix, journal-hash and result reproduction checks. Exact commands are in e3_4_test_report.json. This is a relevant regression selection, not the entire historical repository suite.

## One next experiment

A separately registered SOURCE-TRAINING-ONLY blocked-reset audit of a baseline-anchored residual advantage prediction: keep the existing ridge and features, predict deviations from fold-training model means, and add that known baseline back for selection. Compare direct ridge and model means under identical held-out training resets, recomputing all anchor means/scaling without withheld labels. Use only the36 new TRAINING pairs; keep all16 E3.4 evaluation contexts closed. No hyperparameter search, neural fitting, environment or imagined transitions. Proposed15s CPU cap. This tests a minimal way to retain a strong learned prior before paying for more collection; it does not guarantee that residual predictions will be safer. Not allocated, implemented or executed here.

No main merge, frozen-checkpoint retraining, H17 execution, E2.17 grant reuse, unfamiliar-physics confirmation, autonomous-discovery success or AGI claim.
