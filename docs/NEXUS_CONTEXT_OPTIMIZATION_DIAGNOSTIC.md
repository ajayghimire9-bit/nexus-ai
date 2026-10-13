# Bounded context optimization diagnostic

Starting SHA `462b388e24933842297ea9719ed1c9dc5b3902bd`. Config: `configs/context_optimization_diagnostic.yaml`. The runner loads that file and rejects drifted settings.

Not AGI. Not a control experiment. Not confirmation. Source-physics prediction only.

## Preserved diagnosis

At 300 updates, fixed-length real context did not beat zero or wrong-task context on held-out source MAE (0.0703 vs 0.0700 and 0.0702 at budget 128). Development angular-velocity error got worse. The 0–128 control interval for variable-length training included 0. Confirmation physics were not evaluated. Those artifacts stay as they are.

The old flag name `variable_length_helps_short_histories` remains in that artifact. New code calls the same pattern `variable_length_short_history_point_estimate_positive`, which is a point estimate, not an interval that excludes 0.

## Hypothesis

**H-optimization.** Increasing source-training updates, with architecture, data, learning rate, loss, and context policy fixed, enables real context to improve held-out source prediction over both zero and wrong-task context.

A lower error shared by zero context is better dynamics fitting, not task-specific context use. This run cannot establish faster target adaptation, control improvement, or learning-to-learn.

## What stays fixed

Eight source physics. The existing source datasets and source-only normalization. Context dimension 8, encoder width 32, trunk (48, 48), FiLM, the current prediction loss, Adam at 1e-3, query batch 64. Support policy: 20% empty, otherwise 128 transitions. Episode-disjoint support and query. Three paired seeds. The first 300 scheduled updates use the same seed as the diagnosis, so they reproduce that fixed-length schedule.

No wider trunk, variable-length training, auxiliary loss, task classification, Reptile, ensemble, GRU, or architecture search.

## Checkpoints

Train each context model continuously to 3000 updates. Snapshot 300, 1000, and 3000 without restarting Adam. The same schedule is precomputed, so scoring a snapshot cannot change later samples.

The multitask residual MLP (64, 64) is trained by the same update counts, with its own Adam state preserved. Reported MLP checkpoints are those update counts, not an unlabeled best-validation checkpoint. Its own angular-velocity selection is labeled separately from the checkpoint that matches the selected context update.

## Data

The diagnosis support and query splits are the selection set. Their hashes must match `artifacts/context_adaptation_diagnosis.json`. They have already been inspected.

Source-audit episodes use frozen seeds: support env base 20000 and seed base 210000; query env base 24000 and seed base 211000. They are disjoint from training, source validation, and the selection set. Audit predictions are not computed until the selection record is written.

Wrong-task context uses donor `(i+1) mod 8` at the same support length. No physics parameters or task ids enter the model. Primary support budget is 128.

## Screen

Positive context benefit is zero-context error minus real-context error, and wrong-context error minus real-context error. Tasks are averaged inside each seed. Intervals across three seeds are exploratory (2 degrees of freedom).

The development screen, not a proof, requires all of:

- At least 5% lower mean angular-velocity MAE than both zero and wrong context on the audit.
- That benefit positive in at least two of three seeds.
- No more than 5% worsening in overall MAE or horizon-16 error versus zero context.

Rollouts start at offsets 0, 32, 64, 96, 128, and 160 when the horizon still ends inside the episode. Windows are averaged inside an episode before tasks are averaged. Overlapping windows are not replicates.

If 300 updates is selected, longer training is not claimed to have helped. If the screen fails, training stops at 3000. It does not continue to 10000 and does not add another mechanism.

## Results

Not run yet.
