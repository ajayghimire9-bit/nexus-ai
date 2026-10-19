# E3.11 — Fresh post-probe selection did not improve returns

Branch: `codex/e3-11-fresh-post-probe`. Base:
`3eacec07feec90c3c7d89cd39a1ed3f426ac3bbf`. Protocol, allocation, tested
implementation and seed preflight committed before collection:
**`048d06cb3d779ccba0668f4d327aca4701673480`**.
One complete run; no retry, retuning or neural training. Protocol remains
`NEXUS_E3_11_POST_PROBE_PROTOCOL.md`.

## Primary outcome

Registered label: **`post_probe_context_selection_not_established`**.
The contextual selector chose exactly the same whole controller as its
model-mean baseline in **16/16 evaluation contexts**. Both family paired
return differences are **0.000**, per-model differences `[0,0]`, and the
mechanical df1 paired intervals are `[0,0]`. Both >=1-point family screens
fail. This is a completed negative selection result, not an incomplete run.

The zero-width intervals reflect identical selected/cached paths on this
finite sample. They do **not** establish population equivalence or rule out
effects on other states. Only two independently pretrained models per family
were used, not sixteen independent model replications.

## Actual held-out 192-step returns

Families have different reward definitions; do not pool their return scales.
Each family mean equally averages its two frozen models after averaging four
held-out episodes/model.

- **Pendulum:** contextual−206.395836; model mean−206.395836;
  fixed successor−134.125932; fixed rank blend−255.074802.
  Contextual-minus-successor−72.269905, exploratory95% interval
  `[−990.546108,+846.006299]`; versus rank blend+48.678965,
  `[−569.845935,+667.203866]`.
- **Acrobot:** contextual−283.152652; model mean−283.152652;
  fixed successor−288.205995; fixed rank blend−283.152652.
  Contextual-minus-successor+5.053343, exploratory95% interval
  `[−27.919583,+38.026270]`; versus rank blend0, identical paths.

Per-model contextual/model-mean returns:

- Pendulum bundle0−280.087890; successor−135.548081, rank−280.087890.
- Pendulum bundle1−132.703783; successor−132.703783, rank−230.061714.
- Acrobot bundle0−285.048529; successor−287.506846, rank−285.048529.
- Acrobot bundle1−281.256775; successor−288.905145, rank−281.256775.

Intervals are unadjusted exploratory t intervals across two models, df1,
not across episodes. The fixed-successor advantage over the contextual method
on Pendulum is descriptive and highly uncertain across model replications.
It is not selected after the fact as a newly validated controller.

## Where the evidence failed to distinguish the candidates

In training the two proposals chose the same first action in8/12 contexts;
in evaluation they agreed in **15/16**. In all15 evaluation cases, the saved
common-tail candidate forecasts are exactly identical across controllers.
This follows the construction: same model, observation, first action and
shared fifteen-action tails. Those forecasts represent first-action choices
under a common continuation, not the two controllers' different future
replanning rules over192 steps. The reward/survival forecast gaps have zero
within-model evaluation variation in three of four models. Probe residuals
still vary; this does not prove that all available information is useless.

Advantage MAE (contextual / model-mean baseline) by model:

- Pendulum0:260.990045 /265.306384; sign accuracy0.50.
- Pendulum1:44.003012 /51.685131; sign accuracy1.00.
- Acrobot0:35.372443 /39.015149; sign accuracy0.75.
- Acrobot1:38.995889 /33.355614; sign accuracy0.75.

Smaller magnitude error in three models did not change any selected strategy
or improve actual return. Pendulum0's fresh training rank-minus-successor
mean was+120.766575, while its evaluation mean was−144.539809. The learned
correction did not reverse that prior. Small training size, first-action
collapse and continuation mismatch are plausible limitations; this experiment
does not isolate one as the sole cause or prove ridge/encoder inadequacy.

In-set regret is reported in raw summaries. Its reduction relative to model
mean is mathematically the same as the return gain, not independent evidence.
No control generalization, learning-to-learn or autonomous improvement claim.

## Execution, resources and integrity

All28 contexts and56 physical controller continuations completed. Training:
12 pairs/4704 real steps; evaluation:16 pairs/6272 real steps. Total:
**10976 real interactions**, including224 probes and10752 continuation steps.
No diagnostic or validation environment collection beyond that grid.
The64 logical method returns reuse32 executed evaluation continuations;
cached selectors add no executed environment interactions.

**16129288 imagined transitions,638596 model calls and638596 observed top-level
network forwards**, all completed; unknown work0. Includes proposal generation,
common-scoring evidence and support prediction, not just controller search.
Two fixed four-coefficient ridge fits,0 optimizer/world-model updates.
Contextual inference has extra one-time compute; mean/fixed controllers would
be cheaper standalone. Do not claim equal FLOPs or a speedup.

Wall **91.809702667s** under cap300s; worker process CPU91.523259s, local
one-thread execution. Peak memory was not separately instrumented. Offline
no-inference verification took **5.068857250s**. Carried session ledger after
run plus verification: **884.5235102100257 used /2715.476489789974 remaining**.
No additional experiment was started from the remaining allowance.

All four original checkpoint bytes/state fingerprints and source arrays
remain unchanged. All375 pre-existing research JSON files retain their hashes.
Registered2744 numerical seed values have no collisions in the audited current
artifact/config/source seed metadata or conservative historical reservations.
This is not a claim about unavailable external runs. No reserved physics,
closed evaluation returns or E2.17 grant was reused; H17 remains blocked.

Audit verified10780 lossless journal records against actual completed work,
replayed forecasts/reward timing, restored frozen predictions without fitting,
recomputed analyses and checked original execution source hashes. All16
precommitted decision records match the capture, and evaluation resource
records reference that decision-file hash. No evaluation feedback updates.
Phase reports summarize192 completed decision receipts; the full per-call
events are stored once in six lossless compressed journal parts (94,496,000
bytes total). No checkpoint binaries are added to Git.

## Tests and reproducibility

Pre-run focused72 passed in1.80s;29-module relevant regression537 passed
in11.38s. Final539 passed in11.53s, including saved-result/first-action-collapse
replay and rejection of unverified exports. These are relevant regressions,
not the entire historical suite; known legacy learned-inference benchmark
excluded from source-only tests. An initial test's seed-count arithmetic
expected2730 instead of2744; corrected before protocol lock. No scientific
execution occurred during those fixture tests.

Commands (prefix: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
VECLIB_MAXIMUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps):

```
python3 scripts/run_e3_11_post_probe.py
python3 scripts/run_e3_11_post_probe.py --verify
python3 scripts/summarize_e3_11_post_probe.py
```

Raw result `artifacts/e3_11_post_probe.json`, SHA256
`abb0f5be2acef397535bd42a02a31fdd5ad033b70ae56956c367956e42a27e2b`.
Validation SHA256
`4ce37ce2f61e1c11441bd252a5f5c4b034979102729f10d79fa27de0716ec593`.
Frozen selector SHA256
`5427226f93927ff08ab941e4020eb017db2b49ab93f3e2b275a9f8fb1632e2af`.
Predecision log SHA256
`8040a6186c20b005b0ae6baad87f467b94b4a0428acd9c3ddd4366743a0b2160`.
Machine summary `e3_11_summary.json`;64-row CSV `e3_11_evaluation_returns.csv`;
full raw paths, forecasts, source hashes, dependency versions and six resource
journal hashes are in the capture. Previous results remain unchanged.

## One next experiment

**A separately registered source-only controller-specific rollout headroom
audit:** test whether forecasts that simulate each controller's repeated
decision rule distinguish strategies when their first actions agree. Use
original permitted source observations and an explicit small inference cap;
do not fit/select features using these now-closed16 evaluation contexts.
This targets the observed representational collapse before another fresh
return study, mutation-credit learning or architecture expansion. Not executed.
