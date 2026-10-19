# Measured learning: status and separate experiment designs

These are implementation plans, not executed experiments, registered seeds or
new allocations. The current task forbids new simulations. Existing code and
recorded evidence are retained; no new model/learner/memory stack is proposed.

## Limited-feedback exploration — already measured, superiority unestablished

E3.12C and D used balanced single-child exploration, then frozen choices on
fresh query episodes. D gave raw means and existing mutation credit exactly
the same revealed observations, and their final choices tied4/4. No superiority
was established; the query screen failed. Do not rerun D or count this audit as
new independent validation. Improve collection design only after the training-
reset diagnosis, not by changing gates against closed query outcomes.

## Actual continual learning — designed, not demonstrated

Future stream A→B→A→C must use freshly registered task physics/episode seeds,
not replays of D's eight training episodes. Use the same frozen model within
each stream so task shift is not confounded with replacing the decoder. Family
schemas stay separate. Labeled A/B/C identity is allowed only if declared as a
known-task retention study; it would not demonstrate autonomous task recognition.
Four existing source-model units, two per family, are a small exploratory
screen, not ten new pretrained replications.

Reuse TaskStream, StrategyGenerator, measured_mutation, Host/Dispatch/ledger,
cycle_checkpoint and a real-evaluator session manifest that also persists
consumed resource counters. A→B must finish before process restart; restore
the exact learned/RNG/cost state for A→C. Reset control starts from the same
source prior at each task but receives identical revealed feedback and budget.
The current durable CLI is authored-fixture only and cannot supply this evidence.

Proposed shared physical panels per model/block: four training resets, parent
plus one child (two exposures/child); two query resets, all three strategies.
Freeze each method's choice before queries. Share these outcomes across the
two methods without counting cached reuse as new interactions. After B, collect
two additional independent A probe resets, three paths each, strictly evaluation
only; this is needed to measure forgetting rather than assuming it.

Total4 models×[4 blocks×(4×2+2×3)+2×3]×200 = **49600 real steps**.
Estimated6–8 minutes from D's same planner; proposed600s cap, no allocation.
Primary: persistent-minus-reset normalized adaptation-curve return on returning
A, with episode averages inside each model and family-specific paired intervals
across the two model units. Proposed screen: at least1-point gain and interval
lower>0, no more than1-point degradation on B/C or post-B A retention probes.
This is intentionally hard to establish with n2; report incomplete/negative/
inconclusive evidence honestly. Register exact aggregation and multiplicity
before collection. Do not change exploration methods simultaneously.

## Evolution-4 — preserve rule choices; measure future utility

Existing mean/recent/conservative rules and training-incumbent progress objective
remain available. E3.12E replays these rules on training feedback only; different
probabilities are not useful learning-rule adaptation. No new neural architecture
or rule is justified by that replay alone.

A separate study needs disjoint source3/development1/final2 task blocks for each
of four frozen model units, with the same proposed4 training/2 query reset panels
per block. Source/development feedback can select a rule; final block returns
cannot. Compare that locked selector with each fixed rule and the strongest
constant rule chosen only on source feedback. Utility is query-return AUC versus
feedback count, plus forgetting/retained return and measured compute, not weight
or probability change. Reward net improvement over the accepted TRAINING
incumbent; never expose hidden gate outcomes to the proposer. Charge failed and
duplicate attempts; assess deployed strategy separately with held-out outcomes.

Proposed **67200 real steps**=4×6×(4×2+2×3)×200. Shared panels across update
rules are matched observations, not extra evaluations. D-scaled estimate about
8 minutes, proposed850s cap; exact CPU/imagined cap must be validated before
registration. Require at least1-point final AUC advantage with paired interval
lower>0 versus the source-selected strongest fixed rule, and≤1-point retained
performance loss. n2/family is exploratory. No rule selection or final-physics
registration has occurred here. Do not reuse the continual study's final tasks
for selecting this procedure or call them untouched again.

## Transfer — blocked scientific prerequisites, not silently substituted

Freeze a useful procedure before testing it. Separate independently initialized
world models on familiar dynamics from frozen models on changed dynamics. Do
not count repeated student seeds on the same decoder as new decoder units.
Additional independently trained checkpoints with source-data/recipe/hash
provenance are not available for this protocol; the existing four cannot be
relabeled as unseen. Training new checkpoints requires separate scope and budget;
historical frozen weights must never be replaced. An unfamiliar model starts
from a source prior, not its true average return. Physics and episode exclusions
must be reviewed before any numerical registration. H17 stays blocked.

Compute for a defensible model-replication count is not yet established; no
exact allocation is fabricated. All future experiments must separately fit
the standing≤900s/100000-step per-experiment limits and remaining session ledger,
or receive explicit additional approval. Current no-simulation scope overrides
any temptation to launch these studies. Configured arithmetic is in
configs/measured_learning_followups.json and tested, but is not a grant.

## Learning Lab — usable local engineering, scientific backend still absent

The standard-library replay launcher and hash-referenced browser notebooks
provide repeatable local use. The existing learned-state codec is connected
to an append-only fixture-session CLI, including persisted evaluator call/cost
counters across restart. Replay, authored fixture execution and unavailable
live environments are visibly distinguished. This is a local demonstrator,
not a deployed scientific execution service or a proven adaptive controller.
See NEXUS_LEARNING_LAB_LOCAL.md for exact commands and boundaries.
