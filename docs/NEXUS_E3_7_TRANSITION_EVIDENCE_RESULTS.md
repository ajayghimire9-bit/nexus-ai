# E3.7 — Genuine Transition Evidence Ablation: Results

## Outcome

**transition_evidence_not_established.** The complete valid run fails its predeclared screen in every pretrained model. Replacing schema-only coordinates with genuine source-transition summaries did not improve held-out advantage prediction over model means. Cached selection worsened in both family averages. No predictor/controller variant is promoted; no neural architecture, historical weights, catalogue or regularization changed.

Branch codex/e3-7-transition-evidence-ablation. Verified base ad8afce400adb12abb2d1bf4854741d02c7774f9; clean protocol/implementation execution commit **95c206d87aaa60696e1774e899fcebe10c74e253**. Protocol NEXUS_E3_7_TRANSITION_EVIDENCE_PROTOCOL.md, config configs/e3_7_transition_evidence.json. Implementation was committed before the E3.7 real-data fits.

## What changed

Reuse the existing AdvantagePredictor and fixed ridge1, feature_informativeness blocked-reset/permutation adapter, training_feedback_audit fold anchors/receipts and the SAME audit host. transition_evidence is only source preprocessing, not another learning/memory/planning stack. Existing describe_support has an opt-in require_fit flag that raises on failed diagnostic least squares; default historical behavior is unchanged. The installed historical advantage_features representation and all neural weights remain unchanged.

Each fitted predictor retains192 coordinates. Only three schema coordinates are replaced by mean absolute normalized state change, normalized linear-support residual MAE and action coverage. Read the original first32 support transitions from each of four pinned TRAIN arrays, preserve the source-family normalizer, and verify original support receipts. Packed original+new384 values are paired storage, not a384-parameter learner. No new interactions or normalizer fitting.

Source summary triples (normalized delta, linear residual, action coverage):
- Pendulum0:0.153030669,0.058499152,1.
- Pendulum1:0.144670651,0.043960895,1.
- Acrobot0:0.103576408,0.006550529,1.
- Acrobot1:0.175350950,0.022897854,1.

These are real observed-transition summaries, unlike E3.6's schema-only slots. They differ between models but are constant across all reset contexts within each model; action coverage is1 everywhere. Within-model varying columns and centered rank remain24/rank3 for Pendulum and48/rank6 for Acrobot in both original and transition representations. The additive feature layout supplies no observation×support interactions. The experiment therefore tests changed pooled-model conditioning, not new reset-specific evidence or demonstrated task identification.

## Data boundary, baselines and decision rule

Use only the pinned E3.4 training manifest's36 permitted training pairs, features, original support receipts and frozen normalizers. No E3.4 closed evaluation outcomes or prediction traces are parsed for fitting/scoring. Four original source TRAIN arrays are file-hash verified before/after access; typed32-row prefix hashes and exact normalizers are saved. No validation/bundle2/E2.17 source arrays or checkpoint files are loaded by the registered E3.7 run.

Nine reset-block folds each train32 pairs/eight per model and query4. Recompute means, both anchor feature blocks, residual targets and feature RMS from fit rows only. Original and transition variants share nineteen within-model training-feature maps per fold; labels and model means are unchanged and held-out features are never mixed into fitting. All360 coefficient sets and query estimates are frozen before scoring.

For every model require: >=5% MAE reduction versus model means; strictly lower MAE than original features; better MAE than>=18/19 transition permutations; and nonnegative cached-return gain versus means. All four models must satisfy the intersection. No change to thresholds after inspection. Permutation ranks are descriptive, not p-values. Shared fitting and only two pretrained models per family preclude treating reset folds or permutations as independent replications.

## Per-model held-out results

MAE below is residual-advantage MAE, equivalently total-advantage error after the same training-only prior:
- Pendulum0: model mean147.282206; original236.423636; transition239.842602. Transition worsens62.85% versus means; permutation wins1/19; cached-return gain−0.104935 versus means,0 versus original.
- Pendulum1: mean258.074190; original299.230786; transition298.565401. Worsens15.69% versus means; wins9/19. Return gain−35.410920 versus means,−18.557423 versus original. Slight MAE improvement over original does not imply better selection.
- Acrobot0: mean11.331733; original14.440597; transition17.438343. Worsens53.89%; wins7/19. Return gain+5.346101 versus means,−0.291095 versus original. Positive local selection can coexist with worse magnitude error.
- Acrobot1: mean20.889419; original22.212941; transition22.986243. Worsens10.04%; wins10/19. Return gain−6.408153 versus means,−1.799467 versus original.

Every model fails the5% mean-relative MAE and18/19 permutation conditions. Only Pendulum1 improves MAE against original, but loses selection return. No consistent improvement is established.

## Family summaries and limits

Average resets inside model, then two models inside family; never pool raw family units:
- Pendulum MAE mean202.678198 /original267.827211 /transition269.204002. Cached selected returns−356.130684 /−364.609900 /−373.888611. Transition-minus-means **−17.757927**, transition-minus-original **−9.278711**.
- Acrobot MAE16.110576 /18.326769 /20.212293. Returns−293.983034 /−293.468779 /−294.514060. Transition-minus-means **−0.531026**, transition-minus-original **−1.045281**.

Original estimates reproduce E3.6's full representation within abs1e−10/rel1e−12 (repository-only regression checks). This is consistency, not fresh confirmation. Raw reset cells, all permutation predictions, MAE/RMSE/sign/return/regret, per-model checks and variability are saved. Family RMSE is mean model RMSE. Regret reduction equals selected-return gain; sign and two-arm ranking accuracy are dependent. No confidence interval, transfer, general control, learning-to-learn or AGI claim.

The feedback bank remains small, reused source TRAINING data, with only four fixed source models. Failure of these three summaries with this additive ridge representation is not proof that transition evidence or nonlinear representations cannot help. Static support cannot uniquely explain within-model reset differences; conditional slopes or candidate-specific predictive evidence remain hypotheses. Do not start a larger neural architecture simply because the current screen fails.

## Provenance, integrity and actual resource use

Input SHA2565bc051a2effe1fb2c9220393881fe4a1f8ec77f08c28f9660d5d6cb8418c743a; config2486bde38aae2d2500d6cdcb5c7fffd70f3f8b374e52f36336b0c966e206d404; protocol e796195ef1ed25bc9b27a6deae5ff5b99027f119785c8472bda412a9fb848df2. Capture21d6fcb55eefaf75a4ce32722dfbdf9ee5e9fa16386f7b38cd754ebe200ceaeb; frozen folds5d0bf33436a5d8d04748e9a37221afe454aa4516431018ab12372c7b5c603a91. Source paths/complete NPZ hashes, typed support-prefix hashes, normalizers, exact code revision/file hashes and dependencies are saved.

Registered run:360 ridge fits,4 descriptor least-squares calls; wall **0.493147541s**, CPU0.491835s, within30s. Independent verification: **0.330873459s**,0 ridge fits and4 explicitly counted source-descriptor least-squares recomputations. It certifies all360 saved ridge solutions by normal equations(abs1e−6), replays predictions(abs1e−10/rel1e−12), reconstructs source features/receipts, validates complete grids/arithmetic and357 pre-existing JSON files. Those357 include356 prior research JSON plus the newly committed engineering-recovery record.

E3.7 run and independent audit each use **0 new environment steps,0 imagined transitions,0 neural inference/updates**. Existing32-row source prefixes are reused, not new interactions. Unique feedback36 pairs; each ridge fit sees32 unique rows/64 antisymmetric numerical rows. Nine overlapping folds and360 ridge fits are not360 pretrained models.

Combined E3.7 run/audit0.824021000s. Carried ledger after preflight recovery784.6290710430173 used; after E3.7 **785.453092043025 used /2814.546907956975 remaining**. No reset or extra grant. Local Python3.13.5/NumPy2.5.4 and OPENBLAS_NUM_THREADS/OMP_NUM_THREADS/VECLIB_MAXIMUM_THREADS all1. One execution, no retries.

## Preprotocol regression incident — not hidden scientific work

The initial broad engineering suite passed462 tests in10.44s, but six legacy benchmark tests wrote historical JSON paths. One residual benchmark also loaded existing learned models and ran inference. No simulator steps or model training occurred. Its forward and imagined-row counts were not metered and remain UNKNOWN; do not apply the E3.7 zero-inference claim to that invocation. It included older permitted source/development benchmark contexts, never E3.4 evaluation data; no outputs feed this study.

Preserved the six test-produced outputs in the34,694-byte artifacts/e3_7_regression_side_effects.tar.gz and recorded original/test-written hashes in e3_7_preflight_recovery.json. Restored exact original HEAD bytes; redirected seven legacy writer tests (including deterministic fit-clock metadata) to pytest temporary paths. Excluded the learned-residual inference benchmark from the final source-only command; its test assertion was not replaced by a fake-model claim. Conservatively charged the entire10.44-second invocation to the standing ledger. Recovery and isolation were committed before E3.7 execution.

After correction, **462 source-only tests passed in9.93s** before protocol execution, with no historical artifact diff. Focused prechecks89 passed in1.83s. Post-result repository-only tests replay saved ridge evidence without NPZ loading/learning, compare original predictions to E3.6 and verify that the primary screen accepts a perfect authored toy signal but rejects failure in just one model. Final relevant command/counts are in artifacts/e3_7_test_report.json. The suite is relevant regression coverage, not the entire historical test tree or a fresh scientific replication.

## One next scientific question

Final source-only relevant regression suite: **465 passed in10.11s**, with no historical artifact diff. The saved original-condition predictions reproduce E3.6 with maximum absolute difference0.0. No further experimental fitting followed the locked execution.

**Can a prespecified small observation×support interaction let the same lightweight learner predict model-dependent planner advantages?** Prepare a separately locked, fixed-budget comparison against model means and existing additive features, with within-model negative controls and explicit capacity accounting. Do not retune this failed variant, increase the world-model architecture, run control or treat a future positive reanalysis of this already inspected training bank as independent confirmation. No follow-up experiment is implemented or allocated in this branch.
