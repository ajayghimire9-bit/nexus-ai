# Task-blocked cumulative learning-rule comparison

Base: 12a2b2ca306737efa8412f3df288d32dc9f2d128.
Branch: codex/seed-cumulative-learning. Reused-source development experiment;
not untouched validation, control or confirmation. No runtime promotion.

## Hypotheses

H-evidence: explicitly fitting all observed teaching labels improves adaptation
over bounded per-example correction and scaled replay. H-learned: a small
context-conditioned precision rule trained across tasks improves that cumulative
procedure on tasks excluded from its fit, beyond source-trained static precision
and fixed cumulative fitting. Ordinary cumulative fitting is not learning-to-learn.

Earlier teaching labels already affect the old theta implicitly; the intervention
explicitly includes their current residuals in the fitting objective. Test both
questions, not just whether a learner's training loss decreases.

## Data and folds

Use only the same 12 saved source tasks' arrays from the hash-verified original
nonlinear study. The host discards old controller weights and global scale.
No old development, audit or control payload enters the worker. The original
source file and source-plan hashes remain fixed. Its pretrained feature extractor
and readout were previously trained; all data have been inspected. Excluded
tasks are held out from THIS update-rule fit, not fresh independent evidence.

Four fixed folds: task index modulo four determines the excluded group, three
tasks each. Train on the other nine. Fit feature scale only on those nine tasks'
support and old-anchor features; apply it unchanged to the excluded tasks.
Fit the bounded control's tau on the nine training support residuals only, using
the preceding max(1e-6,.25*RMS) rule. Neither preprocessing sees excluded queries,
support or retention data. Query labels cannot enter inner updates.

## Update and training

Keep the 33-dimensional feature interface and original old-anchor initialization
theta0 from learning_benchmark.initial. At prefix k, concatenate four old anchors
and k observed support rows into X,y. With positive diagonal D and ridge .1,

theta_k = theta0 + D X' (.1 I + X D X')^-1 (y - X theta0).

This minimizes sum squared residuals plus .1 times squared change from theta0
in the D^-1 metric. No query rows are in X,y. D is positive plasticity;
regularization precision is proportional to D^-1. The small controller uses the
existing four inputs via plasticity.context(previous theta,current example,old
anchors), including the existing detached context convention. No new features,
world-model training or architecture enlargement.

Compare six methods at 1,2,4,8 labels and save every prefix 0–8:

- Learned cumulative: new PlasticityController(33), 165 trainable parameters.
- Static cumulative: same initialization, fixed zero contextual weights; train
  33 biases only. This strong source-informed baseline learns global precision.
- Fixed cumulative: D=1, no outer training.
- Existing scaled replay, unchanged.
- Existing bounded fixed per-example update, fold-training-only tau.
- None: same theta0, no new-task correction.

For each fold and outer seed 7101/7102/7103, initialize fresh learned/static rules
with seed outer_seed+100*fold. Use the existing fit_source optimizer loop with
the cumulative curve callback: 64 Adam updates, lr .01, mean source query MSE
at 1,2,4,8 plus .5 times retention-MSE change. Same source schedule and initial
biases across learned/static; no excluded-task checkpoint selection. Final
update only. No HPO. There are 24 new small rule checkpoints; historical models
remain frozen and are never replaced.

## Metrics, units and screen

Primary metric: mean excluded-task query MSE over 1,2,4,8. Aggregate all twelve
tasks/four folds within each independent update-rule training seed FIRST. Report
paired 95% t intervals across the THREE meta-training seeds (df2), conditional
on this fixed source bank and ONE frozen feature extractor. These seeds are
not independent pretrained world models and do not estimate task-distribution
uncertainty. Overlapping cross-validation folds are not independent replicates.
Also report each task, fold and budget, retention, worst-prefix error, gradients,
parameter changes and compute. Do not count query rows as independent samples.

Source screen passes only if learned cumulative achieves >=5% lower mean curve
MSE against EACH of static cumulative, fixed cumulative, scaled replay and
bounded fixed, with each paired seed interval lower bound >0, plus final mean
retention MSE <= fixed cumulative+.01. Intersection rule; component intervals
are exploratory and unadjusted. Report no-adaptation comparison too.

Report the generic fixed-cumulative versus replay contrast separately. A generic
benefit cannot substitute for the learned-specific screen. A pass licenses only
proposing fresh validation. A failure is retained without extending epochs or
retuning on the excluded tasks. No actual action/control benefit is tested here.

## Reuse, limits and completeness

Reuse LessonTask, initial/scaled/update, PlasticityController/context, fit_source,
the prior trajectory/grid/arithmetic helpers, bounded limiter, and EXPERIMENTAL
host/worker/runner. Do not create another optimizer, meter or memory framework.
Commit protocol, executable config and tests before execution; then run once.

Standing grant: local CPU, 60-second wall/CPU cap, 2048 MiB sampled-RSS limit
(macOS sampling is not a kernel-hard limit), 0 new real/imagined transitions,
0 world-model forwards. 1536 outer optimizer updates total: 768 per learned arm,
including static. Source query and retention examples each 165888; source
teaching examples presented 12288. Cumulative training also processes 55296
prefix-support row appearances and 49152 old-anchor row appearances. New
controls/rules are matched in teaching
data; solve and replay compute differ and must be reported.

Expected 4 folds × 3 seeds × 2 fitted arms, 64 training rows each, and
3 seeds × 12 excluded tasks × 6 methods × 9 prefixes = 1944 evaluation snapshots.
Record exact fold membership, scales/tau, source schedule hashes, all weights
and checkpoint hashes, runtime/dependencies/resources. Validate every planned
cell and required finite metric before declaring complete. Persist incomplete
or invalid attempts honestly. No scientific retry or shrinking the grid.

Carried ledger:1922.6321034559958 seconds used /1677.3678965440042 remaining.
Keep historical artifacts/closed splits unchanged. Commit results separately,
push without merging main, and recommend exactly one evidence-based next study.
