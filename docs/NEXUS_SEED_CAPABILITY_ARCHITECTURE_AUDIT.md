# What Seed actually executes — source audit

Audited base `79c65d9ea959da0346027c5f72c717a2550e7d4d`, which contains the
reviewed `8033e06`, the conversation branch `b4c9693`, and corrective `c35252a`.
The primary checkout's untracked model and conversation output directories were
left alone. Work is isolated on `codex/seed-capability-evidence-audit`.
No stable promotion or historical weight change.

## Actual call path

`scripts/run_learning_lab.py` receives loopback requests →
`seed.lab.SeedWorkspace.dispatch` → `Conversation(SharedBrain(...)).send` →
`conversation.interpret` (bounded regex/phrase parser) →
`workspace_conversation.WorkspaceTurn.dispatch` →
`SymbioticWorkbenchController.try_handle_chat` for command prefixes, otherwise
the existing CSV/finite teaching handler. Explicit command routes include `agent`,
`code`, `program`, `z3`, `sympy`, `lean`, `capsule`, `docs`, `plan`, `investigate`.
The UI is a command-capable workspace, not a general conversational foundation
model with autonomous access to every backend.

CSV tasks compile an intent into the vetted data AST; unsupported intent parsing
may call `SeedWorkspace.ensure_runtime` → `PersistentLocalRuntime.complete` → a
real owned CPU llama.cpp server. `assistant_benchmark_v2.SCHEMA` restricts it to
sum/rows/clarify/unsupported, a minimum and order. No arbitrary model-generated
Python is executed by that path. Response cards use actual output receipts;
ordinary turns and context are stored in the Session/E1 journal. Explicit save
uses `seed.storage.save`; reload reconstructs Session and conversation context.
An executed AST can be saved into the procedures directory for compatible reuse.

`agent {public JSON task}` instead constructs `AgentTaskPublicView` →
`SymbioticAgentLoop.solve` → `PolyglotCodingWorkbench.load_repository` →
`RepositoryModel.index_files`, public call traces, doc retrieval →
`PythonASTMutationSynthesizer` or `TypeScriptCSTflashSynthesizer` →
`agent_loop_worker.run_worker_subprocess` → public results/revision → final
files/diff. Public success is not hidden-test success. Those proposal classes use
handwritten bounded edit rules, not a trained general coding model. The fixture
doc retriever can receive supplied executable bindings; that is privileged
task documentation, not language grounding learned from scratch.

`investigate` chat exposes status/reset/engineering fixture commands, not a
general automatic invocation of the v2 learning study. Benchmark training happens
in `EqualizedInvestigationEngineV2.select_and_train_v2`, not ordinary chat. Its
publicly named `LocalNeuralProposer.score_operations` is a token-substring weighted
sum, not a neural forward. The separate local GGUF probe in the v2 report did not
produce the study's selected symbolic candidates.

## Component reachability and capability classification

| Component / source | Actual mechanism and caller | Status / persistence / limit |
|---|---|---|
| `seed/conversation.py`, `workspace_conversation.py` | Finite parser, dialogue context, CSV compiler and response receipts; chat dispatch | Operational for supported syntax. Saves/reloads journal/context/explicit AST procedures. General conversation unmeasured. |
| `seed/local_model_runtime.py` | Real CPU GGUF inference; optional CSV intent fallback | Operational when weights + llama-server exist. Frozen inference, instance response cache; no online neural learning. Binary absent from Git. |
| `world/seed_rssm.py`, `seed/grounded_agent.py`, `state_contract.py` | Shared GRU32 + h32/z8 transition/head network, `Belief`, explicit observe/inspect contract | Optional owner-configured world path via `SeedWorkspace.attach_grounded`; not the coding/chat policy. Frozen checkpoints must be supplied with hashes. No weights trained here. |
| `seed/latent_planner.py` | Subclasses existing RandomShootingMPC over RSSM rollout adapter | Optional authored-world control, not general reasoning over arbitrary repositories. Historical action evidence stays separate. |
| `seed/adaptive_state.py`, `plasticity.py`, `structural_edits.py` | Small-block reward/meaning updates, anchors, repair/skill/merge/rollback | Optional API path; snapshots restore blocks/anchors/edits with parent hashes. Failed learned-rule studies remain negative. Not generic foundation-model adaptation. |
| `seed/shared_brain.py`, `library.py` | Finite symbolic program enumeration/checking and saved skills across four labs | Operational bounded teaching API/chat. Supplied grammar and cross-domain mappings are not learned universal meanings. |
| `seed/master/coding.py` | List-program grammar parser/synthesizer, source index, restricted list interpreter | Prototype/API. `ExecutionSandbox` is not an arbitrary Python runtime; real patch execution uses the separate bounded worker. |
| `seed/master/meta_learning.py` | Operator counts/macros/probe priors; its own docstring flags exact-motif demo/constructed transfer | Prototype. Do not treat synthetic transfer/retention scores as independent evaluation. |
| `seed/symbiotic_workbench.py::StigmergicCapsuleRegistry` | Content-addressed source/probes and versions, active/cold/rejected storage, exchange with revalidation | Bounded API/command acquisition and retrieval. Not autonomous global model learning; supplied code must be disclosed. |
| `seed/symbiotic_workbench.py::StatefulProgramEditor` | Supplied typed pipeline state and reversible edits | Operational on supported operator grammar. A stored plan or node is not an acquired learning procedure. |
| `MultiFormatDataBackend` | Actual CSV/JSON transforms and SQLite joins/transactions from explicit specs | Operational APIs; selected command routes. SQL expressions are supplied, not automatically inferred from arbitrary prose. |
| `StatefulZ3Coordinator`, `SymPySymbolicBackend`, `Lean4ProofBackend` | Real installed symbolic solvers/checker, explicit formal input | API/command routes. Lean binary absent here → BLOCKED. Symbolic substitution ≠ proof of arbitrary natural-language claims. |
| `combined_investigation_engine.py` | Finite candidate ranking/questioning, source priors, prefix index | Benchmark prototype. Target-conditioned pools and handwritten mappings limit v2 interpretation; corrected pilot is separate. |
| `CurriculumGenerator` / v2 selector | Selects from a finite authored task pool using coverage/ambiguity | Prototype; no open-ended autonomous curriculum or held-out-family advantage established. |

## Evaluation defects A–J and corrections

**A/B:** Original reset disabled questions and used different shortlists; v2
active comparisons fix these. But v2 compositional reuse still sets effective
shortlist to 2 versus 3, despite saved controller descriptors. New opt-in
`strict_controller_bounds` preserves 3 for all, including capsule conditions.

**C/D:** Original 350 reported versus 844 candidate calls is documented by the
prior audit, not newly rerun. v2 logs each support/probe function invocation, but
outer training is only counted and evaluator/worker calls are separate or omitted.
New meter covers source generation/training/probe/oracle/retrieval, worker cases,
assessment and inference with explicit units. Complete CPU/process-tree costs
include uninstrumented bookkeeping. Pipeline invocations are not primitive calls.
All policies now share singleton early stopping, previously learned-only.

**E/F:** v1 source capsules came directly from excluded targets; v2 uses disjoint
source tasks and disjoint inputs. Nevertheless `_make_v2_candidate_pool` receives
the hidden target and foils, and places them in a specially ordered candidate
menu. Training directly reads `task.target_ops`, even though its oracle answer
is not used to identify those operators. v2 also writes `repo_*` weights by hand.
The new public-view-only trainer receives no such labels/mappings, and the same
target-independent 252-program space is used throughout. No real repair claim
is assigned to that finite sequence solver.

**G:** v2 repository tasks select evaluator-supplied callable candidates and
preconstructed patched file alternatives. Subprocess verification makes outputs
real but does not make patch construction independent. `SymbioticAgentLoop` and
the earlier config-repair baseline *do* construct AST edits. Pilot coding uses
that existing real loop on public files/tests, including requests outside its
known mutation menu, and preserves failures.

**H:** `run_engineering_replacements_suite` builds ranks/probabilities by hand.
Its conformal coverage is synthetic calibrator engineering evidence, not coverage
of actual model proposals. New returned metadata says so explicitly. No new
coverage claim is made; calibrating actual candidate proposals remains unmeasured.

**I:** v1 accepted the zero-cost attack. v2 checks episode counts and replays,
but originally accepted its own saved table keys and did not require exact grid
identities or equality of the whole call trace. The verifier now anchors expected
keys/controller to committed config and compares complete deterministic traces.
New pilot verification also uses an elementary independent interpreter, lock
ordering, complete grid, source-feedback replay and per-case patch evidence.
Timings are measurements, not independently provable from an untrusted trace.

**J:** The v1 runner hardcoded `bounded_learning_to_learn_established=True` even
after withdrawal. It now refuses rerunning the closed study and carries no true
claim flag. Historical JSON stays unchanged. This audit/pilot cannot establish
general learning-to-learn regardless of a narrow statistical screen.

## Safety and remaining scope

Before this audit, repository load/patch paths could escape their workspace.
The new checks prevalidate every path and reject traversal, absolute names and
symlink escapes before writing. Parent and child workers reject unsafe names.
This is necessary containment, not a hardened OS sandbox; TypeScript's token gate
and Python's static/builtin restrictions are not sufficient for hostile arbitrary
generated code. This pilot uses newly authored bounded fixtures only.

Baseline comparisons on public coding/language/tool tasks are coverage probes,
not a matched broad six-method general-assistant trial. Same-controller ablations
are measured only on the finite program family. Cross-domain acquired skill
advantage, whole-repository held-out transfer, general factual dialogue, autonomous
curriculum benefit, neural forgetting and calibrated live-proposal coverage remain
UNMEASURED. This explicit limitation is preferable to scripting positive demos.
