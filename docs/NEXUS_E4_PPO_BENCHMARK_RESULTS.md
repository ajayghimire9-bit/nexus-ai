# E4 five-family scratch PPO pilot — complete, overall screen failed

Branch `codex/e4-five-family-ppo-benchmark`, base
`b2ae7ac9da70ee8aff2a54f65f039181fa33e4ac`. Protocol, configuration,
allocation, seed audit and implementation were committed **before collection**:
`54c915f7603665cbb2fab2feeebbe22e3455ea91`. One execution only; no retry,
checkpoint selection, hyperparameter change or extra episode. The original
protocol/config and all297 pinned source hashes still match. Main unchanged.

## Decision

**`five_family_scratch_learning_not_established`**. Valid complete execution,
not an incomplete run or correctness failure. None of the five families passed
the predeclared BOTH-baseline rule at4096 training interactions/model. This is
not proof PPO cannot learn these tasks or that the architecture lacks capacity.
It establishes that this particular short, shared recipe did not demonstrate
useful learning across all five known source/default tasks.

All15 independent scratch fits completed32 rollout updates/512 Adam steps
each. All90 full evaluation episodes completed on new paired resets; no
episode was dropped or replaced. Every model's initial and fitted parameter
hashes differ, and all15 fitted hashes remain identical after evaluation.
Neither parameter changes nor finite training losses were treated as success.

## Returns and paired contrasts in each family's units

Numbers below average two episodes inside each of three independent learner
seeds, then report paired seed-level95% t intervals, df2/critical4.303. Higher
return is better. Intervals are exploratory/unadjusted; episodes and families
are not additional model replications. No raw cross-family return average.

* **CartPole:** PPO21.333, random18.000, fixed9.500.
  PPO−random **+3.333 [−46.822,+53.489]**; PPO−fixed
  **+11.833 [−34.849,+58.515]**. Required margin25; fails.
  PPO−random per seed:+26.5,−10.5,−6.0.
* **MountainCar (existing dense reward):** PPO−189.471, random−195.870,
  fixed−171.592. PPO−random **+6.399 [−40.674,+53.472]**;
  PPO−fixed **−17.879 [−65.075,+29.316]**. Required margin5; fails.
  PPO−random per seed:−3.225,+28.228,−5.805.
* **Continuous MountainCar (existing discrete force/dense reward):**
  PPO−128.287, random−190.647, fixed−137.587. PPO−random
  **+62.360 [+42.668,+82.052]**; PPO−fixed
  **+9.299 [−30.716,+49.315]**. Required margin5; fails the fixed-policy
  comparison. PPO−random is positive in all three seeds; the fixed difference
  is+27.898,0,0, so the random comparison alone cannot establish overall success.
* **Pendulum:** PPO−1490.193, random−1226.791, fixed−1308.267.
  PPO−random **−263.402 [−1031.760,+504.957]**; PPO−fixed
  **−181.926 [−1025.131,+661.279]**. Required margin25; fails.
  PPO−random per seed:−30.444,−614.301,−145.460. Negative point estimates
  in all three seeds coexist with very wide intervals.
* **Acrobot (existing dense height):** PPO−394.591, random−378.687,
  fixed−392.990. PPO−random **−15.904 [−29.285,−2.523]**;
  PPO−fixed **−1.601 [−10.102,+6.901]**. Required margin5; fails.
  PPO−random per seed:−21.908,−14.309,−11.496. This is an exploratory
  negative contrast on this finite source task, not universal harm evidence.

Raw seed/task/method/episode metrics, all32-update training histories and
checkpoint hashes are in `artifacts/e4_ppo_benchmark.json`. Its SHA256 is
`67d5959f1fdae31569d03e1d4474b76acb8129f284c3f0a85fa78c7ea775c67f`.
The independent stdlib replay reproduces every paired interval and decision
from episode means rather than using the original analysis implementation.

## Descriptive diagnostic, not a new primary test

Posthoc counts from saved evaluation actions show that **13/15** greedy policies
used a single action throughout their two recorded episodes. Both continuous
MountainCar learner1/learner2 trajectories exactly match fixed-index-zero,
explaining their identically zero paired differences algebraically. Other
families often choose a different constant action. These observations do not
establish why learning failed or what a stochastic rollout would return.

Some final training-batch entropies remain near uniform, despite deterministic
argmax evaluation (e.g. Pendulum learner0:1.0975 vs log(3)=1.0986). Batch entropy
is not held-out statewise logits, and stochastic training differs from greedy
evaluation by the registered rule. A readout mismatch, short training budget,
reward/observation scaling and optimization remain competing explanations.
No explanation was used to change or rerun this experiment.

## Costs and integrity

* Real interactions: **76,133** = **61,440 training +14,693 evaluation**,
  below84,840. Native early CartPole failures explain the unused allowance;
  all planned episodes are present. No support/probe/validation collection.
* **Zero imagined transitions/world-model calls.** Actor–critic work is NOT
  zero:135,728 trunk forwards/373,808 trunk input rows;74,048 policy-head calls;
  130,800 value-head calls;7,680 Adam steps. Training minibatch examples245,760
  include four-epoch reuse of61,440 actual transitions. No model-based planning.
* Execution21.044135s wall/21.005993s CPU. Separate independent raw-journal/
  checkpoint audit4.091240s wall/4.089467s CPU. Additional stdlib arithmetic/
  action-description pass0.220592s. Combined **25.355966s**, within300s.
  Training per-model timers sum18.090583s; evaluation path timers1.849767s.
* Peak process RSS438,534,144 bytes, including Python/Torch overhead. Networks
  have4675 CartPole,4612 MountainCar/continuous MountainCar,4676 Pendulum and
  4868 Acrobot parameters each; no capacity search.
* Fifteen new local checkpoints total1,233,523 bytes under ignored
  `runs/e4_ppo_benchmark`. They retain model, Adam and existing RNG/environment
  metadata, but are not uploaded binaries or a promised exact Host-resume codec.
  Their paths/hashes are in the result. Sixteen tracked compressed raw-journal
  parts total17,369,365 bytes; every transition and its resource receipt is saved.
* All434 historical base JSON files and12 prior manifest-listed checkpoint/
  source files remain unchanged. Original frozen research checkpoints were
  neither loaded for inference nor retrained. All closed confirmation physics
  and seeds, H17 blockage and F's unexecuted status remain intact.

The independent saved-data audit reconstructs all76,133 receipt/hash chains,
90 full returns and verifies all15 local checkpoint hashes with zero new
simulation/inference. The raw validation record contains the exact phase ledger.
For conservative session accounting, charge **26s** including startup/save
rounding: **1835.6321034559958 used /1764.3678965440042 remaining**. This is
slightly larger than measured phases; raw clock records are not overwritten.

## Tests and reproduction

Before collection:69 focused checks in1.10s and973 relevant source/fixture
regressions in55.87s. Afterward:75 combined focused checks in0.99s; final
relevant suite **982 passed in57.62s**, including independent arithmetic and
explicit missing/changed-checkpoint rejection. Exact module list/commands are
recorded in `artifacts/e4_ppo_benchmark_delivery.json`.
This is not every historical scientific/simulator test. Authored-world tests
and untrained/tiny toy tensor updates do not collect scientific environment data.

Repeatable local binary integrity verification uses Python's standard library:

```
python3 scripts/verify_e4_ppo_checkpoints.py --checkpoints
```

That repeatable stdlib integrity audit fails if required checkpoint/journal files
are absent or changed. It does not silently skip missing binaries or overwrite
evidence. The original one-time full raw-journal audit was
`scripts/run_e4_ppo_benchmark.py --verify`, using `PYTHONPATH=src:.deps` and the
registered single-thread settings, creating its exclusive validation record.
Its locked code stays unchanged.
A fresh clone can independently check the tracked evidence WITHOUT binaries:

```
python3 scripts/summarize_e4_ppo_benchmark.py --check-only
```

The original `--run` entry is consumed and refuses a rerun. Reproducing missing
local binary models requires a separate explicit reproduction procedure/grant
and new output paths; never remove the usage marker or alter historical results.

## Limitations and single next experiment

Three learner seeds and two evaluation episodes give low power and mixed
training/evaluation variability. Known default physics, adapted dense rewards,
discretized continuous actions and fixed short training do not establish task
transfer, convergence, continual learning, learning-to-learn or general control
improvement. Random/fixed receive no training interactions; this is not an
equal-total-compute comparison between learning algorithms. No strong tuned PPO
or alternative RL baseline was run, and no checkpoint/hyperparameter was selected.

**Next proposed experiment:** freeze these15 checkpoints and compare categorical
sampling versus greedy argmax on fresh paired resets, retaining uniform-random
and fixed controls. This directly tests whether the registered readout matters
before changing architecture or increasing training. Proposed upper31,200 real
steps/90s, no training; not registered or executed here. A negative result would
leave insufficient short-budget policy learning as an unresolved problem rather
than justify an automatic capacity increase.
