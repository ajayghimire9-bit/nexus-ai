# NEXUS Seed — Code Ownership and Reuse

## Corrected capability evidence path

`seed/capability_evidence.py` extends the existing EpisodeCallLedger and
EqualizedInvestigationEngineV2 through opt-in instrumentation/strict bounds; it
reuses VersionedCapsule, the existing public coding loop/worker, Conversation,
data adapters, local runtime and E1/Sandbox host. It does not replace the older
`seed/capability_audit.py` world diagnostics or create another learner framework.
`verify_seed_capability_audit.py` combines an elementary independent output
reference with source/controller replay and exact grid/hash checks.
`replay_seed_capability_tools.py` re-executes saved authored final patches only.
The focused read-only `/experimental?study=capability_audit` view avoids loading
all history and can never start a run. [Findings](NEXUS_SEED_CAPABILITY_AUDIT_RESULTS.md).

## Configuration repair and real Python validation

`seed/config_repair_baseline.py` reuses `master.coding.RepositoryModel`, with
public-contract inference, source-free AST edits and an ordinary exact patch
cache. It is not a learner. `seed/config_repair_worker.py` uses the historical
black-box worker's safe builtins under a narrower vetted three-module execution
contract; it does not change that historical evaluator. The master
ExecutionSandbox's list interpreter is not used as if it supported real Python.
The existing host adds trusted `--study config_repair` dispatch and retains E1
metering. Independent verification replays saved patches in bounded workers and
reconstructs cache/stage arithmetic. [Results](NEXUS_SEED_CONFIG_REPAIR_RESULTS.md).

## Saved-candidate audit and boundary probes

`seed/candidate_identifiability.py` reuses `discovery_headroom.Plan`, the fixed
grammar and vetted AST executor. It reconstructs already-observed evidence,
normalizes only justified identities and constructs answer-free distinguishing
inputs. It does not replace the runtime or promote a policy. The existing
headroom runner adds an explicit trusted `--study identifiability` dispatch and
uses the SAME Sandbox/E1 host/meter; published attempts refuse reruns. The new
verifier reuses the previous independent arithmetic reference, not the executor
or constructor. [Results](NEXUS_SEED_CANDIDATE_IDENTIFIABILITY_RESULTS.md).

## Baseline-first discovery workload

`seed/discovery_headroom.py` reuses the vetted real-data AST executor for a
typed, unfamiliar-schema workload and an exact source-free baseline with
ordinary prefix caches. It does not replace the assistant or runtime. The
runner reuses `experimental.Sandbox`, E1 accounting and the existing assistant
supervisor's process-tree meter. Its independent verifier recomputes outputs
arithmetically without the executor or model. No learning comparison yet.

## Persistent local assistant study

`seed/local_model_runtime.py` owns a CPU llama.cpp server, strict deadlines,
instance-scoped application cache, native telemetry and shutdown. The existing
`GrammarConstrainedLocalIntentModel` delegates to it; no class-wide decode cache
or user-specific model path remains. `seed/assistant_benchmark_v2.py` reuses
`TypedDataAdapterProgram`, `ParameterizedAdapterTemplate`, schema profiling and
the execution-backed renderer. The versioned runner extends existing Sandbox/E1
reservation/debit conventions with a descendant-process meter. The independent
verifier replays saved programs and reference outputs; the analysis script is
saved-data only. [Guide](NEXUS_LOCAL_ASSISTANT_RUNTIME.md),
[negative result](NEXUS_SEED_ASSISTANT_BENCHMARK_V2_1_RESULTS.md).

## Active runtime

- 10-Part NEXUS Seed Integrated Architecture & Black-Box Open Primitive Code Transfer v1:
  `seed/integrated_architecture.py` implements the 3 operating timescales, 3-tier
  `EvidenceKernel`, `PerceptionAndLanguageInterface` (compact encoder + predictive
  feature discovery, 3 interchangeable language modes, 3-way intent routing,
  source-attributed claims), `BeliefWorkspace` with splittable observational
  equivalence groups, Kautz-Singleton $AG(2,3)$ $9\times 12$ 2-disjunct matrix +
  conditional group testing + Bat `SURVEY -> DISCRIMINATE -> VALIDATE_AND_ACT`
  scheduler + `DiagnosticProcedureLibrary`, 6-part `MechanismCapsule` with
  separately verified `goal_adapter`, bounded 1-minimal `ddmin` `DeltaDebuggingReducer`
  + `FailureLibrary`, `TriLibrarySleepConsolidator` + `SuccessorFeatureLearner`
  (zero-shot GPI) + `SmallLearnedOptimizer`, 6-stage `DevelopmentalCurriculum` +
  11-action `CognitiveController` (5 policies), and all 7 isolated component
  comparisons (`scripts/verify_seed_integrated_architecture.py`).
  `seed/meta_rule_evolution_v1_audit.py` audits all 15 v1 evaluator-leakage and
  guided-injection confounds without altering `artifacts/seed_meta_rule_evolution.json`.
  `seed/open_primitive_transfer.py` and `seed/blackbox_evaluator_worker.py` implement
  strict `LearnerTaskView` vs `EvaluatorTaskPrivate` separation (`assert_zero_evaluator_leakage`),
  real counted candidate execution over 3 non-isomorphic Stage A families (`list_transformations`,
  `boolean_circuit_induction`, `fst_string_rewrite`), uniform mutation without
  guided injection, in-loop Dream novelty without seed in hash, real pre/post
  retention, real Sleep test re-execution + non-overlapping MDL compression, and
  Stage B `CommonEnvironmentAdapter`, `TransitionReceipt`, `PROPOSE_PRIMITIVE`
  6-stage kernel lifecycle, and multi-file `UnknownLibraryCodeLab` with decoy helpers,
  candidate call sites, learner-synthesized AST patches, and isolated subprocess hidden
  evaluation over 3 independent unknown-library families (`ulib_window_checksum`,
  `ulib_runlength_bucket`, `ulib_zigzag_interleave`) reusing the SAME `EXPERIMENTAL`
  host/worker/journal. `scripts/verify_seed_open_primitive_transfer.py` is a
  standalone stdlib verifier.
  [Integrated Architecture](NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md),
  [v1 Audit](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md),
  [Protocol](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md),
  [Results](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_RESULTS.md).

- Combined Wake–Sleep–Dream–Evolution Architecture & Meta-Rule Evolution v1:
  `seed/meta_rule_evolution.py` implements the `ImmutableTrustedKernel`, 13-opcode
  typed learning-rule DSL interpreter, 7 mutation operators, `ConceptCapsule`
  acquisition without stored whole-program fingerprints (`zorp` $\to$
  `filter-even -> decrement -> reverse -> unique`), Dream 6-criterion
  admissibility & regret generator, Lexicographic/Pareto evolution over separate
  Episodic and Continual regimes, and Sleep Stitch-like subprogram compression &
  choice-policy distillation, reusing `evolution1.catalogue.canonical/digest`,
  `disjoint_meta.frozen_hashes`, `source_acquisition.FROZEN`, and the SAME
  `EXPERIMENTAL` host/worker/journal. `scripts/verify_seed_meta_rule_evolution.py`
  is a standalone stdlib verifier that independently audits kernel integrity,
  pre-sealed rule freezing, capsule provenance, paired intervals, and all 9 gates.
  [Protocol](NEXUS_SEED_META_RULE_EVOLUTION_PROTOCOL.md),
  [Results](NEXUS_SEED_META_RULE_EVOLUTION_RESULTS.md).

- Task-conditioned program ranking, source-only signature audit, and cross-lab transfer:
  `seed/signature_audit.py`, `seed/task_conditioned_meta.py`, and `seed/cross_lab_transfer.py`
  reuse `disjoint_meta.probe_domain/action_probe_domain/frozen_hashes`,
  `evolution1.catalogue.canonical/digest`, `shared_brain.SharedBrain`,
  `skill_library`, `foundation.programs`, and the SAME `EXPERIMENTAL` host/worker/journal.
  `scripts/verify_seed_task_conditioned_replication.py` is a standalone stdlib
  verifier that independently reconstructs the 6-operator catalogues, three-way
  partition invariants, family summaries, paired Student-$t$ intervals, and all 7
  advancement gates. [Protocol](NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md),
  [Results](NEXUS_SEED_TASK_CONDITIONED_REPLICATION_RESULTS.md),
  [Signature Audit](NEXUS_SEED_SIGNATURE_AUDIT_RESULTS.md),
  [Cross-Lab Transfer](NEXUS_SEED_CROSS_LAB_TRANSFER_RESULTS.md).

- Disjoint compositional meta-learning replication: `seed/disjoint_meta.py`
  reuses `skill_programs.run/value` for primitive execution, `evolution1.catalogue.canonical/digest`
  for canonical serialization and SHA-256 digests, `investigation_transfer.FROZEN` for
  frozen checkpoint verification, and the SAME `EXPERIMENTAL` host/worker/journal.
  `scripts/verify_seed_disjoint_meta.py` is a standalone stdlib verifier that
  independently recomputes all primitives, canonical forms, ridge weights,
  candidate orderings, retention, cross-domain transfer, intervals, and gates.
  [Protocol](NEXUS_SEED_DISJOINT_META_PROTOCOL.md), [Results](NEXUS_SEED_DISJOINT_META_RESULTS.md).

- Master architecture: `seed/master/` (`types.py`, `grounding.py`, `memory.py`,
  `hybrid_world.py`, `reasoning.py`, `coding.py`, `controller.py`, `runtime.py`,
  `meta_learning.py`) connects all 15 master architecture
  components, the bounded exact-motif program-prior reuse demo, and the 6-domain
  bounded multi-reasoner integration suite over the SAME `Session`,
  `SharedBrain`, `E1 Journal`, `skill_library`, `foundation`, `structure`, and
  `Conversation`. No replacement database or unverified memory store.
  [Guide](NEXUS_SEED_MASTER_ARCHITECTURE.md).

- Query-conditioned acquisition: `seed/conditioned_acquisition.py` extends
  `source_acquisition.fit_selector` with an explicit source-count option,
  reuses its utility cases and all fixed learner/baseline paths, plus `nn.ridge`.
  Same EXPERIMENTAL host and journal; no parallel learning/memory framework.

- Query-context audit: `seed/query_context.py` reuses source acquisition's
  feature map, posterior update, public grammar and fixed learner. It reads only
  saved source projections, computes expected-value counterexamples and uses
  the SAME EXPERIMENTAL host/journal. No learner or model is trained.

- Source acquisition: `seed/source_acquisition.py` uses the SAME bounded
  `foundation.programs` interpreter, `question_selection.LabelOracle`,
  `nn.ridge` fitter and EXPERIMENTAL host/journal. A ten-feature question
  selector is separate from the fixed target version-space learner.
  No parallel memory framework or historical neural checkpoint change.

- Source-inferred investigation: `seed/inferred_investigation.py` fits only source
  traces, reuses `structure.investigation.learn`, `investigation_transfer.adapt`,
  `investigation_hybrid.choose`, `compiled_greedy.compile_table` and the SAME
  EXPERIMENTAL host. Explicit table arguments preserve historical defaults;
  no global table swapping or new memory/optimizer framework.

- Source-free compilation: `seed/compiled_greedy.py` compiles the supplied grammar
  and reuses `investigation_transfer.adapt`, `LabelOracle`, `investigation_hybrid.choose`
  and the existing EXPERIMENTAL host/journal. Saved-bank audit only; no live promotion.

- Independent-tree replication: `seed/investigation_replication` reuses the same
  investigation runner, hybrid proposer and host, with task-balanced evaluator
  assignments and source-tree aggregation. Frozen neural models are unchanged.
- Phase1–7 workbench extends `foundation.library/runtime/curriculum` in the SAME
  Session/E1 Journal: typed expression abstractions, taught verified-function
  phrases, source practice and the existing `meta.kind_statistics` updates.
  `structure.runtime` remains the graph/mechanism backend; no parallel framework.

- Selective investigation fallback: `seed/investigation_hybrid.py` reuses
  `investigation_transfer.run/validate_output/adapt` with explicit internal
  profiles, the same LabelOracle and existing EXPERIMENTAL host/journal. Only
  the fallback changes; parent source/tree are hash-verified and never refit.
  Exact single-pass greedy scoring charges each lookup. No new learning store.

- Investigation transfer: `seed/investigation_transfer.py` reuses the existing
  `structure.investigation` tree, `question_selection.LabelOracle` and
  EXPERIMENTAL host/worker. No parallel memory or learning framework. The
  registered screen failed; no live promotion. Conversation code composition
  reuses `foundation.programs.pipeline/execute` and the existing journal.

- Foundation: seed/foundation uses the SAME Session/E1 Journal, skill_programs
  primitives and structure.investigation learner. programs is a bounded typed
  composition interpreter; library discovers repeated source list sequences;
  knowledge derives evidence-linked views, not a new store. language is a small
  source-count surface decoder, not a replacement neural model. Frozen GRU/RSSM
  remain intact. [Usage and limits](NEXUS_SEED_FOUNDATION.md).

- Optional executable state: seed/structure/state,features,learning,mechanisms,
  investigation,neural,runtime. Reuses Session/E1 Journal/storage, skill_programs,
  nn.factory/ridge and EXPERIMENTAL host. New graph-effect BFS is bounded and
  opt-in; it cannot replace default neural planning or known-grid execution.
  [Architecture and status](NEXUS_SEED_EXECUTABLE_WORLD.md).

- Chat: seed/conversation.py parses bounded intents and delegates to SharedBrain.
  Messages/pending references are Session/E1 Journal events, saved by the existing
  storage. No second knowledge store. seed/workspace_conversation.py handles
  local CSV tools and explicit capsules on that same turn context; it reuses
  assistant_benchmark_v2 / ParameterizedAdapterTemplate / PersistentLocalRuntime
  rather than a parallel executor. Fresh requests do not inherit filters; save
  stores the executed AST. seed/conversation_capability.py only orchestrates
  those existing tools plus config_repair and Session world probes.
  seed/lab.py routes typed chat requests;
  web/learning-lab/chat.* renders replies/cards with textContent. Supporting
  views share the same Session ID. [Guide](NEXUS_SEED_CONVERSATION_WORKSPACE.md).

- Shared labs: seed/shared_brain.py is an adapter over Session, not another agent
  state store. seed/skill_library.py derives typed skill revisions and source-only
  rule feedback from that SAME E1 Journal; existing storage saves them.
- Typed skills: seed/skill_programs.py reuses core Predicate/GRAMMAR/Move and adds
  bounded list operators. seed/relations.py extracts the old Relation primitives
  with semantic_lessons public aliases intact. Existing planning.to_cell and the
  original authored reward serve the World Lab reference.
- meta/kind_statistics.py is the original EpsilonGreedyController numeric core,
  shared by that controller and the lab adapter. No second bandit framework.
- Optional representation/retrieval is the existing frozen SeedRSSM encoder/key/
  query network; new domains have supplied sensor schemas, unvalidated neural
  semantics. No GRU, normalization, recurrent contract or checkpoint is changed.

- Finite concepts, typed programs, correction, evidence: src/nexus/seed/core.py.
- Durable sessions and bounded local requests: seed/storage.py, seed/lab.py.
- Recurrent state: seed/state_contract.py over world/seed_rssm.py.
- Neural execution: seed/grounded_agent.py; data-only replay: grounded_records.py.
- Existing planning: seed/latent_planner.py adapts world/planning.py.
- Action scorer: seed/action_readout.py; do not replace with another planner.
  Its frozen nonlinear33-feature bridge reuses PlasticityController/correction;
  no new optimizer stack or runtime adapter is enabled by that API.
- Local adaptation: seed/plasticity.py and adaptive_state.py.
- Vetted edits and rollback: seed/structural_edits.py.
- Surprise/one-use acceptance: seed/surprise.py.
- Source-only future-learning credit: grounded_meta.py wraps the existing
  meta/controller.py EpsilonGreedyController. Do not open a parallel controller.
- Shared provenance: evolution1/catalogue.py canonical/digest and
  evolution1/fixtures.py Journal. Do not delete these as obsolete Evolution code.

## Verification versus experiments

Answer-free utility: seed/answer_free_utility.py reuses question_utility's current-
outer-fold counterfactual construction and training extraction, question_selection's
LabelOracle/variance, question_headroom's fixed update and nn/ridge. Its separate
pure ten-scalar API has no answer or assessment argument. Same EXPERIMENTAL host,
ledger and read-only Lab. No new optimizer or live questioning framework.
[Protocol](NEXUS_SEED_ANSWER_FREE_UTILITY_PROTOCOL.md).


Question utility: seed/question_utility.py adapts question_selection's variance
orders/fixed damping and question_headroom's counterfactuals, plus the existing
nn/ridge primitive. Current-outer-fold source constants/normalization are reused
for all training cases, avoiding other folds' held-task contributions. Query
answers and unasked labels are absent from the public selector API. Same
EXPERIMENTAL host/worker/ledger; no new learner framework or neural model.
scripts/verify_seed_question_utility.py reuses the earlier stdlib variance solver.

Larger query bank: seed/query_replication.py reuses the EXACT saved headroom
states/normalization and nonlinear_learning.fresh_world/score_basis/Meter.
It collects only source query starts, with all selection choices persisted
before checking. No new learner, world, optimizer, memory or runtime policy.
scripts/verify_seed_query_replication.py replays stored scalar arithmetic with
stdlib only. Existing EXPERIMENTAL caps/ledger/one-use manifests remain enforced.
scripts/validate_seed_query_replication.py is an OFFLINE arithmetic/accounting
validator for the unchanged initial capture; it does not reopen or rerun it.

Question-pool headroom: seed/question_headroom.py is an evaluator adapter over
saved question_selection states, its shared damped_step/assess helpers, frozen
source pack and existing cumulative posterior. It adds no runtime questioner.
Oracle choices are computed after all independent counterfactual fits; query
blocks derive from hashed original records. Same EXPERIMENTAL host and ledger.
scripts/verify_seed_question_headroom.py checks recorded equations using the
prior verifier's numeric audit primitive; no new learner/framework or collection.

Question choice: seed/question_selection.py reuses sequential source/hash/fold
validation, the existing constant damping and cumulative posterior, anchor fit,
paired intervals and EXPERIMENTAL host. Input-only variance chooses a requested
saved teaching row; an oracle adapter reveals only its label. Fit and assessment
functions have separate arguments. No new learner, memory, model or simulator.
scripts/verify_seed_question_selection.py independently checks recorded equations
and original-order replication using stdlib only. No live promotion.

Learning choices: seed/learning_choice.py performs one roll-in/reference refit
through existing prefix_consistency helper options and cumulative trajectories.
seed/learning_decision.py is a pure immutable advisory over predicted benefit,
observed-anchor damage and budget; it does not replace Session/concept questioning.
Same EXPERIMENTAL host, ledger and Lab. Ask waits for the next scheduled label;
no autonomous active-query efficacy established. No live promotion. Stdlib-only
scripts/verify_seed_learning_choice.py checks fitted equations and decision math.

Sequential frozen selector: seed/sequential_consistency.py reuses cumulative
posterior/folds, prefix_consistency.features/predict, update_diagnosis trajectories/
paired intervals and bounded protection. Same EXPERIMENTAL host/worker and Lab;
no new optimizer, memory or resource framework. Frozen source-fitted state is
tracked JSON; scripts/verify_seed_sequential_consistency.py checks complete
sequential arithmetic without fitting, neural imports or private binaries.

Teaching-prefix informativeness: seed/prefix_consistency.py uses existing source
packing, cumulative folds/posterior, anchor initialization and task intervals.
The original E2.25 ridge math is extracted to nn/ridge.py; original public APIs
delegate to it with identical numerical results. No new regression framework.
Same EXPERIMENTAL host/worker and Lab; saved vectors/normal equations allow
stdlib-only verification without fits. This is retrospective local utility,
not a runtime update-policy promotion or another world-model training stack.

Scalar update/retain gate: seed/update_gate.py reuses PlasticityController(1)
logits, nonlinear_learning.fit_source's model factory, cumulative_learning's
posterior/fold/summary/validator helpers and update_diagnosis.trajectory. Same
metered host and Lab, no runtime promotion or parallel learning framework.
scripts/verify_seed_update_gate.py reuses the existing checkpoint verifier;
explicit audits fail on missing files, tracked weights allow exact restoration.

Task-blocked cumulative learning: seed/cumulative_learning.py uses the original
PlasticityController and the existing fit_source optimizer via a curve callback.
Its small dual solve assimilates permitted prefix/anchor rows. Four source folds
fit training-only preprocessing and new small rules; no historical weights are
retrained. Existing host/worker/runner handle caps, logs and immutable results.
Stdlib verifier reconstructs all24 new JSON checkpoints without retraining.

Bounded source comparison: seed/bounded_correction.py wraps the existing update
and reuses update_diagnosis trajectory/grid/arithmetic helpers. Its limiter
accepts only observed rows; it is not enabled in runtime adaptation. Same host,
worker and runner entry; cached baselines are verified rather than re-executed.

Source-only update diagnosis: seed/update_diagnosis.py reuses LessonTask,
initial/update/scaled and existing frozen PlasticityController weights. Its
fixed adapter uses the SAME EXPERIMENTAL host/meter; stdlib replay recomputes
recorded arithmetic without model inference or collection. No new learner.

Owner-controlled experimental host: seed/experimental.py and the fixed numeric
worker seed/experimental_worker.py reuse E1 Journal/canonical hashes, the existing
nn.factory and Learning Lab server. Run data stays under runs/experimental.
This is process supervision/development routing, not a second learner or memory.
New planner/simulator/GPU workers need reviewed metering before execution.
The vetted nonlinear-learning adapter (seed/nonlinear_learning.py) now routes a
single registered Seed study through that SAME host. It reuses existing update
math and frozen features. seed/nonlinear_learning_audit.py is stdlib-only for
complete-grid/resource arithmetic and fresh-clone GUI replay; no verifier fits
or collects data. Historical runner math remains unchanged.

Data-only audits: grounded_audit, contract_audit, learning_validation_audit,
readout_validation. Neural studies have explicit runner/config/protocol files.
A verifier must never silently fit a model or collect new scientific data.
The old original action-readout runner remains historical/unrun; the corrected
runner is scripts/run_seed_surprise_readout.py. Its one-run artifact is closed.

## Shared dependencies

The neural factory/expressions, existing meta-controller, planning interfaces
and running statistics have historical names but live Seed dependencies.
Use the source-only dependency audit before any removal. A static unreferenced
module is only a review candidate: dynamic imports and reproduction scripts may
still require it. No automatic code deletion based only on an import graph.

[Prior full map](history/seed-focus-2026-10-20/NEXUS_CODE_REUSE_MAP.md) retains
all older tracks and original module ownership. No generic memory, learning,
resource, planner or evolution framework is replaced.
