# Evolution-1 adapter and evaluator-boundary review

Verdict: **BLOCKED_RUNTIME_GATES**. This is a source-only engineering review,
not an experiment lock, execution approval or new scientific result.

Branch: `codex/evolution1-adapter-boundary-review`.
Starting revision: `3ac0c5f49bc67e5202f6836a9b688ed5cf301095`, matching the
refreshed GitHub contract-harness branch. Both remotes were refreshed and the
starting working tree was clean. No historical implementation, checkpoint,
artifact, seed, allocation or result is modified. Root instructions and master
context remain unchanged. The Evolution-1 research direction is the bounded
planning-strategy-selection proposal in `NEXUS_EVOLUTION1_FEASIBILITY.md`.

## What this review verifies

`artifacts/evolution1_adapter_review.json` binds this manual review to15 explicit
source files and selected definitions by full-file SHA-256 and normalized AST
hash. The inventory is fixed in `scripts/audit_evolution1_adapters.py`, independently
of the rows supplied by a manifest. Missing/duplicate/extra files or definitions,
changed hashes, invalid types, duplicate JSON keys and nonfinite constants fail
verification. Expected readiness and zero-execution fields are checked exactly;
changing `false` to0 cannot exploit Python equality.

The checker reads source bytes and parses ASTs only. It never imports the
reviewed implementations, constructs a task, calls a planner/model or loads a
checkpoint. Its CLI accepts `--check`, not an execution action. The snapshot
does not prove transitive dependency closure or semantic equivalence and cannot
authorize a run. It intentionally pins the evidence reviewed here, not every
dependency or all possible behavior of these modules. The checker itself is
reviewed/versioned in Git; this is not an external trust root.

Reviewed areas include random-shooting scoring and factories, four family
lookahead entry points, shared candidates, reward functions, action/reward
wrappers, task creation, model stepping/broadcast behavior, the old research
action schema, the original confirmation guard and the new fixture contracts.
The manifest lists every pinned path and symbol. Context checkpoint loading
and scientific seed-exclusion closure are not revalidated by this source audit.

## Findings and required adapter semantics

### 1. Family inference is not an adequate interface

`planning.mpc_for_model` selects Pendulum when action count is3 **or** observation
dimension is3. Acrobot and both MountainCar interfaces also have three actions;
therefore this factory must not be reused as a generic family dispatcher.
The family lookahead modules avoid it by explicitly constructing
`RandomShootingMPC` with their own reward callback. Its fallback also assumes
two actions; the proposed five-action navigation family cannot use that fallback.

Future trusted task adapters must supply action/observation dimensions, action
decoding, reward timing, termination semantics and callable identity explicitly.
The proposer must not provide Python callbacks or task identifiers selecting a
hidden evaluator. Existing historical factories stay unchanged. This is an
integration risk, not evidence that earlier family-specific runs were wrong.

### 2. Root survival differs between the successful historical recipes

Let V_H(s') be the maximum of the shared H-step tail scores. In Pendulum's
`bellman_backup_control.lookahead_first_action`, Q(a)=r(s,a,s')+V_H(s'); the root
termination output is assigned `_p` and is not applied. The Acrobot and two
MountainCar entry points instead compute Q(a)=r+(1−clip(p_root,0,1))*V_H(s').
Their tails use the common cumulative-survival scorer. The Pendulum tail scorer
also applies cumulative survival inside its own H steps.

A future adapter must name/version the root-survival rule. Unifying these
formulas would change a decision rule; it is not an exact engineering refactor.
Whether the distinction matters numerically requires a separately permitted
evaluation. No inference or historical-result invalidation follows here.

### 3. Reward timing and wrappers are family-specific

Pendulum's reward uses the **current** angle, angular velocity and decoded
torque, ignoring `next_obs`; torques are−2,0,+2. Acrobot dense upright height
uses `next_obs`, not the native−1/step reward. MountainCar dense valley height
likewise uses the next position. Discrete MountainCar indices and continuous
MountainCar's−1,0,+1 force mapping are not Pendulum torque semantics.
The Acrobot/MountainCar dense wrappers suppress native goal termination and
preserve truncation. These are continuing200-step research tasks, not the
unmodified sparse-reward benchmarks.

The trusted adapter must bind the wrapper chain and reward identity to the
task specification. A common normalized search score additionally needs a
predeclared analytic return range and finite-value checks; the fixture's[0,1]
scores are synthetic and do not implement that scientific normalization.
Do not clip model outcomes or redefine actual rewards to obtain a favorable
comparison. Root-survival and reward-timing choices belong to the evaluator
specification, not a mutable proposer field in this initial design.

### 4. Horizon and candidate semantics must be explicit

Flat H-step shooting predicts H transitions per candidate. Historical
successor lookahead predicts one root transition and then H tail transitions:
its effective sequence depth isH+1. Thus historical“H=16” means16 tail steps
for successor, not16 total. The new catalogue's cost A+ANH correctly reflects
that convention; it does not equalize objective depth across decision rules.
Any future scientific claim must disclose this structural difference.

`prediction_control_gap.candidate_sequences` creates an IID integer array using
a fresh local NumPy generator. The family entry points use the **same tail
array** for every root action and select first maxima via NumPy argmax. The
historical shape is16×16; simply passing arbitrary catalogue horizons/counts
into those entry points fails shape checks. Balanced-first-action generation
is proposed in the catalogue, not implemented by these historical functions.
Its remainder handling when N is not divisible by A must be defined and tested
before implementation. Historical variants cannot be relabelled as balanced.

Future equivalence checks must preserve random draw order, candidate ordering,
shared tails, tie handling, state/action dtype and reward arithmetic. Flat
`RandomShootingMPC.act` uses a persistent episode RNG and chunked scoring;
family helper functions receive per-step candidate arrays. Interchanging these
paths changes RNG semantics unless explicitly proven otherwise.

### 5. Existing counters are not hard reservation meters

`bellman_backup_control.Meter` checks elapsed time before a wrapped call, but
increments environment/model totals and checks caps **after** the operation.
It can execute one excess environment step or a whole excess model batch before
raising. Its model counter uses action-array size. `WorldModel.step` can
broadcast a single action across several observation rows; in that use case
action-array size is not the actual number of state predictions.
`InferenceCounter.step` counts observation rows instead, but is an instrumentation
counter rather than a hard quota. These source findings do not show that the
closed historical runners actually exercised a mismatched broadcast call or
exceeded their reported complete-run budgets.

A future trusted meter must reserve the exact observation batch before a call,
reject broadcasting/shape ambiguity or expand it before counting, and count
executed work once even when results fail validation. Reserve real steps before
`env.step`. Failed attempts and cached reuse require distinct physical and
logical accounting. Count model API calls, actual underlying network calls,
imagined transitions, CPU seconds and wall time separately. An ensemble would
add member work, so it is outside this initial single-model recipe.

`RandomShootingMPC.act` can stop after partially scoring candidates under its
default elapsed-time rule. The family helpers disable that local time budget.
Do not let adaptive early exit masquerade as equal candidate opportunity.
Future hard-cap interruption must yield an honest incomplete attempt, not a
scientifically successful controller with an unreported reduced search budget.
Pre-call quotas alone cannot interrupt an already-running opaque neural call;
trusted wall-time supervision remains a separate gate.

### 6. State, context and evaluator boundaries are not sealed by types

The scorer invokes `begin_rollout`, and recurrent models can mutate hidden
state. Historical GRU limitations remain excluded; no recurrent model is
validated by this review. A future adapter must verify architecture compatibility,
install the frozen context before scoring, preserve normalization, reset episode
RNG state and verify context/network fingerprints after the attempt. Actual
checkpoint files/tensors were not loaded here. The fixture rollback restores
only state references, not a live model, RNG or memory object.

The old `ExperimentAction` contains both feedback and assessment seeds. It must
not be sent as the new proposer wire message. The original confirmation guard
enforces one historical protocol; importing it does not authorize Evolution-1
or prove hidden-data isolation. Legacy experiment modules import scientific
stacks and configuration helpers; the source checker deliberately parses rather
than imports them.

## Proposed trusted boundary, not deployed infrastructure

The proposer receives only public interface features, remaining logical budget
and permitted **training** feedback. Dimensions may identify a family indirectly;
do not call that task-blind inference. It emits only the existing catalogue wire
message. A trusted dispatcher maps its identifiers to reviewed pure operators.

A separately supervised evaluator owns task construction, hidden datasets,
seed capabilities, normalization/model loading, reward definitions, quotas and
closed outcomes. Hidden tasks/outcomes must not be mounted/readable by the
proposer or returned through logs, exceptions, archive queries or promotion
messages. No executable source, path or environment factory crosses that wire.
Subprocess separation alone is insufficient when both processes can read the
same hidden filesystem. Actual OS access restriction and capability tests remain
unimplemented; this task changes no permissions or security settings.

Only allowed training receipts may update proposal statistics. A winner is
frozen before an independent gate, and gate outcomes cannot become proposal
rewards or trigger repeated tuning on that gate. Durable externally anchored
logs and independently held signing authority must bind operator versions,
source/config/data/checkpoint hashes, complete attempts and allocation identity.
The fixture HMAC and in-memory journal are not that production boundary.

## Decision and one next milestone

Do not connect the current catalogue to legacy scientific entry points yet.
Outstanding gates are explicit family/reward/survival adapters, generalized
candidate handling, pre-call quotas, checkpoint/context verification, durable
provenance, restricted evaluator IPC/isolation and a separately reviewed
scientific protocol with full exclusion closure. H17 remains blocked and is
not reopened. No closed scientific result changes because these gates exist.

One next milestone: implement a **source-only pre-call resource-reservation
ledger**, with adversarial synthetic event tests for batch-size accounting,
failures, cached reuse, interruption and complete/incomplete labels. Do not add
a real model/environment execution path or allocation in that milestone.

## Verification and resource record

Read-only check:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/audit_evolution1_adapters.py --check
```

It reports`SOURCE_REVIEW_MATCH: 15 files; runtime remains blocked`.
Focused tests: **16 passed in0.52s**. They reject missing/duplicated source rows,
missing definitions, stale byte/AST hashes, changed flags/types, duplicate JSON
keys and nonfinite manifests. Temporary-source fixtures demonstrate that even
a comment-only source edit invalidates the full-file anchor. A fresh interpreter
checks the CLI without importing torch, NumPy, Gymnasium, world or task modules;
`--execute` is rejected. These are provenance tests, not behavioral planner tests.

Environment: CPython3.13.5. AST serialization is interpreter-dependent; on a
different AST version a mismatch must trigger review, not automatic reapproval
or silent hash regeneration. Full-file hashes remain the byte identity anchor.
Combined source-only regression result: **282 passed in7.97s**. Command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution1_adapter_review.py tests/test_evolution1_source_contracts.py tests/test_evolution1_feasibility.py tests/test_h17_seed_dependency_closure.py tests/test_h17_reservation_closure.py tests/test_h17_exclusion_coverage_review.py tests/test_h17_exclusion_registry_audit.py tests/test_h17_protocol_readiness.py tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider -o addopts='' -q
```

`git diff --check` and a repeated read-only manifest check passed. The scientific
test suite and real checkpoint audit were not run.

Actual scientific costs: **0s,0 real interactions,0 imagined transitions,
0 training updates**. Source parsing/test wall time is separate. No new physics
or numerical scientific seeds were registered. Ledger remains **305.842s used /
3294.158s remaining**. Historical artifacts and closed evaluations are preserved.
