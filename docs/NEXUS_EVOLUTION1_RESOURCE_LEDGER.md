# Evolution-1 pre-call resource ledger

Status: **SOURCE_LEDGER_TESTED — SCIENTIFIC_RUNTIME_STILL_BLOCKED**.
Branch: `codex/evolution1-resource-ledger`.
Starting revision: `d5339de7b103569453ab15293c7c2fc1995aefb6`, matching the
refreshed GitHub adapter-review reference. The starting tree was clean.
This implements the source-only milestone in `NEXUS_EVOLUTION1_ADAPTER_REVIEW.md`.
It is not a scientific protocol, allocation, execution approval or experiment.

## Implemented state machine

`src/nexus/evolution1/resources.py` accepts a trusted host's fixed tuple of
typed operations and immutable limits. The plan allows at most8192 uniquely
named operations. It has no evaluator callback, model, environment, source-code
field, file/network access, timer reader or execution entry point.
The existing proposer wire format is unchanged; proposers cannot create or
replace ledgers through that message interface.

Each operation declares real steps, imagined transitions, model API calls and
underlying network-forward calls separately. One environment operation represents
exactly one step. `model_work` uses **observation rows**, not action-array size;
an eight-row batch with a single broadcast action charges eight imagined
transitions. A one-dimensional observation is one row. Invalid/empty shapes,
ambiguous action-row counts, booleans, numeric strings and nonfinite/fractional
counts fail. Actual adapters must validate real arrays, action ranges and the
underlying network-call count; metadata alone cannot attest to real work.

Before dispatch, the host requests a reservation for a planned operation key.
Both cumulative **physical reservations** and **logical charges** must fit their
respective caps. A quota rejection reserves nothing, records rejection and stops
the ledger. Successful reservations cannot be refunded or reused. Only one
operation may be pending. Duplicate/unknown keys, forged/cross-ledger tickets,
replayed settlement and post-finalization mutation fail. The implementation is
for serialized host use; it is not a concurrent transaction service.

After dispatch the host settles the exact ticket as success, failure,
interruption or invalid result. Reported successful physical work is counted
once. Failure/interruption keeps the full conservative reservation but records
physical work as **unknown up to the reserved bound**, not zero work and not
invented completed work. Closing with a pending operation retains that same
uncertainty. Missing planned operations cannot disappear from the report.

Cached reuse charges the full declared logical cost but reserves no new physical
steps/model work. A64-character record hash is mandatory and retained in the
event log. The ledger checks reference format, **not authenticity or original
cost truth**. A future trusted cache must independently verify provenance,
recorded costs, compatibility and eligibility before declaring a cached
operation. Actual CPU/wall elapsed during reuse still counts. Logical work
charges do not simulate equal CPU cost across search methods.

## Time and completion semantics

The host supplies monotonic elapsed CPU and wall readings in integer nanoseconds
from one common origin. The ledger never reads clocks or infers CPU time from
imagined transitions. Invalid/backward readings cause `invalid_integrity`.
At or beyond either cap, new reservations are denied. A successful call that
finishes after the cap is counted, but final status is `incomplete_execution`.
An opaque running call cannot be interrupted by this state machine; trusted
external wall-time supervision remains necessary. Hosts must include proposal,
parsing, cache, validation and collection overhead, and aggregate any workers'
CPU usage correctly. No such process supervision is implemented here.

Final labels concern **execution accounting only**:

- `complete_execution`: every planned operation settled successfully, clocks
  remain valid and limits were not reached.
- `incomplete_execution`: missing/pending/failed/interrupted work or a cap hit.
- `invalid_integrity`: invalid clocks or an explicitly invalid result.

A complete ledger does not prove a complete scientific metric grid, valid
checkpoint/split provenance or a positive hypothesis result. An inconclusive
scientific outcome belongs to a separate statistical validator and must not be
relabelled incomplete merely because its confidence interval includes zero.

## Provenance and limits

The initial hash-chained journal event binds the complete declared plan and
caps. Later events record reservations, settlement, timestamps and closure.
Reports retain immutable work values, completed/unresolved keys, any pending
key and an immutable event tuple. The existing fixture journal uses an explicit
synthetic marker; these source tests are not measured experimental records.
The externally anchored head/count verification remains available.

This in-memory sequential contract is not durable storage, cryptographic
authorization or isolation. A malicious host could misreport work, clocks,
cache provenance or the plan itself. A proposer must never control that host
or reconstruct its ledger to reset a budget. Future integration must bind the
operation plan/caps to the independently locked protocol and real allocation,
validate model/context hashes and enforce all experiment/session caps externally.

No historical meter or planner is replaced, and no historical evidence is
retroactively reclassified. The15-file adapter snapshot still matches; it does
not claim a transitive review of this newly added module. Family/reward/root-
survival semantics, trusted planner adapters, actual metering, durable logs,
restricted evaluator IPC and OS isolation remain unresolved runtime gates.
H17 remains blocked; no excluded physics, seeds or closed outcomes are reopened.

## Tests actually run and costs

Initial focused ledger run: **36 passed in0.07s**. Two later tests add cached-only
accounting and initial plan/cap hash binding. The final combined source-only
run includes all38 ledger cases: **320 passed in8.07s**.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution1_resources.py tests/test_evolution1_source_contracts.py tests/test_evolution1_adapter_review.py tests/test_evolution1_feasibility.py tests/test_h17_seed_dependency_closure.py tests/test_h17_reservation_closure.py tests/test_h17_exclusion_coverage_review.py tests/test_h17_exclusion_registry_audit.py tests/test_h17_protocol_readiness.py tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider -o addopts='' -q
PYTHONDONTWRITEBYTECODE=1 python3 scripts/audit_evolution1_adapters.py --check
```

Tests exercise every work dimension before dispatch, cumulative caps, broadcast
counts, logical cache charges, failure/pending uncertainty, malformed/replayed
tickets, immutable reports, missing-operation rejection, CPU/wall cap equality
and overshoot, invalid clocks, deterministic logs and scientific-import absence.
The read-only adapter checker passed. `git diff --check` passed. Full scientific
tests, model inference, checkpoint deserialization, simulator construction and
experiments were not run. No new scientific seeds or physics were registered.
Actual scientific cost: **0s /0 real steps /0 imagined transitions /0 updates**.
Ledger remains **305.842s used /3294.158s remaining**; source-test wall time is
reported separately. Prior artifacts, instructions and checkpoints are unchanged.

## One next milestone

Implement the explicit trusted task-adapter **metadata contract**, using analytic
fixtures to reject family/reward/action/root-survival mismatches and bind planner
operator identities. Keep real planners and environments disconnected until the
remaining scientific/runtime gates have been independently reviewed. This is
engineering preparation, not evidence of autonomous algorithm improvement.
