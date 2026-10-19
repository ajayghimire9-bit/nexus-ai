# NEXUS code-reuse map

E3.12 measured-mutation binding: mutation_control provides pure replay/grid/
statistics helpers. run_e3_12_mutation_control binds SAME post_probe.Host,
Dispatch, ForwardCheckedStep, ReservationLedger and DecisionJournal to SAME
generated_strategies.execute. Dispatch.action_strategy generalizes the existing
label route without changing defaults. StrategyGenerator.paired_child fixes
leaves and external uniform to isolate existing structural credit. No new
learner/memory/meter. measured_mutation verifies actual completed paths;
episode receipts are summary references, not duplicated physical accounting.
Protocol NEXUS_E3_12_MUTATION_CONTROL_PROTOCOL.md; outcomes not yet collected.

Bounded learning-cycle integration uses SAME StrategyGenerator mutation credit,
TaskStream, EpsilonGreedyController, FixtureCost/Journal and E1 promotion harness.
Mean update/default RNG behavior preserved; new rules are opt-in. measured_mutation
checks trusted charged actual paths without collecting data. learning_lab gains
allowlisted verified control replay; run_learning_lab serves loopback only plus
an opt-in authored fixture playground. No duplicate contextual-memory, RL or
scientific metering stack; real usefulness remains separately unverified.

E3.11D adds --horizon-calibration to SAME runner/worker. horizon_calibration
locks64-step outer forecasts and analyzes their cached16-step prefixes; it
does not replace planners, models, memory, learner or meter. Existing replay
and journal checks accept registered duration, old profiles default16 unchanged.
Forecast_calibration.summarize shares arithmetic after profile-specific strict
validation. See NEXUS_E3_11D_HORIZON_CALIBRATION_PROTOCOL.md.

E3.11B execution extends SAME run_e3_11_post_probe.py with --calibration;
calibration_execution binds existing Host/Dispatch, restoration, walk, planners,
evidence and ReservationLedger to the preparation capture/analysis functions.
rollout_headroom.validate_forecasts is extracted unchanged for shared replay.
No new learner/meter/controller or changes to historical profiles/artifacts.
Separate execution config/protocol/allocation and output paths; preparation
checker remains blocked. See NEXUS_E3_11B_FORECAST_CALIBRATION_EXECUTION.md.

E3.11B forecast_calibration is pure preparation/statistics glue; does not
replace post_probe.Host/Dispatch, rollout_headroom.walk, planners, memory or
ReservationLedger. Source-only prepare_e3_11b_forecast_calibration.py checks
pinned TRAIN metadata and refuses --execute. Real host binding, seed audit and
allocation remain prerequisites. No new learner/parallel execution framework.

E3.11A extends SAME run_e3_11_post_probe.py with --rollout-audit/--verify and
separate config, grant, result, usage and journal paths. rollout_headroom wraps
post_probe.Host/Dispatch, planning_ops, existing planners/rewards/model/ledger;
no new meter, learner or controller. Policy advances use charged model calls,
no environments. First actions reused only within the same execution context.
555 relevant tests; numerical headroom passes, accuracy untested. See E3.11A
results. Original E3.11 profile and historical result remain unchanged.

E3.11 post_probe is a phase/host adapter over SAME StagedStudy, EpisodeContext,
AdvantagePredictor, generated_strategies.execute, planner_evidence and ledger.
Host binds actual frozen models/TaskSpec wrappers; deepcopy restores complete
post-probe simulator/RNG/time-limit state, never learner input. ProbeSelector
fits2 existing ridge models, not another learner. Existing DecisionJournal
stores per-call receipts once; StagedStudy receives explicitly labeled path
summaries. Cached selector returns do not reexecute/count physical episodes.
scripts/run_e3_11_post_probe.py allocation consumed; --verify replays saved
data only. summarize_e3_11_post_probe.py exports verified CSV/JSON without
runtime imports. Screen fails,539 tests. See E3.11 results; no E3.12 promotion.

E3.10 ForwardCheckedStep extends SAME planner_evidence and uses existing
ReservationLedger tickets to bound/observe one top-level net call per step.
Host scripts/run_e3_10_metered_model.py binds exact CPU WorldModel residual
MLP only, reuses score_open_loop/state_hash/rewards and original source files.
No new learner, planner or meter.521 relevant tests; registered actual-model
equivalence verified. Learning Lab optional load_integration verifies capture
digest and labels engineering separately; --integration writes a new page.
Real-environment StagedStudy host remains unbound. Report E3.10 results.

E3.9 hardens SAME StagedStudy and planner_evidence; no new meter/learner/planner.
Registered grids have independent locked task/episode axes; evidence batch rows
must match reserved operations. scripts/audit_e3_9_planner_evidence_readiness.py
uses only stdlib byte hashes/AST literals, never imports NEXUS model runtimes.
4 local checkpoints/8 source arrays match; production metered host remains
unbound.503 relevant tests; no scientific execution. See E3.9 readiness report.

E3.8 compact_interactions builds ONE versioned9/21-coordinate representation;
SAME AdvantagePredictor/ridge and feature audit host --compact. EpisodeContext
is episode evidence beside existing source memory, not another memory stack.
planner_evidence uses existing score_open_loop/ReservationLedger. StagedStudy
only coordinates trusted metered host phases; production worker remains unbound.
StrategyGenerator opt-in paired mutation credit changes structural-kind proposal
preferences without leaf credit; default preserved. TaskStream reuses that
same generator/Journal and existing meta.controller.EpsilonGreedyController
statistics, not another RL engine. learning_lab is offline artifact display,
separate from evaluators. See NEXUS_LEARNING_MILESTONES_IMPLEMENTATION.md.

E3.7 uses SAME AdvantagePredictor/ridge, feature_informativeness fold/permutation
adapter and existing audit host (--transitions/--verify). transition_evidence
is pinned TRAIN-prefix preprocessing only. describe_support's require_fit=True
opt-in refuses numerical fallback; historical default remains unchanged. Two
192-coordinate views, not a384-parameter model. Four descriptor LS calls per
run/audit; audit performs0 ridge fits. Seven legacy artifact-writer tests now
redirect to tmp paths; earlier side effects archived/restored/disclosed. No
new learning/memory/planner stack; negative screen, allocation consumed.

E3.6 feature_informativeness is a slice/permutation/fold adapter over the SAME
AdvantagePredictor, base training_feedback_audit anchor/identity functions and
ridge; no second learner/proposer/memory/planner/meter. Existing audit host
adds exact --features/--verify profile. Source discovery: advantage_features
uses describe_support[:3] schema only; no true transitions reach this feature
bank. Four locked groups/19 within-model maps each;720 fits, no inference.
Allocation consumed; no reruns. Report NEXUS_E3_6_FEATURE_INFORMATIVENESS_RESULTS.md.

E3.5 extends SAME AdvantagePredictor with observed-baseline targets/prediction;
baseline0 preserves direct behavior. SAME training_feedback_audit and existing
runner gain explicit --residual profile for9 training reset folds/27fits.
No replacement learner, memory, proposer, planner or meter. Anchors/targets/
RMS exclude withheld resets; independent verify uses saved coefficients only.
No simulator/world-model calls. Both screens fail; report
NEXUS_E3_5_RESIDUAL_ADVANTAGE_RESULTS.md. Allocation consumed, no retries.

E3.4 reuses the SAME FrozenReturnSelector with explicit budget/path parameters.
feedback_coverage only coordinates snapshots3/6/9 and paired metrics; no new
learner/proposer/memory/controller. Existing runner --coverage (and --audit)
uses the exact coverage_feedback_v1 profile. DecisionJournal losslessly rotates
the existing ledger JSONL after4000 decisions; full verifier requires six
ordered hashes and complete20800-decision reconciliation. This is storage,
not approximate compute reduction or a new resource meter. Allocation consumed;
no retries. Source candidate counts are cap-derived31/root successor and
48 flat/15/root successor under blend, not historical16×16. Report
`NEXUS_E3_4_FEEDBACK_COVERAGE_RESULTS.md`. Primary/broad screens failed.

E3.3 `training_feedback_audit` is an offline fold/metrics adapter over existing
AdvantagePredictor/ridge and return_feedback selection semantics. It uses
saved training features only, replaces the two anchor-mean blocks with
fold-training means, and never reads closed evaluation outcomes. No new memory,
proposer, planner, meter or learner stack. Runner
scripts/run_e3_3_training_feedback_audit.py (--verify for zero-fit coefficient
replay). One-run allocation consumed; no source .pt/.npz needed. Screen failed
with descriptive Acrobot selection gain. Reuse these fold-only transforms when
auditing this exact feature layout; do not reuse all-training anchor rows.

E3.2 `return_feedback.FrozenReturnSelector` is a phase/feedback adapter around
existing `generated_strategies.AdvantagePredictor` and `advantage_features`.
It does not replace the learner, proposer, memory, planner or resource meter.
The existing full_policy_source host adds exact return_feedback_v1 staging:
all training first, frozen manifest, choices saved before evaluation rewards.
Use scripts/run_e3_2_return_feedback.py (--audit for offline verification).
One-run allocation is consumed. Result screen failed; no retry/retuning.
Repository-only tests use synthetic source features and tracked captures;
explicit audit additionally requires original checkpoint/source files.

`scripts/audit_e3_1_learned_model.py` is a recorded-data audit, not a new learner
or collector. Reuses headroom summarizer, full_policy_source grid/hash helpers,
fit-clock inventory/disposable_model loader and ReservationLedger; metric cells
cross both frozen models over the same recorded queries. No new proposer,
memory, controller or hidden evaluator. Its source-only allocation is consumed.
Raw predictions allow no-inference `--verify`; model binaries are required for
explicit integrity checks, but repository-only regression reads tracked JSON.

The same host now has a third exact `crossed_reset_v1` profile with shared
model-independent reset/search streams. Invoke the existing replication runner
with `--crossed-reset` (and `--audit` for saved-data verification); do not create
another controller or meter. `crossed_screen` reports paired model interactions
and the preregistered descriptive sign screen. Its one-run allocation is consumed.
Old profiles/result arithmetic remain regression-tested and unchanged. Report
`NEXUS_UNIFIED_CROSSED_RESET_RESULTS.md`.

The same `evolution2.full_policy_source` host now supports exactly two locked
profiles: original screen and fresh-episode replication. `run_paths` keeps their
configuration/allocation/usage/result/journal files separate; old evidence is
preserved. `scripts/run_unified_full_policy_replication.py --audit` reuses the
existing no-inference verifier with an explicit journal path. No second planner,
resource ledger, memory or proposer. Both allocations are consumed. See
`NEXUS_UNIFIED_FULL_POLICY_REPLICATION_RESULTS.md` for the mixed outcome.

`evolution2.full_policy_source` is the one-run bounded source-physics host for
four fixed generated/anchor controllers, using existing TaskSpec/wrappers,
`generated_strategies.execute`, frozen WorldModel and ReservationLedger.
`scripts/verify_unified_full_policy_source.py` is its no-inference offline
grid/reward/journal verifier. No extra memory, proposer, meter or planner stack;
the consumed allocation cannot authorize retries or the old scientific runner.
Results are mixed; see `NEXUS_UNIFIED_FULL_POLICY_RESULTS.md`.

Source-verified at the research-tip merge, then extended by the
consolidation review. Future agents must consult
`docs/NEXUS_CANONICAL_CURRENT_STATE.md` and
`docs/NEXUS_FULL_RESEARCH_REGISTRY.md`, then reuse these surfaces
instead of opening parallel packages.

## Canonical stacks (keep)

Bounded executable compositions now use `evolution2.generated_strategies`
(Strategy/StrategyGenerator/AdvantagePredictor) and `unified_source_bench`.
They wrap existing catalogue operators, AdaptiveProposer, E2.25 ridge,
ObservationAwareAdaptive, TrustedEvaluator and ReservationLedger. Do not
create an independent E3 memory/proposer/planner stack. Development is negative
for useful learning/selection; only finite-source behavioral novelty passes.
See `NEXUS_UNIFIED_AUTONOMOUS_LEARNING.md`; no scientific dispatcher enabled.

`persist_reset_scoring.freeze_shared_reference` and `analyze_return_grid`
provide opt-in shared-source reference and complete ten-bundle raw-return
receipt analysis. Reuse them with the existing manifest evaluator and
ReservationLedger; do not create another scorer or meter. E2.29 is authored
fixture evidence only; no trusted real-return worker or scientific gate is
enabled. See `NEXUS_E2_29_RETURN_CONTRACT.md`.

Prospective method-sensitive hidden evaluation can use
`persist_reset_scoring.prospective_hidden_evaluator` with its saved,
hash-verified training-scale manifest. It reuses `MethodSensitiveHiddenEval`
and checks scope before cache access. See `NEXUS_E2_27_FEEDBACK_INTEGRATION.md`.
This is synthetic integration evidence, not a scientific run authorization.

For future feedback normalization use the existing `TrustedEvaluator`
opt-in `freeze_feedback_scale` and `FrozenTrainingFeedbackScale` in
`pendulum_acrobot_protocol_v2_pilot`. See
`NEXUS_E2_26_FEEDBACK_BOUNDARY.md`. Do not normalize from a query's full
catalogue or replace historical scalers/runners. This is a tested
synthetic path, not an automatically authorized scientific evaluator.

| Need | Use | Do not start |
|---|---|---|
| Discrete/continuous family env construction | `nexus.tasks.spec`, family modules, wrappers | A new env factory that guesses family from `obs_dim` |
| Residual world model | `nexus.world.dynamics`, `nexus.world.train` | A second dynamics MLP |
| Random-shooting / successor planning | Family lookahead modules + `RandomShootingMPC._score_batch` via `evolution2.planner_adapter` | `planning.mpc_for_model`, or calling catalogue H=16 historical 16×16 |
| Residual-MLP timing on frozen files | `evolution2.residual_timing_probe` plus `scripts/run_evolution2_residual_timing_probe.py` | A second probe that constructs envs or rewrites checkpoints |
| Source-fitting inventory / v2 wall-clock combine | `evolution2.source_fitting_benchmark` | Collecting replacement transitions or inventing a fit time |
| No-fit residual inventory | `evolution2.nofit_inventory` | Treating confirmation/latent/control files as n=10 bundles |
| Equal-information evaluation cache | `evolution2.pendulum_acrobot_protocol_v2_pilot.TrustedEvaluator` | Letting a candidate supply or overwrite scores |
| Analytic plan cost | `evolution1.catalogue.plan_bound` | Recoding H versus A+ANH |
| Pre-call work reservation | `evolution1.resources.ReservationLedger` | A third meter class |
| Synthetic training receipts | `evolution1.fixtures.FixtureBroker` | Ad-hoc lookup tables in proposers |
| Linear catalogue proposer | `evolution1.toy_loop.AdaptiveProposer` | A new SGD bandit for the same 12 arms |
| Task-conditioned strategy memory | `nexus.core.strategy_memory.ContextualStrategyMemory` | Replacing AdaptiveProposer or a second Evolution-2 method stack |
| Decide()-owned memory bench | `nexus.core.strategy_memory_decide_bench`; reuses `FakeStepModel`, `fixture_hidden_return`, `TrustedEvaluator`, E2.8 source arrays | Scoring with authored `hidden_score`, loading E2.17 science arrays, or collecting |
| Observation-aware memory bench | `nexus.core.strategy_memory_obs_bench`; reuses `ContextualStrategyMemory` modes and the locked eight tasks | A second memory stack or tuning `acro_zero_collision` after seeing results |
| Retrieved-mean / gated selector | `nexus.core.strategy_memory` selectors plus `strategy_memory_selector_bench` | A new proposer stack or changing persist features without a matched comparison |
| Persist + planning-obs features | `nexus.core.persist_obs.PersistentAdaptiveObs`; historical `PersistentAdaptive` stays 6-weight | Editing AdaptiveProposer in place or claiming FakeStepModel transfer |
| Residual decide() memory bench | `nexus.core.strategy_memory_residual_bench`; reuses `persist_reset_path.disposable_model` and E2.8 arrays | E2.17 science fits/arrays, new collection, or more 12-arm FakeStep/E2.9 selection |
| Residual identity / adapt bench | `nexus.core.residual_adapt` plus `residual_adapt_bench`; reuses `describe_support`, E2.9 `disposable_model`, `WorldModel.clone` | E2.17 science files, writing checkpoints, or replacing `WorldModel` |
| Observation-conditioned E2.22 memory | `evolution2.observation_memory.ObservationAwareAdaptive` wrapping `AdaptiveProposer`; bench `observation_memory_bench` | A second evolution stack, replacing persist, or calibrating the gate on shifted tasks |
| Cross-bundle E2.23 calibration | `calibrate_cross_bundle` plus `observation_memory_cross_bench`; reuses E2.22 wrapper and tasks | Tuning the p95 rule on E2.22 first-free, widening the gate again, or a new memory stack |
| E2 persist/reset/evolution wrappers | `evolution2.methods` | A second method registry |
| Pendulum/Acrobot proposer screen design | `evolution2.pendulum_acrobot_protocol_v2` (target) and `_v2_pilot` (reduced worksheet) | A third protocol that silently rewrites n, Bonferroni, or v2 hashes |
| Explicit n=3 no-fit micro | `evolution2.pendulum_acrobot_protocol_n3_micro` | Treating n=3 unmatched residuals as a v2 pass or using the df=9 t crit |
| Evolution-2 execution blockers | `evolution2.execution_blockers` | Opening a fourth worksheet or recovering source arrays from `.pt` weights |
| Source-array persist request | `evolution2.source_persist_request` plus `scripts/run_evolution2_source_persist.py` | Collecting 25600 or treating 7680 as v2 confirmation |
| 7680-step persist plan/collect | `evolution2.source_persist_plan` and `source_persist_collect`; arrays already at `artifacts/evolution2_source_arrays` | Closed confirmation/H17 physics, a second write, or treating the persist as a residual fit |
| Disposable residual fit clock | `evolution2.fit_clock` plus `fit_clock_run` and `scripts/run_evolution2_fit_clock.py` | Twenty-fit / n=10 training, new env steps, or treating disposable weights as v2 residuals |
| Development evaluator dry-run | `evolution2.evaluator_readiness` plus `evaluator_dry_run`; reuses `TrustedEvaluator`, `ReservationLedger`, catalogue, `planner_adapter` | A second planner/proposer/memory, or treating the dry-run as persist-versus-reset science |
| Persist-versus-reset request | `evolution2.persist_reset_request` plus `scripts/run_evolution2_persist_reset.py` | Collecting, naming a holdout, treating continue as approval, or treating `dispatch()` as a runner |
| Persist-versus-reset development dry-run | `evolution2.persist_reset_dry_run` plus `scripts/run_evolution2_persist_reset_dry_run.py`; reuses `methods`, `screen` contracts, `TrustedEvaluator`, `ReservationLedger` | A parallel screen framework, calling `require_named_holdout`, or treating the dry-run as science |
| Persist-versus-reset readiness / refuse-only runner | `evolution2.persist_reset_readiness`, `persist_reset_runner`, `persist_reset_planner_audit` | Treating 7680 or 9600 as the fresh total, enabling `run_scientific`, or naming a holdout |
| Persist-versus-reset resource budget / real path | `evolution2.persist_reset_budget` plus `persist_reset_path`; reuses `decide`, disposable residuals, `TrustedEvaluator` | Granting 7680, collecting fresh physics, or treating the 27.3 s planner prior as a scientific clock |
| Persist-versus-reset receding stored-obs clock | `evolution2.persist_reset_recede`; reuses locked train arrays and disposable residuals | Gymnasium rollouts, treating 27.7 s as new-physics screen time, or naming a holdout |
| Persist-versus-reset approval-text gate | `evolution2.persist_reset_approval` | Treating continue / i authorised you as a 17280 grant, or flipping frozen yaml |
| Four-role unused-instance verification | `evolution2.persist_reset_roles` plus locked `ROLE_DIGESTS` | New selection, outcome-based retuning, or treating verification as a named live holdout |
| Gated persist-versus-reset executor | `evolution2.persist_reset_executor` behind `persist_reset_request` / `persist_reset_runner` | Collecting, executing six fits, granting 7680, or treating development verify as science |
| One-run persist-versus-reset science | `evolution2.persist_reset_grant` plus `persist_reset_science`; reuses `collect_transitions`, `train_world_model`, `decide`, `TrustedEvaluator`, `methods` | Rewriting frozen request hashes, retrying a consumed grant, promoting n=3 to n=10, or starting Evolution-3 |
| E2.17 causal-sensitivity diagnosis | `evolution2.persist_reset_diagnosis` plus `persist_reset_science.MethodSensitiveHiddenEval` | Rewriting the inconclusive label, collecting, or treating E2.17 development as a new confirmation holdout |
| E2.19 persist/reset policy-state | `evolution2.persist_reset_policy_state`; reuses `AdaptiveProposer`, `PersistentAdaptive`, `ResetAdaptive`, `MethodSensitiveHiddenEval` | A second proposer, different persist/reset seeds to manufacture a contrast, or collecting new physics |
| E2.20 method-sensitive next screen | `evolution2.persist_reset_method_sensitive`; reuses `MethodSensitiveHiddenEval`, consumed `persist_reset_grant` | Reusing `run_bundle`, retrying 17280, treating continue as a 24480 grant, or naming E2.17 roles as confirmation |
| E2.21 executable scoring | `evolution2.persist_reset_scoring` plus `persist_reset_science.FrozenRevealedScale` / `fixture_hidden_return`; reuses `decide`, `FakeStepModel` | Treating fingerprint overlap as a leak, collecting, or rewriting E2.17/E2.20 locks |
| Unused Pendulum/Acrobot instance naming | `evolution2.pendulum_acrobot_holdout_review` (NAMING_BLOCKED) plus `evolution2.pendulum_acrobot_instance_rules` (unnamed four-role digests) | Shopping a new tuple or treating one Acrobot key as four roles |
| E2 public IPC / stub host | `evolution2.bindings` + `evolution2.host` | Importing `FAMILY_SPEC` into the worker |
| PPO training | `nexus.rl.ppo` | A new on-policy trainer for CartPole-scale tasks |
| V0.1 experiment memory | `nexus.memory.store.ExperimentStore` | SQLite of planner fixtures |
| World-model snapshot memory | `nexus.world.memory.PredictiveMemory` | Mixing this with ExperimentStore |
| V0.5 experiment selection | `nexus.meta.controller.LinUCBController` | Treating E2 SGD as the V0.5 meta-controller |
| Independent eval of PPO | `nexus.eval.evaluate` | Self-scored evolution fitness without a holdout |
| Closed-split guards | `nexus.world.confirm_guard` and H17 exclusion inventory | Reopening a named unused tuple |

## Three different “evolution” systems

| Package | What it evolves | Scientific status |
|---|---|---|
| `nexus.evolution` | PPO **architecture specs** (width, activation, residual) | V0.1 historical; not LEVEL 2 transfer |
| `nexus.evolution1` | **Planning-config catalogue** (rule × generator × horizon) | Toy loop works; real transfer untested |
| `nexus.evolution2` | Persistence of E1 proposer weights across **synthetic** families | Contract only |

Do not merge these into one module. Do not claim that running any of
them is learning-to-learn.

## Two different memories

| Module | Stores | Safe reuse |
|---|---|---|
| `nexus.memory.store` | Trained PPO experiment rows | V0.1 / meta-loop bookkeeping |
| `nexus.world.memory` | World-model weight snapshots + probe MAE | V0.8 adaptation memory |

Neither is a cross-task proposal-policy memory. E2 persistence is a
6-vector, not a memory system.

## Two different meta-controllers

| Module | Object | Status |
|---|---|---|
| `nexus.meta` | Which **PPO experiment** to run (LinUCB / ε-greedy / random) | V0.5 implemented |
| `nexus.cl.linucb_strategy` | Continual-learning strategy selection | V0.6 family |
| `evolution1.AdaptiveProposer` | Which **catalogue arm** to try | Toy / E2 |

A new “meta-learner” that does not name which of these it replaces is
a duplicate.

## Technically reusable vs not reusable as evidence

**Reusable implementation (after integrity checks):** family lookahead
entry points, residual world-model code, PPO trainer, catalogue schema,
reservation ledger, H17 exclusion *list* as a blocklist, runtime stub
for fixture tests.

**Not reusable as fresh scientific evidence:** H8–H16 returns, closed
confirmation physics, H16 unused MCC `(0.0015, 0.0014, 0.055)`,
Evolution-2 authored hidden scores, V0.8.9 CartPole/Pendulum closed
splits, any result whose protocol says “closes only this configuration.”

Reading a checkpoint to verify a hash is allowed. Training on its
holdout labels is not.
