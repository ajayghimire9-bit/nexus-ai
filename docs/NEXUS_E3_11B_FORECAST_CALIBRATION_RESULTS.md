# E3.11B — Forecasts differ, useful selection advantage not established

Branch **codex/e3-11b-forecast-calibration**. Actual execution revision:
**2cfd99232f01d1103d5abbb2a328c5056bb4f5fc**, committed before collection.
Starting preparation HEAD6831102935c58d88f715e778836d15530cc0fcf8. Final
lock: NEXUS_E3_11B_FORECAST_CALIBRATION_EXECUTION.md. Preparation documents,
configuration, E3.11/E3.11A evidence and historical checkpoints are unchanged.

## Registered decision

**forecast_utility_not_established**. Complete valid execution, not an incomplete
run: all16 paired cases and32 actual192-step controller continuations finished
once. Both families fail the predeclared intersection point screen. No retuning,
retry, model fitting or neural updates. This is known-source-model exploratory
calibration; it is not unfamiliar-physics confirmation or useful self-improvement.

Policy-forecast direction accuracy was **75.0% Pendulum /62.5% Acrobot**.
Training-mean baseline: **87.5% /62.5%**. Common-tail: **50.0% /62.5%**.
Common-tail had forecast ties in75% of cases in each model. Registered ties
score0.5 for accuracy but choose successor for realized selected return. Thus
tie-adjusted accuracy is not simply the frequency that a deterministic choice
picked the better controller. Policy forecasts and actual192-step advantages
had no numerical ties. Include all16 cases, no favorable subgroup filtering.

Average selected192-step returns, equally weighting models within family:

- Pendulum: policy forecast−165.904977; common-tail−246.933228;
  training mean−164.346873.
- Acrobot: policy forecast−281.470432; common-tail−281.881309;
  training mean−283.040377.

Policy forecast minus training mean selected-return differences:

- Pendulum **−1.558104 [−21.355693,+18.239485]**.
- Acrobot **+1.569945 [−17.203892,+20.343782]**.

Against common-tail: Pendulum+81.028251 [−948.533294,+1110.589796],
Acrobot+0.410877 [−4.809806,+5.631560]. All return intervals include zero.
These are paired exploratory unadjusted t95 intervals across **two existing
pretrained model bundles per family**, df1. Four episodes/model are averaged
inside the model; neither episodes nor forecast candidates add model replications.
Do not pool family reward scales.

Accuracy differences versus training means: Pendulum−0.125
[−1.713276,+1.463276], Acrobot0 [0,0]. The zero Acrobot interval follows equal
discrete accuracy in both models, despite different choices/returns; it is not
population equivalence. Unbounded t intervals for accuracy differences can
exceed their feasible range; retain the registered calculation rather than
switching estimators after seeing results.

## Per-model results and retained failures

Each line gives direction accuracy for policy/common/mean, selected return for
policy/common/mean, then policy-minus-mean return:

- Pendulum0: .500/.375/.750; −167.868678/−329.925180/−164.752470;
  **−3.116208**. Fails accuracy and nonnegative model-gain requirements.
- Pendulum1: 1.000/.625/1.000; −163.941276/−163.941276/−163.941276;
  **0**. No gain over the strong prior.
- Acrobot0: .500/.625/.500; −281.247834/−281.247834/−281.340246;
  **+0.092412**. No accuracy gain over mean, lower than common-tail.
- Acrobot1: .750/.625/.750; −281.693031/−282.514784/−284.740509;
  **+3.047478**. Positive return point difference, no accuracy gain over mean.

The large Pendulum-versus-common-tail mean benefit is concentrated in model0;
model1 gain is0. One model0 case has actual strategy advantage+648.226.
Raw case rows, decisions and outcomes remain in the JSON/CSV, including losses.
Do not portray that mean as consistent cross-model improvement.

## Short versus long prediction diagnostics

Policy forecast advantage MAE relative to actual first16-step differences:
Pendulum5.257815 versus common-tail7.599508; Acrobot0.107539 versus
common-tail0.058053. More expensive policy forecasts are not uniformly more
accurate even on the matched short window.

Relative to actual192-step differences, policy MAE is149.616076 Pendulum and
8.570240 Acrobot; common-tail148.190910 and8.571947; mean prior152.493597 and
42.091155. The mean prior estimates192-step advantage, so its first16 MAE is
a horizon-mismatched reference, not evidence of superior short forecasting.
Lower magnitude error does not establish more accurate direction or better
selection: Acrobot's magnitude error is far below the mean prior while its
direction accuracy remains equal and its return interval includes zero.

Descriptively, Pendulum model0 episodes0,2,3 have negative actual first16
rank-minus-successor advantage but positive actual192 advantage. Example
episode3: forecast−10.747031, actual first16−27.050477, actual192+13.029664
(rounded). This is compatible with a horizon mismatch; it does not isolate a
causal mechanism. Trajectories diverge, only four resets/model were sampled,
and each forecast uses one paired planning stream. No new metric or subgroup
replaces the predeclared primary screen.

## Integrity and resource audit

One registered execution plus saved-data verification, with no additional
environment or learned-model calls during verification. All6688 journal
records reconcile reservations/settlements and the separate stage counts:

- Probe128 real steps,0 imagined/forwards.
- Policy forecast763904 imagined transitions/30720 forwards,0 real.
- Common-tail8192 imagined/512 forwards,0 real.
- Actual control6144 real/9160704 imagined/362496 forwards.

Total **6272 real steps,9932800 imagined transitions,393728 model calls and
observed top-level network forwards**, zero unknown work. Cached method-return
reuse adds no executed interactions. No fits or model updates. Policy evidence
alone still costs93.25× common-tail imagined rows and60× forward calls; that
ratio does not describe the total control cost or establish efficiency.

Parent wall **55.86182158299198s** under180s cap; worker process CPU55.175685s.
Measured worker peak RSS467927040 bytes (446.25 MiB; includes runtime/model/IO).
Five lossless journal parts total58302684 bytes; checkpoint binaries remain
outside Git. Saved-data verification3.004717667005025s.
Final carried ledger **948.6320812930051 used /2651.3679187069947 remaining**.
No extra scientific experiment started.

All four checkpoint bytes, eight source inputs, model state/RMS fingerprints
and **387 pre-existing research JSON** retain hashes. Seed audit:1568 values,
zero collisions within current artifact/config metadata, all original source
arrays and conservative historical reservations. Unavailable external runs
remain outside coverage; no global completeness claim. No confirmation tasks,
H17 execution or consumed E2.17 grant reuse. Two unrelated untracked adapter
files are preserved and excluded from commits.

## Tests and reproducibility

Pre-run focused108 tests passed in3.23s;32-module relevant regression611
passed in13.45s. Coverage includes exact restore/RNG pairing, forecast-first
durability, uniform probe and candidate stream replay, reward timing, raw
transition continuity, first-action reproduction, complete grids, finite
metrics, frozen hashes, resource caps, closed-seed rejection and one-run gating.
The entire historical suite was not run: known legacy inference benchmarks
are outside the no-extra-execution verification scope. Final saved-capture
test and regression outcomes are recorded separately in e3_11b_test_report.json.

Thread environment: OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1,
VECLIB_MAXIMUM_THREADS=1, PYTHONDONTWRITEBYTECODE=1, PYTHONPATH=src:.deps.

```
python3 scripts/run_e3_11_post_probe.py --calibration
python3 scripts/run_e3_11_post_probe.py --calibration --verify
python3 scripts/summarize_e3_11_post_probe.py --calibration
```

The first two ran on the precommitted execution code. Export support and the
saved-capture regression were added afterward; neither changes outcomes or
the registered analysis. Re-execution is intentionally blocked by consumed
usage/output records. Verification also checks execution-source bytes through
Git, frozen inputs and all historical JSON. Runtime versions are recorded in
the raw artifact. Return gain and regret reduction are mathematically dependent
and are not two independent pieces of evidence.

Raw artifact e3_11b_forecast_calibration.json SHA256:
d1c1297518b56dfdb28107c29a0aabe5b8c768068d01becfbf62f50d9746b56b.
e3_11b_forecast_calibration_validation.json contains stage accounting/ledger;
e3_11b_forecast_predecision.jsonl contains durable forecast receipts;
e3_11b_forecast_summary.json and e3_11b_forecast_returns.csv provide readable
paired summaries and48 logical-method return rows from32 physical paths.
Full observations/actions/rewards/forecasts and journal hashes are preserved.

## One next scientific question

**Does a longer, explicitly matched forecast horizon predict later controller
advantage better than the frozen training-mean prior?** Prepare a separate
fresh-data horizon-calibration protocol, without changing models/planners or
tuning on this now-closed sample. Short-versus-long sign reversals motivate
this question, but do not already answer it. Do not prioritize making an
unproven selector cheaper or expand mutation/continual-learning claims before
establishing useful ranking information. No next experiment executed here.
