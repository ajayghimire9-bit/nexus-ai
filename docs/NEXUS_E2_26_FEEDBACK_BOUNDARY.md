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

Pending the committed synthetic audit. No scientific result or general
learning capability follows from correct information isolation.
