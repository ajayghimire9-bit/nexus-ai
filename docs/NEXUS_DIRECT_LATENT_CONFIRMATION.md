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

The confirmation has not been run in the implementation commit.
