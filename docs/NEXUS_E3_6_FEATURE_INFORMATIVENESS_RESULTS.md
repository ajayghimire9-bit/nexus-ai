# E3.6 — Within-Model Feature Informativeness Audit: Results

## Decision and scope

**feature_signal_not_established.** No registered feature group passes the locked practical screen. Full and observation-only anchored residual predictors have worse held-out advantage MAE than the model-mean baseline in ALL four pretrained models. Schema-only and anchor-only predictions are numerically equivalent to the baseline. This is a complete valid negative audit, not incomplete execution and not proof that no useful representation exists.

Branch codex/e3-6-feature-informativeness. Verified local/GitHub base b9aa1e2e2ad1815a41bafd7d8bbd9da067f9c3f2. Protocol/implementation clean execution commit **ebdeddc9914eed84f4bcba7f21321600d7f7fb9c** preceded all real-data fitting. Protocol NEXUS_E3_6_FEATURE_INFORMATIVENESS_PROTOCOL.md; executable config configs/e3_6_feature_informativeness.json. No new simulator collection, model inference, neural training, strategy generation or hyperparameter search. E3.4 evaluation remained closed. All351 pre-existing JSON artifacts are unchanged. Unrelated untracked evolution1 adapter files were preserved and excluded.

## A concrete representational omission

Source review found that generated_strategies.advantage_features computes describe_support but uses only support_stats[:3]. Those entries in core/strategy_memory.py are observation dimension/16, action count/16 and episode steps/16. They contain NO observed state/action/outcome statistics. The existing source selector caches a32-transition support history, but its actual transition evidence does not reach this predictor. A test changes support observations, actions, next observations and rewards substantially and verifies identical existing features.

Accordingly, the planned support comparison is honestly named **support_schema**, not support-transition prediction. Genuine transition features are absent, so their informativeness could not be evaluated without changing the representation. E3.6 does not add them or rewrite historical results. Earlier descriptions of this feature bank as containing transition evidence should not be read as evidence that actual transition statistics were tested.

The complete bank is outer(task12, strategy-descriptor16). Group rows are full0–11(192 coefficients), observation0–6(112), support_schema0/7/8/9(64), anchor0/10/11(48). All groups retain the same fixed strategy-descriptor/intercept row. Current fixed rank-blend/successor descriptors do not vary with reset observation. Observation-only therefore means observation plus this common fixed descriptor, not an unrestricted alternative representation.

Within each model, full and observation-only have identical varying coordinates:24 columns/rank3 on Pendulum,48/rank6 on Acrobot. Support_schema and anchor have0 varying columns/centered rank0 in every model. Nominal192 dimensions do not mean192 independent signals. Different feature slices also imply different effective ridge capacity; this audit does not isolate pure information content from regularization bias.

## Registered comparison and leakage controls

Only parsed research input: artifacts/e3_4_predictor_b9.json, SHA2565bc051a2effe1fb2c9220393881fe4a1f8ec77f08c28f9660d5d6cb8418c743a. Project36 permitted TRAINING pairs/features; ignore learned coefficients. No E3.4 evaluation capture or prediction trace is parsed for fitting/scoring. No historical checkpoint or source NPZ is loaded; historical binary verification is inherited, not newly claimed.

Nine blocked reset folds fit32 pairs/eight per model and query4. Each fold recomputes model means, both anchor blocks and training RMS. Residual target d−mu and prediction mu+f use the same existing AdvantagePredictor/ridge1 as E3.5. No withheld labels enter fitting. Each feature group has19 additional within-model training-feature permutations; labels/model means stay fixed, whole joint feature rows are permuted only among the eight training rows of the same model, and query features remain unpermuted. Groups share maps. All720 coefficient sets/predictions were saved before scoring.

The practical screen required >=5% MAE reduction against model means in ALL four pretrained models and better MAE than >=18/19 paired feature permutations in each model. None passes. Permutation win counts are descriptive, not p-values. No posthoc winning-group promotion or threshold change.

## Results by pretrained model

Values below are held-out advantage MAE, equivalently residual MAE after accounting for the same fold-training prior. These are cached training-feedback selections, not new environment returns.

- Pendulum0: mean147.282206; full236.423636; observation219.944159; support_schema147.282206; anchor147.282206. Full MAE worsens60.52%, observation49.34%. Permutation wins full1/19, observation0/19. Cached return gains versus means: full−0.104935, observation−0.104935.
- Pendulum1: mean258.074190; full299.230786; observation260.205261; support_schema258.074190; anchor258.074190. Full worsens15.95%, observation0.83%. Permutation wins9/19 and15/19. Return gains−16.853497 and−1.499452.
- Acrobot0: mean11.331733; full14.440597; observation15.752962; support_schema11.331733; anchor11.331733. Full worsens27.44%, observation39.02%. Permutation wins15/19 and9/19. Return gains+5.637196 and+5.431440.
- Acrobot1: mean20.889419; full22.212941; observation23.537886; support_schema20.889419; anchor20.889419. Full worsens6.34%, observation12.68%. Permutation wins12/19 and11/19. Return gains−4.608687 and−6.119077.

Schema-only and anchor-only return gains are0 in every model; tiny MAE differences(~1e−14) are numerical roundoff, not improvements. Their permuted variants are identical because those groups are constant inside each model.

Average models WITHIN family, never raw units across families:
- Pendulum MAE: mean202.678198; full267.827211; observation240.074710; schema/anchor202.678198. Selected cached returns: mean−356.130684; full−364.609900; observation−356.932878; schema/anchor−356.130684. Full−mean−8.479216; observation−mean−0.802194.
- Acrobot MAE: mean16.110576; full18.326769; observation19.645424; schema/anchor16.110576. Returns: mean−293.983034; full−293.468779; observation−294.326852; schema/anchor−293.983034. Gains+0.514255 and−0.343818.

Full reproduces the previous E3.5 residual predictions within absolute1e−10/relative1e−12; this is an exactness check, not fresh scientific evidence. Observation-only improves Pendulum MAE relative to full but still fails versus means; it is not a successful replacement. Acrobot0 shows why magnitude error and choice utility differ: MAE worsens while cached selection improves, but model1 reverses the return effect.

Raw predictions/true residuals, all19 permutations per group, sign accuracies, RMSE, cached returns/regrets and per-model screens are saved. Family RMSE is explicitly mean per-model RMSE, not pooled-row RMSE. Regret reduction equals return gain on the shared two-arm bank; sign/ranking/choice accuracy are dependent. Constant-group equality is mathematically expected from centered residual targets, not independent negative corroboration.

## Independent audit and tests actually run

Independent zero-fit verification reconstructs fold-training targets/features, exact permutation maps, RMS and query priors; certifies720 ridge solutions with normal-equation absolute tolerance1e−6; replays estimates at1e−10 absolute/1e−12 relative tolerance; checks complete config-derived grid and scoring; rehashes351 historical JSON files. Complete/valid. No learner updates in verification.

Pre-execution relevant regression suite: **418 passed in8.50s** across17 test modules. One earlier focused invocation found a JSON numeric-type mismatch in the newly written config (integer1 versus locked float1.0); corrected before protocol commit, no real-data fitting or scientific attempt consumed. Post-run regression adds three saved-evidence tests: no-fit replay/history preservation, exact E3.5 full prediction reproduction and parser access restricted to the training manifest. Final command/counts are recorded in artifacts/e3_6_test_report.json; it is the relevant suite, not the entire historical repository suite.

Other focused checks cover existing support-outcome insensitivity; group slices; informative synthetic context and constant-group behavior; within-model permutation/unchanged labels; held-out outcome and saved-anchor poisoning; seed determinism; complete-grid and numeric bool/string/NaN/infinity rejection; missing coefficient/permutation/query/model/fold rejection; fit guards; exact config and one-run/thread restrictions. No real environments or learned networks are executed by this suite.

Final relevant suite: **421 passed in8.84s**. All36 full-feature held-out estimates reproduce E3.5 with maximum absolute difference0.0; no tolerance margin was needed on this runtime. Full test command and the resolved pre-execution schema failure are retained in the test report.

## Resources and provenance

720 ridge fits:4 groups×20 orders×9 folds. Each uses32 unique paired training rows,64 antisymmetric numerical rows. Repeated fits are not720 pretrained models or extra environment samples.36 contexts yield2880 fitted estimates plus36 mean estimates. Four frozen pretrained bundles, two per family, remain the only model units; shared regression fitting also couples their predictions. No confidence intervals or independent-generalization claim from reset folds/permutations.

Execution wall **0.510763583s**, CPU0.510025s; independent audit **0.314667167s**; combined charged time **0.825430750s**. Cap30s,720fits,0real/imagined/neural work, one run, no retry. Carried ledger **774.1890710430174 used /2825.8109289569825 remaining** from773.363640293, not reset. Tests are separate engineering checks.

Local Python/NumPy and three thread variables are recorded in the capture; each thread variable1. Command: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_e3_3_training_feedback_audit.py --features; independent audit adds --verify. Config SHA256e19fb04a5b748106a5345e74b1b4444cb2ae488aee76492efebfe2d46ae9984b; protocol00fbb439b08f220aaf186a11d6e6d1b7827a3b7cd541ed1ca062a221ddbc3497. Capture9f8c04695a6ca7e3963bbf9f7d6aa0f43d7717ae99098c4ce8faf7855a3b813c; frozen predictions4a257f74312b5ab2c4a11b0804398e29b28108d0c378c45700165d0d952173a5. Full source hashes/immutable usage/allocation are saved. Historical source .pt/.npz availability is not required for repository-only reproduction of this arithmetic.

## Interpretation and one next experiment

This audit fails to demonstrate useful within-model residual prediction under the present features, ridge rule and small reused source feedback bank. It cannot distinguish all nonlinear information from insufficient samples, noisy planner outcomes or estimator bias. Static source support is also shared across resets; even genuine fixed support statistics alone cannot identify reset-specific differences. No new generalization, control, self-improvement, learning-to-learn or AGI claim follows.

**One recommended next experiment:** a separately registered representation ablation that replaces the three schema-only support slots with prespecified genuine transition summaries already available from permitted source-training support (for example mean absolute next-state change, transition-residual magnitude and action coverage), retaining the same feature dimension, ridge and blocked-reset/model-mean comparison. Inspect representation variability before fitting and distinguish between-model context from within-model observation interactions. Use no closed outcomes or new collection; do not implement/tune it here. This tests a concrete source omission before investing in larger learners, candidate-trajectory features or more strategy generation.
