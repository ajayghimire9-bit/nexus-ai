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

Execution SHA `6fbf78d865e328ca137a8be8fdd55f6d6e781018`. Source tree was clean. Wall clock **17.4 s**. Declared selection and audit are complete. The screen **failed**. Confirmation and control were not run.

Selection artifact: `artifacts/context_optimization_selection.json`. Audit artifact: `artifacts/context_optimization_audit.json`. Plot: `artifacts/context_optimization_prediction.svg`. Checkpoints are local `.pt` files in `artifacts/context_optimization_checkpoints/` (27 files). Their SHA-256 hashes are in the selection artifact. They are not in git.

The first 300 updates reproduce the previous fixed-length run. Encoder L2 change from initialization was **1.4986, 1.5403, 1.5662** on seeds 0, 1, and 2, and support counts were **30720, 31104, 31360**. Those match the diagnosis. Selection-set MAE at 300 updates was real **0.0703**, zero **0.0700**, wrong **0.0702**.

### Selection set

Means across three seeds. Angular velocity is observation dimension 2. Lower is better.

| Updates | Real angvel | Zero angvel | Wrong angvel | MLP angvel | Real MAE | Zero MAE | MLP MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 300 | 0.1500 | 0.1384 | 0.1499 | 0.1221 | 0.0703 | 0.0700 | 0.0484 |
| 1000 | 0.1383 | 0.1273 | 0.1376 | 0.1133 | 0.0528 | 0.0520 | 0.0417 |
| 3000 | 0.1363 | 0.1259 | 0.1317 | 0.1234 | 0.0508 | 0.0468 | 0.0444 |

Horizon-16 selection error moved with the one-step trend. At 3000 updates it was real **0.592**, zero **0.505**, wrong **0.544**, MLP **0.535**. Real context stayed worse than zero context at every checkpoint on angular velocity.

Training loss fell. The 1000–3000 segment mean state loss was about **0.001** and the termination loss about **0.0002**, down from about **0.013** and **0.09** in the first 300 updates. Encoder gradient norms fell from about **0.013–0.016** to about **0.002**. That is better dynamics fitting, not evidence that real context is being used.

**Selected context checkpoint: 3000 updates.** Rule: lowest mean selection-set real-context angular-velocity MAE; ties would have preferred fewer updates. There was no tie. This choice was written before the audit.

**MLP matched to that choice: 3000 updates.** **MLP's own angular-velocity selection: 1000 updates** (0.1133 vs 0.1221 at 300 and 0.1234 at 3000). These are different comparisons.

Each context seed processed 192,000 query examples and about 305,000–308,000 support examples. The MLP processed 192,000 examples per seed. Parameter counts remain 4332 and 4868. Context training took **4.45 s** and MLP training **3.08 s**. Support encoding is extra compute.

### Source audit

Fresh episodes, scored once. Real context at 3000 updates:

| Quantity | Real | Zero | Wrong |
| --- | ---: | ---: | ---: |
| Angular-velocity MAE | 0.1264 | 0.1256 | 0.1234 |
| Overall MAE | 0.0479 | 0.0469 | — |
| Horizon-16 MAE | 0.669 | 0.652 | — |

Zero minus real angular velocity: **−0.0008 [−0.017, +0.016]**. Wrong minus real: **−0.0030 [−0.022, +0.016]**. Both means say real context is slightly worse. The intervals include 0. One of three seeds had real context better than both controls. The 5% screen failed (`angvel_ok` false, `positive_seeds` 1, `harm_ok` true).

The 300-update audit reference had real angular velocity **0.1489** and zero **0.1373**. By 3000 updates, zero-context angular velocity fell by about **0.012** and real-context angular velocity fell by about **0.022**. The shared dynamics improved. Real context remained worse than zero and wrong context, as it was at 300 updates.

The MLP at its own selected checkpoint (1000) had audit angular velocity **0.114**. The MLP at the context-matched 3000 updates had **0.123**. The matched-update MLP is still ahead of the context model.

### Decision

Additional training improved the dynamics model. It did not make real task context useful. H-optimization is not supported. The screen failed, so this branch does not continue to 10,000 updates and does not add another mechanism.

### Resources

Source training **9,600** interactions. Source validation **768**. Selection support **1,024**. Selection query **3,200**. Audit support **1,024**. Audit query **3,200**. No control-evaluation interactions and no imagined MPC states.

### Next experiment

Do not buy more updates of this joint objective. Freeze the 3000-update dynamics trunk and train only the encoder and FiLM, scored by held-out source angular-velocity error against zero and wrong context, using the same 5% screen. No control sweep and no confirmation unless that screen passes on a later pre-registered run.
