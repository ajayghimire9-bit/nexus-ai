# E3.6 — Within-Model Feature Informativeness Audit

## Scope, hypothesis and immutable starting evidence

Registered before real-data fitting on codex/e3-6-feature-informativeness, from verified local/GitHub b9aa1e2e2ad1815a41bafd7d8bbd9da067f9c3f2. Preserve unrelated untracked evolution1 adapter files. Human explicitly requested E3.6; standing2026-10-16 grant covers bounded local CPU training-feedback analysis. No simulator construction/steps, neural training/inference, checkpoint loading, imagined transitions, new physics/seeds, new strategies or reserved/closed evaluation access. H17 remains blocked and E2.17 consumed.

H-feature: at least one fixed existing feature group predicts held-out within-model residual strategy advantage better than the fold-training model mean, consistently across all four existing pretrained models. Competing explanations: the current representation has useful but obscured information; it contains no useful signal for this learner/data budget; small feedback bank or ridge bias hides available signal. A failed audit does NOT establish information-theoretic absence. No architecture, regularization, target definition or planner changes.

Input is ONLY artifacts/e3_4_predictor_b9.json, SHA2565bc051a2effe1fb2c9220393881fe4a1f8ec77f08c28f9660d5d6cb8418c743a, projecting training_pairs and feature_rows. Existing learned outputs are ignored. Exactly36 pairs: two families(Pendulum/Acrobot)×two pretrained bundles×nine training resets. Previously scored E3.4 evaluation capture/traces must not be parsed for fitting/scoring. Historical JSON may be byte-hashed for preservation. No PT/NPZ files needed. This is exploratory reuse of permitted TRAINING data, not untouched confirmation or new control evaluation.

## Source audit and precise feature groups

Reuse existing AdvantagePredictor, training_feedback_audit identity/receipt/anchor transforms, generated_strategies.advantage_features, planner_quality_diagnostic ridge=1/RMS and the SAME one-run audit host. feature_informativeness is a feature-slice/fold adapter, not another learner/proposer/memory/controller/meter. Executable config is configs/e3_6_feature_informativeness.json and is exactly validated against runtime settings.

Current192 features are outer(task12, arm16); task rows:0 intercept,1–6 tanh(source-normalized observation),7–9 support_stats[:3],10–11 revealed controller means/100. All groups retain row0 (same fixed strategy-descriptor/intercept nuisance), then:
- full: rows0–11,192 columns.
- observation: rows0–6,112 columns.
- support_schema: rows0,7,8,9,64 columns.
- anchor: rows0,10,11,48 columns.

IMPORTANT: describe_support's first three entries are observation dimension/16, action count/16 and episode length/16. advantage_features discards ALL actual transition statistics via [:3]. Therefore support_schema is NOT a transition-evidence predictor. Audit and report this representational absence; do not silently add new transition features or relabel schema as dynamics. Test that radically different support observations/actions/outcomes/rewards leave the existing features unchanged for fixed schema and current observation. Fixed rank-blend/successor descriptors do not switch with observation; verify their saved row0 is constant inside model. Source-only metadata check requires rows7–9 equal these exact schema multiples of row0.

Fold-specific training controller means replace BOTH anchor blocks. Extract groups without constructing new features. Row0, support-schema and anchor groups have no reset-specific information within model. Report within-model varying columns and centered design ranks; constant columns are not evidence about diverse histories or genuine transition statistics.

## Blocked-reset estimation and permutations

Nine folds hold reset index e out across all four models. Each fits32 rows/eight resets per model and predicts4 rows; all36 receive one out-of-fold prediction. Fit the SAME anchored residual rule as E3.5: d=rank_blend return−successor return; mu=model-specific mean d from eight TRAINING resets only; target=d−mu; estimate=mu+f(x). Rebuild anchors and fit RMS inside each fold. No withheld outcomes in means, targets, feature scaling, permutation generation or fitting. Tie chooses successor. Different feature dimensions imply different effective capacity despite common ridge=1; disclose rather than tune.

For EACH group fit the original feature order plus19 within-model training-feature permutations, IDs0–18. For each fold e/permutation p/model ordinal k (Pendulum0, Pendulum1, Acrobot0, Acrobot1), RNG seed613000+e*10000+p*10+k permutes the eight TRAINING row positions for that model. All four groups share each mapping. Keep labels, model memberships and model means UNCHANGED. Shuffle whole feature rows together, preserving joint distributions/correlations and within-model feature multisets. Never permute held-out rows into fit; query retains its actual feature vector. No across-family label shuffle. No seed selection or repeated runs.

80 predictors/fold=(1+19)*4 groups;720 fits total. Same32 fit rows,64 antisymmetric numerical rows/fit. Feature slices and repeated fits do not add real feedback. Model-mean-only is a zero-correction baseline, not a separately trained predictor. Full unpermuted arithmetic should agree with E3.5 residual estimates within absolute1e−10/relative1e−12. That replay is not independent evidence.

Freeze coefficients/scales, training targets, fold-only feature matrices, train/query IDs, permutation maps and all pre-scoring estimates in an exclusive-create artifact BEFORE scoring labels. Keep optimization and scoring APIs separate.

## Metrics, statistical unit and locked practical screen

Primary per-model metric: held-out residual advantage MAE; equivalently absolute error of total advantage after adding the same mu. Compare each group against model mean. Average nine query resets inside each pretrained model; report every model and each family separately. Four models, only TWO per family; neither folds nor permutations nor augmented rows are new model replications. No pooled raw-family return scale, confidence interval or formal p-value from this small reused source suite.

For each group require ALL four models:
1. At least5% reduction in MAE versus model means.
2. Its unpermuted MAE is STRICTLY below at least18 of19 paired within-model permutation MAEs.

Zero baseline MAE (<=1e−12) makes a relative-improvement screen unavailable/failing, not a division trick. A group passes only if every model satisfies both conditions; overall exploratory label feature_signal_screen_passed if any registered group passes, otherwise feature_signal_not_established. Nineteen permutation comparisons are descriptive ranks, NOT significance tests. Four feature groups are reported together; no winning-group promotion, multiplicity-adjusted claim or posthoc retuning. A pass motivates independent study only.

Secondary: raw per-reset predictions/residual truths, selected cached returns/regret, sign accuracy, RMSE, per-family summaries, permutation distribution and feature variability. Correct choice frequency is not independent of two-arm sign accuracy; regret reduction equals cached-return gain. Prediction accuracy is distinct from control utility; no newly executed return or transfer claim. Report negative/neutral groups, including numerically duplicate baselines. Full and subset performance comparisons do not isolate pure information differences because ridge capacity differs.

## Budget, provenance and invalid/incomplete handling

Single local CPU run,30-second cap,720 reserved/completed ridge fits,0 real/imagined/neural execution; estimated a few seconds, not measured until execution. Thread environment OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=VECLIB_MAXIMUM_THREADS=1. Carry previous ledger773.363640293 used/2826.636359707 remaining; never reset. Committed allocation must cite standing grant and this request, exact config/protocol/prior-validation hashes. Protocol and tested implementation must be committed with clean tracked execution tree before fitting. No automatic retries.

One-run exclusive markers, pre/post-fit deadline guards and process alarm reuse existing host. Record attempts/partial folds on failure. Missing model/fold/reset/method/permutation/coefficient/required metric or numeric bool/string/NaN/infinity means incomplete/invalid, not scientific failure. Expected sets derive from locked config/runtime constants, never produced rows. Preserve historical artifacts and code SHA/dependency/source hashes. A separate zero-fit verifier reconstructs fold-only inputs/targets, certifies ridge normal equations(abs1e−6), verifies feature maps and coefficient replay(abs1e−10,rel1e−12), arithmetic, historical hashes and feature variability. Save actual runtime, CPU and session ledger. Do not load historical models just to claim integrity here.

Tests before execution: synthetic informative/no-signal mappings, support-outcome insensitivity, exact feature slices, within-model maps/unchanged labels, no query-label leakage, training-only anchors/RMS, reproducibility, coefficient replay with fitting forbidden, missing grids/nonfinite rejection, cap/one-run/config guards and original audit regressions. After execution add repository-only saved-result replay and input-boundary tests without new real-data fitting.

Run same host: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps with thread environment above, python3 scripts/run_e3_3_training_feedback_audit.py --features; then --features --verify. Commit results separately; push branch, never merge main.

## Decision boundary

If a group passes, prepare a separately registered test of that fixed representation/learner on fresh permitted training feedback, not old closed evaluations. If none passes, report no demonstrated signal under this exact representation/learner/sample budget; the source-code finding of absent transition evidence justifies ONE next proposed minimal representation experiment adding existing genuine transition statistics in a separately registered comparison. Do not implement that change here, search regularization or generate more strategies. Do not infer global feature impossibility, learning-to-learn, generalized control improvement or AGI.
