# E3.3 — Training-only feature sufficiency audit

Valid, complete exploratory reanalysis; registered label **training_only_feature_signal_not_established**. Acrobot has a positive selection signal, while overall feature/selection superiority is not established. Do not reinterpret either conclusion as independent confirmation.

Branch `codex/e3-3-training-feedback-audit`; verified local/GitHub starting revision `ded811d1f9ddaa2d907dd1a807fe06b174d9dbe9`. Protocol, implementation, configuration and one-run allocation committed before fitting at **d9c196cad2afa7c6d59a43ce34b0a4e46bbd1b65**. No uncommitted user files were included. The existing AdvantagePredictor/ridge and selection semantics were reused; no planner, neural model, memory or proposer was replaced.

## What was tested

Can the existing feature/ridge rule beat simple training means when one of the three TRAINING reset blocks is withheld across all four frozen source models? Each fold fits eight pairs and predicts four; every one of the twelve training contexts receives one out-of-fold prediction. All sixteen E3.2 evaluation contexts remain closed and were not parsed for this audit. Only the hash-pinned training manifest was parsed; old artifact bytes were hashed for preservation.

The saved feature rows contained anchor means calculated over all three training resets. Reusing them would leak withheld labels. We replaced both outcome-derived anchor blocks with fold-only means and recomputed ridge feature scaling from the eight fit rows. Synthetic tests demonstrate that changing withheld outcomes cannot alter the fold's predictions, coefficients or baselines. Rebuilt features match the canonical feature function to 1e−12. This correction applies to the new cross-validation computation; it does not alter the legitimate all-training E3.2 fit or any historical result.

## Primary and model-level results

Aggregate three withheld resets inside each model, then the two models inside each family. Families' raw return units are not pooled.

- Pendulum predictor mean −172.835 versus model mean −172.002: **−0.833 points**. Model0 −0.172; model1 −1.494. Advantage MAE 363.686 versus 246.643 (117.043 worse). Sign accuracy 4/6 versus 5/6. Regret 0.964 versus 0.131.
- Acrobot predictor mean −293.299 versus model mean −304.868: **+11.569 points**. Model0 +6.410; model1 +16.727. Advantage MAE 23.408 versus 22.671 (0.737 worse). Sign accuracy 4/6 versus 0/6. Regret 3.536 versus 15.104.

Pendulum fails the return-margin, per-model sign and MAE requirements. Acrobot passes the >=1-point return and both-model gain requirements, but fails the prespecified MAE requirement. Both family screens and the combined screen therefore fail. This is a scientific negative under the locked intersection rule, not an incomplete execution. The positive Acrobot selection contrast must not be hidden: choosing the better arm and accurately estimating advantage magnitude are distinct objectives. A future objective must be registered independently; do not change this screen afterward.

## Other selectors

Pendulum predictor-minus-baseline: shuffled labels +148.342; family mean +21.627; global mean +21.627; always successor +175.349; always rank blend +21.627; deterministic uniform +125.751. The stronger model-mean comparison is −0.833.

Acrobot predictor-minus-baseline: shuffled labels +8.851; family mean +7.230; global mean +4.030; always successor +4.002; always rank blend +4.030; deterministic uniform +4.517. Model mean comparison is +11.569.

The shuffled predictor retains the same legitimately revealed fold-only anchor features, so this is a paired-label ablation, not removal of all feedback. Uniform uses one fixed digest rule, not a distribution over random-selector runs. Regret reduction equals return gain, and two-arm ranking accuracy equals sign accuracy; these are dependent metrics, not independent corroborations.

## What this establishes and leaves open

There is source-training Acrobot selection information under this blocked-reset check, despite poor magnitude calibration. Its mean baseline reverses the held-out advantage sign on every one of these six contexts; with only two fit resets per model, that does not establish reliable deployment behavior. The separate E3.2 evaluation remains a negative result and is not superseded by this reanalysis.

On these Pendulum training contexts, model means already leave only 0.131 mean in-set regret. There is little decision headroom even though advantage magnitudes are poorly predicted. This differs from E3.2's fresh evaluation context distribution. Neither result proves the cause of the previous generalization failure.

Each training design has rank8 against192 coefficients; the six antisymmetric fits use16 numerical rows each, still only eight unique contexts per fold. This is a sparse-data limitation, not proof that more data will solve the problem. There are two existing pretrained models per family, three overlapping folds, no new independent models or physics, no confidence interval/p-value, no control-transfer or learning-to-learn conclusion. Query-label sensitivity tests and arithmetic verification establish engineering integrity, not scientific success.

## Resources and provenance

Six ridge fits completed in **0.244354s wall /0.244084s CPU**, below15s. Zero real interactions, imagined transitions, neural inference, checkpoint modifications or new simulator instances. Separate coefficient/arithmetic verification: **0.182754s**, zero fits. All334 pre-existing JSON artifacts remain byte-identical. Verification reproduces the twelve predictions, six coefficient models, fold means/scaling and ridge normal equations without refitting. Original source NPZ/checkpoint files are not required by this recorded-feature audit and were not loaded; their previously verified provenance remains in E3.2. No new checkpoint-integrity claim is substituted for that earlier audit.

Carried ledger: 588.722984459005 before execution; **589.1500925009981 used /3010.849907499002 remaining** after offline verification. Tests are reported separately from experimental execution. Python/NumPy versions and code/config/allocation hashes are in the raw capture. The input manifest hash is e84d55ce4b8f3bd6dbc4cda1edcbecfe411e808ed91c63a16504b52fb3453b83. Capture hash **63ffb68346a350961a1a54cb6b5408de00ce99486e9c94466767ac00ba0b097a**; frozen prediction hash **a5d78d1f32ab4b79e230e9a8cb8d352e9976843203f7db157724a05c5d86c006**.

Files: e3_3_training_feedback_audit.json (raw outcomes/metrics/provenance), e3_3_frozen_fold_predictions.json (saved before scoring, including weights/features/IDs), e3_3_training_feedback_validation.json, and one-run usage record. Commands: protocol focused tests; `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_e3_3_training_feedback_audit.py` once, then `--verify` once. Pre-execution focused30 tests passed; relevant327 regressions passed before allocation's final hash-only provenance check was added, followed by30 focused tests on the committed implementation. Final **330 relevant regressions passed in5.16s**, including repository-only provenance/arithmetic and input-boundary tests. This is not the full historical repository suite; exact command is in e3_3_test_report.json.

## One next scientific question

Does broader paired training-feedback coverage improve the SAME frozen feature/ridge selector over equally informed model means? Proposed separate source development study: fresh nested training budgets3/6/9 reset pairs per model, followed by four common fresh evaluation reset pairs; same four frozen models, same two controllers, no feature/regularization change or new physics. Primary budget9 selection return versus model means; budgets3/6 are secondary learning-curve diagnostics, not hyperparameter selection. Register the thresholds, new seeds, complete-grid rules and protocol before collection; retain all existing evaluations closed.

Estimated physical cost: 4 models×(9 training+4 evaluation)×2 controllers×200=20800 interactions, at most31948800 imagined transitions. Scaling from E3.2 gives about151s; proposed240s local CPU cap with honest incomplete handling. No allocation, seed registration or execution has been made for that proposal here. It targets the observed sparse-feedback uncertainty before adding a larger encoder or predictor.

No main merge, old checkpoint retraining, H17 execution, E2.17 grant reuse, autonomous-discovery success or AGI claim.
