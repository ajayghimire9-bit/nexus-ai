# NEXUS Seed

**Latest: [capability/evidence audit](docs/NEXUS_SEED_CAPABILITY_AUDIT_RESULTS.md).**
The corrected pilot failed its improvement screen: learned investigation solved
19/24 tasks versus fixed boundary-first 24/24. Actual Python/TypeScript coverage
passed 3/6 projects; live local intent inference and restart checks passed.
[Actual call paths and capability limits](docs/NEXUS_SEED_CAPABILITY_ARCHITECTURE_AUDIT.md).
No general learning-to-learn claim. Prior results below remain historical.

**Latest repair baseline:** [fixed multi-file configuration workload](docs/NEXUS_SEED_CONFIG_REPAIR_RESULTS.md)
repaired **12/12 projects** and passed all final/retention checks. Discovery was
**0.56 ms**, only **0.96%** of repair wall; subprocess overhead dominated.
No practical discovery headroom, so no learned-repair study followed. This
tool-first baseline derived the supplied contract from public tests without
neural inference. The persistent runtime and prior evidence remain unchanged.

**Latest saved-data audit:** [candidate identifiability](docs/NEXUS_SEED_CANDIDATE_IDENTIFIABILITY_RESULTS.md)
found genuinely different programs in all seven distinct unresolved cases, but
one all-zero boundary row separates each pair. Median construction: **20.5 µs**,
two program executions; zero new answers or model calls. This family still lacks
practical discovery headroom. A different baseline-first task proposal is ready;
no learning comparison or new practical-task experiment has run.

**Latest baseline preflight:** [ambiguous workflow headroom](docs/NEXUS_SEED_DISCOVERY_HEADROOM_RESULTS.md)
solved 28/28 authored tasks with an exact source-free cached solver. New
compositions required median 8.10 ms discovery, below the locked 10 ms floor:
**practical screen failed**. No abstraction-learning comparison followed. This
symbolic preflight made zero model calls; the persistent runtime is unchanged.

**Closed assistant study:** [persistent local assistant v2.1](docs/NEXUS_SEED_ASSISTANT_BENCHMARK_V2_1_RESULTS.md)
completed all 144 trials and **failed its development screen**. All methods
scored 83.33%; retained AST capsules added no correctness/candidate-count benefit
and did not beat ordinary caching in measured latency. The real persistent GGUF
runtime, explicit cache accounting and independent saved-data verifier work.
[Runtime guide](docs/NEXUS_LOCAL_ASSISTANT_RUNTIME.md). The initial startup failure
is preserved separately; older research entries below retain their chronology.

**Teach. Remember. Act. Learn how to learn.**

A local research agent for learning finite concepts, using memory and making
decisions in a small authored world. Learning-to-learn is the goal, not a
capability we already claim. No external LLM or API key is required at runtime.

**Active research:** NEXUS Seed and measured learning-to-learn. The GitHub
`main` branch carries this work; earlier control and Evolution studies remain
preserved research. Future experiments use separate bounded research branches.

## Latest research result

[NEXUS Seed Real-Data Adapter Learning & Wall-Breaking Pillars v1](docs/NEXUS_SEED_REAL_DATA_ADAPTER_LEARNING_V1.md),
[10-Part NEXUS Seed Integrated Architecture & Black-Box Open Primitive Code Transfer v1](docs/NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md),
and [Meta-Rule Evolution v2 (Leakage-Repaired) & Open Primitive Code Transfer v1](docs/NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_RESULTS.md)
([protocol](docs/NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md),
[v1 adversarial audit](docs/NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md)) **passed
all `10/10` Real-Data Adapter Learning & Wall-Breaking Pillars gates (`artifacts/seed_real_data_adapter_learning_v1.json`),
Stage A, Black-Box Subprocess Stage B (`12/12` gates), and all `10/10` Integrated Architecture gates** (`seed-open-primitive-transfer-1`,
pre-run SHA `4bc6443e939287f80bac50cbdfa935e6b5bf0049`): following the adversarial
audit confirming all 15 evaluator-leakage and guided-injection confounds in v1,
Stage A separated `LearnerTaskView` from `EvaluatorTaskPrivate` (`zero_leakage_verified = true`,
`0` forbidden fields), removed all guided rule injection (`uniform_mutation_sampling = true`),
integrated Dream inside every generation (`novelty_uses_seed = false`), and evaluated
real counted candidate executions (`2,806,530` executions, `950,634` hidden evaluations)
across 3 genuinely non-isomorphic families (`list_transformations`,
`boolean_circuit_induction`, `fst_string_rewrite`) and 8 independent seeds
(`1762000001..1762000008`). `evolved_meta_rule` achieved `1.0000` task success and
`1.0000` real pre/post protected old-skill retention (`worst_regression = 0.0`) at
`11.2244` mean episodic compute cost (`3.8125` candidate executions, `1.5938`
experiments), beating `exact_information_gain_plus_effect_composition` (`19.6275`,
paired diff `+8.4031`, 95% CI `[+4.7622, +12.0441]`), `exact_information_gain_learner`
(`97.0508`, paired diff `+85.8265`, 95% CI `[+82.4780, +89.1750]`), and untouched
`random_evolutionary_selection` (`0.3229` success, `42.1309` cost). Frozen before
Stage B, the evolved rule entered `UnknownLibraryCodeLab` via `CommonEnvironmentAdapter`
across 3 independent multi-file unknown-library families generated after freezing
(`ulib_window_checksum`, `ulib_runlength_bucket`, `ulib_zigzag_interleave`, each with
1 true helper + 2 decoy helpers, 3 candidate post-steps, and 3 candidate call sites),
with hidden tests (`12` private inputs per family per seed) isolated in a separate
evaluator subprocess (`src/nexus/seed/blackbox_evaluator_worker.py`,
`private_inputs_exposed_to_learner = false`). Driven directly by `execute_code_lab_rule_interpreter`
(`method_specific_hardcoded_policy_branching = false`, verified by unconfounded causal instruction ablations where `PROPOSE_PRIMITIVE` removal keeps AST inspection, helper probing, all 12 hypothesis constructions, and AST patch synthesis identical),
the learner inspected files, chose probes, proposed new primitives via `PROPOSE_PRIMITIVE`
(`24/24` passing `PROPOSED -> ... -> PROMOTED`), synthesized its own AST patch
(`def solve_pipeline(seq): return ...`), achieved `1.0000` hidden subprocess accuracy vs `0.0000`
without `PROPOSE_PRIMITIVE` under strict execution-scope registration (`without_propose_tests_execution_scope_registration_only = true`), beat `strongest_handwritten_learner` (`34.9146` vs `92.4438`
compute cost, paired diff `+57.5292`, 95% CI `[+45.0887, +69.9696]`; `2.3750` vs `9.1250`
experiments, CI `[+5.5060, +7.9940]`) and `exact_information_gain_plus_effect_composition`
(`47.5500` cost, diff `+12.6354`, CI `[+7.7556, +17.5153]`), beat `direct_helper_import_without_capsule` (which has identical access and costs and is cheaper on a single task at `32.3146` vs `34.9146`) across a sequence of 4 fresh tasks ($T_1 \dots T_4$: breaking even by $T_2$ at `51.5271` vs `64.6292` and reducing 4-task cumulative cost from `127.6958` to `84.7521`, paired diff `+42.9438`, 95% CI `[+30.8344, +55.0531]`; `5.3750` vs `9.5000` experiments, CI `[+2.8270, +5.4230]`), and transferred promoted primitives
(`krelv`, `voux`, `zarn`) across all 4 labs (`Language`, `Coding`, `Reasoning`, `World`:
`1.0000` accuracy via neural utterance parsing and autonomous cross-domain adapter induction vs `0.0000` for `isolated_labs` and `<= 0.1875` for non-null-callable `capsule_removed`, `unlearned_binding`, and `unlearned_adapter` controls, `1.0000` old-skill
retention). In addition, the [10-part NEXUS Seed Integrated Architecture](docs/NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md)
(`src/nexus/seed/integrated_architecture.py`) verified 3 operating timescales, the
3-tier `EvidenceKernel`, a genuinely trained 10,970-parameter subword + token-level neural encoder-decoder
`SmallNeuralLanguageCodec` (`input_dim = 119` with `55` lexical tokens + `64` char-trigram buckets and `0` handcrafted structural features, `hidden_dim = 16`, `dec_hidden_dim = 16`, `35`-token fixed-length, position-conditioned token decoder where previous generated tokens are not inputs to the next prediction, `artifacts/seed_neural_language_weights_v1.json`, `1.00` accuracy across `36` held-out
unfamiliar paraphrases, multi-clause compositions, subword/typo variants, and OOD abstentions, zero XML tags), splittable `BeliefWorkspace`
equivalence groups, Kautz-Singleton $AG(2,3)$ $9\times 12$ 2-disjunct non-adaptive + conditional
group testing, hypothesis-sensitive `synthesize_compound_probe`, evidence-directed mutation across
4 distinct mechanisms (`3.50` vs `7.25`/`12.25`/`12.00` evals, zero hardcoded operator preference),
6-part `MechanismCapsule` with 4-lab transfer, 1-minimal `ddmin` delta debugging,
`TriLibrarySleepConsolidator` + trajectory-learned TD($0$) `SuccessorFeatureLearner` (`105,000`
transitions in the 5×5 `ResourceGridEnv`, `+3.085207` vs `-0.500000` closed-loop GPI return) + outer-loop meta-trained
`SmallLearnedOptimizer` (`artifacts/seed_learned_optimizer_params_v1.json`, `0.001862` target loss
vs `0.003482` `tuned_momentum`, `0.023808` `tuned_adam`, `0.027659` `tuned_sgd`), 6-stage
`DevelopmentalCurriculum` + 11-action `CognitiveController`, and all 7 isolated component ablations
(`10/10` gates passed, tamper-rejection verified).
**NEXUS demonstrated bounded executable learning-rule transfer and acquired one
previously unavailable primitive from sandboxed code interactions. This does not
establish arbitrary coding, general language understanding, unrestricted
self-improvement or AGI.** No live promotion. Previous closed results remain below.

[Combined Wake–Sleep–Dream–Evolution Architecture & Meta-Rule Evolution v1](docs/NEXUS_SEED_META_RULE_EVOLUTION_RESULTS.md)
([protocol](docs/NEXUS_SEED_META_RULE_EVOLUTION_PROTOCOL.md)) **passed all 9
preregistered gates** (`seed-meta-rule-evolution-1`, pre-run SHA
`322583377f03ccca702dda5478d158f57c1b0408`): inside an `ImmutableTrustedKernel`
(`kernel_sha256_before == kernel_sha256_after`), NEXUS evolved a 32-rule
population across 20 generations and 8 independent seeds (`5,120` rule
evaluations) over a 13-opcode typed learning-rule DSL (`10–30` instructions),
freezing the winning rule (`frozen_evolved_rule_sha256`) before generating the
sealed final grammar. With **zero stored whole-program fingerprints** and **no
manually supplied cross-lab mapping**, the evolved learning rule constructs
concept capsules from learned primitive transition models (including
`filter-even -> decrement -> reverse -> unique` bound to `"zorp"`), achieves
`1.0000` task success and `1.0000` (`>= 98%`) protected old-skill retention, and
beats the handwritten `exact_information_gain_learner` across all **4
independent grammars** (`list_transformations`, `boolean_mechanisms`,
`relational_graphs`, and sealed `sealed_action_state_transitions` with new
sensor `thermal_flux`, action `calibrate_shield`, and hidden variable
`latent_drift_polarity`), reducing active experiments by **`66.67%`** (`1.0000`
vs `3.0000`) and execution compute by **`92.50%`** (`5.2361` vs `69.8039`
episodic, `4.9080` continual after Stitch-like Sleep subprogram compression;
sealed paired cost reduction `+64.4656`, 95% CI `[+63.8448, +65.0864]`).
Removing the evolved rule removes the advantage, and neither
`random_evolution_control` nor `rule_size_only_control` matches it. **Adversarial v1 audit ([NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](docs/NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md), [`artifacts/seed_meta_rule_evolution_v1_audit.json`](artifacts/seed_meta_rule_evolution_v1_audit.json)): Meta-Rule Evolution v1 passed its internal synthetic contract but does not establish bounded learning-to-learn because evaluator-derived hypothesis labels, isomorphic grammar families, guided rule injection and non-executed protected assessments confound the result.** No live promotion. Previous closed results
remain below.

[Task-conditioned program ranking & sealed compositional replication](docs/NEXUS_SEED_TASK_CONDITIONED_REPLICATION_RESULTS.md)
([protocol](docs/NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md),
[source-only I/O signature audit](docs/NEXUS_SEED_SIGNATURE_AUDIT_RESULTS.md),
[cross-lab shared-memory transfer](docs/NEXUS_SEED_CROSS_LAB_TRANSFER_RESULTS.md))
**passed all 7 preregistered gates** (`seed-task-conditioned-replication-1`,
pre-run SHA `cc57cddff4491a93b76a842e43a85229216f0bce`): on a fresh 6-operator
grammar (`258` raw $\to$ `100` canonical $\to$ `65` semantically unique: `18`
source, `23` quarantined `v1` targets, `24` fresh sealed `decrement` targets
with `0` overlap), conditioning candidate ranking on the 17-dimensional
input-output signature $S(p\mid D_B) = -\|\operatorname{signature}(D_B)-\operatorname{signature}(p)\|_1 + \alpha S_{\text{structural}}(p) - \beta\operatorname{complexity}(p)$
reduced primary candidate evaluations to **`1.0000`** (`1.0000` held-out
accuracy, `1.0000` old-task retention), beating `flat_catalogue` (`12.7083`,
`92.13%` reduction, 95% CI `[+8.0858, +15.3309]`), `shortest_program` (`28.2500`,
`96.46%`), `exact_macro_cache` (`30.5000`, `96.72%`), `random_ordering`
(`33.0130`, `96.97%`), task-independent `structural_meta_prior` (`42.3333`,
`97.64%`), and `operator_frequency` (`50.2500`, `98.01%`), while also outperforming
`bayesian_version_space` (`1.3333`) and `learned_linear_ranker` (`5.6250`) so no
neural ranker is needed. Cross-domain transfer under a supplied mapping
(`action_token_sequence`) reduced evaluations from `48.0417` (`scratch_flat`) to
`1.0000` (`97.92%` reduction), and shared-memory cross-lab transfer (`Language`
$\to$ `Coding` $\to$ `Reasoning` $\to$ `World`) reduced downstream evaluations
from `66.0` to `1.0` (`98.48%` reduction, `100%` World Lab goal completion vs
`0%` for `isolated_labs`). This establishes **bounded task-conditioned program
ranking and shared-memory cross-lab transfer within the registered finite
grammar**; open-ended general intelligence remains unestablished. No live
promotion. Previous closed results remain below.

[Disjoint compositional meta-learning replication](docs/NEXUS_SEED_DISJOINT_META_RESULTS.md)
([protocol](docs/NEXUS_SEED_DISJOINT_META_PROTOCOL.md)) **failed its registered
learning-to-learn screen** (`seed-disjoint-meta-1`, Gate 1 passed, Gates 2–7
failed): across 8 families and 24 canonically and semantically disjoint target
programs (`0` source/target overlap), `structural_meta_prior` required `18.555556`
construction-inclusive evaluations (held-out accuracy `0.911458`), beating
source-fitted `exact_macro_cache` (`26.902778`), `bayesian_model_based`
(`25.263889`), and `operator_frequency` (`24.527778`), but losing to
`flat_catalogue` (`15.583333`, accuracy `0.921875`). Structural transfer under a
supplied mapping (`action_token_sequence`) required `17.652778` evaluations
versus `scratch_flat` `16.722222`. **The registered bounded learning-to-learn
screen failed. The architecture and benchmark remain useful engineering
infrastructure, but useful learning-to-learn was not established.** No live
promotion. Previous closed results remain below.

[Fresh query-conditioned selection](docs/NEXUS_SEED_CONDITIONED_ACQUISITION_RESULTS.md)
**failed both screens**: primary MSE .230198 versus blind .218490 and
source-informed model-based .210423; 0/8 wins versus blind. No promotion or
learning-to-learn claim. Honest results and costs are available in the GUI.
Previous closed results remain below.

[Query-context source audit](docs/NEXUS_SEED_QUERY_CONTEXT_RESULTS.md): relevant
query information is missing from the current question selector. Optimal choices
conflict in 489/512 saved contexts. No new labels or training, and no demonstrated
improvement in actual learning. Next: test query-conditioned acquisition on fresh
assignments. Previous closed results remain below.

[Source-trained question acquisition](docs/NEXUS_SEED_SOURCE_ACQUISITION_RESULTS.md)
**failed both screens**: primary MSE.221353 versus fixed order.215762 and
source-informed model-based.210662. It beats random expectation, but not strong
controls. Eight source fits; disjoint target programs; no live promotion or
learning-to-learn claim.

Previous closed result:

[Source-inferred investigation](docs/NEXUS_SEED_INFERRED_INVESTIGATION_RESULTS.md):
**learned hybrid failed** its strong-baseline screen on eight new authored
response tables. Hybrid3.046875 questions versus compiled greedy3.015625;
construction-inclusive work19880 versus9765. Source-only model reconstruction
works; useful learning-to-learn remains unestablished. No live promotion.

Previous closed result:

[Source-free compiled greedy audit](docs/NEXUS_SEED_COMPILED_GREEDY_RESULTS.md)
**passed its exactness/cost screen** on saved data: exact greedy decisions,
2208 construction-inclusive work units versus learned hybrid6012 (63.27% lower
proxy, not wall-speedup). Zero new collection or fitting. This shows caching
the supplied grammar suffices here; it does **not** establish learning-to-learn.

Previous closed result:

[Independent rule-balanced replication](docs/NEXUS_SEED_INVESTIGATION_REPLICATION_RESULTS.md)
**failed** its registered screen: hybrid3.042 questions versus pure greedy3.000
across three independently source-trained trees. Compute savings persisted,
but the strict question-quality criterion did not. No live promotion.

Previous closed result:

[Selective greedy fallback](docs/NEXUS_SEED_INVESTIGATION_HYBRID_RESULTS.md)
passed its authored development screen:2.969 questions versus greedy3.000,
no five-question cases,98.2% fewer search checks and47.3% less source-inclusive
work proxy. The interval does not establish question superiority; equal-rule
reweighting favors greedy. No live promotion or general learning-to-learn claim.

The prior result remains closed:

[Frozen investigation transfer](docs/NEXUS_SEED_INVESTIGATION_TRANSFER_RESULTS.md)
completed and **failed its registered screen**. The learned question order used
3.375 questions versus fixed4.219/random4.563, but greedy/exhaustive used3.000.
This narrow authored result is not general learning-to-learn. Historical
results remain unchanged; no live-agent promotion.

## Try it

The [15-Component Seed Master Architecture](docs/NEXUS_SEED_MASTER_ARCHITECTURE.md)
(`src/nexus/seed/master/`) is now integrated into the single unified GUI at `/`:
- **Natural Dialogue & Grounding**: Talk naturally (“How are you?”, “Who are you?”), teach immediate concepts (`"Flip" means reverse the order of a sequence.`), solve relational & math problems (`"If A is north of B and B is north of C, where is A relative to C?"`, `"Solve 3*x + 7 = 22"`), or sort sequences (`"Could you arrange these from smallest to largest? [4, 1, 3, 2]"`).
- **15-Component Master Hub**: Inspect and run Neural Grounding, Shared Belief Workspace, 6-Tier Memory, Hybrid World Model disagreement triggers, the 8-Reasoner Portfolio, Code Synthesis & Auto-Debugger, Cognitive Meta-Controller, 3 Learning Timescales, and the 5-check `LearningAcceptanceGate` from one tab.
- **Bounded Exact-Motif Program-Prior Reuse Demo & Bounded Multi-Reasoner Integration Suite (`meta_learning.py`)**: Engineering demonstration of within-family search-prior reuse (`9.5 -> 1.75` candidate evaluations when source and target share exact canonical motifs `sort->unique`, `reverse->increment`, `even->sort`) alongside the 6-domain bounded multi-reasoner integration suite (`Relational`, `Constraint CSP`, `Mathematical`, `Causal`, `Analogical`, `Hierarchical Planning`). Genuine held-out learning-to-learn on disjoint compositions is tested separately in [NEXUS_SEED_DISJOINT_META_RESULTS.md](docs/NEXUS_SEED_DISJOINT_META_RESULTS.md) and remains unestablished.

The [Phase 1–7 workbench](docs/NEXUS_SEED_PHASE1_7_WORKBENCH.md) connects
structured state, mechanisms, investigations, grounded phrases, checked typed
functions, generated source exercises and the same local conversation/session.
Open `/foundation`; in chat try “Show phases” or “Generate lessons”. These are
bounded implemented workflows; general learning-to-learn remains unproven.

The new [executable foundation](docs/NEXUS_SEED_FOUNDATION.md) is available at
`/foundation` on the same server: six operator stages, bounded typed programs,
attributed document ingestion, conflict-preserving memory, checked program
abstractions and investigation tools. This is tested engineering, not a new
learning-to-learn result. Historical findings and frozen models are unchanged.

Python3.11+ and a browser are enough for the symbolic teaching demo:

```sh
python3 -I -S scripts/run_learning_lab.py --allow-seed --port 8766
```

Open **http://127.0.0.1:8766/** for the new conversational workspace. Teach a word
or a checked skill, ask about memory, and explore the same authored world from
one conversation. It can also compose and execute small list programs: try
“Write code to sort and remove duplicates on [3, 1, 3, 2]”.
These are bounded supplied operators, not unrestricted coding. Open Evidence →
Latest investigation results to inspect the actual study. Start with “A dax means a red object” or “Teach you a skill
from examples.” [Conversation guide and screenshots](docs/NEXUS_SEED_CONVERSATION_WORKSPACE.md).

The original form-based interface remains at `/seed`. Teach an invented word using positive/negative
examples, ask clarifying questions, execute a typed movement program, save the
session and correct a previous label. The local server stops after15minutes.

The same server now has four [shared learning labs](docs/NEXUS_SHARED_LEARNING_LABS.md)
at `/labs`: language concepts, small typed programs, reasoning patterns/relations
and authored world goals. They share the existing Session and checked skill
library. This is a functional teaching playground; useful learning-to-learn and
neural cross-domain transfer remain unestablished. `nexus serve --mode labs`
loads the original hash-verified frozen encoder when its recorded core is present.

For the frozen neural model and tested action scorer:

```sh
python3 -m venv .venv-seed
. .venv-seed/bin/activate
python -m pip install -e ".[seed,dev]"
nexus serve --mode readout
```

Run from this checkout, or supply `nexus --repository /path/to/nexus-ai ...`.
Use **Learned one-step action**. Source assets and the tracked hash-bound JSON
checkpoints are required; this is not an asset-free wheel or cloud service.

The same server provides a read-only experiment dashboard at `/experimental`,
including the saved 1/2/4/8-example learning curves and baseline comparisons.
Opening it does not train models or collect data. See the
[owner-controlled experimental workflow](docs/NEXUS_EXPERIMENTAL_MODE.md)
for bounded local development and explicit resource approvals.

## What the evidence says

The newest optional [executable-world-model study](docs/NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md)
passed its authored source history-feature screen. This is prediction on a supplied
grammar, with no control, transfer or live promotion. The prior utility studies
remain failed and closed.

The preceding ten-scalar **answer-free question-utility predictor failed** its
source screen. Primary next-update MSE at budgets1/2/4: .170313 learned versus
.173580 variance, .172771 uniform, .172599 original order and .173857 keep.
Gains are below5%, required intervals include zero, and6/12 tasks beat keep.
Retention passes. Budget8 is a singleton secondary result. No live promotion.
[Executable-model results](docs/NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md).

The preceding54-feature predictor also failed its source screen
([results](docs/NEXUS_SEED_QUESTION_UTILITY_RESULTS.md)). The larger independent
source query bank passed evaluator selection stability
([results](docs/NEXUS_SEED_QUERY_REPLICATION_RESULTS.md)); evaluator utility is
not learned question choice. Neither result establishes learning-to-learn.

An earlier evaluator-only audit found useful questions retrospectively: query
oracle MSE .174050 versus variance .193552. But selection using two query states
**failed on the third** (.194374 versus keep .194222). This is potential in
known source data, not a deployed question learner or learning-to-learn claim.
[Historical headroom results](docs/NEXUS_SEED_QUESTION_HEADROOM_RESULTS.md).

The previous fixed-learner question study **failed its source improvement screen**:
informative selection MSE .193552 versus random .191753; its interval includes
zero. Original-order constant damping remains .180187. No new collection or
live promotion. [Question-selection results](docs/NEXUS_SEED_QUESTION_SELECTION_RESULTS.md).

The previous learning-choice study **failed all improvement screens**: protected
learning error .210911 versus constant damping .180187. Observed-memory
protection passed, but asking mostly deferred learning. No live promotion.
[Learning-choice results](docs/NEXUS_SEED_LEARNING_CHOICE_RESULTS.md).

The earlier nonlinear-feature study also failed its development screen.
Average error after 1/2/4/8 new examples was .170873 for learned contextual
protection, .171423 for source-trained static protection and .128930 for scaled
replay. The small advantage over static was inconclusive; learned/static/fixed
protection produced identical tested control actions. No useful learning-to-learn
advantage was demonstrated. [Full results](docs/NEXUS_SEED_NONLINEAR_LEARNING_RESULTS.md).

The earlier frozen spatial-transfer screen passed versus frozen ranking:
goals45.3% versus4.7% across four changed start/goal mixtures. Greedy remained
stronger; cross-diagonal goals trailed random. [Transfer results](docs/NEXUS_SEED_SPATIAL_TRANSFER_RESULTS.md).

The earlier nonlinear action-readout development test improved goal completion
from frozen12.5% to64.6%. Known-grid greedy achieved100% and remains stronger.
The model uses supplied position/goal features; this is not pixels-only grounding.

The preceding learned-plasticity experiment lost to scaled replay. The
future-edit selector tied historical-best. Useful continual learning and
learning-to-learn are **not established**. Negative results stay visible.

[Executable-model results](docs/NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md) ·
[Action-readout results](docs/NEXUS_SEED_SURPRISE_READOUT_RESULTS.md) ·
[Learning failures](docs/NEXUS_SEED_LEARNING_VALIDATION_RESULTS.md) ·
[Current state](docs/NEXUS_CANONICAL_CURRENT_STATE.md)

## Understand and develop

- [Teaching walkthrough](docs/seed/QUICKSTART.md)
- [Architecture and shared dependencies](docs/seed/ARCHITECTURE.md)
- [Research and evidence index](docs/README.md)
- [Master context](docs/MASTER_CONTEXT.md) and [agent workflow](AGENTS.md)
- [Cleanup boundaries](docs/NEXUS_SEED_FOCUS_CLEANUP.md)
- [Contributing](CONTRIBUTING.md) and [security](SECURITY.md)

```sh
nexus status
nexus check
nexus verify
nexus audit-source
make test-seed
```

Help/status/data-only verification do not train or collect research data.
Neural mode needs the seed extras; historical research commands require
`pip install -e ".[research,dev]"` and remain accessible as `nexus-research`.
They are not the default next task. The old `nexus train` spelling is replaced
by `nexus-research train`; historical Python modules remain import-compatible.

## Research boundaries

The current world, finite grammar and supplied observations are a testbed, not
general intelligence. Frozen models stay frozen. Protocols are committed before
outcomes for registered studies. Exploration iterations use lightweight manifests
and reusable development data; independent assessments and closed evaluations
remain protected. Resource caps are enforced, with backend limits documented.
No paid services, real-money activity, automatic main merge or unrestricted self-modifying
execution is enabled by this repository.

Historical research is indexed under [history](docs/history/README.md).
Original artifacts/configurations/source paths remain available for reproduction.
Redundant branch names can be retired only after exact-tip archival and
worktree/ancestry checks. Unique research and failed outcomes are not discarded.
