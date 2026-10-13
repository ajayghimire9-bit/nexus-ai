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

The full diagnostic has not been run in the implementation commit. Smoke output, if present, is a pipeline check and is not this result.
