# Acquired experience transfer — protocol

Isolated branch `cursor/seed-acquired-experience` from reviewed
`cursor/seed-capability-routes` `1a1b932`. Protocol committed before
target scoring. Not confirmation. Not learning-to-learn. Ranking stays
paused. Frozen 1.5B weights are not updated. Do not merge `main`.

## Question

Does experience automatically acquired on source tasks help NEXUS solve
different later tasks more accurately or with less total work than strong
ordinary baselines?

## Shared interface fixes (every method)

### A. API-ID binding validation

Reuse `contract_ids` and `assemble_id_wiring`. `api_id_bindings` is the
gate: selected API must exist; named parameter-to-ID bindings are
preferred; required names must be present; extras are rejected, not
dropped; types and `field.*` / `elem.*` must match the declared
iteration context. Invalid bindings never assemble an executable call.
Tracks are separate: selection correctness, binding validity, binding
correctness, assembly validity, public execution, private correctness.
Selection is not generally solved.

### B. Coordinated editing

Helper and caller keep distinct contracts. Staging exposes the actual
helper source and import path to caller generation. Publish requires the
existing hash-bound passing receipt. File/function existence, required
call, and behavior are scored separately. Constants are not globally
banned; a constant caller is refused when it violates the public request
or tests. Requested solutions are never inserted into model feedback.

## Memory

Reuse `RepairSchemaStore` and `OrdinaryExactCache`. No parallel store.
Source episodes record the public request and contract, initial
proposal, public failure, revision action, resulting program, public
validation, and cost. Abstraction is the existing `infer_ast_transform`
plus `apply_make_inclusive` / `apply_or_to_explicit_none`. Those
transforms are programmer-supplied. Private tests, task-ID features and
handwritten answers do not enter memory. A public-tested repair is
scoped evidence. If acquisition yields nothing usable, that result is
reported; the store is not secretly filled.

## Frozen splits

Closed selective-reuse and capability-map IDs unused. Fresh IDs are not
independence. Structural overlap is recorded on each task.

| ID | Split | Role | Held-out change |
| --- | --- | --- | --- |
| `src_allow_limit` | source | acquire Lt→LtE | — |
| `src_null_tag` | source | irrelevant family | null_default only |
| `dev_capture_lt` | development | freeze representation | not scored |
| `tgt_rename_layout` | target | related rename / layout | identifiers and path |
| `tgt_gt_floor` | target | related rebound | operator Gt, not seen on source |
| `tgt_strict_cut` | target | harmful if applied | exclusive; starter already correct |
| `tgt_join_parts` | target | unrelated abstain | missing_function |
| `tgt_near_bound` | target | ambiguous ask | no inclusive/exclusive cue |
| `tgt_exact_limit` | target | exact repeat | reported separately |

Representation and retrieval were chosen on source/development only:
family lookup, public-requirement gates, captured `compare_op_swap`.
Targets were not chosen because scratch failed.

## Methods (same targets)

| Arm | Mechanism |
| --- | --- |
| A `scratch` | frozen model + tools, `generate_direct`, empty memory |
| B `exact_cache` | ordinary exact request+files cache |
| C `ordinary_template` | guarded Lt→LtE template, same public gates |
| D `acquired` | captured schema + `propose_retrieved_repair` |
| E `acquired_reset` | empty store + `generate_direct` |
| F `irrelevant_memory` | store holds only `null_default` |

Identical model, prompt, contracts, tools, validation and revision
limits. C receives the same source experience class and applicability
gates. C is not unguarded. C and D are **not** the same: C applies only
`Lt→LtE`; D’s inclusive path uses `apply_make_inclusive` and may rebound
`Gt→GtE`. Do not collapse the arms.

## Metrics

Primary: later-task private correctness, harmful transfer, correct
applicability/abstention. Secondary: attempts, model calls, tokens, tool
executions, wall time, process memory, acquisition/retrieval cost.
Source skills are retested after acquisition. Exact-repeat caching is
reported separately. Accuracy and cost jointly. Break-even only from
observed costs and observed reuse savings.

## Decision rule

Useful transfer: D beats C and A on later private correctness, the
advantage shrinks under reset and irrelevant memory, and harmful
transfer is zero. Tie with C is useful template reuse, not a unique
NEXUS learning advantage. Memory persistence is not learning-to-learn.

## Budget

Standing local-CPU grant. Cap 80 calls / 900 s. Frozen research ledger,
product chat and Metal are not charged. A and E are the live arms
(12 cells). B/C/D/F are AST/offline. If the runtime is unavailable,
offline acquisition and memory cells are saved; live cells are marked
unavailable and scoring stops without inventing outcomes.

## Verifier

Replay saved programs against locked private tests. Reconstruct from
source episodes, memory snapshots and raw records. Do not trust success
flags alone. Check source/target isolation, reset emptiness, frozen
debit 0, and historical artifact hashes.
