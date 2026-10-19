# E3.12F — Reset-blocked exploration runner integration

**Engineering preparation; unregistered, unauthorized for collection, unrun.**
Base: `e13c863ce221f6fbe9d60ebae918844fdf279a24`.
Branch: `codex/e3-12f-runner-integration`. GitHub fetched before branching;
local base matched its pushed revision. Preserve unrelated untracked
Evolution-1 adapter files. No historical artifact/config/protocol is rewritten.

This supplements `NEXUS_E3_12F_RESET_BLOCKED_PREPARATION.md`. It does not
change its proposed scientific estimand, screen, models, operators, feedback
budget or resource ceilings, and is **not a scientific protocol lock**.

## What is implemented

The SAME `scripts/run_e3_12_mutation_control.py` accepts `--reset-blocked`.
It dispatches to `reset_blocked_study.py`, which reuses `reset_blocks`,
`partial_feedback.parent_inclusive_decision`, `operator_headroom.validate`
and its paired interval helper. Actual future operation remains through SAME
`post_probe.Host`, `Dispatch`, E1 `ReservationLedger`, original planning
operators, world-model loader and per-call instrument. No alternative learner,
memory, planner, resource meter or simulation runner is introduced.

The runtime configuration is `configs/e3_12f_reset_blocked_runtime.json`.
Its executable validator fixes the recipe and requires the complete four-model
registration grid. It currently has null environment/planner/schedule seeds,
`prepared_not_registered` status and `execution_authorized=false`.
There is deliberately **no allocation file**. The run, worker and preflight
paths reject this template before host access, model loading or environment
creation. Merely changing the status is insufficient: fresh complete seeds,
collision audit, exact config/protocol allocation hashes, clean code, unused
output paths and standing-resource checks remain required.

## Ordering and permitted feedback

For each model the future worker first obtains the eight registered public
reset observations through an injected observation-only callback. It builds
both schedules using the existing matching rule, writes an exclusive schedule
file and hashes it **before any training return**. Recreating each training
reset must reproduce its registered observation exactly.

The worker executes the shared union of required training children and parent.
It never sends that union to mutation credit: this profile instantiates no
`StrategyGenerator`. Before the first query environment is opened it constructs
the strict one-child-per-reset projections, invokes the SAME parent-inclusive
raw selector, and exclusively saves both frozen decisions. It executes parent,
switch and rank-blend on each paired query reset, without updating choices.
The pure selector filters query rows before reading path fields; opaque query
dictionaries are used to test this boundary.

Every physical decision receipt records its schedule file hash and, for query
work, its frozen-decision file hash. Independent verification checks each
family/model/reset/condition/tick exactly once, rejects duplicates or unknown
work, checks seal references, and reconciles actual call/forward/imagined/real
totals. The files and hashes are rechecked after collection. This is trusted
runner/data-boundary enforcement, not a claim of filesystem tamper resistance
against a user who can rewrite the repository and all evidence.

## Exact work versus upper caps

Shared union collection can cost less than the maximum. The existing panel
validator now has an optional, explicitly supplied `planned_real_steps`:
F derives it from all four validated schedules; default behavior for all older
profiles remains exact equality with their original `real_cap`.

F requires exactly its schedule-derived 22,400–28,800 real steps, including
9,600 query steps, not an arbitrary partial grid below 28,800. Caps remain
44,236,800 imagined rows, 1,440,000 model calls/forwards and 300 seconds.
Physical paths are counted once; each logical selector gets exactly sixteen
revealed training returns/model. These are prospective limits, not measured
performance or matched FLOPs. No source collection or neural fitting is added.

The parent timer starts before F's preflight and subtracts elapsed time before
starting its worker timeout; post-run preservation checks are included in the
recorded execution time and an overrun invalidates completion. Independent
offline receipt verification is timed and charged separately to the carried
session ledger, as in previous studies. A cap-hit run remains consumed and
incomplete; it is not automatically retried.

## Statistics and independent export

The production analyzer validates the full config-derived grid, recreates all
choices and averages four queries inside each independent model before making
the two-model/family (df=1) paired interval. It never pools reward scales across
families. The existing stdlib exporter now supports `--reset-blocked`; it
independently recomputes masked training means, tie-breaking, physical phase
costs, family contrasts and the screen, rejecting missing contrasts, shortened
interval arrays, nonfinite values and wrong choices.

Primary remains blocked-minus-random-balanced selected actual return. Both
families must have mean gain at least one point, positive lower 95% bound and
positive model differences. Secondary fixed parent/children/uniform comparisons
are descriptive; uniform is an expected mixture of shared paths. An identical
choice produces identical cached returns, not independent supporting evidence.
Two models per family leave very limited statistical power. No success label
can come from authored fixture values or a complete engineering test.

## Verification and remaining scientific gate

Tests include strict schema/recipe checks; rejection before host access;
public-observation callback ordering; exclusive seals; opaque queries;
incomplete/malformed grids; reward, resource and frozen-model checks;
model-level rather than episode-level intervals; independent stdlib export;
duplicate receipts and wrong seal references; and the production worker with
**all world, host and model operations replaced by authored callbacks**.
That last test does not execute its planning body or any simulator/model step.
It exercises profile selection, orchestration, projection and seal ordering.

An initial authored-host test failed because its Acrobot fixture used -1
instead of the existing dense hang-down reward -2. The published-reward
validator caught this; only the test fixture was corrected. No scientific
data or reward function changed. Exact commands/counts and preserved-file
hashes are recorded in `artifacts/e3_12f_runner_integration.json`.

No new simulation, checkpoint inference/training, numerical scientific seed
registration or allocation occurred. The carried research ledger stays
**1808.9990201649957 used / 1791.0009798350043 remaining**. Main and historical
evidence remain unchanged. Continual learning, E4 rule utility and transfer
remain untested by this work.

One next scientific action: register and authorize this concrete fresh
random-balanced versus public-blocked comparison, commit its exact protocol,
configuration and allocation before collection, and execute once within the
proposed cap. Current no-simulation scope remains in effect; no run starts
automatically from this engineering work.
