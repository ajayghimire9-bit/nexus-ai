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

The full diagnostic has not been run in the implementation commit. Smoke output, if present, is a pipeline check and is not this result.
