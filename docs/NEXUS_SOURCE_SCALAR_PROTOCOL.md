# Source-only scalar calibration, then fresh visited-state audit — protocol v1

Base `beab44938076d454a12129e60fe3667619b33e2f` matched GitHub before branching to `codex/source-scalar-calibration`. The scalar has not been calculated. Freeze executable config `configs/source_scalar_calibration.yaml`, implementation and focused tests before fitting. Commit the source-only fit manifest separately before fresh evaluation experience. Preserve all prior protocols, results and checkpoints.

## Hypotheses and one fixed fitting rule

H-magnitude: source-calibrated shrinkage improves visited-state candidate selection relative to both the unchanged terminal correction and no correction. H-generalization: a source-only gain does not improve selection at visited states. Useful pair ordering with poor centered error motivates the test but does not establish scaling as a cause.

Use only source tasks0..7 of the original frozen-readout calibration capture, whose original numerical validation failure was recovered by a separate hash-bound complete offline proof. Use imagined-endpoint terminal predictions for five student contexts, ten decoders, eight source tasks and four recorded candidates:400 groups/1,600 examples. Never use tasks8..10 or any closed visited outcomes in fitting, model selection, clipping choice or a retry. Exact hashes are bound in config. These source episodes were inspected previously; this is development calibration, not independent source confirmation.

In each decoder/task/context group center its four predicted48-step tails p and recorded48-step common-zero tails y. Fit **one shared scalar** beta_raw=sum((p−mean(p))*(y−mean(y)))/sum((p−mean(p))²). Set beta=min(1,max(0,beta_raw)); denominator≤1e−12 gives beta0 and a degeneracy flag. No intercept, grid search, per-task coefficients, regularization tuning or extra fit. Equal group sizes give equal decoder/task/context weighting. Save all source covariance/variance terms, beta, source hashes, clean fit revision and runtime. Recompute deterministically for audit only; do not revise after fresh results.

For decoder d let c_d remain its fixed original source-training48-step mean. At a new state use calibrated tail **c_d+beta*(p−c_d)** and score **base+survival*calibrated_tail**. Beta1 is exactly the original correction; beta0 is the fixed-constant correction, not necessarily the no-correction score because survival varies. Original no correction and beta1 remain explicit baselines. No historical readout/encoder/decoder/FiLM/head/normalization checkpoint is modified. Only an external scalar is newly fitted. Source fitting uses no real interactions or world-model inference; linear readout arithmetic is checked on stored data.

## Fresh visited-state evaluation

Keep all ten independent decoders/five student scoring seeds, three known development physics, H16/16 candidates, actions −2/0/+2, source normalizers, saved contexts and common-zero future. Use the preceding visited diagnostic's phase50 method unchanged: one student visitor `(d+t) mod5` and one zero visitor per decoder/task, each50 live steps, equal visitor weights. This is one student-visitor history per decoder/task, not all five visitor trajectories. Reproduce the final live decision before counterfactual scoring. All five students score every saved state.

Fresh seeds: reset3000000+100*d+t; live candidate3010000+10000*d+100*t+k, k0..49; same-state candidates3200000+100*d+10*t+v; future3300000+10000*d+1000*t+100*v+k, k0..63. Verify exact disjointness against all previous closed registries and the immediately preceding visited-state sets. True simulator state is research-only restoration information, never agent input. Clocks50/66/end114, exact restored states, identical16 candidate sequences for all three scoring rules, action-independent future seeds and fixed contexts.

Measure all16 full candidate sequences plus48 zero-policy continuation steps and all three first-action outcomes plus63 zero-policy steps. Cached outcome reuse across scoring rules/contexts is not extra interaction. Scalar scores use only saved predictions/survival/source constants, never actual future outcomes. The old visited collection/validation helpers are parameterized for file provenance and a required custom preflight/finalizer; their default historical behavior remains regression-tested. Old raw artifacts stay unchanged.

## Primary analysis and screen

Primary paired contrasts are calibrated-minus-no-correction and calibrated-minus-original-correction **full-sequence chosen64 return**. Average five students inside decoder/task/visitor, then equal visitors, then equal three tasks inside each of ten independent decoders. Two-sided t95 intervals,df9,critical2.262. Require mean calibrated-minus-base≥1 and its lower>0, and calibrated-minus-uncalibrated lower>0. This conjunction is one intersection screen, label `source_scalar_selection_gain`; otherwise `scalar_selection_gain_not_established`. Missing/invalid/timeout is `incomplete`, not an inconclusive scientific finding. Both intervals and all signs must be reported, including if beta0/1 makes a comparator identical. No claim that scaling established useful task information if beta0 wins.

Secondary unadjusted diagnostics: first-action calibrated gains, corrected/scaled/no-correction absolute returns and regrets, sequence/action disagreements, centered tail prediction benefit versus the original correction, beta and per-decoder/task/visitor/zero-context results. Regret reduction duplicates chosen-return gain. No statistically favorable secondary measurement upgrades the screen. Even passing full-sequence selection is not improvement of a receding-horizon/full-episode controller or an explanation of historical negative transfer.

## Limits and provenance

Standing-authority allocation: **360 seconds total including fit and fresh evaluation**, less than429.5209seconds remaining in the current conservatively accounted session. Estimate4–5CPU minutes for evaluation from the preceding242.932-second run, plus a few seconds for fitting/validation. Enforce the remaining deadline after fit. Single CPU, no paid service. Save incomplete data if capped; do not shrink the grid, refit or silently retry.

Exact fresh interactions **75,960**: collection3000+prefix15360+block tails46080+first-action branches11520. Imagined transitions **15,667,200**, including60 last-live-decision replays; no new support collection. Inherited source calibration labels cost15,872 real source-only steps previously (8×4×16 prefixes +10×8×4×48 suffixes), not recollected. The inherited neural/readout training and384 target-support steps remain separate prior costs. No retraining/replacement of frozen checkpoints. Source beta fitting and validation consume CPU time and are recorded even with no new environment steps.

Verify all120 binaries/30 model-context groups before collecting fresh data and120 binaries afterward. Require exact60-cell grid, finite typed metrics, both visitor groups, all contexts and candidate outcomes, reward/clock/RNG consistency, frozen fingerprints, clean execution revision, immutable source-fit hash and a committed fit manifest ancestor before any new environment is made. Protocol/implementation commit precedes fit; fit-manifest commit precedes evaluation; results commit follows once. No main merge, confirmation tasks or closed-seed reuse.

## Tests and commands

Test analytical scalar recovery, clipping/degenerate cases, source-task filtering and invariance to changed development labels, exact beta0/1 score limits, no outcome input to score calculation, paired ten-decoder/equal-visitor aggregation, missing/invalid cells, locked fit-manifest audit gate and closed-seed rejection. Run previous visited/commitment regressions, full regressions and explicit frozen-checkpoint audit. Save a separate independent reward/selection calculation without simulation.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_source_scalar_calibration.py tests/test_visited_commitment.py tests/test_commitment_value.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_source_scalar_calibration.py --fit-source
# Commit the complete source-fit manifest before this command:
PYTHONPATH=src:.deps python3 scripts/run_source_scalar_calibration.py --execute
PYTHONPATH=src:.deps python3 scripts/run_source_scalar_calibration.py --audit
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
```

If calibration fails, stop this scalar branch rather than retuning on fresh evaluation. If it improves prediction only, retain the prediction/control distinction. If it passes selection, propose a separately locked policy-value test rather than deploy. No architectural change or extra experiment is included.
