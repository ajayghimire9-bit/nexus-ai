# Direct latent unseen-physics confirmation

Starting SHA `f3ab5e6914d7c399be4235fdf4ffc628c78c952f`. Config: `configs/direct_latent_confirmation.yaml`. The runner rejects a drifted file.

Not AGI. Not control. Not learning-to-learn. This asks whether the locked latent-fitting procedure still lowers prediction error when the Pendulum physics were not in the world-model training set.

The replication unit is the model-training seed. There are three. Tasks, episodes, and rollout windows are averaged inside each seed. Intervals are exploratory Student-t intervals with 2 degrees of freedom.

## What is locked

The source diagnostic selected Adam learning rate **0.1** and **256** updates from the global vector (`docs/NEXUS_DIRECT_LATENT_CONTEXT.md`). This confirmation uses that rule and does not search another one.

Each seed loads the same history-decoder checkpoint, checks its file hash, and freezes the encoder, FiLM, trunk, heads, and normalization. The global vector is the one stored in `artifacts/direct_latent_selection.json`, checked by hash. It is not refit. Only a new `z`, initialized from that vector, receives Adam updates, and only on that confirmation task's 128 support transitions.

The loss stays the existing normalized prediction loss: state error plus 0.25 times the termination loss.

<!-- protocol-lock
confirm_hash: 87b83c41be34aa1a
support_env0: 64000
query_env0: 68000
support_base: 250000
query_base: 251000
learning_rate: 0.1
updates: 256
support_budget: 128
query_episodes: 4
query_transitions: 800
donor: confirmation_task_(i+1)_mod_n
horizons: 3,8,16
screen_angvel_improvement: 0.05
screen_min_positive_seeds: 2
screen_max_worsening: 0.05
-->

## Physics

The reserved confirmation split hash is `87b83c41be34aa1a`. The live tuples must be:

| Task | g | m | l |
| --- | ---: | ---: | ---: |
| pendulum_ctx_c0 | 4.8 | 1.0 | 1.0 |
| pendulum_ctx_c1 | 15.2 | 1.0 | 1.0 |
| pendulum_ctx_c2 | 10.0 | 0.35 | 1.0 |
| pendulum_ctx_c3 | 11.8 | 1.6 | 0.75 |

These tuples are disjoint from the eight source-training physics. The runner checks the hash before it collects a transition.

## Episodes

Support and query are new and disjoint from training, validation, diagnostic splits, and the optimization, frozen-dynamics, and direct-latent audits.

- Support env base **64000**, seed base **250000**, 128 transitions
- Query env base **68000**, seed base **251000**, 800 transitions, four complete episodes per task

The four query episodes are shared across conditions and model seeds. The donor for task `i` is confirmation task `(i+1) mod 4`. Query rows do not enter the optimizer.

## Conditions

Same frozen decoder:

1. Task-specific latent, fit on that task's support.
2. Zero latent.
3. Global latent from the source-training fit.
4. Wrong-support latent, fit on the donor's support with the same rule.
5. Frozen history-encoder latent, inferred from the same 128 support rows with no update.

The 1000-update multitask MLP is an external reference. It is a different network and is not a same-decoder control.

## Screen

The task latent must:

- Cut mean angular-velocity MAE by at least 5% versus zero, the global vector, and the wrong-support vector.
- Do that against all three in at least two of the three model seeds.
- Stay within 5% of the global vector on overall MAE and on horizon-16 error. Worsening past that fails the screen.
- Leave every network parameter and normalization statistic unchanged.
- Finish with finite losses and metrics.

A lower support loss is not success. The artifact lists any confirmation task whose own mean misses the 5% bar, and any seed-task cell that does not beat a control. Those task rows are not extra replications.

A pass would mean the locked fitting procedure transferred to this physics set. It would not mean the encoder amortizes that fit, that control improved, or that the result holds for every pendulum. A failure would mean the source-task gain did not hold here. The protocol stays fixed either way.

## Results

Execution SHA `aac5e33d677f05fc57e9191bd522e82982e3ef20`. `source_dirty` was false. Wall clock **5.2 s**. The split hash checked out as `87b83c41be34aa1a`. The three frozen-network digests matched the source diagnostic (`71d44b78…`, `4bcdc147…`, `13090d27…`). Nonfinite steps **0**. Mean gradient norm **1.37e-4**.

Support loss fell from **0.00411** to **0.00154**. That is not the screen. The screen uses held-out query error.

Angular velocity, mean of three model seeds, exploratory Student-t interval, df = 2:

| Condition | Angvel | Overall MAE | RMSE | Horizon 16 |
| --- | ---: | ---: | ---: | ---: |
| Task latent | **0.152 [0.104, 0.201]** | 0.0584 [0.0436, 0.0732] | 0.108 [0.0769, 0.139] | 0.523 [0.308, 0.738] |
| Zero | 0.308 [0.279, 0.338] | 0.111 [0.100, 0.121] | 0.200 [0.182, 0.218] | 1.176 [1.073, 1.279] |
| Global | 0.314 [0.301, 0.328] | 0.112 [0.108, 0.117] | 0.203 [0.195, 0.212] | 1.225 [1.199, 1.251] |
| Wrong-support | 0.398 [0.348, 0.448] | 0.144 [0.124, 0.163] | 0.262 [0.230, 0.293] | 1.717 [1.597, 1.837] |
| Frozen encoder | 0.307 [0.269, 0.344] | 0.110 [0.0976, 0.122] | 0.198 [0.174, 0.221] | — |
| MLP reference | 0.316 [0.297, 0.335] | 0.113 [0.106, 0.120] | 0.204 [0.194, 0.215] | — |

The MLP is an external network. Paired contrasts are control minus task on angular velocity, so a positive number is a lower task error. All five exclude 0:

| Contrast | Mean [interval] |
| --- | --- |
| Zero − task | **+0.156 [0.136, 0.176]** |
| Global − task | **+0.162 [0.127, 0.197]** |
| Wrong − task | **+0.245 [0.146, 0.344]** |
| Encoder − task | **+0.154 [0.120, 0.189]** |
| MLP − task | **+0.164 [0.134, 0.194]** |

Per seed, task angular velocity was **0.164, 0.163, 0.130**. Each seed beat its own zero, global, and wrong-support vector. Positive seeds **3/3**. The task mean is about **51%** below zero, **52%** below the global vector, and **62%** below the wrong-support vector.

Open-loop error at horizons 3 and 8: task **0.129** and **0.294**, global **0.294** and **0.724**. Paired task-minus-global MAE **−0.0539 [−0.0640, −0.0439]** and horizon 16 **−0.702 [−0.892, −0.513]** exclude 0, both in the direction of a lower task error.

Cosine task-minus-global **−0.00201 [−0.00824, +0.00422]** includes 0. Sine **+0.00236 [−0.00019, +0.00490]** includes 0. The angular-velocity component is the one that moves.

Every confirmation task met the 5% point bar. Means across the three seeds:

| Task | Physics | Task | Zero | Global | Wrong |
| --- | --- | ---: | ---: | ---: | ---: |
| c0 | g=4.8 | 0.0725 | 0.233 | 0.214 | 0.436 |
| c1 | g=15.2 | 0.108 | 0.295 | 0.316 | 0.188 |
| c2 | m=0.35 | 0.335 | 0.374 | 0.374 | 0.391 |
| c3 | m=1.6, l=0.75 | 0.0943 | 0.332 | 0.354 | 0.575 |

No task missed the point screen, and no seed-task cell failed to beat a same-decoder control. The low-mass task c2 is the weak case: the relative drop is about **10%** versus zero and the global vector, and the remaining angular-velocity MAE is **0.335**.

The frozen encoder, given the same 128 support rows, sits on zero context (**0.307** versus **0.308**). The useful code was the optimized latent, not the encoder's inference.

Env steps: support **512**, query **3200** (four episodes on each of four tasks). Optimizer steps **6144**. Support examples processed **786432**. Plots: `artifacts/direct_latent_confirmation_angvel.svg`, `artifacts/direct_latent_confirmation_dims.svg`, `artifacts/direct_latent_confirmation_tasks.svg`.

The locked fitting procedure lowered prediction error on this four-task physics set. n=3 is exploratory, and the primary intervals exclude 0. This is not a universal pendulum result, not amortized inference, not a control result, and not learning-to-learn. No control sweep was run.
