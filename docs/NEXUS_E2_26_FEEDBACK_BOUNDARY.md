# E2.26 — Training-frozen feedback normalization boundary

## Scope and protocol

Base `5b9a243cfb4aa348f52b7a60c091c59fd174f183`, verified against
GitHub. Branch `codex/evolution2.26-feedback-normalization-boundary`.
This is a bounded engineering repair and synthetic information-flow
audit, **not** a scientific experiment or evidence of self-evolution.
No environments, neural inference/training, planner scoring, source
proxy replay, holdout registration, allocation or scientific execution.
Scientific ledger327.869/3272.131 unchanged. Existing untracked adapter
files are outside scope. Main and previous outcomes stay unchanged.

E2.25's source-only negative screen remains closed. Its inherited unit
scale depends on all query extrema; hiding the truth dictionary alone
does not prevent information reaching public anchor feedback. Do not
recompute that closed result with a corrected scale.

## Reuse and repair

Extend the existing `pendulum_acrobot_protocol_v2_pilot.TrustedEvaluator`
with **opt-in** `freeze_feedback_scale`. Do not replace that evaluator,
`AdaptiveProposer`, `ContextualStrategyMemory`, the resource ledger,
planner or method registry. Historical `evaluate`/`training_feedback`
continue returning raw values; `FrozenRevealedScale` and all old
runners remain untouched. This additive API is not automatically
installed in historical or prospective scientific runners.

Before obtaining reference outcomes a trusted future runner commits
the digest of family, training bundle and ordered reference variants.
Only this method's exact exposed training-reference set may freeze
the scale. Missing, extra, foreign-method, hidden/development, duplicate
or wrongly scoped references fail. Snapshot creation must not call a
score producer or include future cache entries. Once frozen for that
method, refitting is refused. The snapshot is immutable and serialized
with the reference scores, scope digest and snapshot digest.

The reference is **raw permitted training returns**, not already
query-normalized labels. An API cannot prove a producer has not
consulted hidden outcomes; trusted runner provenance and a precommitted
plan remain necessary. Hash checks provide consistency, not process
isolation, digital signatures, or permission/authorization changes.

## Fixed transform

For raw return r and frozen training extrema lo<hi, feedback is
`clip((r-lo)/(hi-lo),0,1)`. Check bounds before division to avoid
overflow. NaN, infinity, numeric strings, booleans, empty or degenerate
reference ranges fail closed. A zero-width reference does **not**
silently map all future outcomes to0.5. Overflowing reference width
also fails. Out-of-range values saturate, with a `clipped` indicator.

Clipping is a declared information loss, not an improvement trick:
future runners must report saturation frequency and retain **raw
returns** for primary scientific metrics. Do not change bounds using
later query extrema to reduce saturation. Different methods must
share the same authorized reference/scale for a fair comparison.

## Synthetic audit, not research outcomes

Commit this protocol and tested implementation before the audit.
The bounded audit uses fixed synthetic raw-reference values−10/+10,
query anchors2/8, and an unobserved query extreme changed from−1e8
to+1e8. It must demonstrate identical normalized anchor feedback,
identical feedback-driven proposer weights and identical next choices.
Only the permitted two anchor values may be requested in each query.
Verify future cache growth cannot alter the snapshot and refits fail.
Report out-of-range saturation; unit tests require zero-width refusal.
Audit command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/audit_evolution2_26_feedback_boundary.py`.

Audit cap10seconds, local CPU, zero real/imagined transitions and
zero fits. Synthetic producer lookups are bookkeeping, not simulator
interactions. Preserve and verify historical JSON hashes. Save an
artifact with source/protocol revision and hashes, resource accounting,
and exact observed invariants. A failure must remain a failure.

Tests cover end-to-end query-extreme independence, exact reference
scope/receipt membership, foreign/hidden receipts, immutable snapshots,
refit rejection, finite numerics, degenerate/overflow ranges, explicit
clipping, serialization/tamper checks and backward compatibility.
These tests establish only this trusted synthetic path. They do not
prove all existing evaluators or arbitrary producers leakage-free.

## Results

**Synthetic boundary audit passed.** This is engineering evidence for
the new opt-in path, not a learning-efficiency, control or general-AI
result. The historical E2.25 fixture is still transductive and is not
retroactively repaired or reinterpreted.

Protocol/implementation execution revision:
`57d5d189fcfad1c0f8179bed7ca9be4e89926baf`.
Capture `artifacts/evolution2_26_feedback_boundary.json`, SHA256
`ff58aac3f338ccfe49a0e16fa077a8451ad461145ecce0b3a17186803bf5b567`.
Arithmetic clarification:
`artifacts/evolution2_26_feedback_boundary_validation.json`.

Both opposite-extreme cases expose the same feedback **[0.6,0.9]**,
produce identical six linear proposer weights after two feedback
updates, and select the same next planner `c01e7ee7…`. Each query
requests exactly two raw values; neither requests the unobserved
extreme. The reference snapshot remains byte-equivalent after the
source cache grows; refit is refused. Saturated−20/+20 examples
produce0/1 with explicit clipping flags. The zero-width refusal and
foreign/missing/hidden-reference cases pass unit tests rather than
being extra experimental queries.

The shared-reference test also confirms that two comparison methods
using the same evaluator-owned reference produce equal snapshots;
cache hits remain charged. Payload round trips preserve predictions;
altered payloads fail the expected snapshot digest. Freezing itself
does not call a producer.

Runtime **0.196636s wall /0.196626s CPU**, within10s. Seven synthetic
raw lookups; **zero real/imagined transitions, zero model inference,
zero neural fitting**. Existing linear `AdaptiveProposer` makes **four
feedback SGD updates**, two per independent synthetic case. The original
capture's generic `optimizer_steps=0` meant *neural* optimizer steps;
that ambiguous label is clarified in the separate arithmetic record,
without changing the capture. Future audit output explicitly separates
`neural_optimizer_steps` from `proposer_feedback_updates`; this reporting
correction does not change the mechanism or replay outcomes.

All **306** pre-existing root JSON artifacts verify unchanged. No old
checkpoint, split, configuration, allocation or outcome was modified.
The scientific ledger remains327.869/3272.131. E2.17 remains consumed
and inconclusive; H17 remains blocked. Python3.13.5/NumPy2.5.4, local CPU.

Pre-audit focused tests: **21 passed in0.47s**. Regression tests cover
the new boundary, original evaluator contracts, resource accounting,
synthetic adaptive updates and hidden-return provenance. No historical
benchmark writer or planner-scoring/collection suite is run here.
The later capture checks independently recompute update accounting and
verify source hashes against `git show` of the execution revision.

Final selected command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution2_feedback_normalization.py tests/test_evolution2_pendulum_acrobot_protocol_v2_pilot.py tests/test_evolution1_resources.py tests/test_evolution1_toy_loop.py tests/test_evolution2_cross_task_screen.py tests/test_evolution2_evolutionary_search.py tests/test_evolution2_persist_reset_scoring.py::test_hidden_isolation_allows_fingerprint_overlap_not_hidden_returns tests/test_evolution2_persist_reset_scoring.py::test_persist_reset_crn_and_separate_controls -p no:cacheprovider -o addopts='' -q`.
**111 passed in0.85s**. No full scientific/collection suite was run.

## Remaining limits and one next milestone

The new transform is opt-in. Existing proxy/scientific paths have not
been migrated, and no scientific entry gate is unlocked. The runner
must supply raw permitted training returns, enforce reference provenance
and family scope, use a common scale across methods, and report clipping.
An untrusted producer could still leak information into its raw score;
hashes and a frozen dataclass do not constitute a security sandbox.

Next: integrate this opt-in boundary into **one prospective
method-sensitive evaluator path** with end-to-end source-only tests,
requiring a frozen training-reference manifest before query callbacks
are accessible. Preserve closed runners and outcomes. Do not collect
new control data or promote this engineering pass as self-evolution.
