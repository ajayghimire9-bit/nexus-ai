# E3.5 — Baseline-Anchored Residual Advantage Learning: Results

## Decision

**residual_advantage_not_established.** The complete, valid training-only blocked-reset run fails the predeclared screen in both families. Retaining the model mean helps relative to direct prediction on Pendulum, but does not beat the mean itself; on Acrobot the small mean gain fails the practical threshold and has opposite signs across models. Do not expand strategy generation or claim reliable transferable decision learning from these results.

Protocol: NEXUS_E3_5_RESIDUAL_ADVANTAGE_PROTOCOL.md. Base74289818291ac448de69c84a5db97d17f572229e; clean execution/protocol commit **f128c29a8b116886dd20dd42cc025436d5421386**. Branch codex/e3-5-baseline-anchored-residual. No simulator collection, checkpoint loading, world-model inference, neural training or closed E3.4 evaluation scoring. Historical decoder integrity is inherited from E3.4, not freshly verified by loading binaries here.

## Implementation and isolation

Reused AdvantagePredictor in generated_strategies.py, existing ridge/scaling, and training_feedback_audit; no parallel learner, planner, memory or resource meter. Optional observed-baseline arguments fit d−mu and predict mu+f(x); baseline0 retains the original direct API. Residual correction is not constrained and offers no safety guarantee.

Only parsed research input is artifacts/e3_4_predictor_b9.json, SHA2565bc051a2effe1fb2c9220393881fe4a1f8ec77f08c28f9660d5d6cb8418c743a, projecting36 permitted training pairs and their features. Nine blocked reset folds each fit32 pairs and query4, with training-only model means, both anchor feature blocks and RMS scaling. Saved all-nine-reset anchors were replaced before fitting. Query outcomes cannot affect that fold's fit. Direct, residual and shuffled-residual models each have the same192 coefficients and ridge1. No feature or hyperparameter search.

The complete frozen fold artifact was written before scoring. Independent verification performed0 fits, reconstructed targets/scales, checked normal equations (tolerance1e−6), replayed predictions (absolute1e−10/relative1e−12), checked complete grids and arithmetic, and verified346 previous JSON files byte-for-byte. Regression tests also perturb held-out outcomes and check that fold predictions remain identical.

## Primary selection results

All values below are **out-of-fold selections scored on previously collected training return pairs**, not new executed control returns. Average resets within each model, then models within family. Only two pretrained models per family; no confidence interval or p-value is justified by treating nine overlapping folds as independent models.

Pendulum: residual selected return−364.609900, model mean−356.130684; primary gain **−8.479216**. Individual model gains **−0.104935 / −16.853497**. Relative to direct prediction, residual gains+9.278711, but its primary comparison remains negative. Both-model and >=1-point rules fail.

Acrobot: residual−293.468779, model mean−293.983034; gain **+0.514255**. Individual model gains **+5.637196 / −4.608687**. Relative to direct prediction, residual loses−2.366230. The >=1-point, both-model and no-worse-than-direct rules all fail.

The unchanged registered criterion required >=1-point mean gain over model means in EACH family, positive gain in BOTH models and no worse mean selection than direct regression. This is a valid negative research outcome, not an incomplete execution.

## Every baseline and diagnostic

Pendulum mean selected returns: direct−373.888611; residual−364.609900; shuffled residual−351.703670; model mean−356.130684; family mean−401.539918; global mean−401.539918; always successor−328.850060; always rank blend−317.543266; deterministic uniform−351.861987. Residual loses to both fixed arms and uniform. Posthoc strongest fixed arm is descriptive, not a newly selected deployment rule.

Acrobot: direct−291.102549; residual−293.468779; shuffled residual−293.138399; model mean−293.983034; family mean−291.774823; global mean−294.437548; always successor−291.774823; always rank blend−294.835787; uniform−294.111582. Residual fails to beat direct or always successor. Shuffled residual also beats real residual in both family means; mixed-family shuffling changes label scale and is not independent evidence of absent signal.

Advantage MAE (model mean / direct / residual): Pendulum202.678198 /271.462010 /267.827211; Acrobot16.110576 /17.414231 /18.326769. Thus residual MAE is worse than model means by65.149013 and2.216193 respectively. Sign accuracy (same order) is Pendulum0.666667 /0.500000 /0.555556 and Acrobot0.333333 /0.666667 /0.555556.

Residual mean absolute correction: Pendulum113.366988, Acrobot11.899244. Of18 held-out choices per family, residual overrides model means6 times on Pendulum (2 improved,4 harmed) and8 times on Acrobot (6 improved,2 harmed). Override frequency alone obscures error magnitudes: Acrobot's two harmful changes offset most gains. Raw return/regret/choice/prediction cells and all baseline contrasts are in the result JSON.

Mean residual regret: Pendulum128.101920 versus model mean119.622704; Acrobot7.747013 versus8.261268. Regret reduction equals selected-return improvement for this shared two-arm return table; these are not independent supporting metrics. Model mean equals zero residual correction, and two-arm sign/ranking accuracy are dependent. Do not pool incompatible family return scales.

## Resources and reproducibility

The single authorized run completed27 ridge fits across9 folds, each using32 unique training rows and64 antisymmetric numerical rows. Those reused fit rows are not additional environment experience. Execution wall0.287327500s /CPU0.286207s; independent zero-fit audit0.207447500s. Total charged research execution/audit0.494775000s. Ledger carried from772.868865293 to **773.363640293 used /2826.636359707 remaining**; no reset or additional grant. Tests are recorded separately.

Local Python3.13.5 /NumPy2.5.4; OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and VECLIB_MAXIMUM_THREADS each1. Caps15s/27fits/0real/0imagined/0neural. No retries. Protocol/config/allocation hashes and execution-file hashes are in the result/usage artifacts.

Capture SHA2569673109960d499184cc323e5ad346538e11d1cb37491df5bf2c51e15d17bb63b. Frozen fold SHA2564ee7d6393188ea1e311a13105a2184a6560514441b8c920cb294498685c22d06. Immutable files: e3_5_residual_advantage.json, e3_5_frozen_fold_predictions.json, e3_5_residual_advantage_usage.json and e3_5_residual_advantage_validation.json under artifacts/.

Commands: single-thread environment above plus PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_e3_3_training_feedback_audit.py --residual; then --residual --verify. Both complete. Pre-execution relevant regression suite389 passed in7.94s. Post-result suite adds two repository-only tests for saved replay without fitting and the input-parser boundary; exact final command/results are in artifacts/e3_5_test_report.json.

## Limits and one next question

This is exploratory reuse of permitted source TRAINING feedback, not independent task confirmation. Same-family held-out resets do not establish cross-model or cross-family transfer. Two models per family, small return bank and192-dimensional ridge make feature signal, optimization bias, variability and overfitting competing explanations. Failure of this fixed residual method does not prove that context contains no useful information.

**Next recommended experiment:** a separately preregistered, source-only within-model feature-informativeness audit: test whether the present predecision features predict within-model advantage beyond model means and within-model context permutations under the same blocked-reset isolation. Preserve family scales and model means in the ablation. No new collection, feature search or architecture expansion is justified yet. Not executed or allocated here. E3.4 closed evaluation, E2.17 consumed grant, H17 block and historical results remain unchanged.
