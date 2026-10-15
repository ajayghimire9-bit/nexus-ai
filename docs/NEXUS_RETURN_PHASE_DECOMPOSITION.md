# NEXUS — Full-episode return decomposition

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
