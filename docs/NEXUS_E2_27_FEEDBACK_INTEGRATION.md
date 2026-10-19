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

**Synthetic integration passed.** A functional pass is not evidence
of autonomous improvement, better control, learning-to-learn or AGI.
The method selections are authored interventions, not learned winners.

Execution/protocol commit:
`850da761feb356132fd69eebb50a8f1edafdf9f8`.
Artifact `artifacts/evolution2_27_feedback_integration.json`, SHA256
`b4a46b9a16391102ac6ceb83f311fd29de9126058d6ffc5d6cfd22e319a14518`.
The saved manifest is embedded in the artifact and reconstructs its
original bytes with `json.dumps(manifest,sort_keys=True).encode()`;
SHA256 `a52656455c2a55b2bd5341b4fa8e8b975d949c5988f2c72e917f808204ab0f02`.
The audit saved that file before query attachment; temporary fixture
paths are not required to reproduce the manifest.

Both opposite-extreme cases return persist/random0.6 and
reset/evolution0.9, from raw values2/8. This demonstrates sensitivity
to the selected planner and equality for identical selections, not
performance superiority of reset. Per case: two physical callback
results, two cache hits and four logical receipts; hidden outcomes
are blocked from training. All outcomes retain raw values, clip flags
and the training snapshot digest. Query extremes never enter scaling.

The strict scope guard runs before cache lookup and refuses boolean
aliases, wrong families/bundles/slots and unregistered planners before
query production. Missing or inconsistent manifests fail before
callback attachment. File mutation after construction cannot expand
the copied scope. Numeric strings, booleans, NaN and infinity from
callbacks fail before cache insertion. A separate clipping test
preserves raw1000 while reporting unit1 and `clipped=true`; it is
not part of the two-case integration capture.

Runtime **0.200632s wall /0.200407s CPU**, within10s. Two training
reference lookups plus four query callbacks, eight logical query
receipts; zero real/imagined transitions, model inference, neural
training or proposer updates. All **308** pre-existing root JSON
artifacts verify unchanged. Original scientific configurations,
checkpoints and allocations remain unchanged. Ledger327.869/3272.131
preserved; no E2.17 or H17 execution.

Pre-execution focused tests: **46 passed in0.75s**. Initial selected
regressions: **134 passed in0.89s**, before two additional saved-capture
checks. Tests deliberately exclude scientific execution, planner/model
scoring and historical benchmark writers. Saved-capture checks validate
the exact case/method grid, raw/unit values, cache identity, manifest,
historical hashes and sources against the original execution commit.
No audit replay is required for those checks.

Final selected command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution2_feedback_integration.py tests/test_evolution2_feedback_normalization.py tests/test_evolution2_pendulum_acrobot_protocol_v2_pilot.py tests/test_evolution1_resources.py tests/test_evolution1_toy_loop.py tests/test_evolution2_cross_task_screen.py tests/test_evolution2_evolutionary_search.py tests/test_evolution2_persist_reset_scoring.py::test_hidden_isolation_allows_fingerprint_overlap_not_hidden_returns tests/test_evolution2_persist_reset_scoring.py::test_persist_reset_crn_and_separate_controls -p no:cacheprovider -o addopts='' -q`.
**136 passed in1.05s**. This is the relevant synthetic regression set,
not the full repository scientific/collection suite.

## Remaining scientific entry conditions and one next milestone

Only this prospective factory is integrated; historical callers stay
unchanged. There is no model-training replication, new scientific task
registration, real-controller budget allocation, promotion or completed
learning-to-learn evaluation. A callback must still be trusted to return
raw permitted outcomes, and expected hashes must have independent
protocol provenance. The API cannot establish dataset disjointness or
scientific approval by itself.

Next: perform one **source-only readiness audit** of the existing
method-sensitive persist-versus-reset study under this corrected
feedback path, checking raw primary metrics, reference-selection
fairness, clipping, model provenance, missing-result rules and resource
preconditions. Do not collect outcomes, retrain, create an allocation,
register a holdout or unlock scientific dispatch during that audit.
