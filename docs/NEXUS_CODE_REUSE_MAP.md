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
| Random-shooting / successor planning | Family lookahead modules + `RandomShootingMPC` constructed **explicitly** | `planning.mpc_for_model` as a generic dispatcher |
| Analytic plan cost | `evolution1.catalogue.plan_bound` | Recoding H versus A+ANH |
| Pre-call work reservation | `evolution1.resources.ReservationLedger` | A third meter class |
| Synthetic training receipts | `evolution1.fixtures.FixtureBroker` | Ad-hoc lookup tables in proposers |
| Linear catalogue proposer | `evolution1.toy_loop.AdaptiveProposer` | A new SGD bandit for the same 12 arms |
| E2 persist/reset/evolution wrappers | `evolution2.methods` | A second method registry |
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
