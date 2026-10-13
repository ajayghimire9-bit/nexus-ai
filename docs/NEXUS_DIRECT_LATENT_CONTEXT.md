# Direct latent context diagnostic

Starting SHA `5cc3a6611ffd0c6d4839d813c2521181e248a6e8`. Config: `configs/direct_latent_context_diagnostic.yaml`. The runner loads that file and rejects drifted settings.

Not AGI. Not a control experiment. Not confirmation. Source-physics prediction only. Not learning-to-learn. Not a claim that a searched latent is globally optimal.

## Preserved frozen-trunk result

Encoder and FiLM training on the frozen 3000-update trunk failed (`docs/NEXUS_FROZEN_DYNAMICS_CONTEXT.md`). Fresh-audit real angular velocity was **0.1484** versus zero **0.1159**, wrong **0.1207**, and that run's constant vector **0.1127**. This diagnostic does not train the encoder, trunk, FiLM, or heads, and it does not rewrite that artifact.

## Paired constant-versus-MLP contrast

The frozen-dynamics write-up reported separate seed intervals for the constant vector and the MLP. Overlap of those intervals is not a paired test. On the same audit artifact, the paired difference constant minus MLP, one number per model seed, is:

| Seed | Constant − MLP |
| --- | ---: |
| 0 | −0.00758 |
| 1 | +0.00075 |
| 2 | −0.000015 |

Mean **−0.00228 [−0.0137, +0.0092]**, df = 2. The interval includes 0. That is the paired summary. It does not by itself say the constant pathway and the MLP are interchangeable, and it does not come from comparing the two marginal intervals.

## Why the audit grid is locked

The expected audit seeds, source task ids, labels, and conditions are built from the locked configuration and `pendulum_context_train`, not from the rows a run happened to emit. Dropping a seed from the results does not shrink the planned grid. The incomplete grid fails validation, and a failed validation does not open the audit.

## Hypothesis

**H-latent.** With all network weights fixed, a latent vector optimized from a task's support transitions improves held-out query angular-velocity MAE over zero context, a global task-independent vector, and a vector optimized from wrong-task support.

The vector is optimized only on support data. A lower support loss is not success. A query-conditioned vector and a physics-conditioned vector are not allowed.

## Decoder

Each model seed uses the selected history checkpoint from `artifacts/frozen_dynamics_selection.json`, at 1000 additional updates. The file hash is checked before loading.

Frozen, and hashed before and after every latent step:

- Dynamics trunk
- FiLM weights and bias
- State and termination heads
- History encoder
- Normalization

Only a standalone latent `z` receives Adam updates. Zero, global, task, wrong-task, and encoder contexts all use this decoder. The separately trained constant-model checkpoint has different FiLM weights. It is an external reference, not the constant control for this mechanism test. The 1000-update residual MLP is the other external reference.

## Conditions

- **Zero.** `z = 0`.
- **Global.** One vector per model seed, fit from zero with Adam at learning rate 0.01 for 300 full-batch steps on that seed's pooled source-training transitions. It is shared across tasks and does not see diagnostic support or query rows.
- **Task.** Initialize from the global vector. Optimize a separate `z` on exactly 128 real support transitions.
- **Wrong.** Same initialization, rule, and budget on donor `(i+1) mod 8`. Apply that vector to the current task's queries.
- **Encoder.** Infer `z` from the same 128 real support rows with the frozen encoder. No update.

Development grid for task and wrong vectors, fixed before any scores:

- Learning rates 0.01 and 0.1
- Checkpoints 0, 16, 64, and 256
- Full support batch
- A fresh Adam state for every task and learning rate
- The same Adam state carried across checkpoints inside one candidate

Checkpoint 0 is the global vector. There is no gradient clipping, restart, penalty, or loss change. The prediction loss stays state error plus 0.25 times the termination loss.

## Selection and audit

Selection uses the inspected source diagnostic support and query splits. Their hashes must match the frozen-dynamics selection artifact. One learning-rate and update pair is chosen for all three seeds and eight tasks by minimum mean held-out development angular-velocity MAE. Ties prefer fewer updates, then the lower learning rate. If checkpoint 0 wins, task-specific optimization was not selected.

The manifest, including the global-vector hashes and parent checkpoint hashes, is written before the fresh audit is scored.

Audit episodes are disjoint from training, validation, diagnostic splits, diagnosis prefixes, the optimization audit, and the frozen-dynamics audit:

- Support env base **48000**, seed base **240000**, 128 transitions
- Query env base **52000**, seed base **241000**, **800** transitions, **four** complete episodes per source task

Those four query episodes are shared across methods and model seeds. On the audit, `z` is optimized only from the new support, with the locked rule, for the selected update count. Query rows do not enter the optimizer. The update count is not chosen per task from query error.

## Screen

Tasks are averaged inside each model seed. Intervals across the three seeds are exploratory Student-t intervals with 2 degrees of freedom. Episodes and rollout windows are not training replicates.

The development screen, not a proof, requires all of:

- At least 5% lower mean audit angular-velocity MAE than zero, global, and wrong-task optimized context.
- That gain against all three controls in at least two of three model seeds.
- No more than 5% worsening in overall MAE or horizon-16 error relative to the global vector.
- Complete finite cells.
- Unchanged network parameters and normalization.

Encoder and external MLP and constant-model comparisons are reported either way. A failed bounded search does not prove that no useful latent exists.

## Stopping rule

At most 256 task updates and one hour. No second grid, encoder training, architecture change, control sweep, or confirmation evaluation on this branch.

If support and query both improve and the task vector beats the three same-decoder controls, the decoder can use `z` and the encoder remains the likely limitation. If only support improves, the next question is coverage or overfitting. If real and wrong supports improve together, task identity was not demonstrated. If support loss does not fall, inspect the latent gradient before calling the representation useless. If the global vector matches the task vector, generic recalibration was enough here.

## Results

Execution SHA `d037ffda2fb34238411f39c82d64ff5812b98810`. `source_dirty` was false. The working tree also contained untracked smoke files, so the git snapshot was dirty; those files are outside the source tree the runner checks. Config SHA-256 `a168521a64b9ad228bf1d5aeae51a6ca98c4a59781918031776a1f8ecf76f9cd`. Wall clock **29.3 s**.

Parent history checkpoints, verified before load, are the 1000-update frozen-dynamics history models:

| Seed | SHA-256 |
| --- | --- |
| 0 | `83e90a9b187cdffe5e39d794ce86abf65ef891fde011daf8e55b7eee1f348959` |
| 1 | `cd5400070a69238ce8e35ca036c57448b18664f7ce1e8600ac5a3aab2983ef3e` |
| 2 | `254b097c5dbd3df02c463913c60392928aaed0584c6c29245e060ed25113b6fd` |

Frozen-network digests after locking, unchanged through global fit, task fit, and the audit refit:

| Seed | Digest |
| --- | --- |
| 0 | `71d44b7880f145c99bc99f6b8e24921134e5b90f58dbf8c78f56d942daf80636` |
| 1 | `4bcdc147a80171bf6123b1bc9079f1174614e750a2337a75f9d3ef79942a3104` |
| 2 | `13090d27d02476584c39284cc045f19d9b727c33721e22186be25a055bc064ac` |

### Selected rule

One rule for every seed and source task: **Adam learning rate 0.1, 256 updates**, initialized from the global vector. Development query angular-velocity means:

| Rule | Task angvel |
| --- | ---: |
| lr 0.01, 0 updates | 0.1107 |
| lr 0.01, 16 | 0.0884 |
| lr 0.01, 64 | 0.0708 |
| lr 0.01, 256 | 0.0661 |
| lr 0.10, 0 updates | 0.1107 |
| lr 0.10, 16 | 0.0682 |
| lr 0.10, 64 | 0.0649 |
| lr 0.10, 256 | **0.0630** |

Checkpoint 0 was eligible and was not selected. The same 256-step wrong-support vectors scored **0.180** on the selection queries. Curves: `artifacts/direct_latent_curves.svg` and `artifacts/direct_latent_curves_support.svg`.

On the selection supports, that rule moved latent norms from the global vectors (norms **0.920, 0.892, 1.206**) to a mean norm **2.44** (range **0.69–7.47** across 3 seeds × 8 tasks). Support loss on those fits fell from **0.001025** to **0.000325**. Mean gradient norm **4.6e-5**. Nonfinite steps **0**. The audit file stores support loss and gradient norm for the fresh supports. It does not store the audit latent vectors.

### Fresh source audit

Support env base 48000 / seed base 240000, 128 transitions. Query env base 52000 / seed base 241000, **800** transitions, **four** complete episodes per source task, shared across methods and model seeds. Collection counts: audit support **1024** env steps, audit query **6400** env steps. Angular velocity is the mean across the three model seeds, with an exploratory Student-t interval, df = 2. Episodes are not replicates.

| Condition | Angvel | Overall MAE | Horizon 16 |
| --- | ---: | ---: | ---: |
| Task latent | **0.0628 [0.0569, 0.0688]** | 0.0255 [0.0219, 0.0290] | 0.230 [0.185, 0.274] |
| Zero | 0.1151 [0.103, 0.128] | 0.0421 [0.0374, 0.0469] | 0.396 [0.387, 0.404] |
| Global | 0.1109 [0.0998, 0.122] | 0.0406 [0.0368, 0.0444] | 0.387 [0.370, 0.403] |
| Wrong-support latent | 0.1762 [0.166, 0.186] | 0.0642 [0.0600, 0.0684] | 0.634 [0.593, 0.675] |
| Frozen encoder | 0.1256 [0.0909, 0.160] | 0.0464 [0.0324, 0.0604] | 0.471 [0.264, 0.679] |
| MLP reference | 0.1141 [0.104, 0.124] | 0.0420 [0.0381, 0.0458] | 0.414 [0.370, 0.459] |
| Constant-model checkpoint | 0.1119 [0.100, 0.123] | 0.0410 [0.0371, 0.0448] | 0.387 [0.361, 0.413] |

Per-dimension MAE, task versus global: cos **0.00649** versus **0.00529**, sin **0.00712** versus **0.00565**, angular velocity **0.0628** versus **0.1109**. Paired task-minus-global intervals for cos **+0.00119 [−0.00265, +0.00504]** and sin **+0.00147 [−0.00111, +0.00405]** both include 0. The angular-velocity gap is the part that moves overall error.

Task RMSE **0.0442 [0.0388, 0.0497]**. Open-loop MAE at horizons 3 and 8: task **0.0540** and **0.126**, global **0.103** and **0.229**. Paired task-minus-global horizon intervals exclude 0: h3 **−0.0485 [−0.0552, −0.0418]**, h8 **−0.103 [−0.108, −0.0968]**, h16 **−0.157 [−0.217, −0.0964]**.

Paired audit contrasts are control minus task, so a positive number is a lower task error. All six exclude 0:

| Contrast | Mean [interval] |
| --- | --- |
| Zero − task | **+0.0523 [0.0413, 0.0632]** |
| Global − task | **+0.0481 [0.0344, 0.0617]** |
| Wrong − task | **+0.113 [0.0985, 0.128]** |
| Encoder − task | **+0.0628 [0.0230, 0.103]** |
| MLP − task | **+0.0512 [0.0354, 0.0670]** |
| Constant-model − task | **+0.0490 [0.0346, 0.0634]** |

Per-seed task angular velocity: **0.0611, 0.0619, 0.0656**. Each seed is below its own zero, global, and wrong-support vector. Positive seeds **3/3**.

Support loss on the audit supports fell from **0.001141** to **0.000304**. Mean gradient norm **5.12e-5**. The screen passed: about **45%** below zero, **43%** below the global vector, and **64%** below the wrong-support vector. Overall MAE and horizon-16 error are lower than the global vector, by about **37%** and **41%**. The classification label is `task_specific`.

The MLP reference at **0.1141** sits with zero and the global vector. The support-fit latent is lower on this source audit. That comparison uses a different network. It is an external reference.

### Reading

Support loss fell and the query error fell with it. The task vector beat zero, the global vector, and the wrong-support vector, and the wrong-support vector made query error worse. The same decoder can use a support-fit `z`, and the fit is using which support it saw. The frozen encoder, given the same 128 rows and no updates, remains worse than zero context (**0.1256** versus **0.1151**). Encoder inference is the remaining limitation inside this pathway.

The global vector is close to zero context. The additional drop comes from the task updates. Checkpoint 0 was not the selected rule.

This is a bounded Adam search on source physics the trunk already trained on, with new episodes. It is not a claim that the latent is globally optimal, that control improved, or that the rule survives unseen physics. A passing point screen is still a three-seed exploratory interval. Those intervals exclude 0 on the primary angular-velocity contrasts above. Confirmation physics hash `87b83c41be34aa1a` was not evaluated. No control sweep was run.

### Cost

| Item | Count |
| --- | ---: |
| Source-training env steps | 9600 |
| Selection support / query env steps | 1024 / 3200 |
| Audit support / query env steps | 1024 / 6400 |
| Global Adam steps | 900 |
| Task Adam steps, development plus audit | 36864 |
| Support examples processed | 7598592 |
| Global fit time | 1.58 s |
| Task fit time | 9.34 s |
| Total wall | 29.3 s |
