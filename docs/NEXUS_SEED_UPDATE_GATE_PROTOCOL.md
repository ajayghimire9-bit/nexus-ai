# Scalar update/retain gate — locked source development comparison

Starting revision: **96825e5d49629bc26c70e8a1be21fffa7c4ca714**, verified against
GitHub after fetching. Branch: `codex/seed-update-retain-gate`. Main, unrelated
root-worktree files, historical weights, closed evaluations and prior results
remain unchanged. This is reused-source development, not fresh validation.

## Question and competing explanations

H-gate: task-conditioned update strength can improve the 1/2/4/8-example
prediction curve over a source-trained constant strength, unit-strength
cumulative fitting, scaled replay and bounded fixed protection. Alternative:
generic damping is sufficient; alternatively neither strength rule beats strong
simple controls because the proposed direction or representation is inadequate.
The previous cumulative test failed its practical screen; its first-example harm
is motivation, not a demonstrated cause. No retuning its closed result.

## Fixed mechanism and reuse

Reuse cumulative_learning.posterior/prepare_fold/validation, PlasticityController,
nonlinear_learning.fit_source, update_diagnosis.trajectory, the EXPERIMENTAL
host/worker/shared runner and Learning Lab replay. No parallel learner, meter,
memory or planner is introduced. No world model is loaded or inferred.

The fixed proposal is the existing ridge .1 cumulative posterior, centered at
the old-anchor initial fit, with unit diagonal, using the four permitted anchors
and observed teaching prefix only. The only new learnable decision is:

```
g = clamp(0.5 + 0.25 * (w @ observed_context + b), 0, 1)
theta_next = theta_previous + g * (theta_proposal - theta_previous)
```

Use the existing four context inputs: current-label absolute residual clipped at
4 and divided by4, anchor count/16, minimum mean squared feature distance to an
anchor clipped at1, and fixed task-channel0. No task IDs or query outcomes enter
this context. The clamp allows exact retention/full update; saturation can block
gradients and must be disclosed if observed. Learned capacity is five scalars;
the constant control fixes four weights at zero and trains only the bias.
Both start with the same bias initialization and query-task schedule. Do not
change the frozen 33-dimensional feature extractor or grow the architecture.

## Data and training

The executable source of truth is configs/seed_update_gate.json. Verify the
saved source plan SHA256
788d2df3ae49cdd71a91068fc0a4fd04b7a65790a475c16635bccd6135c4866b and its
parent source artifact/array hashes. Pass only twelve original source tasks to
the worker, stripping legacy globally fitted preprocessing/rule weights.
Do not pass prior development, audit or control data.

Task IDs are 95000000 through95110000 at10000 spacing. Four folds exclude
indices modulo4, three tasks per fold, fitting nine. Scale and the bounded
reference's tau use those nine training tasks only, exactly as in the preceding
study. Excluded tasks never determine normalization, gates or tau. They remain
previously inspected source data and cannot be called untouched confirmation.

Three independent new-rule seeds7201/7202/7203; fit seed is seed+100*fold.
Exactly64 Adam updates per fold/arm, lr .01, using the existing shuffled-cycle
source-task schedule. Outer objective is mean query MSE at1/2/4/8 labels plus
.5 times mean retention-MSE change. Only training-task query outcomes may train
the outer gate. Inner updates receive observed support/anchors only. No HPO,
early stopping, best-checkpoint selection, retries or second study in this run.

Six methods, recomputed on identical excluded-task prefixes:
learned gate, trained constant gate, unit-strength cumulative fit, existing
scaled replay, existing bounded fixed protection, and no new-task adaptation.
Record all prefixes0–8, not merely the primary four. Query and retention rows
are identical across methods. Learning and inference compute differ: report it.

## Screen and statistics

Primary: mean query MSE over budgets1/2/4/8, averaging all twelve excluded tasks
inside each independent rule-training seed. Require at least5% lower mean error
versus EACH constant/unit/replay/bounded reference and each paired seed-level
95% interval strictly above zero for reference-minus-learned. Retention at8 must
be no worse than unit cumulative+.01 MSE. Intersection of these requirements is
one conservative advancement screen; every contrast and task failure is shown.
Intervals are exploratory t intervals with n3, df2, t4.302652730. They condition
on one frozen feature extractor and this fixed reused source bank. Overlapping
folds, tasks, prefixes and repeated baseline scores are not extra independent
replicates. Deterministic-baseline contrasts may have zero-width intervals;
this is not zero uncertainty about transfer.

Report per-task/fold/seed curves, first-label changes, final retention, gates by
prefix, endpoint saturation, gradient norms and parameter changes. Low training
loss, nonzero gradients, or a small positive contrast is not success. Passing
this source screen alone permits only a separate fresh-validation proposal,
never runtime promotion, action-quality or general learning-to-learn claims.

## Completeness, resources and provenance

Expected:24 new checkpoints,1536 optimizer updates,1944 evaluation snapshots.
All planned cells, source-only split arithmetic, checkpoints, weights, schedules
and finite metrics must validate. Independently recompute query/retention MSE,
gate contexts, gate values, update interpolation and fixed-proposal normal
equations from saved arrays without neural inference. Save partial failures;
missing cells cannot be reduced away. Freeze gate parameters during evaluation.

One existing-host dispatch under **60 seconds wall/CPU**,2048MiB sampled RSS,
1536 updates, **zero new real/imagined/world-model interactions**. CPU only.
The host enforces process CPU/wall caps; macOS sampled RSS is not kernel-hard.
Record locked file hashes and clean execution SHA before running. Preserve the
journal, raw traces, all checkpoint weights/hashes and outside-Git checkpoint
files. No historical binary is replaced. Gate/train inference work is counted
separately from stored-vector verification and read-only GUI replay.

Carried ledger:1927.6321034559958seconds used /1672.3678965440042remaining.
Exactly12288 training support presentations,165888 query and165888 retention
training row scores;55296 cumulative training-prefix rows plus49152 anchors.
Evaluation:52488 query and52488 retention row scores,1728 inner updates,
12864 gate forwards and13152 cumulative solves including training. The24 files
store120 scalars (five each;72 distinct trainable scalars across all fits).
These are expected logical counts, verified against actual operation counters.

Commit tested implementation/protocol before the run, results separately, and
push without merging. Preserve a negative/inconclusive result and recommend
exactly one next study from the evidence. No second scientific execution here.
