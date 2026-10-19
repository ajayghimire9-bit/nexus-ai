# E3.11B — Fresh forecast/actual-return calibration: execution lock v1

Branch codex/e3-11b-forecast-calibration, starting from preparation commit
6831102935c58d88f715e778836d15530cc0fcf8. The human's subsequent “continue
please” follows the explicit180-second/6272-step approval proposal and is
interpreted as approval of that scope, together with the standing local CPU
grant. No fabricated human quotation or additional budget is implied.

This final executable lock supplements the immutable preparation protocol
NEXUS_E3_11B_FORECAST_CALIBRATION_PROTOCOL.md. It changes no scientific estimand,
threshold, model, controller, analysis or budget. Preparation files stay intact.
Code/protocol/config/allocation must be committed before outcomes. One run only,
no automatic retry; time cap180s, max6272 real steps and9932800 imagined rows.
Maintain the carried ledger889.765542043008/2710.2344579569917, CPU only.

## Numerical registration and input provenance

Executable source: configs/e3_11b_forecast_calibration_execution.json. Two
source-default physics families Pendulum/Acrobot × four episode indices0–3,
crossed with the same two frozen source model bundles. No new physics or
confirmation data. Both controllers share all eight real probe transitions.

Independent role bases: reset2131000000, planner2132000000, probe2133000000,
common-tail2134000000. Each adds family_index×10000 +episode_index×1000,
with family order [pendulum,acrobot]. Same roles across model bundles. Planning
uses base+original tick8–199; forecast decisions use matching ticks8–23.
Common-tail arrays use common-tail base+1; the base itself is conservatively
reserved too. Uniform probe actions come from their separate role stream.
No action-dependent RNG consumption or controller-specific seed offsets.

Before dispatch, audit all current research artifact/config seed metadata, all
twelve original source-array env_seeds and the conservative H17 exclusions.
Unavailable external runs remain outside the stated coverage; do not claim
global seed completeness. Store the zero-collision audit in results. Pin all
four frozen checkpoints/eight input arrays via E3.9 inventory and the immutable
TRAIN-only E3.11 prior via preparation settings hashes. Byte-verify before and
after; no training or numerical fallback. No E3.11 evaluation labels are used.

## Execution and durable ordering

Reuse run_e3_11_post_probe.py with explicit --calibration profile, existing
post_probe.Host/Dispatch/restoration, rollout_headroom.walk/forecast replay,
planners/rewards, ForwardCheckedStep and ReservationLedger. This profile adds
no learner, planner or meter. Original runner profiles and output paths remain
unchanged. The preparation checker continues refusing execution.

For each context:8 probe interactions, then both16-decision imagined policy
paths, then existing common-tail forecasts using the cached initial actions.
Save raw observations/actions/termination probabilities/reward/survival paths.
Use all three frozen advantage forecasts exactly as registered. Persist and
fsync an acknowledged per-case prediction receipt BEFORE either actual path.

Clone the complete post-probe wrapper/simulator/RNG for each192-step controller
continuation. Match restored fingerprints, paired planner ticks and the first
predicted action against its executed action. Save every actual immediate
reward and transition, validate published reward timing/continuity and time-limit
truncation at tick199. No outcome-driven changes, fitting or online switching.
Parent enforces180s subprocess deadline and exclusive consumed allocation.
If interrupted, save incomplete data/resources and active-case upper bound;
do not present it as completed science or rerun on these seeds.

## Frozen analysis and decision

All rules remain those of the preparation protocol/config. Primary: accuracy
of rank-minus-successor forecast direction versus actual192-step difference.
Forecast/actual ties within1e-6 get0.5 accuracy; selection ties choose successor.
All16 contexts included. Compare policy_forecast against common_tail and
pinned training_mean. Average four episodes per model, then two models/family;
never pool family reward scales or count episodes as model replications.

Point screen requires >=0.125 accuracy gain against BOTH baselines in BOTH
families, positive selected-return gains against both, and nonnegative gains
in each model. Report paired t95 df1 intervals even on point-screen passage;
they remain exploratory and unadjusted, not confirmation. A failed complete
screen is forecast_utility_not_established. Incomplete or invalid execution
has no scientific pass/failure label. Separate first16 actual advantages and
magnitude errors to expose horizon mismatch; never rescale or calibrate on
this sample. Preserve raw per-case failures and all baseline comparisons.

## Accounting

Probe:128 real/0 imagined/0 forwards.
Policy forecast:0 real/763904 imagined/30720 forwards.
Common-tail:0 real/8192 imagined/512 forwards.
Control:6144 real/9160704 imagined/362496 forwards.
Total6272 real/9932800 imagined/393728 calls and top-level forwards, no fits.
Cached selected returns add0 executed steps. Raw lossless reservation/settlement
journals rotate every1500 decisions; all6688 stage records must reconcile.
Report parent wall/worker CPU/worker peak RSS and charged verification time.

Saved-data --verify replays forecasts, actual rewards/continuity, exact grid,
prediction receipts, executed-source hashes, historical JSON preservation,
frozen binary/source hashes, forward counts and per-stage journal totals without
new inference or simulation. No other scientific experiment is authorized by
this lock. E3.11C–E4.0 remain separate conditional proposals.
