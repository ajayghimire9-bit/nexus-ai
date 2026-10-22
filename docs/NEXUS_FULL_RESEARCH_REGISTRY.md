# NEXUS Seed — Research Registry

## Latest — Meta-Rule Evolution v2 (Leakage-Repaired), Black-Box Open Primitive Code Transfer v1 & 10-Part Integrated Architecture PASSED all registered gates

Clean execution `4bc6443e939287f80bac50cbdfa935e6b5bf0049` (`seed-open-primitive-transfer-1`, `seed_open_primitive_transfer_v1` & `seed_integrated_architecture_v1`). Following the adversarial v1 audit ([NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md)) confirming all 15 v1 confounds, Stage A enforced strict `LearnerTaskView` vs `EvaluatorTaskPrivate` separation (`zero_leakage_verified = true`), real counted candidate execution (`2,809,305` executions), uniform mutation without guided injection, in-loop Dream novelty without `seed`, real pre/post retention (`1.0000` -> `1.0000`, `worst_regression = 0.0`), and real Sleep test re-execution over 3 non-isomorphic families (`list_transformations`, `boolean_circuit_induction`, `fst_string_rewrite`) across 8 seeds (`1762000001..1762000008`). `evolved_meta_rule` achieved `1.0000` task success and `1.0000` retention at `11.2244` compute cost, beating `exact_information_gain_plus_effect_composition` (`19.6275`, CI `[+4.7622, +12.0441]`), `exact_information_gain_learner` (`97.0508`, CI `[+82.4780, +89.1750]`), and untouched `random_evolutionary_selection` (`0.3229` success). Frozen before Stage B, the rule entered `UnknownLibraryCodeLab` across 3 multi-file unknown-library families generated after freezing (`ulib_window_checksum`, `ulib_runlength_bucket`, `ulib_zigzag_interleave`, each with 1 true helper + 2 decoy helpers, 3 candidate post-steps, and 3 call sites) evaluated by an isolated black-box evaluator subprocess (`src/nexus/seed/blackbox_evaluator_worker.py`, `private_inputs_exposed_to_learner = false`), executed its evolved instruction sequence via `execute_code_lab_rule_interpreter` (`method_specific_hardcoded_policy_branching = false`, verified by unconfounded causal instruction ablations where removing `PROPOSE_PRIMITIVE` keeps AST inspection, helper probing, all 12 hypothesis constructions, and AST patch synthesis identical), promoted new primitives via `PROPOSE_PRIMITIVE` (`24/24` `PROMOTED`), synthesized its own AST patch (`def solve_pipeline(seq): return ...`), achieved `1.0000` hidden subprocess accuracy vs `0.0000` without `PROPOSE_PRIMITIVE`, beat `strongest_handwritten_learner` (`34.9146` vs `92.4438` cost, CI `[+45.0887, +69.9696]`; `2.3750` vs `9.1250` experiments, CI `[+5.5060, +7.9940]`) and `exact_information_gain_plus_effect_composition` (`47.5500` cost, diff `+12.6354`, CI `[+7.7556, +17.5153]`), and transferred promoted primitives (`krelv`, `voux`, `zarn`) across all 4 labs (`Language`, `Coding`, `Reasoning`, `World`: `1.0000` via neural utterance parsing and autonomous cross-domain adapter induction vs `0.0000` for `isolated_labs` and `<= 0.1875` for non-null-callable `capsule_removed`, `unlearned_binding`, and `unlearned_adapter` controls, `1.0000` old-skill retention). In addition, the [10-part NEXUS Seed Integrated Architecture](NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md) (`src/nexus/seed/integrated_architecture.py`) passed all `10/10` component and end-to-end gates (trainable 10,970-param subword + token-level `SmallNeuralLanguageCodec` evaluated across 36 held-out utterances, outer-loop meta-trained `SmallLearnedOptimizer`, trajectory-learned TD($0$) `SuccessorFeatureLearner` in the 5×5 `ResourceGridEnv`, dynamic `synthesize_compound_probe`, evidence-directed mutation across 4 mechanisms, and tamper-rejecting verifiers). **NEXUS demonstrated bounded executable learning-rule transfer and acquired one previously unavailable primitive from sandboxed code interactions. This does not establish arbitrary coding, general language understanding, unrestricted self-improvement or AGI.** [Results](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_RESULTS.md), [protocol](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md), [integrated architecture](NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md). No live promotion.

4096 real steps, 5120 evolutionary rule evaluations, zero neural forwards; 26-second debit (`24.211062s` wall, `24.150074s` CPU). Ledger `2078.632103455996` used / `1521.3678965440042` remaining. All 831 historical `main` artifacts unchanged; independently verified in `artifacts/seed_open_primitive_transfer_audit.json` (`valid: true`). Older entries retain their original chronology.

## Latest — Combined Wake–Sleep–Dream–Evolution Architecture & Meta-Rule Evolution v1 PASSED all 9 registered gates

Clean execution `322583377f03ccca702dda5478d158f57c1b0408` (`seed-meta-rule-evolution-1`, `seed_meta_rule_evolution_v1`). Across 8 independent seeds (`32` rules $\times$ `20` generations = `5,120` evaluations), `evolved_meta_rule` (`10–30` typed DSL instructions, frozen before sealed grammar generation, `stored_whole_program_fingerprints = 0`, `manually_supplied_cross_lab_mapping = False`, `"zorp"` $\to$ `["even", "decrement", "reverse", "unique"]`) achieved `1.0000` task success and `1.0000` (`>= 0.98`) protected old-skill retention, beating `exact_information_gain_learner` on all 4 independent grammars (`list_transformations`, `boolean_mechanisms`, `relational_graphs`, `sealed_action_state_transitions`) and all `8/8` seeds: `1.0000` vs `3.0000` experiments (`66.67%` reduction) and `5.2361` vs `69.8039` episodic execution cost (`92.50%` reduction; `4.9080` continual after Stitch-like Sleep compression; sealed CI `[+63.8448, +65.0864]`). Removing the evolved rule removes the advantage, and `random_evolution_control` and `rule_size_only_control` do not match it. **Adversarial v1 audit ([NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md)): Meta-Rule Evolution v1 passed its internal synthetic contract but does not establish bounded learning-to-learn because evaluator-derived hypothesis labels, isomorphic grammar families, guided rule injection and non-executed protected assessments confound the result.** [Results](NEXUS_SEED_META_RULE_EVOLUTION_RESULTS.md), [protocol](NEXUS_SEED_META_RULE_EVOLUTION_PROTOCOL.md). No live promotion.

3072 real steps, 5120 evolutionary rule evaluations, zero neural forwards; 6-second debit (`4.969516s` wall, `4.845922s` CPU). Ledger `2052.632103455996` used / `1547.3678965440042` remaining. All 831 historical `main` artifacts unchanged; independently verified in `artifacts/seed_meta_rule_evolution_audit.json` (`valid: true`). Older entries retain their original chronology.

## Latest — task-conditioned program ranking & sealed compositional replication PASSED all 7 registered gates

Clean execution `cc57cddff4491a93b76a842e43a85229216f0bce` (`seed-task-conditioned-replication-1`, `seed_task_conditioned_replication_v1`). Over 65 semantically unique 6-operator programs (`18` source, `23` quarantined `v1` targets, `24` fresh sealed `decrement` targets, `0` overlap), `deterministic_signature` averaged `1.0000` evaluations (`1.0000` held-out accuracy, `1.0000` old-source retention), beating `flat_catalogue` (`12.7083`, `92.13%` reduction), `shortest_program` (`28.2500`), `exact_macro_cache` (`30.5000`), `random_ordering` (`33.0130`), `structural_meta_prior` (`42.3333`), `operator_frequency` (`50.2500`), `bayesian_version_space` (`1.3333`), and `learned_linear_ranker` (`5.6250`). Cross-domain transfer under a supplied mapping (`action_token_sequence`) required `1.0000` evaluations vs `scratch_flat` `48.0417` (`97.92%` reduction). Shared-memory cross-lab transfer (`Language` $\to$ `Coding` $\to$ `Reasoning` $\to$ `World`) required `1.0` downstream evaluation vs `66.0` for `scratch_learning` (`98.48%` reduction) and `1.0000` vs `0.0000` accuracy for `isolated_labs`. [Results](NEXUS_SEED_TASK_CONDITIONED_REPLICATION_RESULTS.md), [protocol](NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md), [signature audit](NEXUS_SEED_SIGNATURE_AUDIT_RESULTS.md), [cross-lab transfer](NEXUS_SEED_CROSS_LAB_TRANSFER_RESULTS.md). No live promotion.

2624 real steps, 16 ridge fits, zero neural forwards; 8-second debit (`6.709615s` wall, `4.442347s` CPU). Ledger `2046.6321034559958` used / `1553.3678965440042` remaining. All 831 historical `main` artifacts unchanged; independently verified in `artifacts/seed_task_conditioned_replication_audit.json` (`valid: true`). Older entries retain their original chronology.

## Latest — disjoint compositional meta-learning replication FAILED its registered screen

Clean execution `540a30596814ec1687db13e7e38cdc0ab43aa701` (`seed-disjoint-meta-1`, `seed_disjoint_meta_v1`). Over 41 semantically unique programs (`17` source, `24` canonically and semantically disjoint target programs, `0` overlap), `structural_meta_prior` averaged `18.555556` evaluations (accuracy `0.911458`), beating `exact_macro_cache` (`26.902778`), `bayesian_model_based` (`25.263889`), and `operator_frequency` (`24.527778`), but losing to `flat_catalogue` (`15.583333`, accuracy `0.921875`). Structural transfer under a supplied mapping (`action_token_sequence`) required `17.652778` evaluations versus `scratch_flat` `16.722222`. **The registered bounded learning-to-learn screen failed. The architecture and benchmark remain useful engineering infrastructure, but useful learning-to-learn was not established.** [Results](NEXUS_SEED_DISJOINT_META_RESULTS.md), [protocol](NEXUS_SEED_DISJOINT_META_PROTOCOL.md). No live promotion.

2496 real steps, 8 ridge fits ($d=23$), zero neural forwards or simulator steps; 33-second debit. Ledger `2038.6321034559958` used / `1561.3678965440042` remaining. All 831 prior artifacts unchanged; independently verified in `artifacts/seed_disjoint_meta_audit.json` (`valid: true`). Older entries retain their original chronology.

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


## Active evidence, newest first

- [Executable foundation engineering](NEXUS_SEED_FOUNDATION.md): typed
  composition, checked abstraction, curriculum, ingestion, memory projection,
  investigation and grounded wording. Deterministic fixture/GUI verification;
  no scientific experiment, resource allocation or learning-to-learn result.

- [Executable world model](NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md): complete
  bc57da1 SOURCE feature screen PASSED. Primary Brier0 versus fixed .238707 /
  all-history .050260; all unavailable candidates rejected. GRU source-fitting
  did not generalize. No control, transfer, default promotion or learning-to-learn.
  Planning, residual and investigation components remain engineering variants.

- [Ten-scalar answer-free utility](NEXUS_SEED_ANSWER_FREE_UTILITY_RESULTS.md):
  complete8d9bdad run, SOURCE screen FAILED. Primary1/2/4 MSE .170313 versus
  variance .173580/keep .173857, intervals include zero,6/12 keep wins. Retention
  passes. Budget8 singleton secondary; no new collection/neural calls/promotion.

- [Task-blocked question utility](NEXUS_SEED_QUESTION_UTILITY_RESULTS.md):
  valid complete runa8ca30a; source screen FAILED. Learned .168235 versus
  action mean .169743/variance .170092, intervals include zero.6/12 keep wins,
  retention passes. Utility prediction MSE worse than mean controls. No new
  data, neural fitting or runtime promotion. One core/reused source bank.

- [Larger source query bank](NEXUS_SEED_QUERY_REPLICATION_RESULTS.md): within-task
  screen PASSED. Selected .159819 versus variance .170092/keep .170649;9/12
  task wins.2592 new authored outcomes; no fitting or live promotion. Raw capture
  keeps its invalid parameter-count receipt; separate offline validation fixes
  the count, no rerun. Execution25b155a; validator7839514. One core and reused
  tasks; evaluator selection, not learned questioning or learning-to-learn.

- [Question-pool headroom](NEXUS_SEED_QUESTION_HEADROOM_PROTOCOL.md): registered
  evaluator-only SOURCE audit completed. Oracle headroom screen passed (.174050
  versus variance .193552); omitted-query-state check FAILED (.194374 versus
  keep .194222). Oracle is not a learned/deployed question policy. No collection,
  neural/meta-training or promotion. [Results](NEXUS_SEED_QUESTION_HEADROOM_RESULTS.md),
  execution354f47a.

- [Fixed-learner question selection](NEXUS_SEED_QUESTION_SELECTION_PROTOCOL.md):
  completed source exploration; improvement screen FAILED. Informative .193552
  versus random .191753, original order .180187. Primary −.001799 interval
  includes zero; retention passed.12 reused tasks/one core. No collection or
  promotion. [Results](NEXUS_SEED_QUESTION_SELECTION_RESULTS.md), execution080d051.

- [Shared Learning Brain and four labs](NEXUS_SHARED_LEARNING_LABS.md): engineering
  foundation over the same Session/journal, bounded skill programs, optional
  frozen representation and existing source-feedback statistics. Authored fixture
  reuse and durable restore are verification targets, not scientific superiority.
  No new scientific experiment, allocation, holdout registration or promotion.

- [Policy-roll-in and learning choices](NEXUS_SEED_LEARNING_CHOICE_RESULTS.md):
  source coverage/protection/strong-baseline screens FAILED. Curve .207067
  roll-in, .210911 protected versus reference .201848 and constant .180187.
  Known-anchor cap/retention tolerance pass.4 learn /80 ask /12 retain;
  no active-question benefit established. Eight new small source ridge fits,
  no collection, historical weight changes or promotion.
  [Protocol](NEXUS_SEED_LEARNING_CHOICE_PROTOCOL.md), execution268589a.

- [Sequential consistency selector](NEXUS_SEED_SEQUENTIAL_CONSISTENCY_RESULTS.md):
  actual1/2/4/8-example MSE .201848 versus damping .180187, replay .187016 and
  bounded .184388. Source screen FAILED; retention tolerance passed;1/4 fold
  wins,11/96 updates. All84 recomputed baseline trajectories reproduce exactly.
  One core, reused source data; no predictor fitting, fresh validation or promotion.
  [Protocol](NEXUS_SEED_SEQUENTIAL_CONSISTENCY_PROTOCOL.md), execution2457901.

- [Teaching-prefix informativeness](NEXUS_SEED_PREFIX_CONSISTENCY_RESULTS.md):
  full utility-prediction MSE .002908 versus constant .002250 and prefix mean
  .002084; primary signal screen FAILED. Consistency-only local regret35.34%
  lower as an uncertain secondary point estimate; its descriptive interval
  includes zero. Fixed-reference/source-only, one frozen core, no actual
  adaptive learning curves or promotion. [Protocol](NEXUS_SEED_PREFIX_CONSISTENCY_PROTOCOL.md),
  execution420ed2a.

- [Scalar update/retain gate](NEXUS_SEED_UPDATE_GATE_RESULTS.md): curve MSE
  .180324 learned versus .180187 constant, .187016 replay, .184388 bounded.
  Source learning screen FAILED; retention passed. Generic damping helps,
  task-conditioned strength does not beat constant. Three rule-training seeds,
  one frozen core, reused data; no fresh validation/control/promotion.
  [Protocol](NEXUS_SEED_UPDATE_GATE_PROTOCOL.md), execution0ce94d0.

- [Task-blocked cumulative learning rule](NEXUS_SEED_CUMULATIVE_LEARNING_RESULTS.md):
  new rule trained across nine source tasks/fold and assessed on three excluded
  tasks. Only .31% gain over source-trained static; worse than replay/bounded
  fixed. Practical source screen FAILED, retention passed. Reused-source data,
  three update-rule seeds, one frozen core; no fresh validation or promotion.
  [Protocol](NEXUS_SEED_CUMULATIVE_LEARNING_PROTOCOL.md), execution5235599.

- [Bounded source correction](NEXUS_SEED_BOUNDED_CORRECTION_RESULTS.md):
  stabilization passed (13.5% versus unchanged learned), strong-replay and
  learned-specific practical screens failed. Reused source evidence only;
  no runtime promotion. [Protocol](NEXUS_SEED_BOUNDED_CORRECTION_PROTOCOL.md),
  execution269bcb6. Original receipt's legacy adapter label is documented;
  future host metadata corrected without rewriting the old receipt.

- [Source update-magnitude diagnosis](NEXUS_SEED_UPDATE_DIAGNOSIS_RESULTS.md):
  large norm ratio12.55×,but only5/12source tasks harmed; registered broad-harm
  pattern not supported. Reused source evidence,not new validation or causation.
  [Protocol](NEXUS_SEED_UPDATE_DIAGNOSIS_PROTOCOL.md), execution9c379aa.

- [Nonlinear-feature learned update rule](NEXUS_SEED_NONLINEAR_LEARNING_RESULTS.md):
  combined development screen FAILED; retention passed; no reliable advantage
  over static and replay; learned/static/fixed control actions identical.
  [Protocol](NEXUS_SEED_NONLINEAR_LEARNING_PROTOCOL.md), execution73d1dcd.

- [EXPERIMENTAL workflow engineering](NEXUS_EXPERIMENTAL_MODE.md): owner budgets,
  typed candidate training, independent assessment routes, retain/rollback and
  read-only GUI. Authored numeric QA only; no scientific result or new simulation.

- [Frozen spatial-transfer development](NEXUS_SEED_SPATIAL_TRANSFER_RESULTS.md):
  screen passed versus frozen ranking; greedy stronger; boundary/diagonal
  limitations. One core,no updates. [Protocol](NEXUS_SEED_SPATIAL_TRANSFER_PROTOCOL.md).

- [Nonlinear action readout and surprise](NEXUS_SEED_SURPRISE_READOUT_RESULTS.md):
  development screen passed; greedy stronger; future-edit credit ties
  historical-best. [Protocol](NEXUS_SEED_SURPRISE_READOUT_PROTOCOL.md).
- [Fresh learning/action/meaning validation](NEXUS_SEED_LEARNING_VALIDATION_RESULTS.md):
  learned plasticity lost to scaled replay; object gates failed; transfer not run.
  [Protocol](NEXUS_SEED_LEARNING_VALIDATION_PROTOCOL.md).
- [Memory-aware local learning](NEXUS_SEED_MEMORY_AWARE_RESULTS.md):
  implementation functional; meaningful learned-update improvement not established.
- [Shared state/memory/value contract](NEXUS_SEED_CONTRACT_RESULTS.md):
  correctness improved; decision screen failed.
- [Grounded architecture pilot](NEXUS_SEED_GROUNDED_RESULTS.md):
  connected neural paths; limited control/language evidence.
- [Finite S0–S1](NEXUS_SEED_RESULTS.md): comparison incomplete, no rerun.

Raw metrics/configurations/checkpoint references remain in artifacts/ and configs/.
A completed implementation is not a successful research hypothesis.

## Learning-to-learn decision

Require measured faster/better adaptation on untouched tasks versus strong
source-informed simple baselines at equal teaching/search budgets, with
forgetting, compute and uncertainty reported. Fitting an action scorer, saving
knowledge, changing proposal probabilities or selecting a winning edit once is
insufficient. Preserve negative results.

## Historical tracks

The [complete previous registry](history/seed-focus-2026-10-20/NEXUS_FULL_RESEARCH_REGISTRY.md)
and [machine-readable registry](../artifacts/nexus_research_registry.json) retain
earlier control, lookahead, cross-family, H12–H17 and Evolution records.
The [history guide](history/README.md) explains old checkpoint availability.
Keep closed seeds/splits, original artifact paths and frozen models unchanged.
No historical experiment is scheduled by this registry.
