# E3.11D — Longer forecasts do not establish better selection

Branch codex/e3-11d-longer-horizon-calibration. Protocol/config/allocation and
tested implementation committed before outcomes as
**4e6be2f2b36a21843ed8804a8018046ab0133bf8**. Starting GitHub/local HEAD
8e9a514398d751d1dd31bf969c90136ff3a561a0. Protocol:
NEXUS_E3_11D_HORIZON_CALIBRATION_PROTOCOL.md. One approved run, no retry,
fitting, model changes or confirmation access. E3.11C efficiency is deferred;
D is a distinct forecast-duration test, not a new planning-horizon controller.

## Decision and primary findings

**longer_horizon_utility_not_established**. All16 fresh paired cases completed
and passed integrity verification. Both family intersection screens fail.
Longer forecasts are not established as useful; failure is scientific, not
an incomplete or invalid run. Preserve E3.11B's earlier negative result.

Direction accuracy on actual192-step controller advantage:

- Pendulum:64-step62.5%,16-step62.5%, TRAIN mean75.0%, common-tail43.75%.
- Acrobot:64-step37.5%,16-step62.5%, TRAIN mean62.5%, common-tail50.0%.

Mean selected192-step returns, equally averaging models within family:

- Pendulum:64-step−213.134346;16-step−199.357533; mean−196.529981;
  common-tail−252.970229.
- Acrobot:64-step−274.139724;16-step−267.187100; mean−271.558710;
  common-tail−274.139724.

64-minus16 selected-return differences with paired exploratory95% intervals:

- Pendulum **−13.776813 [−214.766243,+187.212618]**.
- Acrobot **−6.952624 [−95.294093,+81.388844]**.

64-minus-training-mean differences:

- Pendulum **−16.604364 [−629.413053,+596.204325]**.
- Acrobot **−2.581014 [−31.470974,+26.308947]**.

All return intervals include0. Negative point estimates do not establish
population harm. Accuracy contrasts versus16 are0 Pendulum and−0.25 Acrobot;
versus mean−0.125 and−0.25. Their t intervals are also broad and include0;
retain raw unbounded t intervals in JSON instead of switching estimators.

Statistical units: **two existing independently pretrained model bundles per
family**, each averaging four episodes. Paired t95 df1 critical12.7062047364;
unadjusted exploratory intervals. Do not pool family reward scales, count
episodes as model replications, claim unseen-physics confirmation or call the
test a demonstration of general control improvement. Forecast/actual192 ties
were absent. Common-tail ties87.5% Pendulum/75% Acrobot receive registered
0.5 accuracy but choose successor for selection; these are different metrics.

## Decoder-specific findings and failures

Each line lists accuracy64/16/mean and selected return64/16/mean:

- Pendulum0: .75/.50/.50; −196.703084/−198.744482/−228.327809.
  Positive point changes retained; they do not override the other model.
- Pendulum1: .50/.75/1.00; −229.565607/−199.970583/−164.732153.
  Loses against both primary baselines.
- Acrobot0: .50/.50/.50; −275.682650/−275.682650/−275.375325.
  No gain versus16; loses slightly versus mean.
- Acrobot1: .25/.75/.75; −272.596798/−258.691550/−267.742096.
  Loses against both primary baselines.

Thus gains are heterogeneous on Pendulum; Acrobot has no positive64-minus16
point change in either model. All individual-case predictions, actual16/64/192
advantages, selected controllers and regrets remain in raw JSON/CSV, without
discarding large losses or changing the primary comparison after scoring.

## What the horizon diagnostic adds

The16-step forecast is the exact cached prefix of the same continuous64-step
imagined policy path: identical initial state, first16 actions, candidate
randomness and survival weighting. It costs no second rollout. No planner H,
candidate budget, decoder or loss was changed. Both choices are scored against
the same physically executed pair of192-step paths from a shared8-step probe.

Matched actual-first64 advantage MAE,64 versus16 forecast:

- Pendulum **41.465706 versus26.767961**.
- Acrobot **2.030465 versus2.205399**.

Actual192 advantage MAE,64/16/mean: Pendulum143.107283/153.460005/158.653451;
Acrobot19.274032/18.894944/39.223699. A lower magnitude error can coexist with
worse strategy choices; matched64 error improvement on Acrobot does not
establish192-step utility. Comparing the192-target mean prior on16/64 targets
is explicitly horizon-mismatched, not a fair short-forecast success criterion.

The result does not support simply extending the outer forecast as a remedy.
It does not yet identify compounding model error as the cause: imagined and
actual controllers can choose different later actions as their states diverge.
Action-matched model evaluation is needed before assigning that mechanism.
No additional horizon, architecture, feature or regularization search was run.

## Integrity and costs

All8224 expected journal case/controller/tick identifiers reconcile. Verification
replayed every predicted reward/survival path, actual reward/transition chain,
paired seed, shared tail, restored fingerprint, original first action and both
forecast receipts. The16-prefix score was fsynced before actual outcomes, with
its extended checksum verified alongside the64 forecast receipt. Four model
state/RMS fingerprints, four checkpoint bytes/eight source files and **393
pre-existing JSON** remain unchanged. Existing historical artifacts and the two
unrelated untracked adapter files are preserved. No H17 or E2.17 execution.
Seed exclusions cover current artifact/config metadata, all original source
arrays and conservative historical reservations; unavailable external records
remain outside coverage.

Real interactions **6272**:128 shared-probe and6144 control.
Imagined transitions **12224512**:3055616 policy forecasts,8192 common-tail,
9160704 actual-controller planning. **485888 model calls and observed top-level
forwards**:122880 forecast,512 common-tail,362496 control. No unknown work,
fits or neural updates. Prefix reuse and64 logical method returns execute no
additional interactions beyond32 physical controller paths. Counts are not FLOPs.
Forecast work is4× the16-step forecast, not4× total experiment computation.

Parent wall **67.85799916701217s**, below180s cap; worker CPU67.118962s.
Worker peak RSS472285184 bytes. Verification3.6271712079906138s with0 additional
real/imagined/model work. Final carried ledger:
**1020.1172516680078 used /2579.882748331992 remaining**.
No subsequent scientific experiment executed in this branch.

## Tests and reproducibility

Pre-run focused108 passed in4.13s;33-module relevant regression629 passed in
14.36s. Exact16-prefix reuse, survival arithmetic,64-step completeness, nonfinite
and hash corruption, fresh seed isolation, immutable model checks and source
fixture gates are covered alongside existing restoration/resource tests.
The final saved-capture regression and exact commands are recorded separately
in e3_11d_test_report.json. The entire historical suite was not run: legacy
model-inference benchmarks remain excluded from this verification scope.

Execution and verification (CPU thread variables1, PYTHONDONTWRITEBYTECODE=1,
PYTHONPATH=src:.deps):

```
python3 scripts/run_e3_11_post_probe.py --horizon-calibration
python3 scripts/run_e3_11_post_probe.py --horizon-calibration --verify
python3 scripts/summarize_e3_11d_horizon.py
```

Exporter and saved-capture test were added after collection; neither changes
the locked worker, scientific rule or raw outcomes. Exact runtime dependencies,
execution/code/config/protocol hashes and journal hashes are in the capture.
Consumed usage/output records reject re-execution. Large checkpoint binaries
are not added to Git; replay tests use saved numeric data without loading them.

Raw capture SHA256:
bdec3ef801065d3d3e49e92a5b1c3ee3e62866d234457011b335834fadcd470d.
Artifacts e3_11d_horizon_calibration.json, e3_11d_horizon_validation.json,
e3_11d_horizon_predecision.jsonl, lossless journal parts, summary and64-row CSV.
Return gain and regret reduction are mathematically dependent, not independent
evidence. All query data are now closed to tuning/repeated-success claims.

## One next scientific question

**Do compounding dynamics/reward errors remain when the frozen models are
rolled forward using exactly the recorded actual actions?** Recommend a separate
source-only action-matched replay of these saved trajectories, comparing
teacher-forced one-step error and open-loop cumulative reward error. This needs
no new simulator interactions or model fitting and distinguishes model rollout
error from imagined-policy action divergence more directly. It is proposed,
not executed here. Do not extend the horizon again or enlarge the learner
before resolving that distinction.
