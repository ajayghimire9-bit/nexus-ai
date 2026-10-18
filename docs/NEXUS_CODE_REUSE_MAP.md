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
| E2 persist/reset/evolution wrappers | `evolution2.methods` | A second method registry |
| Pendulum/Acrobot proposer screen design | `evolution2.pendulum_acrobot_protocol_v2` (target) and `_v2_pilot` (reduced worksheet) | A third protocol that silently rewrites n, Bonferroni, or v2 hashes |
| Explicit n=3 no-fit micro | `evolution2.pendulum_acrobot_protocol_n3_micro` | Treating n=3 unmatched residuals as a v2 pass or using the df=9 t crit |
| Evolution-2 execution blockers | `evolution2.execution_blockers` | Opening a fourth worksheet or recovering source arrays from `.pt` weights |
| Source-array persist request | `evolution2.source_persist_request` plus `scripts/run_evolution2_source_persist.py` | Collecting 25600 or treating 7680 as v2 confirmation |
| 7680-step persist plan/collect | `evolution2.source_persist_plan` and `source_persist_collect`; arrays already at `artifacts/evolution2_source_arrays` | Closed confirmation/H17 physics, a second write, or treating the persist as a residual fit |
| Disposable residual fit clock | `evolution2.fit_clock` plus `fit_clock_run` and `scripts/run_evolution2_fit_clock.py` | Twenty-fit / n=10 training, new env steps, or treating disposable weights as v2 residuals |
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
