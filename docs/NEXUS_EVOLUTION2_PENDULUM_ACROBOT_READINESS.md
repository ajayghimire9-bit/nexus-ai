# Pendulum→Acrobot protocol readiness review

Status: **NOT_READY_FOR_SCIENTIFIC_EXECUTION**.
Reviewed lock: `docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL.md`
(v1, SHA256 `c97f307b080daa1e8a4dfacfc9f3172ab8701f8203323ecc8245c026666c3ab2`).
Requirement source: `docs/NEXUS_EVOLUTION1_FEASIBILITY.md`.
Superseding design: `docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2.md`.

No collection. No holdout named. H17 unchanged. Ledger
**305.842 / 3294.158**.

v1 is preserved as historical evidence. It is not the executable
protocol.

## Verdict

The v1 lock correctly refuses collection and leaves the Acrobot
instance unnamed. Against the Evolution-1 feasibility contract it is
**statistically weaker, incompletely replicated, missing fairness
controls, outcome-undefined, operator-incompatible, and
resource-undercounted**.

## Defects

### 1. Statistical weakening

Feasibility §7 requires a memory-minus-control mean of at least 0.05
of a **fixed analytic reward range** and a positive simultaneous
interval against **all five** controls (random, evolution, reset,
fixed flat, fixed successor). Intervals are Bonferroni familywise 95%:
each comparison 99%, df 9.

v1 primary is persist−reset only, ordinary 95% Student-t, and
“interval entirely above 0” with **no practical margin**. Secondary
contrasts are not familywise-controlled. Raw Acrobot return is not
range-normalized.

### 2. Incomplete independent replication

Feasibility requires ten independent **search/model-bundles**:
independently initialized family models and an independent proposal
trajectory, methods paired inside a bundle.

v1 says “10 independent source-training seeds.” That does not lock
independent world models, paired method seeds, or averaging inside a
bundle. Episodes remain correctly excluded; the replication unit is
still weaker than the required bundle.

### 3. Missing fairness controls

Feasibility methods:

- uniform random without replacement
- equal-budget evolution (population ≤4, tournament 2, one legal
  operator-coordinate mutation)
- memory-conditioned proposer
- the same proposer reset at the family boundary
- two non-search anchors: fixed H=16 flat and fixed H=16 successor
- two anchors consume proposal slots; four later proposals; 12
  variants; six slots per family
- counterbalanced A/B training order

v1 has one unnamed “fixed” catalogue index, not both anchors.
Evolution is described as “mutation/crossover.” Retrieval is added as
a weight-guard story rather than the required reset ablation of the
same proposer. Training order is Pendulum→Acrobot only. Proposal-slot
and no-duplicate-evaluation rules are absent. Default Pendulum
`(10, 1, 1)` is a historically occupied source; feasibility required
**new** source and development tasks, not closed-suite reuse.

### 4. Undefined outcomes

Feasibility labels: `development_screen_failed`, `inconclusive`,
`negative_transfer`, `transfer_screen_passed`, `incomplete_budget`,
`invalid_integrity`, `invalid_leakage`.

v1 labels only `persist_beats_reset_{established,not_established,blocked}`.
Missing cells, nonfinite values, hash mismatch, and budget censoring
have no invalidation rule. A complete nonsignificant run is not
distinguished from an incomplete one.

### 5. Incompatible catalogue operators

The locked Evolution-1 catalogue is 12 variants:
`{flat, successor} × {iid, balanced_first_action} × {4, 8, 16}`.
Legal search mutation flips one coordinate. Crossover is not a
catalogue operator. `evolution2.methods.EvolutionarySearch` already
mutates one coordinate and does not implement population-4 /
tournament-2.

v1’s “mutation/crossover” imports V0.1 architecture-evolution
language into a planner catalogue. That is an illegal operator.

### 6. Insufficient resource accounting

Feasibility first-screen worksheet: 97,600 real steps and an imagined
upper bound of 110,592,000 at 1,536 imagined transitions per
decision; CPU seconds and wall time both metered; cached matrix rows
still charged when revealed.

v1 authorizes 0 and proposes 300 s / 40,000 real / **0 imagined**.
Zero imagined is incompatible with any catalogue planner. 40,000 real
steps cannot host ten bundles × source fit × 12-variant matrix ×
development. A 300 s cap is likely `incomplete_budget` even for a
much smaller screen. CPU enforcement remains BLOCKED on the stub
host.

## Runtime host limits (no new framework)

Reviewed `src/nexus/evolution2/host.py` after H-R1–H-R5. Remaining
limits, not repaired here:

- Worker CPU is measured, not enforced.
- `RUSAGE_CHILDREN` can include unrelated child processes.
- Parent and worker share UID, environment, and filesystem. Process
  separation is not a sandbox.
- Physical `real_steps` remain 0. The worker is a synthetic fixture.
- No real planner, checkpoint, or family adapter dispatch.

These block scientific execution even after a corrected protocol.

## What v1 got right

Unauthorized allocation (`runs: 0`). Unnamed holdout. Occupied
Pendulum/Acrobot exclusion. MCC/H17 forbidden. Cross-family weight
copy forbidden. Synthetic E2 contract not promoted.

## Decision

v1 remains in the historical record. The executable design, if any
later lock is accepted, is **v2**. v2 is still unauthorized and still
does not name a holdout.
