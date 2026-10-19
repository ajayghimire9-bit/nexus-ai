# Assignment, estimation and repeatability: gated next studies

**Design only. No allocations, numerical seeds, physics selection or execution.**

First complete the existing E3.12F comparison. Its primary changes assignment
only; its predeclared paired secondary changes estimation on the same feedback.
No architecture expansion or meta-controller replacement is needed. F's two
models/family are not enlarged by counting query episodes or selector variants.

## Repeat the complete learning procedure on known frozen models

After F, freeze one recipe for a separate development-only repeatability study,
including its assignment, estimator, schedule and feedback count. Selection
from F makes F development evidence; it does not turn its outcomes into an
independent confirmation. If no recipe looks useful, preserve that failure and
consider whether more sampling would be informative before allocating it.

Proposed bounded design: four independent batches, each covering the SAME four
frozen source models. Each batch/model has new eight-reset training feedback,
one child/reset balanced four/four, followed by four separate query resets
executing parent/both children. Learn → seal → evaluate afresh in every batch.
No repeated query feedback or a cached model-specific winner may enter fitting.

Per batch: 4 models × (16 training + 12 query) paths × 200 =22,400 real steps.
Four batches: **89,600 real**, conservative **134,745,600 imagined** and
**4,979,200 calls/forwards**, source-derived from twelve parent/eight switch/
eight blend paths per model. Proposed 900-second cap, not granted. D-based
runtime estimate ~636 seconds before audit overhead; save an incomplete run
if exceeded. No additional independent decoder training is authorized.

Primary candidate comparisons: sealed selected strategy minus fixed parent
and minus one strong fixed child baseline chosen using permitted prior source
training only and frozen before batch collection. Report average gain, harmful
change frequency, choice frequencies and variation across complete batches.
Proposed practical criterion: both family gains >=1 with positive paired lower
bounds against both baselines. This is a new development rule, not a weakening
or reinterpretation of F's BOTH-family rule. Finalize before registration.

For a conditional-on-known-model analysis, average queries within each model,
then models within each family/batch; intervals across four independent batch
means have df3. Report every model's batch distribution separately. The unit
here is repeated complete data collection/learning on fixed models, NOT sixteen
new independently trained models. No population-of-decoders inference follows.
Model generalization requires a later independent-checkpoint study; dynamics
generalization requires separately registered new physics. Do not conflate
these with repeatability on the known models.

## Later: adaptive allocation, not another untested framework

Only after the comparison/estimation mechanism works repeatably, compare a
standard fixed-budget best-arm identification baseline against fixed balanced
allocation, with parent a legitimate final choice. Use the existing proposer,
feedback contracts, meta-controller and Host reservations. Predeclare what
feedback is revealed, total evaluation/CPU budget, stopping and frozen query
assessment. A decision is “which comparison earns the next evaluation,” not
“which hidden query return is best.” Predicted rewards are never observations.

The cited [Karnin, Koren & Somekh (ICML 2013)](https://proceedings.mlr.press/v28/karnin13.html)
studies best-arm identification with fixed-confidence and fixed-budget settings.
It motivates a strong standard baseline; its assumptions and guarantees do not
automatically apply to NEXUS's correlated trajectories or changing tasks.
No such adaptive-allocation experiment is implemented or run in this task.

## Later: measured persistence and E4 rules

Reuse the existing TaskStream, durable JSON codec and mean/recent/conservative
update rules. Test learn A → learn B → restart → return A → encounter C against
persistent/reset controls, with equal actual feedback and CPU allowances.
Measure feedback-to-useful-return, retained A return, forgetting, recovery and
negative transfer to C. C must not receive an oracle model mean or stored
winner. A synthetic restart test establishes state persistence, not benefit.

Only then select an E4 update rule on source/development streams, freeze it,
and assess adaptation on separate tasks. Keep task identities, observation
changes and any oracle stream boundaries explicit. Existing proposed budgets
in `NEXUS_MEASURED_LEARNING_FOLLOWUPS.md` remain unallocated; this document
does not activate them or merge distinct studies into an autonomous run.

Negative results can indicate sampling noise, reset difficulty, estimator bias,
uninformative feedback or limited strategy headroom. They do not automatically
justify larger networks. No general learning, control-transfer or AGI claim.
