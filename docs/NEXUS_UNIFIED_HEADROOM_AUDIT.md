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

## Completed result: no headroom

Execution `d1f8c3063592d9f8620ad388ea1d57575f0d956b`. Capture SHA256
`1fe3a89c736cec3c3cc8276a04e4afbbfe61bc57f258e5978ddef77a106b079c`.
All sixteen cells completed. The source-headroom screen failed: **0/16**
eligible states, **0/8 Pendulum**, **0/8 Acrobot**. Mean and maximum positive
grammar-minus-anchor headroom are exactly0.0 in both families. This is not
an improvement result or a failed learner: no learner was trained here.

The labels are not constant everywhere. Nine states have multiple selected
actions with different predicted probe values; seven states have only one
selected action across the grammar. Nevertheless the anchors already attain
the best grammar probe value in every state. The largest within-state spread
between strategies is14.7341 predicted units; that is worse-strategy variation,
not available improvement beyond the anchors. Per-policy raw values and first
actions are saved for every state. No model was tuned from these outcomes.

All four local checkpoint hashes match the E2.9 manifest. Eight locked source
file hashes match; the four model/RMS fingerprints remain exactly unchanged.
Only model bundles0/1 were loaded, with opposite-bundle query episodes. These
are inspected default source physics; no reserved confirmation was accessed.
The manifest's lack of original execution revision remains a provenance
limitation. Historical residual max-score catalogue results remain closed;
this audit used the separately declared common-continuation action label.

Cost: **1.433380s wall /1.5245s CPU**, **8,000 neural model calls**,
**438,336 imagined neural input rows**, zero real interactions, fits or
optimizer updates. All sixteen reservation plans completed. All316 previous
JSON artifacts verified unchanged. Ledger now **335.400204625 used /
3264.599795375 remaining**; the earlier incomplete unified attempt remains
included in the starting ledger. Local CPU only, no new binaries written.
Checkpoint binaries remain local dependencies rather than newly tracked files;
the explicit runner fails clearly if missing or mismatched.

Pre-execution selected regressions155 passed in1.84s; final **157 passed
in2.00s**. Final tests add saved-data arithmetic/provenance and boolean-ID
rejection. The latter is validator hardening after capture, not a rerun or
metric change. No full training/simulator suite was invoked. Tests verify
JSON and executed source via Git without requiring local checkpoint binaries;
the explicit audit command still requires those exact binaries.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest \
 tests/test_unified_headroom.py tests/test_unified_e225_e30.py \
 tests/test_evolution2_return_scoring.py tests/test_evolution2_feedback_integration.py \
 tests/test_evolution2_feedback_normalization.py tests/test_evolution1_resources.py \
 tests/test_evolution2_planner_adapter.py -p no:cacheprovider -o addopts='' -q
```

## One next step

Prepare a **full-policy source-physics return protocol** comparing a small,
frozen subset of generated policies with the anchors, so the generated rule
affects repeated decisions rather than only the first action before a neutral
continuation. Estimated planning upper: two families ×two existing models
×two episodes ×four controllers ×50 steps =1,600 new environment steps and
at most2,457,600 imagined transitions. Full runtime is unmeasured; a proposed
180-second cap is a planning estimate, not an allocation or authorization.
No seeds, policies or holdouts are selected here; no environment constructed.
Separate collection authorization and a locked fair protocol are required
before executing. Do not fit another predictor/generator to the saturated
label or claim that self-evaluation establishes actual control quality.
