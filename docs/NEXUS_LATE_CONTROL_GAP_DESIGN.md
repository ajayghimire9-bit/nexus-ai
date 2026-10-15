# NEXUS — Late-control gap diagnostic design

This document registers a future experiment. It does not collect states, run a planner, change weights, or identify a mechanism. `architecture_change_authorized` is false. `mechanism_identified` is false.

The fresh-physics return decomposition found a student-minus-zero gap of **−30.671 [−41.540, −19.801]** on new episodes, with **−1.230 [−2.583, 0.123]** in steps 0–15 and **−29.441 [−40.706, −18.175]** in steps 16–199. The locked label was `primarily_late`. Mean observation distance along those paired trajectories was **1.697 [1.520, 1.874]**, **0.583** at step 16, and **2.865** at step 199. The controllers had already left the shared initial state, so that late sum is not a same-state effect.

## 1. Observation-distance audit

The return-phase code stacks the five student observation traces, averages them, and then takes the L2 norm against the zero-context observation at the same step:

`distance_t = || mean_s(observation_s,t) − observation_zero,t ||`

That is the distance between the mean student observation and zero context. It is not the mean of the five student-to-zero distances,

`mean_s || observation_s,t − observation_zero,t ||`.

The L2 norm is convex, so the distance of the mean is less than or equal to the mean of the distances. They are equal only when the five student observations at that step are identical. After the first action difference they generally are not. Students on opposite sides of the zero-context observation can make the mean close to zero context while every student is far from it. The mean of cosine and sine also need not lie on the unit circle, so the averaged observation need not be a state the pendulum can emit.

The stored decoder intervals average that mean-then-norm quantity over steps and episodes inside each decoder. Averaging afterward does not recover the mean of the per-student distances.

The receding-horizon `obs_distance` is a third quantity. It is the L2 norm between the mean observation of student-visited states and the observation of a separately collected zero-visited state. Those states come from different episodes. It is not the within-episode paired distance, and it is not the mean of per-student distances either.

A future run may report both the distance of the mean and the mean of the distances. The primary contrast below does not use either distance as an outcome. Distance remains a description of trajectory separation.

## 2. Same-state intervention

The future run uses the ten existing decoders, the saved broad encoders, horizon 16, and 16 candidates. It uses the fresh physics only (`053e8efca60fb4ac`). The closed support traces are recollected with the existing hashes and are not new physics. The return-phase episodes stay closed. New environment seeds start at 500000 and new planner seeds at 510000, one episode per controller slot per task. Each decoder sees the same resets. Five student seeds and one zero-context controller are the slots.

At steps 16, 50, 100, and 150 the simulator's true state is stored. Step 0 is not included. The true state is evaluation-only and is not given to the model. Restoration uses the existing `restore_state` path: elapsed steps return to 0, the order-enforcing wrapper is marked reset, and the unwrapped pendulum state is replaced. A restored observation that differs from the stored observation is an implementation failure, not a scientific result.

At each restored state both contexts score one candidate set. The candidate seed depends on task, phase, and slot. It does not depend on which context is scoring. The planner seed stream for that draw is identical for the student and for zero context. Scoring uses the visiting student's saved encoder on a student-visited state, and each of the five saved encoders on a zero-visited state. Student seeds are averaged inside the decoder before the cross-decoder interval.

## 3. Common continuation

The primary comparison isolates the immediate action. After the first discrete action, both branches follow the same continuation: the decoder's zero-context planner replans for the remaining steps. The continuation seeds do not depend on the committed action. Three candidate first actions are rolled once and then indexed, so the continuation policy is a function of state and step only.

The horizon of this continuation is 16 environment steps. It is the same length as the planning horizon. It is not the 184-step late sum from the return-phase study, and it is not a full-episode value. The contrast is student continuation return minus zero continuation return. A negative number means the student's immediate action is worse under the shared continuation.

Because both contexts score one shared candidate set, the open-loop selected-sequence return gap equals the one-shot regret gap. That identity is reported as a check. It is not a second primary outcome.

## 4. Full policy continuation

A second comparison starts from the same restored state and then lets each policy choose every later action with its own context and its own planner seeds. On a student-visited state the visiting student policy and the zero policy each roll 16 closed-loop steps. On a zero-visited state each of the five student policies and the zero policy roll 16 steps, and the students are averaged inside the decoder.

This comparison does not isolate the immediate action. After the first step the two policies occupy different states, and every later decision uses a different context. A gap here can come from the first action, from later decisions, or from the states those later decisions reach. It is reported separately and cannot change the primary label.

The live late sum from the return-phase study is a third, already measured quantity. In that study the policies were never restored onto each other's states. By step 16 the observation distance was already nonzero, and the remaining 184 steps mixed state distribution with decision rule. This design does not remeasure that sum.

## 5. Pre-registered decision

| Item | Lock |
| --- | --- |
| Primary contrast | Same-state common-continuation return, student minus zero |
| Statistical unit | Decoder, n = 10, Student-t 95% |
| Aggregation | Student seeds, tasks, phases, and visitor types are averaged inside the decoder. States and episodes are not replications. Tasks have equal weight. |
| Practical threshold | Mean at or below −1 return point, and the interval entirely below 0 |
| Episode budget | One episode per slot per task, four late steps, continuation length 16 |
| Failure | Incomplete grid, timeout, seed collision, restore mismatch, or a primary interval that includes 0 |

Labels:

- `incomplete` if the decoder count is not 10.
- `action_quality_not_separated` if the primary interval includes 0 or has a positive upper bound.
- `below_practical_threshold` if the interval is entirely negative and the mean is above −1.
- `same_state_action_worse` if the mean is at or below −1 and the interval is entirely below 0.

Task intervals are descriptive. A sign disagreement across tasks does not create an extra replication and does not by itself change the label. `rp2` dominated the measured late sum; that fact is a reason to report tasks, not a reason to weight them unequally.

## 6. Fixed components

The ten decoder checkpoints, the trained broad encoder weights, horizon 16, and 16 candidates stay fixed. No optimizer step is taken. No new physics is registered. Closed evaluation seeds, including the return-phase block at 400000 and 410000, are not reused. The design seeds were checked against the prediction, receding-horizon, and return-phase seed groups.

## 7. Negative-result interpretation

`action_quality_not_separated` and `below_practical_threshold` mean this sample did not show a reliable, practically sized loss from the immediate action at the frozen late states. That outcome does not recommend an architecture change. It leaves the late return gap compatible with earlier trajectory divergence, with later decisions beyond the first action, or with a 16-step window that is too short to see a 184-step sum.

`same_state_action_worse` would say the immediate action is worse at these states under the shared continuation. That would still be one sample on one continuation length. It would not authorize an architecture change, a planner change, or a claim that the mechanism has been identified. The secondary policy continuation cannot upgrade either result into an architecture decision.

## 8. What this adds beyond the receding-horizon diagnostic

The receding-horizon audit scored states visited by separately executed controllers at steps 0, 50, 100, and 150. Its pooled one-shot regret was **0.812 [−0.038, 1.662]** and its matched next-16 continuation was **−0.528 [−1.139, 0.083]**. Both intervals include 0. Step 0 carried the one-shot advantage. Replay matched 1920 of 1920 decisions.

That study did not restore a late state from one trajectory and cross the two policies there. Its continuation was only the shared zero-context replan, so it could not separate an immediate-action effect from a full policy continuation on the same state. Its observation distance compared student-visited and zero-visited clouds across episodes. The return-phase study then showed that the 200-step gap on a new sample sits in steps 16–199, while the trajectories diverge. This design drops step 0, adds step 16, freezes the late simulator state, and registers the shared continuation and the full policy continuation as different estimands.

## Estimated interaction budget

The locked grid implies **960** restored states, **381,312** environment steps, and **34,488,320** model states:

| Component | Environment steps | Model states |
| --- | --- | --- |
| Closed support recollection | 512 | 0 |
| Live harvest, one episode per slot | 48,000 | 12,288,000 |
| Shared open-loop candidates | 245,760 | 655,360 |
| Common continuation | 46,080 | 11,059,200 |
| Policy continuation | 40,960 | 10,485,760 |

At the receding-horizon rate of about 62,000 model states per second, the model-state count would take on the order of **560** seconds. The time cap is **1800** seconds. This is an extrapolation from a finished study, not a measurement of this experiment. The experiment has not been run.

## Proposed tests

The tests lock the design without launching the planner or loading checkpoints:

- The distance of the mean is below the mean of the distances when students sit on opposite sides of zero context, and the two quantities match when the students share an observation.
- The mean of two unit cosine-sine observations need not be a unit observation.
- Design seeds are unique and disjoint from the prediction, receding-horizon, and return-phase seeds.
- The common-continuation seed has no action argument.
- The primary label follows the threshold table, and every label leaves architecture change false.
- The budget arithmetic matches the table above.
- The design module does not call the environment or the planner.

## Protocol lock

<!-- protocol-lock
design_only: true
executed: false
primary_split: fresh
episodes_per_slot: 1
late_steps: 16,50,100,150
continuation_steps: 16
horizon: 16
n_candidates: 16
n_actions: 3
n_student_seeds: 5
target_decoders: 10
eval_env0: 500000
planner_seed_base: 510000
candidate_seed_base: 520000
common_continuation_base: 530000
policy_continuation_base: 540000
practical_threshold: 1
primary_contrast: same_state_common_continuation
secondary_contrast: same_state_policy_continuation
statistical_unit: decoder
env_steps: 381312
model_states: 34488320
states: 960
architecture_change_authorized: false
mechanism_identified: false
-->
