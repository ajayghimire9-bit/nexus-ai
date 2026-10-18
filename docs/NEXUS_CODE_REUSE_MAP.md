# NEXUS code-reuse map

Source-verified at the research-tip merge, then extended by the
consolidation review. Future agents must consult
`docs/NEXUS_CANONICAL_CURRENT_STATE.md` and
`docs/NEXUS_FULL_RESEARCH_REGISTRY.md`, then reuse these surfaces
instead of opening parallel packages.

## Canonical stacks (keep)

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
