# NEXUS — Full-episode return decomposition

## Measured result

The locked episodes finished on all ten decoders in **774.2 s**. Implementation SHA `cf1e81b07011c6e4a45039dba38a7b9dafb2d734`. Artifact `artifacts/return_phase_decomposition.json` (sha256 `aaa8fc037f8bc481799d65b08308e7e7bdf0f2a8cf27686c5803db22da2e2cc8`). Early plus late matched the total on every paired episode. The largest absolute gap was **2.8e-14**. The encoder, decoder, horizon, and candidate count were unchanged. The closed episode seeds were not reused.

On the new fresh-physics episodes the pooled student-minus-zero return is **−30.671 [−41.540, −19.801]**. Steps 0–15 contribute **−1.230 [−2.583, 0.123]**, and that interval includes 0. Steps 16–199 contribute **−29.441 [−40.706, −18.175]**. The locked label is `primarily_late`. The late share of each decoder's total has mean **0.928 [0.836, 1.020]**. The early share is **0.072 [−0.020, 0.164]** and includes 0. A share interval can extend past 1 when a decoder's early difference has the opposite sign of its total. The lower bound of 0.836 is the stable statement: the late window carries most of the paired difference.

Task totals are not the same size. `rp2` late is **−98.647 [−150.066, −47.227]** and its early interval includes 0. `rp0` late is **−1.582 [−3.118, −0.045]**, with an early interval that includes 0. `rp1` total is **2.249 [−8.745, 13.243]** and includes 0; its early difference is **−5.053 [−9.706, −0.399]**. `rp3` total is **−24.262 [−53.087, 4.564]** and includes 0. Percentages are reported only for the pooled total and for `rp2`, because those are the totals whose intervals exclude 0 and whose decoder denominators stay at least 1 in absolute value.

Mean observation distance along the paired trajectories is **1.697 [1.520, 1.874]**. It is **0.583 [0.366, 0.799]** at step 16 and **2.865 [2.295, 3.434]** at step 199. Initial distance is below **1e-7**. The controllers leave the shared state, so the late sum is not a same-state effect. That distance is a limitation.

This sample is not the closed **−19.4 [−35.4, −3.3]** measurement. Both samples favor zero context. The episode seeds differ, and so do the magnitudes. Environment steps were **192,512**, including **512** closed-support recollections, and model states were **49,152,000**. No architecture change follows. This is not a general control improvement, not learning-to-learn, and not AGI.

The ten-decoder fresh-physics controller loses return to zero context by **−19.4 [−35.4, −3.3]** on the closed episode seeds. Those seeds stay closed. This study asks where a new paired sample of that same controller puts the student-minus-zero difference: in steps 0–15, in steps 16–199, or in both. It does not change the encoder, the decoder, the horizon, or the candidate count, and it does not fit a model.

## Protocol lock

<!-- protocol-lock
episodes_per_task: 4
max_steps: 200
early_steps: 16
horizon: 16
n_candidates: 16
n_actions: 3
n_student_seeds: 5
target_decoders: 10
student_kind: broad
support_budget: 128
primary_split: fresh
eval_env0: 400000
planner_seed_base: 410000
task_stride: 100
share_min_abs: 1
identity_atol: 1e-08
time_limit_s: 1800
fresh_split_hash: 053e8efca60fb4ac
fresh_support_hashes: aa78f66887b76dcf,97b370d876c2a569,bd47719e5850bbf7,9b97c8539673828c
control_artifact_sha256: 35c75320e1c243eaa1914cf6e726e9849d246910ebfc79f6ac0f390c86daf0e9
manifest_sha256: 265cd1822ec73bab8eac6fd792438c3c9fe7834ae5af307b8c33104bf919d06b
prediction_artifact_sha256: f1f36506d3c64086898b6f462f9915a28037784dee52f47bce5c19b91bfe390a
evidence_manifest_sha256: 289b5bc49f3158ed1faeaa1558d1336e3150f801ec408bbf8a9be148285523af
starting_sha: cf2d468c878175c6172b25b6975c5cd90f5968d4
closed_returns_remeasured: false
control_claim: false
is_agi: false
is_learning_to_learn: false
-->

Fresh physics hash `053e8efca60fb4ac` is the only evaluation split. Each of the ten decoders runs four new episodes on each of the four tasks. The five broad student seeds share those episodes and are averaged inside the decoder. Zero context is one controller on the same episodes. Student and zero use the same environment reset and the same planner seed, so the candidate stream starts from the same state. Support rows are the closed fresh supports, recollected only to install the saved context and checked against the four stored hashes.

Δearly is the summed student-minus-zero reward on steps 0–15. Δlate is the same difference on steps 16–199. Δtotal is the sum of the 200 step differences. Early plus late must equal total within absolute tolerance `1e-08`. The published pendulum cost must match the environment reward within `1e-05` on every step.

The primary intervals are Student-t 95% intervals across the ten decoders. A percentage of the total is reported only when that total interval excludes 0 and every decoder's absolute total is at least 1. Otherwise the result reports the absolute phase contributions and does not quote a percentage. The descriptive label is `primarily_early` or `primarily_late` only when the percentage is allowed, one phase interval excludes 0, the other includes 0, and the reported phase carries more than half of the total. `both_phases` requires both intervals to exclude 0 and to have the same sign as the total. Anything else that still finishes is `unseparated`. An unfinished grid is `incomplete` and has no phase claim.

Observation distance along the paired trajectories is a limitation. The initial observations must match. Later distance means the controllers have left the shared state. It is not a cause.

The closed **−19.4** gap is an input from the earlier seeds. This sample does not remeasure it and does not select a hyperparameter. No architecture change follows from the label. This is not a general control improvement, not learning-to-learn, and not AGI.
