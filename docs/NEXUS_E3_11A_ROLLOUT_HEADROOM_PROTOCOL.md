# E3.11A — Controller-specific forecast headroom (source only)

Base f7c698a91bb56f8cb21fb90b8f9eaab83142218f; branch
`codex/e3-11a-controller-rollout-headroom`. Do not reuse E3.12's mutation-credit
name for this prerequisite diagnostic. Read-only access to frozen models and
original source observations; no simulator construction/steps, fitting, new
physics, holdout registration or closed E3.11 evaluation outcomes.

## Fixed question and method

E3.11 forecasts collapsed when first actions agreed. H-headroom: following
each controller's own future decisions inside the same frozen model can
produce different action paths and cumulative reward forecasts despite equal
first actions. Null: such distinguishability is not demonstrated in this
prespecified source grid. This is forecast expressiveness, not calibration,
return improvement, selection learning or autonomous discovery.

Four hash-verified E2.9 source residual64×64 MLPs, same source normalization
and buffers. Use original TRAIN observation rows0,32,64,96/model (16 contexts).
No data-dependent selection. At each context run each fixed controller for16
imagined policy decisions, using its own predicted state at subsequent steps.
Each inner search remains existing H16/cap1536: successor31 tails/root, rank
blend48 flat+15 successor tails/root. Evaluate chosen action with one further
charged model row to advance the predicted state. Sum published step reward
with cumulative predicted survival. Run all16 steps, without early pruning.

Paired candidate RNG seed =731003 +100000×family_index +20000×bundle
+1000×source_offset_index +step. Candidate randomness is shared by the two
controllers, isolated from model loading and all environment seeds. These are
engineering inference seeds, not scientific holdout seeds. Never adjust inner
planning, model weights, or policy rules from outcomes.

Reuse the two first actions already computed at rollout step0, explicitly
cached without additional inference. Score16 H16 sequences per first action,
sharing15-action IID tails with seed=paired_initial_seed+500. This repeats the
common-tail evidence comparison as a reference; it adds512 model rows/context.
No empirical return or advantage labels are used anywhere in this audit.

## Registered screen and interpretation

Record per context/model: first-action agreement, later action disagreement,
all predicted states/probabilities/rewards/actions, cumulative score gap,
common-tail score gap and endpoint distance. Primary cohort is first-action
agreement. Each family must contain at least one such context where later
actions differ AND absolute controller-specific forecast gap>1e-6. If both
families meet this, label `controller_specific_forecast_headroom_visible`.
If a family has no equal-first-action context, label `headroom_unassessable`;
otherwise failure label `controller_specific_headroom_not_established`.
Report each model and all contexts; no posthoc threshold change.

Even a pass says nothing about real-environment accuracy or beneficial control.
Source observations and frozen models are already inspected development assets.
Do not count16 contexts as independent model replications; only two models/
family. No significance/generalization claim or pooled return scales. Different
imagined trajectories may compound model error. A negative result is valid;
do not expand horizon, grids or architecture in this branch.

## Reuse, caps and integrity

Keep SAME post_probe.Host/Dispatch, ForwardCheckedStep, ReservationLedger,
generated_strategies.execute, planner_adapter, full_policy_source planning_ops/
DecisionJournal/state_hash and original world model/rewards. Extend the
existing E3.11 runner with an explicit --rollout-audit profile; do not create
another meter, learner, proposer or environment collector.

Per context:16×2×(1491 planning+1 advance) +512 common scoring =48256 rows.
16 contexts = **772096 imagined transitions**, **31232 model calls/forwards**,
**0 real interactions/updates**. Both branches and reference calls charged.
Top-level forward hooks must match receipts. Cap30 wall seconds, local CPU/
one thread; existing parent timeout/consumed-marker mechanism. Include failed
or interrupted time. Save partial rows/resources/active upper bound; no retries.
Carried ledger884.5235102100257 used/2715.476489789974 remaining.

Before execution commit config, tested implementation, protocol and exact-hash
allocation citing human standing authority. Verify checkpoint/source bytes,
network/RMS/context fingerprints and historical JSON before/after. Reject
missing/duplicate models, contexts, steps, conditions, nonfinite forecasts or
unreconciled work. Save raw results/journals and independently replay reward/
survival arithmetic and the screen without model inference. Commit results
separately and push without merging. No real episode collection authorized by
this profile. Keep E3.11's negative result and closed evaluation unchanged.
