# Frozen-dynamics context diagnostic

Starting SHA `eecdd7b813601613c176b0005d053dc53604ea61`. Config: `configs/frozen_dynamics_context_diagnostic.yaml`. The runner loads that file and rejects drifted settings.

Not AGI. Not a control experiment. Not confirmation. Source-physics prediction only. Not learning-to-learn.

## Preserved optimization result

Three thousand joint Adam updates improved the shared dynamics and failed the context-usefulness screen (`docs/NEXUS_CONTEXT_OPTIMIZATION_DIAGNOSTIC.md`). On the fresh source audit, real-context angular-velocity MAE was **0.1264** versus zero **0.1256** and wrong **0.1234**. This diagnostic does not add more joint updates and does not rewrite that artifact.

## Why the previous completeness check was not enough

`completeness_report` walks only the tree it is given. A missing seed, task, condition, horizon, or checkpoint never appears as a failure. Strings and booleans are skipped, so a numeric string or `True` in a metric field does not fail. `finite_number` would also accept a numeric string if that value were not skipped first. Historical optimization and diagnosis artifacts were not rewritten. They remain the record of those runs.

This diagnostic uses `schema_completeness` on the raw per-task cells before any seed mean is taken. The planned seed ids, source task ids, checkpoint labels, context conditions, metrics, and rollout horizons must all be present. Duplicate cells, shortened per-dimension lists, numeric strings, booleans, NaN, and infinity fail the check.

## Why the previous audit saw extra checkpoints

The optimization audit loaded the selected context checkpoint, the 300-update reference, and the MLP's own selected update. A context checkpoint was therefore scored when its update count happened to equal the MLP selection. That runner is unchanged, so a re-run still matches the published artifact. This diagnostic keeps a separate context plan and a separate MLP plan. The audit loads only:

- the selected history-adaptation checkpoint
- the unchanged starting context model (zero additional updates)
- the selected constant-context checkpoint
- the already selected 1000-update multitask MLP

Audit scoring reads a saved selection manifest. It requires `selection_recorded`, the four checkpoint identifiers, file hashes that match the saved files, a complete per-task grid, and a certificate that frozen weights did not change. A smoke run does not record selection and cannot open the audit.

## Hypothesis

**H-frozen.** With shared dynamics fixed, training a history encoder and FiLM produces lower held-out source prediction error with real context than with zero context, wrong-task context, and a trainable constant-context control.

Improvement shared by real and wrong context is not evidence of task identification. Improvement matched by constant-context training is generic recalibration, not useful history-based adaptation.

## What stays frozen

Each of the three existing 3000-update context checkpoints. Their SHA-256 values are the ones in `artifacts/context_optimization_selection.json`. A missing file is retrained with the recorded optimization procedure and kept only if that hash matches. A mismatch is deleted. New weights are not substituted.

Frozen, and hashed before and after the additional training:

- Dynamics trunk (48, 48)
- State prediction head
- Termination head
- Source normalization statistics stored in the checkpoint

Trained, for history adaptation: the history encoder (hidden 32, context 8) and the FiLM weights and biases.

Trained, for constant adaptation: one context vector shared by every source task, plus the same FiLM weights. The history encoder stays at the starting values. The vector is initialized as the mean of per-task support encodings from the starting encoder, using only that seed's source-training transitions and a separate initialization seed (`V089C_TRAIN_SEED + 8000 + seed`). That initialization does not draw from the query schedule. Both methods copy the starting FiLM parameters.

The 1000-update residual MLP (64, 64) is the fixed reference. It is not retrained.

No new loss, wider trunk, task classifier, learned task id, physics input, extra joint training, or hyperparameter search.

## Training budget

Three paired seeds. Additional checkpoints: **0, 300, 1000**. One continuous Adam optimizer per method, learning rate 1e-3. Optimizer state is kept between checkpoints. Checkpoint 0 is the starting point, before any additional step.

History adaptation uses fixed 128-transition support, empty context with probability 0.2, episode-disjoint support and query, and query prediction loss only. Constant adaptation uses the shared vector on the same nonempty updates and zero context on the same empty updates. Both methods share task sampling, query minibatches, empty draws, and update counts.

The one-hour cap is 3600 seconds. An incomplete run stays unlabeled as a result.

## Selection and audit

Selection uses the already inspected source diagnostic splits. Their hashes must match the optimization selection artifact. Fresh audit episodes are registered before training and are not scored until the selection file is on disk.

Audit collect seeds, disjoint from training, validation, diagnostic support and query, diagnosis prefixes, and the previous source audit:

- Support env base **36000**, seed base **230000**
- Query env base **40000**, seed base **231000**

History checkpoint: lowest mean selection-set real-context angular-velocity MAE. Constant checkpoint: the same criterion on constant-context angular-velocity MAE, chosen independently. Checkpoint 0 is eligible. Ties prefer fewer updates. If checkpoint 0 is selected, additional training is not claimed to have helped.

Wrong-task context uses donor `(i+1) mod 8` at support length 128. Physics parameters and task ids are not model inputs. Audit query episodes are identical across methods. Support episodes are disjoint from queries.

## Screen

Tasks are averaged inside each training seed. Intervals across the three seeds are exploratory Student-t intervals with 2 degrees of freedom. Windows and episodes are not model-training replicates.

The development screen, not a proof, requires all of:

- At least 5% lower mean angular-velocity MAE than history-adaptation's zero and wrong context.
- At least 5% lower mean angular-velocity MAE than the selected constant context.
- Lower angular-velocity error than all three of those controls in at least two of three seeds.
- No more than 5% worsening in overall MAE or horizon-16 error relative to history-adaptation's zero context.
- No worsening relative to the starting model's real-context angular-velocity MAE.
- Complete finite per-task cells and unchanged frozen parameters.

The MLP comparison is reported whether or not the screen passes. It is not part of the pass rule.

## Stopping rule

At most 1000 additional updates per method and seed. If history adaptation improves but the constant control matches it, the result is generic recalibration. If history adaptation beats its controls and remains worse than the MLP, that limit is reported. If the screen fails, this frozen-trunk branch stops. More updates, a larger trunk, and an auxiliary loss are not the next step.

The mechanism-level question left open, and not run here, is whether a directly optimized latent context can improve predictions when the encoder is removed from the path. That separates an encoder limitation from a conditioning limitation. No control sweep and no confirmation physics are run in this milestone, including if the source screen passes.

## Results

Execution SHA `1fb56ea6dd2ad64bb6a593e0899428b6f33f1f27`. Source tree was clean. Wall clock **10.3 s**. Declared selection and audit are complete. The screen **failed**. Confirmation and control were not run.

Selection artifact: `artifacts/frozen_dynamics_selection.json`. Audit artifact: `artifacts/frozen_dynamics_audit.json`. Plot: `artifacts/frozen_dynamics_prediction.svg`. Checkpoint binaries are local `.pt` files under `artifacts/frozen_dynamics_checkpoints/`. Their SHA-256 hashes are in the selection artifact. They are not in git.

The starting history model reproduces the published 3000-update selection score. Real-context angular-velocity MAE at zero additional updates is **0.13631436003682515**, the same value as the optimization selection at 3000 updates. Zero and wrong at that checkpoint are **0.1259** and **0.1317**. Frozen trunk, head, and normalization hashes were unchanged after 1000 additional updates on every seed. History training changed the encoder (L2 from the frozen start **1.601, 1.659, 2.320**) and FiLM (**0.504, 0.808, 1.036**). Constant training left the encoder fixed and moved the shared vector by **0.092, 0.130, 0.078**.

### Selection set

Means across three seeds. Angular velocity is observation dimension 2. Lower is better. This split was already inspected.

| Additional updates | Real | Zero | Wrong | Constant |
| --- | ---: | ---: | ---: | ---: |
| 0 | 0.1363 | 0.1259 | 0.1317 | 0.1261 |
| 300 | 0.1254 | 0.1200 | 0.1198 | 0.1155 |
| 1000 | 0.1180 | 0.1162 | 0.1179 | 0.1114 |

**Selected history checkpoint: 1000 updates. Selected constant checkpoint: 1000 updates.** Both rules chose the lowest angular-velocity MAE. There was no tie. Checkpoint 0 was eligible and was not chosen. That choice was written before the fresh audit. It does not, by itself, show that the extra updates helped on new episodes.

Trainable parameters: history encoder plus FiLM **1448**; constant vector plus FiLM **872**; frozen trunk and heads **2884**. The full context model remains **4332** parameters. The reference MLP remains the untouched **4868**-parameter 1000-update checkpoint. History adaptation encoded **305,664** support rows. Constant adaptation encoded **none**. Each method saw **192,000** query examples. History training took **1.16 s** and constant training **0.83 s**.

### Source audit

Fresh episodes, scored once, after the selection file was saved. The loaded files were only the 1000-update history checkpoint, the zero-update starting checkpoint, the 1000-update constant checkpoint, and the 1000-update MLP.

| Quantity | History real | History zero | History wrong | Constant | Starting real | MLP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Angular-velocity MAE | 0.1484 | 0.1159 | 0.1207 | 0.1127 | 0.1482 | 0.1149 |
| Overall MAE | 0.0543 | 0.0426 | 0.0447 | 0.0415 | 0.0553 | 0.0424 |
| RMSE | 0.1031 | 0.0813 | 0.0845 | 0.0794 | 0.1028 | 0.0811 |
| Horizon-16 MAE | 0.564 | 0.380 | 0.433 | 0.368 | 0.595 | 0.386 |

Per-dimension MAE for history real is **0.0080 / 0.0065 / 0.1484**. For history zero it is **0.0061 / 0.0060 / 0.1159**. The gap is angular velocity.

Exploratory Student-t intervals across the three seeds, in error units of control minus real. Negative means real context is worse:

- Zero minus real: **−0.0325 [−0.073, +0.007]**, includes 0.
- Wrong minus real: **−0.0277 [−0.046, −0.010]**, excludes 0.
- Constant minus real: **−0.0357 [−0.068, −0.003]**, excludes 0.
- Starting real minus selected real: **−0.0002 [−0.062, +0.061]**, includes 0.

No seed had real context better than zero, wrong, and the constant control together. Overall MAE is about **27%** higher than history zero, and horizon-16 error is about **48%** higher. Both exceed the 5% harm limit. Selected real context is also slightly worse than the starting model's real context. The 5% screen failed (`beats_zero_and_wrong` false, `beats_constant` false, `positive_seeds` 0, `harm_ok` false, `start_ok` false). Frozen parameters and the per-task grid did pass.

The MLP audit angular-velocity MAE is **0.1149 [0.105, 0.125]**. History real context remains well behind it. The constant vector's **0.1127 [0.106, 0.119]** sits next to the MLP. Those two intervals overlap, so this run does not show that the constant vector beats the MLP. It does show that a history-free vector is not the failure mode that real context is.

### Decision

H-frozen is not supported. The failure is absence of a history benefit, not a history benefit that the constant control matched. Real context stayed worse than zero and wrong context, and worse than the constant control, whose interval against real context excludes 0. Encoder and FiLM weights moved. The fresh-audit angular-velocity error did not improve on the starting real context. The selection-set decline from **0.136** to **0.118** did not survive the new episodes.

This frozen-trunk encoder branch stops. It does not continue past 1000 updates, widen the trunk, or add an auxiliary loss. The constant-vector result is a reason to ask a different question: whether a latent context optimized directly, without a history encoder, can improve prediction. That experiment was not run.

### Resources

Source training **9,600** interactions, recollected to match the recorded training hashes. Selection support **1,024**. Selection query **3,200**. Audit support **1,024**. Audit query **3,200**. The selection file's resource snapshot was written before the audit collection, so its audit counts are zero. The audit file is the one with both audit counts. No control-evaluation interactions and no imagined MPC states.
