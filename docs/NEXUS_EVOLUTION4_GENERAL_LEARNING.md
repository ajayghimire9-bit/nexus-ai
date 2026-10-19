# Evolution-4 general learning foundation

Branch `codex/e4-general-learning-foundation`, starting at verified GitHub
`fa7d3b4ff27ce6494ce0867366f2e84b5f9e540d`. The tracked tree was clean;
untracked `src/nexus/evolution1/adapters.py` and its test are unrelated user
work and excluded. This is implementation work plus a small engineering
smoke, not a new learning experiment. E3.12F remains unregistered/unexecuted.

## Reuse and working interfaces

`tasks.benchmark` uses SAME `tasks.spec.TaskSpec`, `make_task_env` and existing
wrappers. `FamilyContract` describes all five requested Gymnasium environments,
observation fields, discrete action semantics, reward timing, native termination
versus wrapper-suppressed goals, and episode limits. Wrapped environments expose
their actual Box/Discrete spaces, including bounds and dtypes. Public default
physics are engineering fixtures, not a novel split or excluded-physics search.
Only reviewed positive physical parameters can be overridden. Custom noise,
delay or reward changes need separately reviewed contracts.

MountainCar and continuous MountainCar use the existing successor-position
dense reward and suppress goal termination. Acrobot uses existing successor
height and suppresses goal termination. Pendulum uses native pre-transition
reward; CartPole uses its native reward and failure termination. All retain
TimeLimit truncation. Continuous MountainCar uses the existing gravity patch
and discrete force adapter; Pendulum uses discrete torques. These are not
benchmark-standard native rewards for every environment. Report them explicitly.

`MeteredTaskEnv` reserves before stepping through SAME `post_probe.Host` and
Evolution-1 `ReservationLedger`; a shared Host accumulates costs across tasks,
roles and reopenings. It rejects invalid actions, premature steps and malformed
results, and records failed calls without free retries. Explicit initial seeds
are required; vector autoresets subsequently continue that seeded RNG. NumPy
integer actions from PPO's vector interface are decoded before trusted dispatch.
Do not wrap a world twice or replace the trusted environment factory in science.
The factory injection is solely for deterministic source-only tests.

`ppo_binding` returns kwargs for SAME `rl.ppo.PPOTrainer`: same CPU PPO recipe
and factory architecture for all five families, with independent shaped weights.
It does not instantiate a trainer, fit weights, choose research seeds or grant
execution. The learner's rollout length may overshoot a requested total, so
future allocations must reserve the actual rollout upper bound, not only
`total_timesteps`. All train, support and evaluation worlds must share the
same trusted Host. Physical time caps are cooperative checks at dispatch,
not process preemption; trusted code can overrun by the duration of one call.

Compatibility includes observation/action/reward/termination semantics and
normalization identity. Same dimensions do not imply same model interface:
the two MountainCar variants are deliberately incompatible. A matching contract
is permission to try separately evaluated transfer, not proof it works. Existing
`world.dynamics.WorldModel` remains owner of prediction/checkpoint behavior;
the new guard requires saved contract and normalization descriptors plus actual
network dimensions. It does not manufacture provenance for old checkpoints.
Old scientific planner bindings remain unchanged: four families have existing
bindings requiring verified compatible models; CartPole has no reviewed
Evolution-2 planning binding. This milestone does not claim five trained planners.

## Prospective benchmark, no training results

`configs/e4_general_learning_benchmark.json` is explicitly not registered or
authorized. Numerical research seeds/tasks and allocation are null. It expresses
source/scratch, permitted prior experience, reset shift, dynamics shift and
A-retention, with random/fixed/PPO scratch/reset/persistent/shuffled controls.
Planner comparisons must be added only where bindings and checkpoint provenance
are reviewed. A fixed policy here is action-index zero, not a strong controller.

The JSON schema is structural. `validate_results` additionally requires the
EXACT grid from the locked manifest (including entire missing axes), strict finite
numbers and integer resource counts. `summarize_results` keeps each family in raw
reward units and uses the existing `cl.metrics.seed_level_ci` on independently
trained learner replicates. Aggregate episodes inside learner seeds first. Shared
world-model/student seeds are not additional model replications. The helper
cannot prove that caller-supplied replicate labels are independent: the future
trusted runner must attest checkpoint lineage and raw episodes. No family-pooled
raw reward is reported. Optional normalization must be preregistered using only
source-derived random/strong-reference anchors, with uncertainty carried through.
The result schema is a starting interface, not a complete scientific runner.

## Minimal safe self-modification extension

Existing `evolution.mutate` already changes widths/depth/activation/residuals/
LayerNorm/shared trunks. Existing `nn.expr` interprets restricted Torch trees;
there is no generated Python or shell execution. The smallest addition is opt-in
`softsign` plus structural/arity/operator/node validation before registration
and construction. Legacy UNARY sampling stays unchanged, preserving past random
search recipes. Malformed trees previously accepted until evaluation now fail
early; valid historical checkpoint trees remain supported.

`nn.bounds` checks depth<=4, width<=256, typed flags, parameter and dense-MAC caps
BEFORE using the SAME factory. Exact trunk parameter counts include LayerNorm and
expression affine scalars. Dense MACs exclude activations, normalization, heads,
optimizer work and backwards; expression node-elements are a separate proxy.
Deterministic untrained shape/finite-gradient probes preserve caller Torch RNG.
These checks are not empirical performance or a certified arbitrary-input
stability proof. Residual/normalization variants are existing capabilities,
not new inventions. Update-rule selection reuses mean/recent/conservative rules;
optimizer-family search is deferred, with no unrestricted optimizer generation.

## Continual and experiment-selection boundary

`tasks.learning_stream` is a thin bridge into SAME `continual_state.TaskStream`,
`EpisodeContext`, `StrategyGenerator` and `EpsilonGreedyController`. A→B→A→C can
use new shape-correct contexts while retaining/resetting/shuffling permitted
strategy statistics. Existing fixed/random/adaptive schedules and bounded
mean/recent/conservative rules remain owned there. Synthetic feedback in tests
is labeled synthetic; real feedback must be measured improvement/cost on permitted
training episodes. Predictions and hidden evaluation outcomes are not rewards.

Reuse `cycle_checkpoint` for existing authored fixture sessions and PPO's own
checkpoint machinery for neural/Adam/RNG/normalization state. They are different
codecs: the fixture codec does not save an arbitrary neural continual learner.
The trusted Host's cumulative resource state must survive a future real learner
restart; new ledger origins or restored learner counters cannot refund spending.
That integrated durable neural runner is unfinished, and no real continual
learning or forgetting has been measured here.

The current TaskStream actions are test_challenger, gather_evidence and
refine_strategy (or stop). Map strategy tests/exploration into those existing
actions only with a frozen dispatch plan. Architecture mutation, update-rule
comparisons and revisits need explicit typed plans with Work upper bounds and
trusted evaluator bindings before execution. Do not silently widen legacy
`meta.schema` scientific allowlists or count an alias as implemented behavior.

## Future curriculum, dependencies not installed

First add a separately tested MiniGrid observation adapter, preserving partial
observability and mission semantics, with map/task split provenance. Its discrete
grid-world tasks and available observation wrappers are documented by
[Farama](https://minigrid.farama.org/). Reusing PPO does not imply that today's
flat state MLP or three-action Host dispatch supports its larger action space.
Add memory tests before claiming partial-observation competence.

Then investigate procedural train/test level separation and an image encoder;
[Procgen](https://github.com/openai/procgen) is a reference for procedural
generalization. No level seeds are selected now. Existing vector world models
cannot directly ingest pixels. Finally,
[Crafter](https://github.com/danijar/crafter) would require visual state, longer
temporal credit and achievement-aware reporting with fixed evaluation rules.
Text/tool tasks need tokenizer/action-schema, sandbox and permission boundaries;
an optional LLM must not substitute for evidence of learned adaptation. These
are integration proposals, not installed environments or demonstrated abilities.

## Locked engineering smoke, before collection

Executable source of truth: `configs/e4_foundation_smoke.json`; runner
`scripts/run_e4_foundation_smoke.py --execute-smoke`. Five public default/source
tasks × two authored policies (random/fixed index0) × two identical replays ×
four transitions gives at most **80 real steps**, **zero model calls/imagined
transitions/training**, local CPU, **30-second wall/CPU cap**. Seed0 is an
implementation fixture, not a held-out scientific registration. No result may
be used to select an algorithm. Require identical paired short trajectories,
valid finite observations/rewards, correct schemas and budget receipts; preserve
native termination and honestly record fewer steps if a path ends early.

Commit implementation and this protocol before invoking the runner. It refuses
tracked dirty state and overwrite, saves partial failures, and records execution
SHA/config hash/contracts/versions/receipts. Charge elapsed smoke wall time to
the carried ledger **1808.9990201649957 used /1791.0009798350043 remaining**.
Tests using authored worlds and untrained tensors are engineering checks, not
new scientific execution. Historical artifacts/checkpoint files remain unchanged.

## Delivery status

Implementation complete for the five-family contract, metered evaluation,
PPO constructor binding and minimal activation/bounds extension. Prospective
schema and existing-stream bridge are prepared; scientific benchmark training,
real neural durable stream evaluation, architecture promotion and expanded
curriculum remain unfinished/unrun. Smoke/test outcomes will be recorded in a
separate delivery commit. Before collection, **943 tests passed in57.85s**:
the45 modules listed in the prior `e3_12f_preparation_delivery.json` final_relevant
record plus test_e4_general_learning, test_expr, test_expr_checkpoint,
test_factory, test_activations and test_activation_validate. This curated
source/fixture suite is not the entire historical scientific/simulator suite.
Initial vector fixture tests exposed an unsupported context-manager use in the
test harness; replacing it with explicit closing fixed all five failures.
Passing tests cannot establish transfer, continual
learning, learning-to-learn, self-improvement or AGI.

### Completed delivery

Protocol/implementation `c05330134318bad74b1d1f6a7c2e1d45c327e555`;
pre-execution numeric-scalar compatibility fix
`b79c3c591502c469e51a972c37993fbf3be03752` (94 focused tests passed in1.98s).
The smoke executed ONCE from the latter clean tracked revision and completed
all10 family/policy pairs with two identical four-step replays: **80 real
steps**,0 imagined transitions,0 learned-model calls/forwards,0 fits. Host
wall0.013773875s, CPU0.012755s; total command wall0.633083291s including startup.
Raw trajectories and80 reservation receipts are in `e4_foundation_smoke.json`,
SHA256 `50cf589f97da42e5e765a63ccfd75ac21f6fc5e3c63826d94030ca2fcafba170`.
No random-versus-fixed performance inference is made from these short traces.

Final relevant suite: **945 passed in57.53s**, same51-module selection as above
including new numeric-reward compatibility and saved-smoke accounting checks.
This remains a curated suite, not all historical model/simulator tests. The
full five-family PPO trainer was not fitted: vector APIs, actor–critic shape
and gradients are tested on authored fixtures/untrained tensors. The existing
factory's update rules and real training performance were not improved here.

All432 JSON artifacts tracked at the starting revision are byte-identical;
12 prior manifest-listed checkpoint/source files retain their expected hashes.
No historical checkpoints were loaded for inference or replaced. Unrelated
untracked adapter files remain excluded. `AGENTS.md` is unchanged.

The smoke artifact carries the Host-only tally. Conservatively charge the
larger entire command wall to the session: **1809.6321034559958 used /
1790.3678965440042 remaining**. The extra startup charge is in the delivery
record, not a rewrite of the raw smoke artifact. Unit/regression fixtures are
engineering verification rather than scientific execution. No additional
research allocation, holdout registration, architecture search or F collection.
See `artifacts/e4_foundation_delivery.json` for commands, hashes and unfinished
work. Next proposed study is the separately registered small five-family
scratch-learning benchmark in `NEXUS_EVOLUTION4_NEXT_EXPERIMENTS.md`; not run.
