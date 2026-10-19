# E3.7 — Genuine Transition Evidence at Fixed Predictor Size

## Registration and question

Branch codex/e3-7-transition-evidence-ablation, verified local/GitHub base ad8afce400adb12abb2d1bf4854741d02c7774f9. This new protocol is committed with tested implementation before fitting to real return feedback. Human explicitly authorized continuing evidence-grounded changes; standing2026-10-16 local grant supplies bounded execution authority. No claim of autonomous general intelligence or learned self-improvement.

H-transition: replacing three schema-only support coordinates with prespecified genuine transition summaries improves held-out within-model strategy-advantage prediction and selection over equally informed model means and the original representation. Alternatives: static support cannot explain reset variation; summaries are insufficient; learner/sample budget cannot extract useful information. Do not interpret a failure as proof that dynamics evidence is useless.

Reuse SAME AdvantagePredictor/ridge1, feature_informativeness fold/permutation adapter, training_feedback_audit anchor/receipt helpers, existing describe_support and one-run audit host. transition_evidence performs source preprocessing only, not a new learning/planning/memory framework. Add strict-fit opt-in to describe_support so numerical failure cannot silently substitute a different statistic; default historical behavior stays unchanged. Do not change installed default controller features, any neural architecture/weights, strategy catalogue, regularization or closed results.

## Permitted data and exact representation

Input artifacts/e3_4_predictor_b9.json SHA2565bc051a2effe1fb2c9220393881fe4a1f8ec77f08c28f9660d5d6cb8418c743a. Use ONLY36 permitted training_pairs, feature_rows, normalizers and support_sha256. Ignore saved learned coefficients. No E3.4 evaluation capture/traces, old confirmation outcomes or future trajectory errors for fitting/scoring. No new environments/physics/seeds/collection/imagined rollout/model inference.

Read only the four original source TRAIN NPZs for Pendulum/Acrobot bundles0/1, exactly pinned to LOCKED_ARRAYS in fit_clock and copied into executable config. Verify complete file hashes before and after access. Do not load validation, bundle2 or E2.17 arrays. Slice rows0–31 only, matching source selector's original32-transition support receipt. Verify original support_sha256; save typed prefix hash with shapes/dtypes/data, source digest and unchanged normalizer metadata. Source data are existing training experience, not new interactions.

Use frozen source-family normalizer mean/std from pinned manifest; do NOT refit normalization. For each32-row support:
1. Mean absolute normalized next-state minus current-state change, averaged over rows and dimensions.
2. Mean absolute linear next-state prediction residual on normalized observations plus action one-hot, reusing describe_support()[7] with require_fit=True. Exactly one support least-squares diagnostic per model. This is not decoder training or fitting to strategy returns.
3. Action coverage = number of distinct observed discrete actions /3.

No choices based on observed feature values, label correlation or performance. No clipping/tanh/new interactions/feature search. Replace ONLY task rows7–9 of the existing outer(task12, arm16) representation; preserve rows0–6,10–11 and the same fixed strategy descriptors. Both original and transition-conditioned ridge predictors have192 coefficients. Pack two layouts for paired evaluation; this384-value storage is NOT a384-coefficient predictor. Original features retained for exact comparison; baseline means unchanged.

Source support is identical across reset episodes for each model. Hence new summaries add between-model descriptors, NOT reset-specific information or new within-model variation. The current representation is additive in observation/support blocks; it does not create observation×support interactions. A potential gain can reflect changed pooled-model conditioning/intercepts, not proved history-adaptive identification. Audit varying columns/centered ranks before interpretation.

## Blocked resets, baselines and permutation control

Reuse E3.6's nine held-out reset blocks across four pretrained models. Train32 paired examples/eight resets per model; query4. Both layouts recompute fold-only anchor means, residual labels and training RMS. Existing anchored rule: d=rank_blend−successor, mu=mean d in fold-training model, target d−mu, prediction mu+ridge. Ties choose successor. Query labels never enter any training or normalization operation.

Conditions: original192 features; transition-evidence192 features; model-mean-only baseline. For each fitted representation include19 within-model TRAINING-feature permutations (IDs0–18), identical to E3.6 mapping seed613000+held*10000+permutation*10+model ordinal. Permute entire feature rows only among the same model's eight training examples; labels/means remain fixed; query features untouched. Original/transition use identical maps. No between-family shuffle.

Two representations×20 orders×9 folds =360 ridge fits, each32 unique paired rows/64 antisymmetric numerical rows. Also4 support-descriptor least-squares diagnostics per execution, accounted separately. Original unpermuted predictions must reproduce saved E3.6 full estimates within abs1e−10/rel1e−12. This is a consistency check, not new evidence.

Write immutable fold coefficients, means, packed designs, residual labels, permutation maps, predictions and provenance BEFORE scoring. Original source feature construction is changed only by the declared three-slot replacement.

## Primary screen and unit

Primary metric: held-out residual advantage MAE, identical to total advantage MAE after adding same fold prior. For EACH of all four existing pretrained models require:
- >=5% MAE reduction versus model means (baseline <=1e−12 cannot pass relative screen).
- Strictly lower MAE than original features.
- Strictly lower MAE than at least18/19 paired transition-feature permutations.
- No lower selected cached return than model means.

Only if every model satisfies all conditions label transition_evidence_screen_passed; otherwise transition_evidence_not_established. Original screen is diagnostic and cannot upgrade primary failure. No tuning/promotion from best subset. Save fractional/absolute MAE changes, original-relative metrics and per-model failures.

Average nine queries inside each model, then two models within family. Never pool raw return units across families. Four models/two per family, shared fitted regression: reset folds,19 permutations and64 augmented rows are NOT independent model replications. No inferential confidence interval or permutation p-value from this exploratory reused bank. Record descriptive permutation wins only.

Secondary: MAE/RMSE/sign, cached selection return/regret, every raw reset prediction and target, source summary values, varying-column counts/ranks, compute. Family RMSE is mean model RMSE. Regret reduction equals return gain and sign/ranking accuracy are dependent in this two-arm setting. Cached-return advantage is not new executed control, unseen-physics transfer, learning-to-learn or AGI.

## Bounds, verification and stopping

One local CPU run,30s hard cap,360 ridge-fit attempts and4 descriptor least-squares attempts,0 new real/imagined/neural work. Thread variables OPENBLAS_NUM_THREADS/OMP_NUM_THREADS/VECLIB_MAXIMUM_THREADS each1. Carry ledger784.6290710430173 used/2815.3709289569824 remaining after the preprotocol regression recovery record; do not reset. Exact config/protocol/prior-ledger hashes require committed allocation citing standing grant/current authorization. No historical frozen checkpoint retraining, paid service, main modification or merge.

Preprotocol engineering incident: a462-test regression invocation rewrote six historical benchmark files, and one legacy residual test additionally ran existing learned-model inference. No environments/collection/training occurred. Its forward/imagined counts were not metered and remain unknown, not zero. All six outputs are archived separately, original HEAD bytes restored, seven artifact-writing tests redirected to temporary paths, and the residual inference benchmark is excluded from the source-only final suite. Charge the full10.44-second invocation conservatively to the carried ledger. artifacts/e3_7_preflight_recovery.json plus the small compressed capture preserve this incident; they are NOT training feedback or scientific results. The zero-inference claim applies to the registered E3.7 run, not that earlier regression invocation.

Host retains exclusive one-run markers, attempt accounting, per-fit deadline guards and SIGALRM. Descriptor attempt count is recorded before each attempt; fail closed on bad/missing source hashes, mismatched original support receipts or failed linear fit. Preserve partial/incomplete execution honestly; no automatic retry or enlarged cap. Missing cells/nonfinite predictions/config mismatch cannot become scientific negatives.

After execution independently recompute4 source descriptors from pinned TRAIN prefixes and verify receipts/statistics; report these4 least-squares recomputations rather than calling the whole audit fit-free. Verify ALL360 saved ridge coefficients without ridge refitting using normal-equation abs1e−6 and prediction replay abs1e−10/rel1e−12; verify grids, original result reproduction, resource counts and historical JSON bytes. Save exact execution SHA, source hashes, config/protocol/allocation hashes, dependency versions, wall/CPU and carried ledger.

Repository-only tests can replay ridge evidence using saved descriptors plus pinned training JSON without loading local neural checkpoints. Explicit --verify additionally requires all four source files and must fail if missing; never silently skip source integrity.

Before execution: tests of summary sensitivity to support outcomes; normalization units; explicit least-squares failure; exact32-row source receipts/provenance; only-three-slot replacement/192 capacity; original parity; unchanged schedules/held-out-label isolation; missing cells/nonfinite evidence; coefficient replay without ridge fitting; config/one-run/thread guards; relevant old regressions. Use synthetic fixtures only before protocol commit. Add saved-evidence tests after run without new real-data fitting. Run same audit host with --transitions and --transitions --verify under single-thread environment. Commit results separately and push research branch.

If screen fails, stop this representation variant; inspect additive-conditioning/within-model-information limitation before considering a separately registered interaction representation. Do not increase network capacity, retune ridge or expand strategy generation on this closed bank. If passes, prepare independent fresh-feedback validation, not deployment. At most one next question in final report.
