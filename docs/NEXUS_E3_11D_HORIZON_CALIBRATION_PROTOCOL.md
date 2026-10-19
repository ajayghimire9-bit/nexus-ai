# E3.11D — Longer forecast horizon, fresh paired calibration

Registered before outcomes on codex/e3-11d-longer-horizon-calibration, starting
from GitHub/local8e9a514398d751d1dd31bf969c90136ff3a561a0. E3.11C's efficiency
study remains deferred; D denotes this distinct horizon-mechanism test, not
an efficiency success. The human explicitly authorized locking/running/pushing
this longer-horizon test within the existing standing local CPU limits.

## Hypothesis and fixed intervention

A **64-decision controller-specific imagined forecast** improves prediction of
the direction of192-step actual planner advantage and the resulting one-time
strategy selection, compared with its16-decision prefix and the frozen TRAIN
model-mean prior. Competing explanation: compounding model errors make longer
forecasts no more useful or worse. Numerical differences alone cannot pass.

Same four frozen E2.9 source-default Pendulum/Acrobot models (two bundles/family),
source normalization/reward and successor_anchor/rank_blend controllers. H=16
and cap1536 remain unchanged:1491 imagined rows/actual decision,51/67 forwards.
Only the outer forecast duration changes, not the MPC planning horizon.
No neural/ridge fitting, source data changes, confirmation access or new physics.

For each fresh case collect8 shared uniform probe steps; generate one64-step
imagined path/controller. The16-step score is its exact prefix, with the same
initial state, actions, candidate randomness and survival weighting. No second
short forecast is executed or charged. Frozen policy64, policy16, common-tail
and original E3.11 TRAIN mean are sealed before either actual continuation.
Existing common-tail remains a secondary reference, not an additional primary
screen. Run both unchanged controllers for192 actual steps from identical full
post-probe restoration, with paired tick-indexed planner seeds.

Reuse SAME run_e3_11_post_probe.py --horizon-calibration, calibration_execution
worker/validator, Host/Dispatch, walk, evidence, rewards, ReservationLedger and
ForwardCheckedStep. horizon_calibration is configuration/statistics glue only;
no parallel learner, memory, planner or metering implementation. Generalized
forecast replay defaults to16 for all old profiles; old artifacts stay intact.

## Fresh registration and provenance

Families [pendulum,acrobot], bundles[0,1], episodes[0,1,2,3]:16 paired cases.
Source-default physics only. Seed bases reset2141000000, planner2142000000,
probe2143000000, common-tail2144000000; add family_index×10000+episode×1000.
Same streams across bundles and controllers. Planner ticks8–199 actual and
8–71 imagined; common-tail arrays use their independent base+1. Reserve both
common base/base+1 conservatively. No action-dependent seed consumption.
Audit current artifact/config metadata, all original source env_seeds and H17
conservative exclusions before dispatch; disclose unavailable external coverage.

Execution config pins immutable preparation settings/TRAIN prior, E3.9 checkpoint
inventory, and E3.11B validation/ledger. Verify all four checkpoint/eight source
byte hashes and frozen net/RMS fingerprints before/after. Closed B returns are
not fit labels, new features or new test data. No seed/outcome reuse. Independent
allocation is one-run, consumed before worker launch; no automatic retry.

## Primary analysis and prespecified screen

Direction of rank-minus-successor actual192-step undiscounted advantage, probe
excluded. Forecast or actual ties<=1e-6 get0.5 accuracy; forecast selection ties
choose successor. All16 contexts included without posthoc first-action filters.
Compare64 versus16 and64 versus TRAIN mean. Average four episodes within model,
then equally average two models per family; never pool family reward scales.
Paired unadjusted exploratory t95 across two pretrained models/family, df1,
critical12.706204736432095. Episodes/candidates are not independent replications.
T intervals can exceed feasible accuracy bounds; retain the frozen estimator.

Point screen in BOTH families: >=0.125 accuracy gain against EACH primary
baseline, positive mean selected-return gain against each and nonnegative
selected-return gain in every model against each. Intersection screen, no
alternative horizon selection or favorable subgroup promotion. Passing remains
exploratory; intervals including0 do not establish a confirmed improvement.
Failure label longer_horizon_utility_not_established. Missing/nonfinite work,
hash mismatch, cap exhaustion or incomplete grid is invalid/incomplete, not a
scientific negative result. No retuning/rerunning on these cases.

Secondary: actual first16 and first64 advantage MAE, actual192 advantage MAE,
per-model/case curves and failures, selected returns/regret, common-tail,
forecast survival and costs.16/64 forecasts have naturally different reward
magnitudes; no rescaling/fitted calibration from query outcomes. Model-mean
prior targets192 and is not a matched64 forecast. Regret reduction and return
gain are mathematically dependent, not independent confirmations. Support
reward/actual state paths stay inaccessible to any fitting, because no fitting
occurs. Simulator internals are restoration/audit metadata only.

## Resource lock and stopping

180s local single-thread CPU cap; estimated65–100s using B's measured55.86s
and the extra forecast calls. 6272 real=16×(8+2×192),128 probe+6144 control.
Policy forecast3055616 imagined/122880 forwards; common8192/512;
control9160704/362496. Total **12224512 imagined/485888 model calls and
observed top-level forwards**,0 fits. Prefix16 reuse adds0 executed work.
Cached method returns add0 environment interactions. These are counts, not FLOPs.
Peak RSS, worker CPU, parent wall and saved-data verification time recorded.
Carry session ledger948.6320812930051 used/2651.3679187069947 remaining.

Commit protocol/config/allocation/tested code before collection. Record clean
execution SHA/hashes; preserve every previous JSON and checkpoint. Resource
journals rotate1500 decisions;8224 planned stage records must reconcile with
the exact expected case/controller/tick set. Forecast file is fsynced before
outcomes, including extended16-prefix checksum. Parent deadline saves partial
capture and active-work upper bounds on interruption; no silent sample reduction.
Saved-data verification replays source hashes, complete grid, rewards, forecasts,
receipts, immutable weights and journal counts with0 extra neural/simulator work.

## Decision

If64 fails, retain failure and distinguish short-horizon mismatch from longer
model error descriptively; do not claim no useful forecast can exist. Do not
start efficiency tuning, larger models, mutation learning or new continual
experiments automatically. Recommend one next question from the evidence.
This test cannot establish autonomous self-improvement, general control or AGI.
