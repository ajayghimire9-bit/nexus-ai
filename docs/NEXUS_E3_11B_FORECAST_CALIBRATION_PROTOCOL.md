# E3.11B — Forecast direction versus actual paired returns

**Preparation v1, not authorized, not scientifically locked or executed.**
Starting local/GitHub revision: 4b8c305562e9c9b30e074d3bff2ecd5ec6cf18ea,
branch codex/e3-11a-controller-rollout-headroom. New preparation branch:
codex/e3-11b-forecast-calibration-preparation. The user's six-milestone roadmap
explicitly says this experiment is not yet authorized. Standing research
authority does not override that narrower restriction. No allocation is created.

## Question and competing explanations

Do fixed controller-specific 16-step imagined forecasts predict the direction
of fresh paired 192-step actual return differences better than common-tail
forecasts and a legitimate training-model mean? E3.11A established numerical
distinguishability only; E3.11's failed selector remains closed.

Possibilities include useful policy-specific evidence, model hallucinations,
a short-versus-long horizon mismatch, and a training-mean prior that remains
stronger. Record negative and inconclusive outcomes without tuning forecasts.
This is known-source-model development calibration, not unseen-task confirmation.

## Proposed fixed design

Executable settings: configs/e3_11b_forecast_calibration.json. Four existing
frozen E2.9 residual MLPs: Pendulum/Acrobot × bundles 0/1; original source-default
physics, original normalization, no fitting. Pin checkpoint inventory and
TRAIN-only E3.11 prior by SHA256. Recheck individual binary/source-array hashes
and model/RMS fingerprints before and after any separately approved execution.

Four fresh episodes/model, sixteen paired contexts total. Collect eight shared
uniform-random probe transitions. Restore identical complete simulator state,
wrapper counters and RNG for each controller's 192-step actual continuation.
Use paired planner streams indexed by original episode step, not action or
controller identity. No mid-episode switching or online update.

Existing controllers are successor_anchor and rank_blend. Their existing
H=16, cap1536 implementations actually use 31 successor tails/root versus
48 flat plus 15 tails/root: both1491 imagined transitions/decision, respectively
51 and67 model calls. This is not the historical 16-candidate latent controller.
Do not change these algorithms to fit a misleading candidate-count description.

Before either actual path, persist all three predicted rank-minus-successor
advantages and an acknowledged immutable receipt:

- policy_forecast: two repeated-controller 16-step imagined paths, including
  charged next-state advances, published rewards and cumulative predicted survival;
- common_tail: existing 16×16 shared-tail score maximum per controller's first
  action, reusing step-zero proposals, identical tails when actions agree;
- training_mean: original pinned E3.11 TRAIN means, not its fitted ridge
  correction and never any closed evaluation outcomes.

Reuse rollout_headroom.walk, post_probe.Host/Dispatch/planning_ops/restore_copy,
the existing controller execute, rewards, ReservationLedger and ForwardCheckedStep.
No replacement learner, memory, planner or resource meter. Source/data/schema
metadata are permitted; simulator physics/state are trusted evaluation-only data.

Numerical seed registration remains **null**. Upon explicit approval, register
independent reset/probe/planner/common-tail roles, paired across controllers and
model bundles within family, disjoint from all closed roles. Forecast planning
uses the corresponding continuation tick stream; common tails use an isolated
stream. Audit exclusions before committing numbers. No seed selection based on
returns or reuse of E3.11, E3.11A, H12–H17 or reserved confirmation outcomes.

## Primary and secondary analysis fixed in advance of execution

Primary target: sign of actual rank-minus-successor **192-step undiscounted**
return, excluding the shared probe. Each forecast uses its own natural horizon;
do not scale 16-step forecasts by twelve or fit a posthoc calibration.

Accuracy: correct decisive sign=1, wrong sign=0, forecast or actual numerical
tie=0.5; tie tolerance1e-6. Report tie rates separately; the half credit is a
declared convention, not a claim of randomized controller selection. All methods
choose successor on a forecast tie. Include all16 contexts, without filtering
by first-action agreement. That agreement is a secondary descriptive stratum.

Average episodes within each pretrained model, then equally average the two
models within each family. Do not pool reward scales across families. Paired
exploratory t95 intervals use df1, critical12.706204736432095, across two model
differences/family, never episodes/candidates as independent model replications.
These sparse intervals cannot establish broad generalization.

Practical **point screen**, separately in both families: policy-forecast accuracy
at least0.125 higher than EACH baseline, positive mean selected-return gain
against each, and nonnegative selected-return gain in both model bundles against
each. All conditions must pass. Report intervals regardless; a passing point
screen with intervals including zero remains exploratory, not statistically
confirmed control improvement. Label failure forecast_utility_not_established;
invalid/incomplete data never receives a scientific pass/failure label.

Secondary: selected-return difference, two-controller selection regret, raw
predicted/actual advantages, first16 actual advantages, magnitude MAE, ties and
per-model/per-episode failures. A 16-versus192 magnitude comparison is explicitly
a horizon-mismatched diagnostic; good short-horizon error alone is not primary
success. Keep raw actual immediate rewards for both complete paths. Undefined
correlations, if later reported descriptively, must be null with reasons rather
than dropped or replaced with zero. No correlations are required for the screen.

## Proposed accounting and cap — no allocation yet

16 × (8 probe + 2×192 continuation) = **6272 real steps**.
16 × (47744 policy forecast +512 common tails +2×192×1491 control) =
**9932800 imagined transitions**. Model calls and top-level forwards each:
16 × (1920 policy +32 common +192×118 control) = **393728**.
Zero neural/ridge fits. This excludes support-error inference, which is not
needed in this calibration and must not be silently added. Cached returns add
zero executed interactions. Forecast and control costs must be reported apart.

Estimate1–2 minutes from preceding runs; proposed cap180s local single-thread
CPU. Checkpoints already local; no paid services. A timeout, failed model call,
missing cell, unknown work or fingerprint mismatch means honest incomplete or
invalid capture, no automatic retry. Peak memory must be measured, not invented.
Carry session ledger **889.765542043008 used /2710.2344579569917 remaining**.
Preparation consumes zero scientific execution; do not reset this ledger.

## Implemented preparation and remaining execution prerequisites

forecast_calibration.py provides strict settings/grid/numeric validation,
TRAIN-only prior checks, callback-based durable forecast-before-outcome capture,
and model-level primary/secondary analysis. Tests use authored scalar rewards
only. prepare_e3_11b_forecast_calibration.py verifies pinned metadata without
runtime imports; --execute deliberately fails closed.

It is **not a bound real-environment worker**. Before collection: obtain explicit
execution approval, commit fresh seed/exclusion registration and exact-config
allocation, bind callbacks into the existing metered host, verify byte hashes,
add whole-environment restoration/resource-journal/timeout tests, enforce
one-run consumption and snapshot all previous artifacts. Commit the reviewed
worker and final protocol before outcomes. Result validator must reconcile raw
reward/state continuity, frozen fingerprints, receipts and journal totals;
the preparation's arithmetic-only validator is insufficient on its own.

## Conditional roadmap

E3.11C should test cheaper forecasts only after calibration reveals useful
ranking information. E3.12 mutation-credit learning, E3.13 A→B→A→C persistence,
E3.14 experiment selection and E4.0 bounded learning-rule adaptation remain
separate proposed studies, not demonstrated capabilities or current execution.
No new architecture is justified by numerical forecast differences alone.
