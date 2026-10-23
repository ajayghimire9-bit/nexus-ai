# NEXUS Seed — Current State

## Latest — symbiotic multi-backend workbench v1 (`seed-symbiotic-workbench-v1`)

Pre-registered at `4d053d4` on `codex/seed-symbiotic-workbench-v1` ([Protocol](NEXUS_SEED_SYMBIOTIC_WORKBENCH_V1_PROTOCOL.md), [Results](NEXUS_SEED_SYMBIOTIC_WORKBENCH_V1_RESULTS.md)):
- **Engineering & Verifier Repairs**: Repaired `scripts/verify_seed_conversation_capability.py` to reconstruct expected outputs independently from `configs/seed_conversation_capability_v1.json` and saved input CSVs (rejecting forged output/reference_output pairs while verifying existing `seed_conversation_capability_v1.json` untouched). Repaired post-commit cancellation in `src/nexus/seed/workspace_conversation.py` so cancellation arriving after atomic `os.replace` or SQLite commit preserves the receipt and workspace state and never reports the committed action as undone.
- **Multi-Backend Integration (`src/nexus/seed/symbiotic_workbench.py`)**: Connected `TypedActionProposal` execution contracts, `StatefulProgramEditor` (persistent node IDs, dependency conflict detection, selective undo, 6-step regional sales workflow, cross-schema AST capsule rebinding), `MultiFormatDataBackend` (CSV, nested JSON flattening/reconstruction, SQLite multi-table `JOIN` + `WHERE` vs `HAVING` + transactions), `PolyglotCodingWorkbench` (`tree-sitter-python` + `tree-sitter-typescript` CST indexing, multi-file Python repair, TypeScript `tsc --noEmit` + Node validation, selective undo), `StatefulZ3Coordinator` (`z3-solver` 5.3.1.0 `sat`/`unsat`/selective undo + model translation verification), `SymPySymbolicBackend` (verified algebraic roots, derivatives, equivalence), `Lean4ProofBackend` (rejects `sorry`/`axiom`; honestly reports `blocked_missing_runtime` when `lean` binary is absent on host), `HierarchicalPlanner` (3-level `project_goal` $\leftrightarrow$ `module_contract` $\leftrightarrow$ `function_or_program` invalidation & revalidation), `KnowledgeAndDocRetriever` (versioned docs + offline `WikidataSnapshotAdapter` contradiction detection & lexical-vs-grounded separation), and `StigmergicCapsuleRegistry` (behavioral probe gating, counterexample retention, active/cold consolidation, and `Profile A` $\to$ `Profile B` cross-profile capsule exchange without auto-execution on import) to `Conversation`, `SeedWorkspace`, and `/chat`.
- **30-Task Counterbalanced Benchmark**: Across 30 tasks in 7 categories (19 development, 11 confirmation), `model_tools_editor`, `ordinary_cache_templates_retrieval`, and `nexus_symbiotic_abstractions` each achieved **30/30** (`1` honest `blocked_missing_runtime` on `t19` Lean 4 binary check); `nexus_symbiotic_abstractions` reduced candidate/editor operations from `63` to `58` (`14` vs `17` on `data_programs`, `6` vs `8` on `capsule_transfer`) via cross-schema AST capsule rebinding and cross-profile capsule transfer. Controls `nexus_reset_memory` (`1/1`) and `nexus_wrong_memory` (`2/2`) passed. Live local GGUF model probe (`1` call, `1.3196s`) and independent tamper-rejecting verifier (`scripts/verify_seed_symbiotic_workbench.py`, `valid: true`) passed.
- **Claim Discipline & Ledger**: Demonstrates verified multi-backend tool orchestration, stateful selective undo, and bounded capsule reuse—**not** general learning-to-learn or AGI. Total run `3.240204s` wall / `0.598799s` CPU (`4.0s` debit). Latest accounted ledger: `2197.632103455996 s` used / `1402.367896544004 s` remaining.

## Latest — conversation correctness and capability matrix v1

Engineering fixes on `cursor/seed-conversation-correctness-matrix`: unsupported
comparisons clarify, fresh requests do not inherit filters, cancel is atomic,
explicit save stores the executed AST. Development evaluation
`seed-conversation-capability-v1` (protocol `14a19f9`) scored tools /
ordinary_cache / nexus_procedures **7/7** each; reset follow-up **0/1**; no
procedure benefit. JSON/SQLite/repair remain API-only, not chat.
[Results](NEXUS_SEED_CONVERSATION_CAPABILITY_RESULTS.md). Not confirmation,
not learning-to-learn, not AGI. Closed studies untouched. Ledger carry
unchanged: 2193.632103455996 s used / 1406.367896544004 s remaining.

## Latest — complete cheap configuration-repair baseline

Pre-run `d2eaec0a12a82c591142ae325b892d40eb52cfc5`,
`seed-config-repair-baseline-1`: 12/12 projects pass final/retention checks;
median original discovery 0.560646 ms, 0.958716% of repair wall. Practical
headroom FAILED; no learned comparison. Real bounded Python execution,
source-free AST edits and exact caches; no model calls or language claim.
126 targeted tests and independent saved-patch replay passed. Process/IPC
overhead dominates. [Results](NEXUS_SEED_CONFIG_REPAIR_RESULTS.md).
Latest ledger 2193.632103455996 s used /1406.367896544004 s remaining.

## Latest — boundary clarification resolves saved ambiguity cheaply

[Audit](NEXUS_SEED_CANDIDATE_IDENTIFIABILITY_RESULTS.md) ran once from
`3a24ad55f70a12e6c35212e8a789a93233efa14e`: seven distinct cases, all genuinely
different. A zero-valued singleton separates each pair in two program executions,
median 20.5 µs. No new answers/final assessments, model calls or learning study.
No need to canonicalize distinct semantics; no practical discovery headroom
established. Next: [baseline-first repository-maintenance proposal](NEXUS_SEED_PRACTICAL_DISCOVERY_NEXT.md),
not executed. Runtime and historical evidence remain frozen. Latest accounted
ledger: 2190.632103455996 s used /1409.367896544004 s remaining.

## Latest — discovery headroom not established at the practical floor

[Baseline preflight](NEXUS_SEED_DISCOVERY_HEADROOM_RESULTS.md) completed once
from `50d231555952f630d3debc1f3c4be2233d1bf054`: 28/28 correct; new-composition
median discovery 8.101 ms <10 ms locked floor, so practical screen FAILED.
The strong exact solver has direct compilation and source-free prefix caches;
no forced search, neural calls or learned-abstraction comparison. Persistent
runtime and prior evidence remain unchanged. Nine tasks retain ambiguous
candidates. Next: source-only identifiability audit. Latest accounted ledger:
2188.632103455996 s used /1411.367896544004 s remaining. Older entries follow.

## Latest — persistent assistant benchmark v2.1 FAILED

The [completed v2.1 study](NEXUS_SEED_ASSISTANT_BENCHMARK_V2_1_RESULTS.md) ran
144 trials after clean pushed revision `8fe8192e207bf95fa3b8b153f31913df2c7490e4`.
All three methods: 40/48 correct; 22 real model calls and 40 program executions
each. NEXUS made eight capsule reuses but no execution/correctness gain. Mean
startup-inclusive latency: 649.879 ms tools, 642.951 ms ordinary cache,
646.677 ms NEXUS. The primary screen failed; reset-level timing intervals
include zero. Existing artifacts and model weights remain intact; initial v2
startup failure is separately preserved. Latest accounted ledger:
2186.632103455996 s used / 1413.367896544004 s remaining.
Next: establish discovery headroom in richer multi-step workflows against the
same strong direct/tool-cache baseline. No further study has run.

## Master Architecture & Unified Workspace (Engineering Demonstration of Within-Family Search-Prior Reuse)

The [15-Component Seed Master Architecture](NEXUS_SEED_MASTER_ARCHITECTURE.md) (`src/nexus/seed/master/`) and its [Bounded Exact-Motif Program-Prior Reuse Demo & Bounded Multi-Reasoner Integration Suite](../src/nexus/seed/master/meta_learning.py) are implemented and verified over the existing `Session`, `SharedBrain`, and `E1 Journal`. In [meta_learning.py](../src/nexus/seed/master/meta_learning.py), learning operator and macro priors from solved source tasks reduces candidate program search evaluations from `9.5` to `1.75` (`81.58%`) when source and target curricula share the same 3 canonical motifs (`sort->unique`, `reverse->increment`, `even->sort`) alongside the 6-domain bounded multi-reasoner integration suite (`relational`, `constraint`, `mathematical`, `causal`, `analogical`, `hierarchical_planning`). Genuine held-out learning-to-learn on canonically and semantically disjoint target compositions is tested separately in `seed_disjoint_meta_v1` below and remains unestablished.

## Latest — Meta-Rule Evolution v2 (Leakage-Repaired), Black-Box Open Primitive Code Transfer v1 & 10-Part Integrated Architecture PASSED all registered gates

Clean execution `4bc6443e939287f80bac50cbdfa935e6b5bf0049` (`seed-open-primitive-transfer-1`, `seed_open_primitive_transfer_v1` & `seed_integrated_architecture_v1`). Following the adversarial v1 audit ([NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md), [`artifacts/seed_meta_rule_evolution_v1_audit.json`](../artifacts/seed_meta_rule_evolution_v1_audit.json)) confirming all 15 v1 confounds while preserving `artifacts/seed_meta_rule_evolution.json` (`818300f5100bccf5fcbb461b03aee86742b2173847bbd09d1f52dbd811ec8292`), Stage A enforced strict `LearnerTaskView` vs `EvaluatorTaskPrivate` separation (`zero_leakage_verified = true`), real counted candidate execution (`2,811,060` candidate executions, `955,958` hidden evaluations), uniform mutation across 14 opcodes and 7 operators (`guided_rule_injection_enabled = false`), in-loop Dream novelty without `seed`, real pre/post retention (`1.0000` -> `1.0000`, `worst_regression = 0.0`), and real Sleep test re-execution (`old_capsule_test_pass_rate = 1.0000`, `mdl_before = 27.25 -> mdl_after = 27.25`) over 3 non-isomorphic families (`list_transformations`, `boolean_circuit_induction`, `fst_string_rewrite`) across 8 seeds (`1762000001..1762000008`). `evolved_meta_rule` achieved `1.0000` task success and `1.0000` retention at `11.2244` mean episodic compute cost (`3.8125` candidate executions, `1.5938` experiments), beating `exact_information_gain_plus_effect_composition` (`19.6275`, paired diff `+8.4031`, CI `[+4.7622, +12.0441]`), `exact_information_gain_learner` (`97.0508`, paired diff `+85.8265`, CI `[+82.4780, +89.1750]`), and untouched `random_evolutionary_selection` (`0.3229` success, `42.1309` cost). Frozen before Stage B (`FREEZE_STAGE_A_EVOLVED_RULE`), the rule entered `UnknownLibraryCodeLab` via `CommonEnvironmentAdapter` over 3 multi-file unknown-library families generated after freezing (`ulib_window_checksum`, `ulib_runlength_bucket`, `ulib_zigzag_interleave`, each with 1 true helper + 2 decoy helpers, 3 candidate post-steps, and 3 call sites) evaluated by an isolated black-box evaluator subprocess (`src/nexus/seed/blackbox_evaluator_worker.py`, `private_inputs_exposed_to_learner = false`), executed its evolved instruction sequence via `execute_code_lab_rule_interpreter` (`method_specific_hardcoded_policy_branching = false`, verified by unconfounded causal instruction ablations where removing `PROPOSE_PRIMITIVE` keeps AST inspection, helper probing, all 12 hypothesis constructions, and AST patch synthesis identical), acquired and promoted new primitives via `PROPOSE_PRIMITIVE` (`24/24` traversing all 6 kernel lifecycle stages to `PROMOTED`), synthesized its own AST patch (`def solve_pipeline(seq): return ...`), achieved `1.0000` hidden subprocess accuracy vs `0.0000` for `learner_without_propose_primitive` under strict execution-scope registration (`without_propose_tests_execution_scope_registration_only = true`), reduced compute cost from `92.4438` (`strongest_handwritten_learner`, `9.1250` experiments) and `47.5500` (`exact_information_gain_plus_effect_composition`) to `34.9146` (`2.3750` experiments; paired diffs `+57.5292`, CI `[+45.0887, +69.9696]`, and `+12.6354`, CI `[+7.7556, +17.5153]`), beat `direct_helper_import_without_capsule` (identical access and costs, cheaper on a single task at `32.3146` vs `34.9146`) across 4 sequential fresh tasks ($T_1 \dots T_4$: breaking even by $T_2$ at `51.5271` vs `64.6292` and reducing 4-task cumulative cost from `127.6958` to `84.7521`, paired diff `+42.9438`, CI `[+30.8344, +55.0531]`; `5.3750` vs `9.5000` experiments, CI `[+2.8270, +5.4230]`), and transferred the promoted primitives under invented words (`krelv`, `voux`, `zarn`) across distinct downstream tasks in all 4 labs (`Language`, `Coding`, `Reasoning`, `World`: `1.0000` accuracy via neural utterance parsing and autonomous cross-domain adapter induction vs `0.0000` for `isolated_labs` and `<= 0.1875` for non-null-callable `capsule_removed`, `unlearned_binding`, and `unlearned_adapter` controls, `1.0000` old-skill retention). In addition, the [10-part NEXUS Seed Integrated Architecture](NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md) (`src/nexus/seed/integrated_architecture.py`, [`artifacts/seed_integrated_architecture_v1.json`](../artifacts/seed_integrated_architecture_v1.json)) passed all `10/10` component and end-to-end gates (including trainable 10,970-param subword + fixed-length position-conditioned token-level `SmallNeuralLanguageCodec` evaluated across 36 held-out utterances, outer-loop meta-trained `SmallLearnedOptimizer`, trajectory-learned TD($0$) `SuccessorFeatureLearner` in the 5×5 `ResourceGridEnv`, hypothesis-sensitive `synthesize_compound_probe`, evidence-directed mutation across 4 mechanisms, and tamper-rejecting independent verification). **NEXUS demonstrated bounded executable learning-rule transfer and acquired one previously unavailable primitive from sandboxed code interactions. This does not establish arbitrary coding, general language understanding, unrestricted self-improvement or AGI.** [Results](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_RESULTS.md), [protocol](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md), [integrated architecture](NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md). No live promotion.

4096 real steps, 5120 evolutionary rule evaluations, zero neural forwards; 26-second debit (`24.211062s` wall, `24.150074s` CPU). Ledger `2078.632103455996` used / `1521.3678965440042` remaining. All 831 historical `main` artifacts and frozen checkpoints unchanged; independently verified in `artifacts/seed_open_primitive_transfer_audit.json` (`valid: true`). Older entries retain their original chronology.

## Latest — Combined Wake–Sleep–Dream–Evolution Architecture & Meta-Rule Evolution v1 PASSED all 9 registered gates

Clean execution `322583377f03ccca702dda5478d158f57c1b0408` (`seed-meta-rule-evolution-1`, `seed_meta_rule_evolution_v1`). Over an immutable trusted kernel (`kernel_sha256_before == kernel_sha256_after`), 32 learning-rule programs (10–30 typed instructions over 13 opcodes and 7 mutation operators) were evolved for 20 generations across 8 independent seeds (`1751000001..1751000008`, `5,120` rule evaluations) using lexicographic and Pareto selection over separate Episodic and Continual evaluations, Dream regret-driven adversarial task generation (`64` admissible tasks, `16/16` inadmissible foils rejected, `archive_cycle_rate = 0.0`), and Sleep Stitch-like subprogram compression (`mdl_before = 34.0 -> mdl_after = 32.0`, `mean_mdl_reduction = 2.0`, `100%` old-capsule test pass rate, `neural_decides_truth = False`). Frozen before generating the sealed final family (`sealed_action_state_transitions` with new sensor `thermal_flux`, action `calibrate_shield`, and hidden variable `latent_drift_polarity`), `evolved_meta_rule` constructed unseen length 4–5 concept capsules from primitive models (`stored_whole_program_fingerprints = 0`, `manually_supplied_cross_lab_mapping = False`, including `"zorp"` $\to$ `["even", "decrement", "reverse", "unique"]`), achieved `1.0000` task success and `1.0000` (`>= 0.98`) protected old-skill retention, and beat `exact_information_gain_learner` across all 4 independent grammars (`list_transformations`, `boolean_mechanisms`, `relational_graphs`, `sealed_action_state_transitions`) and all `8/8` seeds: `1.0000` vs `3.0000` experiments (`66.67%` reduction) and `5.2361` vs `69.8039` episodic execution cost (`92.50%` reduction; `4.9080` continual; sealed diff `+64.4656`, CI `[+63.8448, +65.0864]`; overall diff `+64.5678`, CI `[+64.3495, +64.7860]`). Removing the evolved rule eliminated the gain, and `random_evolution_control` (`68.2535` cost, `0.0` retention) and `rule_size_only_control` (`0.2500` accuracy) failed. **Adversarial v1 audit ([NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md), [`artifacts/seed_meta_rule_evolution_v1_audit.json`](../artifacts/seed_meta_rule_evolution_v1_audit.json)): Meta-Rule Evolution v1 passed its internal synthetic contract but does not establish bounded learning-to-learn because evaluator-derived hypothesis labels, isomorphic grammar families, guided rule injection and non-executed protected assessments confound the result.** [Results](NEXUS_SEED_META_RULE_EVOLUTION_RESULTS.md), [protocol](NEXUS_SEED_META_RULE_EVOLUTION_PROTOCOL.md). No live promotion.

3072 real steps, 5120 evolutionary rule evaluations, zero neural forwards; 6-second debit (`4.969516s` wall, `4.845922s` CPU). Ledger `2052.632103455996` used / `1547.3678965440042` remaining. All 831 historical `main` artifacts and frozen checkpoints unchanged; independently verified in `artifacts/seed_meta_rule_evolution_audit.json` (`valid: true`). Older entries retain their original chronology.

## Latest — task-conditioned program ranking & sealed compositional replication PASSED all 7 registered gates

Clean execution `cc57cddff4491a93b76a842e43a85229216f0bce` (`seed-task-conditioned-replication-1`, `seed_task_conditioned_replication_v1`). Following the source-only 17-dimensional input-output signature audit ([NEXUS_SEED_SIGNATURE_AUDIT_RESULTS.md](NEXUS_SEED_SIGNATURE_AUDIT_RESULTS.md), `target_outcomes_accessed: false`, `17/17` unique source signatures, `87.54%` LOSO evaluation reduction vs `flat_catalogue`), the grammar was expanded to 6 operators (`reverse`, `sort`, `unique`, `increment`, `decrement`, `even`; `258` raw $\to$ `100` canonical $\to$ `65` semantically unique: `18` source, `23` quarantined `v1` targets, `24` fresh sealed `decrement` targets with `0` overlap against both source and exposed `v1` targets). Across 8 families and primary budgets $B \in \{1, 2, 4\}$, `deterministic_signature` ($S(p\mid D_B) = -\|\operatorname{signature}(D_B)-\operatorname{signature}(p)\|_1 + 0.05 S_{\text{structural}}(p) - 0.05 \operatorname{len}(p)$) required **`1.0000` mean evaluations** (`72` total across 72 task-budget pairs, `1.0000` held-out accuracy), beating `flat_catalogue` (`12.7083`, `92.13%` reduction, CI `[+8.0858, +15.3309]`), `shortest_program` (`28.2500`, `96.46%`, CI `[+22.8495, +31.6505]`), `exact_macro_cache` (`30.5000`, `96.72%`, CI `[+25.9971, +33.0029]`), `random_ordering` (`33.0130`, `96.97%`, CI `[+30.9743, +33.0517]`), task-independent `structural_meta_prior` (`42.3333`, `97.64%`, CI `[+32.7933, +49.8734]`), and `operator_frequency` (`50.2500`, `98.01%`, CI `[+42.7422, +55.7578]`), while also outperforming `bayesian_version_space` (`1.3333`) and `learned_linear_ranker` (`5.6250`). Old-source retention held at `1.0000` accuracy and `1.0000` evaluations before and after target adaptation. Cross-domain transfer under a supplied mapping (`action_token_sequence`) reduced evaluations from `48.0417` (`scratch_flat`) to `1.0000` (`97.92%` reduction, CI `[+43.3523, +50.7310]`). Real cross-lab transfer (`Language` $\to$ `Coding` $\to$ `Reasoning` $\to$ `World`, [NEXUS_SEED_CROSS_LAB_TRANSFER_RESULTS.md](NEXUS_SEED_CROSS_LAB_TRANSFER_RESULTS.md)) reduced downstream evaluations from `66.0` (`scratch_learning`) to `1.0` (`98.48%` reduction) with `1.0000` downstream accuracy and `1.0000` World Lab goal completion vs `0.0000` for `isolated_labs`. [Results](NEXUS_SEED_TASK_CONDITIONED_REPLICATION_RESULTS.md), [protocol](NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md). No live promotion.

2624 real steps (`1152` source teaching, `192` target teaching, `1280` assessment), 16 ridge fits ($d=23$ and $d=20$), zero neural forwards or simulator steps; 8-second debit (`6.709615s` wall, `4.442347s` CPU). Ledger `2046.6321034559958` used / `1553.3678965440042` remaining. All 831 historical `main` artifacts and frozen checkpoints unchanged; independently verified in `artifacts/seed_task_conditioned_replication_audit.json` (`valid: true`). Older entries retain their original chronology.

## Latest — disjoint compositional meta-learning replication FAILED its registered screen

Clean execution `540a30596814ec1687db13e7e38cdc0ab43aa701` (`seed-disjoint-meta-1`, `seed_disjoint_meta_v1`). Over the 41 semantically unique programs of length $1\dots 3$ in $\mathcal{O} = (\text{reverse}, \text{sort}, \text{unique}, \text{increment}, \text{even})$ (`155` raw $\to$ `68` canonical $\to$ `41` unique across 781 probes), holding out 5 adjacent pairs partitioned the grammar into `17` source programs and `24` canonically and semantically disjoint target programs (`0` overlap). Across 8 non-repeating families and budgets $B \in \{1, 2, 4\}$, `structural_meta_prior` required `18.555556` construction-inclusive evaluations (held-out accuracy `0.911458`), beating source-fitted `exact_macro_cache` (`26.902778`, CI `[+3.103318, +13.591126]`), `bayesian_model_based` (`25.263889`, CI `[+2.491547, +10.925120]`), and `operator_frequency` (`24.527778`, CI `[+1.882069, +10.062375]`), and averaging fewer evaluations than `shortest_program` (`22.402778`, CI `[-2.398620, +10.093065]`) and `random_ordering` (`18.745009`, CI `[-3.644101, +4.023007]`), but losing to `flat_catalogue` (`15.583333`, accuracy `0.921875`, CI `[-10.684631, +4.740186]`). Old-source retention accuracy improved from `0.854818` to `0.881510` (search cost `28.072917 -> 21.125000`, `-24.75%`), below the `0.98` gate. Structural transfer under a supplied mapping (`action_token_sequence`) required `17.652778` evaluations (accuracy `0.942708`), beating `exact_macro_cache` (`19.625000`) and `bayesian_model_based` (`23.291667`), but trailing `scratch_flat` (`16.722222`). **The registered bounded learning-to-learn screen failed. The architecture and benchmark remain useful engineering infrastructure, but useful learning-to-learn was not established.** [Results](NEXUS_SEED_DISJOINT_META_RESULTS.md), [protocol](NEXUS_SEED_DISJOINT_META_PROTOCOL.md). No live promotion.

2496 real steps (`1024` source teaching, `192` target teaching, `1280` assessment), 8 ridge fits ($d=23$), zero neural forwards or simulator steps; 33-second debit (`31.431138s` wall, `20.690358s` CPU). Ledger `2038.6321034559958` used / `1561.3678965440042` remaining. All 831 prior artifacts and frozen checkpoints unchanged; independently verified in `artifacts/seed_disjoint_meta_audit.json` (`valid: true`). Older entries retain their original chronology.

## Latest — fresh query-conditioned acquisition FAILED both screens

Clean execution 609c4d46654826a539494a6a201338bf73bc0e09. On 128 fresh programs
excluding all prior 192 identities, conditioned primary MSE .230198 versus blind
.218490, equal-parameter blind .218832, uniform model-based .212389 and
source-informed .210423. Conditioned lost to blind in all eight selector fits;
paired blind-minus-conditioned -.011707 [-.018121,-.005293], exploratory n8/df7.
Both registered screens failed. The earlier missing-query-information audit
remains valid; these geometry features do not demonstrate useful questioning.
[Results](NEXUS_SEED_CONDITIONED_ACQUISITION_RESULTS.md). No live promotion.

2048 authored labels, 24 small ridge fits, zero neural forwards or simulator
steps; 6-second debit. Ledger 2005.6321034559958 used /1594.3678965440042 remaining.
All 826 prior artifacts unchanged. Next: one source-only utility-label reliability
audit on saved SOURCE cases, comparing realized utilities with posterior-expected
gains. No new labels, target tuning or architecture sweep; not run.
Older entries retain their original chronology.

## Latest — query-context information limitation demonstrated

The source-only audit completed from clean execution
071fe025d4f0d1a1de68ddc35b5fbf07cfa88d37. Optimal question sets conflict across
public query inputs in 489/512 source-prefix contexts; 445 exceed the registered
0.0001 mean-query regret threshold. The ten-feature selector omits relevant query
information under the supplied uniform prior. This does not explain the prior
failure causally or establish better actual learning. No policy promotion.
[Results](NEXUS_SEED_QUERY_CONTEXT_RESULTS.md).

Zero new labels, fits, neural forwards or simulator steps; 3-second debit.
Ledger: 1999.6321034559958 seconds used / 1600.3678965440042 remaining.
All 822 prior artifacts preserved. Next: one fresh, separately registered
query-conditioned acquisition comparison against query-blind and full model-based
selection, with actual independent query error and matched budgets. Not run.
Older entries preserve their chronology.

## Latest — source-trained acquisition completed; both screens FAILED

Clean execution2a7670284a6a530c8cb739c340ec6a7a06971ef7. Eight new10-coefficient
selectors,128 source and64 globally excluded target Boolean programs. Primary
1/2/4 query MSE.221353 versus variance.219191, fixed order.215762, model-based
.214463 and source-informed model-based.210662. Uniform expectation.238161 and
source-static.227639 are weaker. Only3/8 variance wins; both locked screens
failed. Budget8 is identical for every non-keep policy, as required. No promotion
or general learning-to-learn claim. [Results](NEXUS_SEED_SOURCE_ACQUISITION_RESULTS.md).

3072 authored labels, eight numerical ridge fits,zero neural forwards or simulator
steps;6s debit. Ledger1996.6321034559958s used /1603.3678965440042s remaining.
All818 previous artifacts preserved. Next: source-only query-context sufficiency
audit—can identical ten-feature descriptions require different expected-value
question rankings when the public query set changes? No new labels; not run.
Older entries retain their original chronology.


## Latest — source-inferred investigation completed; learned hybrid FAILED

Execution3fb6831aa9282e55828cb4158dd4e6278d66117a; eight new independently
drawn authored response tables,256 targets. Source-only teaching reconstructs
all outcome models, then freezes them. Hybrid3.046875 questions versus compiled
and online greedy3.015625; compiled-minus-hybrid−.031250[−.079625,+.017125],
exploratory n8/df7. Hybrid work19880 versus compiled9765; its quality/efficiency
screen failed. Compiler exactly matches online decisions and passes its separate
cost screen. This is ordinary source model inference, not learned learning-rule
improvement. No neural training, simulator run or live promotion.
[Results](NEXUS_SEED_INFERRED_INVESTIGATION_RESULTS.md). All814 old artifacts intact.

12544 authored interactions INCLUDING256 source class annotations;3s debit.
Ledger1990.6321034559958s used /1609.3678965440042s remaining. Next: separately
test learned source-question acquisition on fresh structured families with
incomplete source coverage, against equal-budget fixed/random and uncertainty
controls. Not executed. Older entries retain their original chronology.


## Latest — source-free compiled greedy audit PASSED its cost/exactness screen

Clean execution7081cc79c0e7f8a98125db7864cfcc3e17d1cb88, one saved-data-only
audit. Compiled greedy exactly matches online greedy on all96 saved tasks:
3.000 questions versus learned hybrid3.041667. Construction-inclusive work
2208 versus hybrid6012 (63.27% fewer proxy operations, not wall/FLOPs).
The hybrid retains slightly higher early classification accuracy; compiled
greedy has lower Brier error. Question interval includes zero. Source learning
is not needed for these compute savings under the fully supplied eight-law
grammar; learning-to-learn remains unestablished. No live promotion.
[Results](NEXUS_SEED_COMPILED_GREEDY_RESULTS.md). All810 prior artifacts preserved.

Zero new data, model fitting or neural inference;2s debit. Ledger
1987.6321034559958s used /1612.3678965440042s remaining. Next: separately test
investigation transfer when query-outcome rules must be inferred from source
experience, against equally informed compiled and online planners. Not executed.
Older entries retain their original chronology.


## Latest — balanced independent-tree replication FAILED

Execution93284549aa8399f15fbb2016a192b5f1214b6b1e, three newly source-trained/frozen trees,96 fresh rule-balanced targets. Hybrid3.041667 questions versus greedy3.000; greedy-minus-hybrid−.041667[−.220944,.137611], n3/df2. Tail and compute gates pass (99.20% fewer search checks;46.93% less source-inclusive work proxy), but the zero mean-regression requirement fails. No statistical superiority/inferiority claim, no promotion. [Results](NEXUS_SEED_INVESTIGATION_REPLICATION_RESULTS.md).

4608 authored observations;2s debit; ledger1985.6321034559958s used /1614.3678965440042s remaining. [Phase1–7 bounded workflows](NEXUS_SEED_PHASE1_7_WORKBENCH.md) are connected and tested, including expression phrases and rollback; their broad scientific claims remain open. Next: source-only exact compiled-greedy baseline audit using public grammar/saved arrays, no new collection. Older entries retain their chronology.


## Latest — selective greedy fallback passed its development screen

Frozen-tree hybrid averaged2.96875 questions versus tree-fixed3.15625, pure greedy3, fixed4 and random4.4375. It removed all6 five-question cases and used60 versus3328 search checks; source-inclusive work1991 versus3776 (47.27% lower proxy, not wall speed). Greedy question-difference interval includes zero; equal-rule descriptive reweighting favors greedy3 versus hybrid3.125. This is one frozen tree in a supplied grammar, not general learning-to-learn. No promotion. [Results](NEXUS_SEED_INVESTIGATION_HYBRID_RESULTS.md), [protocol](NEXUS_SEED_INVESTIGATION_HYBRID_PROTOCOL.md).

Execution32670a1aab235f979e1e836059da024021c4f709; one run,1280 new authored observations,2s debit. Ledger1983.6321034559958s used /1616.3678965440042s remaining. Next: independently source-trained frozen-tree replications with rule-balanced fresh targets against pure greedy; no second run. Older entries below retain their chronology.


## Latest — frozen investigation transfer FAILED its registered screen

Clean execution60eefee173b3cbf62a858ba397b06bdb54b373ca; one complete authored development run. Learned3.375 questions versus fixed4.21875/random4.5625, but greedy and exhaustive3.000. Budget-two gain over fixed4.6875pp missed5pp; extra questions versus strong baselines.375 exceeded.25. No promotion or general learning-to-learn claim. All797 historical artifacts and frozen checkpoints preserved. [Results](NEXUS_SEED_INVESTIGATION_TRANSFER_RESULTS.md), [protocol](NEXUS_SEED_INVESTIGATION_TRANSFER_PROTOCOL.md).

Debit2s; carried1981.6321034559958s used /1618.3678965440042s remaining. Next: separately register fixed versus greedy fallback at tree-abandon states against pure greedy; no second run here. Older entries below retain their original chronology.



Latest study base:e381132c79a2d3c71aed883e54b8577ecd0071ec;
executionbc57da126051d0aa5d148fcbf05bb4704f2571e1. Read
[master context](MASTER_CONTEXT.md) and [reuse map](NEXUS_CODE_REUSE_MAP.md).

## Established within the tested authored setup

[Foundation engineering](NEXUS_SEED_FOUNDATION.md) extends the same journal with
typed composition, checked macros, six supplied curriculum stages, attributed
text ingestion, conflict/rehearsal views, bounded investigation and grounded
wording. New `/foundation` interface; no new scientific execution or efficacy
claim. Base5a554a5853cec039d1e3ab6eaefb0c1265d86cec; old evidence stays closed.

The new [conversation workspace](NEXUS_SEED_CONVERSATION_WORKSPACE.md) is an
engineering interface over the same SharedBrain, verified library and Session
journal. Guided teaching, correction, fresh checks, skill use, world goals,
local CSV grouped-totals/rows, explicit procedure reuse and local save/restore
work through chat; original four labs remain supporting views. An optional
owned local model may serve ordinary chat; missing weights are reported, not
replaced by templates. No new scientific study, neural fitting or
learning-efficacy claim follows.

Shared-labs engineering adds one common Session/skill interface for language,
coding, reasoning and world tasks. Skills require separate authored checks;
new programs are bounded typed data, not arbitrary source. Optional shared
frozen encoding, existing bandit statistics and durable storage are reused.
Cross-lab fixture execution is functional, not scientific transfer evidence.
See [guide](NEXUS_SHARED_LEARNING_LABS.md). Prior improvement screens stay failed.

Finite teaching/correction/persistence works. The shared observation-time and
memory contracts are tested. The frozen-core nonlinear action readout passed
its fresh development screen and improved goals/returns against frozen ranking,
random and latent MPC. Known-grid greedy remains stronger. One core, not
independent world-model replication.

## Not established

Useful learned plasticity versus scaled replay; broad meaning acquisition;
continual learning; generalization across families; learning-to-learn; AGI.
The future-edit selector tied historical-best. Rank-four adaptation is not
enabled. Improved action scoring by ordinary supervised fitting is not evidence
that NEXUS learned a better learning procedure.

## Next gate

Optional executable core completed its first source prediction study: induced
Brier0 versus fixed .238707 and all-history .050260 on eight authored tasks;
source screen PASSED. Noisy error remains .101881, unavailable proposals all
rejected, GRU recipe generalizes poorly. No live promotion or learning-to-learn
claim. [Results](NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md). Next: separately register
a frozen investigation-reuse test with explicit target-support bindings. Prior
question-utility failures stay closed; their reliability audit remains unrun.
Ledger1979.6321034559958 used /1620.3678965440042 remaining.

The ten-scalar answer-free predictor completed from8d9bdad and FAILED the
budgets1/2/4 source screen: .170313 versus variance .173580/keep .173857;
required intervals include zero,6/12 keep wins. Retention passes. Budget8 is
secondary, not ranking evidence. No new collection, neural fitting or promotion.
Next: recorded utility-label reliability audit, not another capacity change.
[Results](NEXUS_SEED_ANSWER_FREE_UTILITY_RESULTS.md). Older entries follow.

The task-blocked question-utility predictor completed and FAILED its source
screen: .168235 learned versus action mean .169743 and variance .170092,
paired intervals include zero;6/12 keep wins. No new world/model execution
or live promotion. Same learner and excluded-task outcome isolation preserved.
Next: utility-label reliability audit using recorded query subsets/fits, before
changing capacity. Not yet run. [Results](NEXUS_SEED_QUESTION_UTILITY_RESULTS.md).

Older next-gate entries below preserve their chronology.

The larger source query bank passed its within-task stability screen: locked
choice MSE .159819 versus variance .170092 and keep .170649,9/12 task wins.
One run collected2592 authored outcomes; same supports/learner and frozen core.
Original invalid parameter-count capture preserved; separate offline validation
corrected the count without replay. Next: task-blocked source question-utility
learning, not yet fitted. This is evaluator-only utility stability, not learned
questioning or task confirmation. [Results](NEXUS_SEED_QUERY_REPLICATION_RESULTS.md).

Older next-gate entries below preserve their chronology.

The evaluator-only pool-headroom audit is complete: an optimistic query oracle
passes the source screen (.174050 versus variance .193552), but omitted-query-
state selection fails (.194374 versus keep .194222). This bounds available
opportunity; it is not useful learned question selection or learning-to-learn.
Next: a larger independently collected source query-bank replication with the
same supports/learner, to test utility stability before training a selector.
See [results](NEXUS_SEED_QUESTION_HEADROOM_RESULTS.md).
Older next-gate entries below preserve their chronology.

The fixed-learner informative-question test is complete and FAILED its source
screen: MSE .193552 versus random .191753, difference −.001799 with an interval
including zero. Original-order damping reproduces .180187 exactly. Retention
passed; no learned question-policy advantage or live promotion. Next: an
evaluator-only source pool-headroom audit to check whether useful candidate
questions exist before training their selector. See
[results](NEXUS_SEED_QUESTION_SELECTION_RESULTS.md).
Older next-gate entries below preserve their chronology.

One policy-roll-in refit plus the protected learn/ask/retain advisory is now
complete: all improvement screens FAILED. Protected curve .210911 versus
constant .180187; known-anchor cap and retention tolerance pass.4 learn /80 ask /
12 retain decisions do not establish useful question selection. Keep the module
optional in the sandbox. Next: informative versus random question choice with
the strong constant-damping learner fixed, separately registered. See
[results](NEXUS_SEED_LEARNING_CHOICE_RESULTS.md).
The following older next-gate entries retain their chronology.

Sequential replay of the frozen consistency selector is now complete: source
screen FAILED, retention tolerance passed. Curve MSE .201848 versus constant
.180187 and replay .187016; only11/96 updates. Prior local-regret evidence did
not establish a useful sequential procedure. All84 baseline trajectories match
exactly; no promotion. Next proposal is one training-only policy-roll-in refit
versus an equal-budget reference-state refit, not more capacity. See
[results](NEXUS_SEED_SEQUENTIAL_CONSISTENCY_RESULTS.md).
Older next-gate wording below is retained as historical chronology, superseded
by this result.

The teaching-prefix feature audit failed: full utility-prediction MSE .002908
versus constant .002250, prefix mean .002084. Consistency-only local regret has
an uncertain positive lead; no actual sequential adaptation was tested. Next
proposal: source-only sequential replay against trained fractional damping,
replay and bounded baselines before fresh validation. No promotion. See
[results](NEXUS_SEED_PREFIX_CONSISTENCY_RESULTS.md).
Earlier decisions below retain their chronology.

The learned scalar update/retain gate also failed its source screen: .180324
curve MSE versus constant .180187; generic damping helps but context conditioning
does not beat constant. Retention passed; no promotion. Next is a proposed
source-only prefix-consistency informativeness audit, not capacity growth or
another run here. See [results](NEXUS_SEED_UPDATE_GATE_RESULTS.md).
The earlier study decisions follow in chronology.

The registered nonlinear-feature comparison completed and failed: learned
plasticity did not beat strong replay or static protection; learned/static/fixed
actions matched. See [results](NEXUS_SEED_NONLINEAR_LEARNING_RESULTS.md).
Source-only first-update diagnosis completed:12.55×median norm ratio,5/12tasks
harmed; broad-harm screen not supported. Later-prefix oscillation remains a
source-only lead. The subsequent bounded comparison improved source stability
by 13.5%, but failed strong-replay and learned-specific practical screens.
The task-blocked cumulative learner has also failed the5% source screen: .31%
gain over source-trained static and worse than replay/bounded fixed. Retention
passed; no fresh validation or runtime promotion. Next proposed scalar update/
retain gate versus a source-trained constant gate. See
NEXUS_SEED_CUMULATIVE_LEARNING_RESULTS.md.
The paragraphs below retain earlier gates.

### Historical setup stage, superseded by the result above

Owner-controlled [EXPERIMENTAL mode](NEXUS_EXPERIMENTAL_MODE.md) provides a
development sandbox, not a new capability claim. Architecture/optimizer/HPO
iterations use small bounded manifests; validation and confirmation stay
separate. No new scientific experiment ran during setup.

Frozen spatial transfer passed versus frozen ranking,with greedy stronger,
boundary initial-ranking weakness and cross-diagonal goal failures. No fitting.
See [results](NEXUS_SEED_SPATIAL_TRANSFER_RESULTS.md). Next is a separately
registered nonlinear-feature learning-curve study. The readout-to-existing-update
bridge is implemented/tests only,not enabled. Closed audits cannot select new
hyperparameters. See [proposal](NEXUS_SEED_READOUT_LEARNING_PROPOSAL.md).

## Start and verify

Use the [quickstart](seed/QUICKSTART.md), [architecture](seed/ARCHITECTURE.md)
and [registry](NEXUS_FULL_RESEARCH_REGISTRY.md). Previous detailed state is
[archived verbatim](history/seed-focus-2026-10-20/NEXUS_CANONICAL_CURRENT_STATE.md).
Historical code remains available where provenance or shared dependencies need it.
