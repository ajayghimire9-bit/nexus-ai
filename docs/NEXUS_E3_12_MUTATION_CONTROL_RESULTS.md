# E3.12 — Measured mutation learning: useful improvement not established

Branch `codex/e3-12-measured-mutation-credit`, starting revision
`b94ed9132762d064f77445e9d0ef92b640334e08`. Protocol, executable config,
allocation and tested implementation committed **before collection** at
`629c8d2cbb30632acab2d3e633b64fc19cccf46a`. No retry or retuning.

## What actually ran

One complete valid development run: four frozen source world models, two each
for Pendulum and Acrobot; eight sequential training contexts and four fresh
query contexts per model. Every paired parent/child path runs200 real steps.
The two mutation operators are switch and rank_blend over fixed successor/flat
anchors, using existing executable grammar. This is a test of learning which
structural operator to propose, not open-ended algorithm invention.

Existing StrategyGenerator mean credit now receives actual trusted episode
returns via measured_mutation. The generic metered Dispatch route preserves
the existing planner implementation. Random generation fixes the same leaves,
threshold and uniform draws and differs only in learning structural preferences.
Both receive equal opportunities and the same1536-row per-decision upper cap.
Actual compute differs by operator. These catalogue-budget planners are **not**
the historical16-candidate controller; its closed results remain unchanged.

## Primary result and all baselines

**useful_mutation_learning_not_established**: both family screens fail.
Learned-minus-random return is **0.000 [0.000,0.000]** in both families.
All48 training/query contexts selected the same sampled kind; the complete
paired learned/random trajectories are identical, including all16 query cases.
This degenerate empirical interval reflects identical realized choices under
common uniforms. It is not proof that the different probability distributions
have equal expected returns or that further experience cannot help.

Pendulum mean200-step return: learned/random **−277.963**, fixed successor
parent **−288.630**, fixed rank_blend **−304.838**. Learned-minus-parent
**+10.668 [−1248.156,+1269.491]**; learned-minus-fixed-blend
**+26.875 [−387.257,+441.008]**. Model0 learned−268.550 vs parent−378.289;
model1 learned−287.376 vs parent−198.972: model heterogeneity is substantial.

Acrobot mean return: learned/random **−297.219**, parent **−293.811**, fixed
rank_blend **−286.761**. Learned-minus-parent **−3.407 [−4.356,−2.459]**;
learned-minus-fixed-blend **−10.458 [−119.882,+98.967]**. Model-level parent
differences−3.333 and−3.482. The parent comparison is a labeled secondary
exploratory result, not an independent confirmatory finding.

Intervals aggregate episodes inside each independent model, then use the two
models within each family (df1), unadjusted exploratory. Families are not pooled
as exchangeable replications. Episodes and mutation draws are not extra model
replicates. CSV contains every model/episode/condition return; raw JSON contains
all actual transitions and strategy payloads/lineage.

## Did feedback change anything?

Yes, the probability state changed after all32 learned training updates. Final
switch probabilities (random stays.5): Pendulum0 **.469425**, Pendulum1
**.529265**, Acrobot0 **.505170**, Acrobot1 **.518214**. These modest shifts
never crossed any sampled query uniform; no sampled decision improvement
resulted. Training parent–child gains also vary strongly by reset; e.g.
Pendulum0 switch gains range−623.163 to+418.535. Those are descriptive observed
gains, not paired estimates of switch versus blend at every state.

We have demonstrated an actual feedback-to-preference connection with real
measured returns. We have **not** demonstrated useful learned generation,
continual adaptation, general control transfer or learning-to-learn.

## Integrity and independent audit

Complete48-context/160-path/32,000-decision locked grid passes. Every query
update is replayed as unchanged; training probabilities reconstruct solely from
permitted training feedback and saved measured CPU costs. Every action/return
uses paired resets and per-tick planner seeds. Seed audit checks9648 registered
identifiers against available artifact/config metadata, original source-array
seeds and conservative historical reservations; no collision found. Unavailable
external history is not asserted covered.

All four model/RMS fingerprints match before/after; all four checkpoint and
eight source-file hashes preserved. Parameters4868 per Pendulum model,5255 per
Acrobot model, all frozen. No neural fitting, support/probe/validation collection,
new physics or reserved confirmation access. All402 previous JSON files remain
byte-identical. Two unrelated untracked evolution1 adapter files remain excluded.

Saved-data verification replays32,000 per-decision receipts:48,057,060 imagined
rows,1,587,620 calls and1,587,620 observed forwards reconcile exactly, with zero
unknown work. Episode-level bridge summaries are references to those receipts,
not extra physical charges. The parent is physically executed once/context and
shared across learners. Child evaluations are physically executed separately,
even when identical. Independent stdlib arithmetic recomputes means, paired
intervals and phase totals; math.fsum versus saved sums differs by0.0.

The reused immutable Journal retains its historical synthetic_fixture hash
namespace; that legacy serialization label does not authenticate measured
execution. Actual feedback is explicitly tagged real_environment and tied to
the trusted host's measured paths/receipts. Same-process Python objects are not
a hostile-process security boundary.

## Tests, commands and resources

Initial focused suite117 passed after correcting a test-file syntax error;
initial relevant regression704 passed in19.28s. Added launch/config/consumed-run
guards: focused27 passed in3.67s. Final relevant suite **707 passed in19.77s**,
including E1 resources/proposer, E2 memory/quality/adapter, E3 source studies,
metered forecasts, bounded cycle and new mutation contracts. These are the
explicit relevant modules in the previous bounded-cycle test report plus
tests/test_e3_12_mutation_control.py, not every historical scientific test.
Exporter tests are run separately after this suite; see new test report.

Commands, with PYTHONPATH=src:.deps, single CPU-library threads and bytecode off:

```
python3 scripts/run_e3_12_mutation_control.py --preflight
python3 scripts/run_e3_12_mutation_control.py
python3 scripts/run_e3_12_mutation_control.py --verify
python3 scripts/summarize_e3_12_mutation_control.py
```

One-run markers intentionally prohibit reexecution of consumed seeds. A fresh
clone can verify raw research JSON/arithmetic; full verification also checks
the original checkpoint/source binaries at the inventory paths and all resource
journals. All four required checkpoints and eight source arrays are already
Git-tracked in this lineage. Missing/hash-mismatched inputs fail explicitly.

Wall **246.474762s**, worker CPU **245.334198s**, peak RSS **891,092,992B**.
Saved-data verification5.341058s. Training96 physical episodes/19,200 real
steps, evaluation64 episodes/12,800 steps. Path CPU totals141.01255/101.294347s
include receipt/capture work, not pure neural latency. Cost-normalized credit
is sensitive to CPU timing; exact update replay uses saved costs. No guarantee
of identical fresh timing-dependent proposals across hardware is claimed.

The total32,000 real steps and48,057,060 imagined rows stay below registered
32,000/49,152,000 caps; calls1,587,620 below1,600,000. Run cap600s. Protocol
used standing local research authority and preserved the carried ledger.
Post-verification ledger1276.4893564590009 used/2323.510643540999 remaining;
the0.052216666s stdlib export brings it to **1276.541573125001 used /
2323.458426874999 remaining**. No further scientific run starts here.

Raw capture SHA256
`df9c59980c0d0efb8bbca4ba5ab5abee5cc4c576c44492399c19cdc028f5bb1e`.
Separate usage, validation, summary and CSV artifacts accompany32 compressed
lossless receipt journals (231,353,772 bytes total). No new checkpoint binary
was created; existing tracked checkpoints retain their original paths/hashes.

## One next experiment

**A balanced paired-operator headroom audit on fresh source resets:** evaluate
both switch and rank_blend at each registered reset under matched planning
caps, with independent training/query blocks. Determine whether their paired
return difference has a stable learnable direction before changing the learner.
This removes the current missing counterfactuals and rare probability-crossing
problem. It requires its own locked protocol and budget; no new execution or
architecture change is included in this result.
