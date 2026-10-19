# E2.27 — Prospective frozen-feedback evaluator integration

## Protocol and boundaries

Base `52857c6077169decc98e82d13d9a5afae0f6b118`, matched against GitHub.
Branch `codex/evolution2.27-frozen-feedback-integration`. Source-only
engineering, not a scientific confirmation or training experiment.
No model, planner, environment, source-array replay, numerical holdout
registration, allocation, or grant reuse. Preserve all closed artifacts,
H17 blocks, E2.17's inconclusive result and ledger327.869/3272.131.
Two existing untracked Evolution-1 files remain outside scope.

Read the master context/current-state/reuse-map/registry and E2.26
report. Reuse **`MethodSensitiveHiddenEval`**, `TrustedEvaluator`,
`FrozenTrainingFeedbackScale`, `matched_hidden_seed` and the existing
catalogue. Do not replace proposers, memory, planners, evaluator stack
or resource meters. Default historical paths retain their behavior.

## Prospective entry point

`persist_reset_scoring.prospective_hidden_evaluator` accepts a saved
manifest path and two trusted expected digests: manifest SHA256 and
predeclared training-reference digest. Validate bytes, schema, scale
snapshot, reference scope, family, query bundle/slots and catalogue
allowlist before attaching a raw query callback. Reuse the same
training-frozen transform for all methods. Manifest and expected digests
must come from trusted, committed runner provenance; a hash supplied
by an adversary does not confer authority or prove independence.

Add only an optional guard to the existing evaluator. It runs **before
every lookup, including cache hits**. Python booleans equal integers,
so a cached `(1,0)` key must not allow `(True,False)` to bypass strict
bundle/slot scope. Guard invalid requests before callback/charging;
authorized callback failures retain logical charges and do not create
successful cache entries. Existing evaluator physical counts represent
completed outcomes, not every failed producer attempt; future real
resource accounting still requires the existing parent ledger.

Validate raw query numbers before legacy float conversion. Refuse
numeric strings, booleans, nonfinite values and out-of-manifest variants.
Copy immutable scope and snapshot at construction; later file edits
cannot widen the live instance. Record raw returns separately from
bounded unit values; clipping never causes scale refitting. Hidden
assessment outcomes remain blocked from training by existing provenance
checks. No caller should feed hidden unit values back to a proposer.

This is cooperative trusted-code isolation, not a security sandbox.
It cannot prove an arbitrary callback never consults hidden data. Raw
producer provenance, real budget enforcement, fresh scientific tasks,
independent replication and authorization remain separate requirements.
No historical runner is silently migrated or scientific gate enabled.

## Bounded synthetic integration audit

Commit tested implementation and protocol first. Audit cap10seconds,
local CPU, zero real/imagined/model transitions and zero policy/optimizer
updates. Fixture bundle IDs0/1 are bookkeeping labels, not newly
registered scientific tasks or seeds. Use reference−10/+10, raw query
returns2/8, and opposite unobserved extrema−1e8/+1e8.

Persist/random select one registered planner and reset/evolution select
the other. Require method-selected unit scores0.6/0.9, equality for
identical selections, changed scores for different selections, equal
logical opportunities, shared physical cache reuse, unchanged scores
under unobserved-extreme changes, and rejection of hidden receipts by
the training boundary. This is **not** a baseline performance comparison;
selections are authored synthetic interventions.

The manifest is saved and its byte hash fixed before query evaluator
construction. No query callback runs during manifest loading. Preserve
all previous JSON hashes. Serialize raw outcomes, charges, snapshot and
manifest digests, source/protocol hashes, execution SHA and wall/CPU.
On failure, save an incomplete audit and do not reinterpret it as pass.

Tests: missing/tampered/wrong-scope manifests; callback nonexecution on
rejection; wrong query family/bundle/slot/planner; boolean cache aliases;
invalid raw values; fixed scope after file edits; cache fairness;
raw/unit separation and hidden-return-to-training rejection.

Command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/audit_evolution2_27_feedback_integration.py`.
Artifact `artifacts/evolution2_27_feedback_integration.json`.

## Results

Pending the committed synthetic audit. A functional pass is not evidence
of autonomous improvement, better control, learning-to-learn or AGI.
