# Frozen source-model headroom audit

Protocol, 2026-10-19; source-only inference authorized by the standing local
grant and the user's continuation of the registered next question. Base
`daa18d2c37157da591dded19f0bb3fe4e2e8dd9a`, verified local/GitHub. Branch
`codex/unified-frozen-model-headroom-audit`. Preserve historical artifacts,
checkpoints, closed splits, untracked E1 adapter files and other worktrees.

## Question and fixed scope

Does the existing common-neutral-continuation quality label have practical
headroom beyond forced anchors when evaluated with frozen learned source
dynamics instead of FakeStepModel? H-headroom: at least4/16 source states,
including2/8 per family, have at least1.0 raw predicted-reward unit of
grammar-best minus best-anchor headroom. Null: this source evaluator still
lacks that headroom. These are diagnostic thresholds, not control success.
No tuning, new learner, model fitting, generation search or environment data.

Use exactly the E2.9 disposable residual MLPs for model bundles0/1 in each
family. Verify all four checkpoint hashes against the existing fit-clock
manifest **before loading any**. Verify eight train/val array file hashes
against fit_clock.LOCKED_ARRAYS; do not read validation outcomes. The fit
runner checked those locked source arrays before fitting; the manifest
records checkpoint hashes and recipe but no execution SHA, so this is
consistency with recorded provenance, not independent attestation of training.
Keep E2.17 fits/arrays, historical confirmations and all other models unused.

For each frozen model, query opposite source bundle at offsets0/32/64/96,
unchanged32-row supports, candidate seeds700+offset. Bundles have disjoint
episode seeds but the same default physics. This is neither unseen physics
nor independent model-training replication across families. Four models,
sixteen context cells, no scientific confidence intervals. Reusing these
inspected source observations is deliberate; it is not fresh confirmation.

Reuse `disposable_model`, `generated_strategies`, `proxy_table`, existing
planner adapter/reward functions, `WorldModel.step`, and ReservationLedger.
The existing source-table routine gains an optional frozen model and explicit
counter names, preserving its default fake-model behavior. Do not replace
the canonical proposer, memory, world model or ledger. No scientific dispatch.

Freeze all parameters, eval mode and CPU device. Require residual MLP64×64.
Fingerprint weights and normalization mean/variance/count/epsilon before
and after inference; checkpoint file hashes must also remain identical.
The predictor/generator are **not trained or evaluated for improvement** here.

## Computation and label

Keep the342-policy grammar, H4/8/16 catalogue operators,1536 total strategy
budget (768 per rank-blend child), existing candidate arrays and common probe:
each of three possible first actions followed by fifteen neutral index1
actions, scored by the existing family reward/survival rules. The learned
model both proposes imagined trajectories and judges this probe. Report raw
per-action/strategy scores, anchor actions, grammar best, headroom, all cells.
This circular self-evaluation cannot establish actual decision quality even
if headroom passes. Different strategy names choosing the same first action
have identical labels. No full-episode policy value is estimated.

One **60-second dispatch cap**, checked before each forward and context;
local CPU only,0 real interactions,0 optimizer steps, no checkpoint writes.
At most590,592 imagined neural input rows, preplanned from16 contexts and
24 leaf/cap pairs plus48 common-probe rows each. Reuse exact leaf decisions;
reserve each batch before dispatch with the existing ledger. Actual model
calls/rows and completed/unknown reservations are reported separately.
The deadline is not preemptive OS interruption of an already-running forward.
Starting ledger333.966824167 used/3266.033175833 remaining. Debit complete,
failed or partial run wall time; do not reset past attempts or use E2.17 grant.

## Gates, tests and recording

Commit implementation/protocol/tests before neural scoring. Missing/wrong
files, recipe/device mismatch, source episode overlap, incomplete sixteen-cell
grid, nonfinite metrics, changed frozen state or budget exhaustion fail closed.
Save partial results with actual work; do not substitute models or rerun to
improve the screen. Source-only tests use byte fixtures, normalization and
tensor-like array fixtures, synthetic headroom grids, existing small fake
adapter tests; no new neural inference in tests.

Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/audit_unified_headroom.py`. Save `artifacts/unified_headroom_audit.json`
with source/config/model hashes, exact revision, per-state policy labels,
resource journals, runtime and prior JSON hashes. Preserve all prior outcomes.
If headroom fails, do not train another selector/generator on this label.
If it passes, establish independent label validity before claiming useful
learning. Choose one next step from actual evidence, not an architecture sweep.
