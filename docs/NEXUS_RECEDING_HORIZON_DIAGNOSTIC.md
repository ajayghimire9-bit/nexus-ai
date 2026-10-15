# NEXUS — Receding-horizon planner diagnostic

## Measured result

The locked grid finished on all ten decoders in **784.6 s**. Implementation SHA `b6a079bab98c965b65a127e90a178a73ddcbb7f2`. Artifact `artifacts/receding_horizon_diagnostic.json` (sha256 `46b0eb85e655b7bb9e71d9a19268202733211f3741ab2fcb8729e193bc7c49f0`). The encoder, decoder, planner, horizon, and candidate count were unchanged. The closed 200-step returns were not remeasured. Every stored live decision reproduced: **1920 / 1920** phase captures matched the recorded action and the recorded scores within `1e-5`.

On the fresh physics, the primary decision is `inconclusive`. Pooled one-shot regret improves by **0.812 [−0.038, 1.662]** (student **2.701**, zero **3.513**). The interval includes 0. Student-visited states are **0.451 [−0.097, 0.998]** and zero-visited states are **1.173 [−0.329, 2.676]**. Both include 0. The matched next-16 continuation changes by **−0.528 [−1.139, 0.083]** (student **−62.43**, zero **−61.90**). That interval includes 0. Selected-action regret moves by the same amount, because the three first actions share one continuation. Because both contexts score one shared candidate set, the open-loop selected-sequence return gap equals the one-shot regret gap. It is the same comparison, reported twice.

The H=16 score of the selected sequence is closer for the student: absolute error falls by **4.751 [3.023, 6.480]** (student **11.65**, zero **16.40**). Candidate reward-forecast error falls by **6.539 [4.548, 8.529]** (student **9.76**, zero **16.30**). Spearman correlation changes by **−0.013 [−0.067, 0.041]** (student **0.645**, zero **0.657**). The first actions agree on **0.639 [0.600, 0.679]** of visited states. The diagnostic candidate set, which is a new draw, selects the same first action as the live episode on **0.469 [0.433, 0.504]** of those states. Live replay of the stored sequences is the implementation check, and that check passed.

Phase and task breakdowns are descriptive. Fresh regret at step 0 is **4.303 [1.276, 7.330]**. Steps 50, 100, and 150 are **−0.472 [−0.977, 0.033]**, **−0.067 [−0.608, 0.474]**, and **−0.516 [−1.382, 0.349]**. The later three include 0. Fresh continuation at step 0 is **−2.221 [−4.622, 0.181]**, and the later phases sit near 0 with intervals that include 0. Task regret is **2.912 [−0.002, 5.826]** on `rp0`, **1.298 [0.839, 1.757]** on `rp1`, **−0.187 [−0.349, −0.025]** on `rp2`, and **−0.775 [−2.101, 0.551]** on `rp3`. Task continuation is reliably negative only on `rp3`, at **−0.056 [−0.102, −0.010]**. The mean observation distance between student-visited and zero-visited states is **2.323 [2.118, 2.528]**. Pearson correlation of decoder-level regret improvement with continuation improvement is **0.297**. Correlation across ten decoders is not a cause.

The registered branches stay open. Replay succeeded, so the planner-implementation branch is not the finding. The student is not reliably worse on visited states, so visited-state shift is not the finding. One-shot regret is not reliably better and the next-16 return is not reliably worse, so replanning and compounding are not the finding. Score error improved while regret, Spearman, action regret, and continuation did not all favor the student, so the local measurements do not agree well enough to leave the full-episode gap as a separated long-horizon question. The next-16 return is a matched 16-step continuation. It is not an estimate of the 200-step episode value. The closed fresh gap of **−19.4 [−35.4, −3.3]** remains an input.

On the previous physics the local measurements agree with the closed positive return. That contrast is `local_agrees_with_closed_return`. Regret improves by **1.464 [1.028, 1.899]** (student **1.156**, zero **2.620**). The student-visited subset is **2.496 [2.037, 2.955]**; the zero-visited subset is **0.431 [−0.290, 1.152]** and includes 0. Selected-score error falls by **10.166 [8.884, 11.447]**, reward-forecast error by **9.701 [8.112, 11.289]**, and the next-16 continuation rises by **0.511 [0.331, 0.690]**. Spearman rises by **0.129 [0.059, 0.199]**. This split already had a closed return advantage. It is a contrast, not a new control result. Task `pendulum_lat_cf0` regret is **−1.837 [−3.153, −0.521]**; `cf1` and `cf2` favor the student; `cf3` includes 0.

Environment interactions were **680,704** steps: **1,024** support recollections, **96,000** live steps, **491,520** open-loop candidate steps, and **92,160** continuation steps. Model states were **48,496,640**: **24,576,000** live plans, **491,520** live-score replays, **1,310,720** counterfactual scores, and **22,118,400** continuation replans. The 1800-second limit was not hit. Ten decoders are the statistical units. Student seeds and states are averaged inside each decoder.

No architecture change and no planner change follow from this sample. This is not a general control improvement, not learning-to-learn, and not AGI.

The one-shot diagnostic found that the 584-parameter student predicts fresh Pendulum states better and ranks shared H=16 candidates better than zero context, while the closed full-episode return on those physics still favors zero context. This study asks whether that gap appears in the states the controllers actually visit, in the difference between an open-loop sequence and a replanned first action, or in the planner implementation. It is a mechanism measurement. It does not remeasure the closed episodes and it does not change the network, the weights, the horizon, or the candidate count.

## Competing hypotheses

These are registered together. A pattern can be described without being treated as a cause.

- **H1 — Visited-state shift.** The student can rank actions well at sampled initial states and poorly at states reached during control.
- **H2 — Replanning mismatch.** The return of a whole open-loop H=16 sequence can favor the student while the return of its first action, followed by replanning, does not.
- **H3 — Trajectory compounding.** A small action difference can move the later state enough that the matched continuation return falls, even when the one-shot ranking looks favorable.
- **H4 — Planning implementation.** Candidate generation, resets, context installation, reward timing, or planner reinitialization can disagree with the recorded live decision.

## Protocol lock

<!-- protocol-lock
episodes_per_task: 1
horizon: 16
n_candidates: 16
n_actions: 3
chunk_size: 4
max_steps: 200
phases: 0,50,100,150
target_decoders: 10
n_student_seeds: 5
primary_split: fresh
continuation_policy: zero_context_replan
continuation_context: zero
live_replication_env0: 170000
live_fresh_env0: 174000
live_seed_stride: 10
planner_seed_base: 176000
diagnostic_candidate_base: 210000
continuation_seed_base: 280000
time_limit_s: 1800
score_atol: 1e-05
starting_sha: 5260f6474e86e0f1db5e6d7820d4a3feaafe4783
prediction_artifact_sha256: f1f36506d3c64086898b6f462f9915a28037784dee52f47bce5c19b91bfe390a
control_artifact_sha256: 35c75320e1c243eaa1914cf6e726e9849d246910ebfc79f6ac0f390c86daf0e9
manifest_sha256: 265cd1822ec73bab8eac6fd792438c3c9fe7834ae5af307b8c33104bf919d06b
fresh_support_hashes: aa78f66887b76dcf,97b370d876c2a569,bd47719e5850bbf7,9b97c8539673828c
confirm_split_hash: baa655fcb94e61bc
fresh_split_hash: 053e8efca60fb4ac
full_episode_remeasured: false
fresh_full_episode_student_better: false
replication_full_episode_student_better: true
-->

## Provenance and seeds

Before any live episode, the run checks the ten decoder checkpoints, the broad and baseline student hashes, the global vectors, the original decoder fingerprints, the checkpoint manifest, the closed control-replication artifact, and the one-shot diagnostic artifact. Fresh support recollections must match the four hashes stored by that one-shot run. A miss stops the run. No checkpoint is written.

GitHub `cursor/prediction-control-gap-diagnostic` was `5260f6474e86e0f1db5e6d7820d4a3feaafe4783` when this branch was created. Live resets start at 170000 and 174000. They are rejected if they intersect a closed collect, a closed control episode, or the one-shot diagnostic seeds. The closed episode blocks at 110000, 120000, and 126000 stay closed.

Each of the five broad student seeds and the zero controller collects one 200-step episode on every task. That is the equal trajectory budget. Student seeds are averaged inside the decoder. The decoder is the statistical unit. States, candidate sequences, and student seeds are not extra replications.

## Live control

The controller is the existing random-shooting planner: horizon 16, 16 candidates, chunks of 4, time budget disabled, published pendulum reward. A new planner is seeded at each episode boundary. At steps 0, 50, 100, and 150 the run stores the true simulator state, the observation, the action, the planner seed, the selected index, the candidate scores, the immediate reward, and the termination flags. The true state is `(theta, angular velocity)`. It is used only to clone the simulator. The model sees the 3-D observation and does not receive gravity, mass, length, or a future reward.

Context is installed before the episode. Zero context is the zero vector. Student context is the saved broad encoder applied to the closed support for that task. The vector is checked at the end of the episode and after every continuation replan.

## Same-state counterfactuals

At each stored state the simulator is restored, including the episode time-limit counter. One new shared set of 16 sequences is drawn. Both contexts score that set with the same chunked planner objective used by `act`. The simulator then executes each full sequence from the restored state. Regret, correct selection, Spearman correlation, and the absolute error of the planner score are computed from those realized returns. The returns are not passed into the model.

The diagnostic candidate set is not the set the live planner drew. Reproducing a live decision uses the stored live sequences. If replaying those sequences does not recover the recorded action and the recorded scores within absolute and relative tolerance `1e-5`, the implementation branch is taken before any regret measurement is treated as evidence about the model.

## Continuation rule

This rule is fixed before any score is read.

From the restored state, apply one committed discrete action and record its published reward. For each of the next 15 steps, reseed a new zero-context planner with `continuation_seed(state_id) + step` and apply the first action of its selected sequence. The seed depends on the split, task, phase, visitor slot, and step. It does not depend on the committed action or on which context is being judged. The continuation model is the same decoder's zero vector, so the continuation policy is the same function of state for every branch. The reported next-16 return is the sum of those 16 environment rewards.

That return is a matched 16-step continuation. It is not an unbiased estimate of the 200-step episode value.

All three discrete first actions are evaluated under this rule. Selected-action regret is the best of those three returns minus the return of the chosen action. The open-loop comparison is different: it executes all 16 actions of the diagnostically selected sequence and does not replan.

## Decision

Positive means the student is better: lower regret, lower absolute score error, or higher return. A reliable improvement needs all ten decoders, a positive mean, and a Student-t lower bound above zero. The primary decision uses the fresh split, pooling student-visited and zero-visited states with equal weight. The replication split is a contrast. The closed full-episode facts stay inputs: fresh did not favor the student, and the previous physics did.

1. If any recorded live decision fails replay, the finding is a planner-implementation discrepancy. Regret is reported and is not the model-quality conclusion.
2. Otherwise, if one-shot regret on the visited states is reliably worse for the student, visited-state shift is the supported finding.
3. Otherwise, if one-shot regret is reliably better and the matched next-16 continuation is reliably worse, the finding is sensitivity to replanning or action compounding. A better open-loop sequence return alongside a worse continuation is recorded as the replanning description. A worse open-loop sequence return alongside a worse continuation is recorded as the compounding description. Those descriptions are not causes.
4. Otherwise, if one-shot regret, selected-sequence score error, selected-action regret, and the next-16 continuation all favor the student, the local measurements agree with each other. On the fresh split the closed episode still does not, so the discrepancy is unresolved and the next study is a controlled long-horizon policy-value comparison. On the replication split the same local agreement is only a contrast with the closed positive return.
5. Otherwise the intervals do not separate the branches.

An unfinished grid is incomplete. It does not choose a hypothesis and it does not justify an architecture change. No change to the planner or the network is made in this branch.

## What this study will not claim

A completed diagnostic is evidence about these controllers, these physics, and this continuation rule. It is not a general control improvement, not learning-to-learn, and not AGI.
