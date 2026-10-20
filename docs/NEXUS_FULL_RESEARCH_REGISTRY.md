# NEXUS Seed — Research Registry

## Active evidence, newest first

- [Scalar update/retain gate](NEXUS_SEED_UPDATE_GATE_RESULTS.md): curve MSE
  .180324 learned versus .180187 constant, .187016 replay, .184388 bounded.
  Source learning screen FAILED; retention passed. Generic damping helps,
  task-conditioned strength does not beat constant. Three rule-training seeds,
  one frozen core, reused data; no fresh validation/control/promotion.
  [Protocol](NEXUS_SEED_UPDATE_GATE_PROTOCOL.md), execution0ce94d0.

- [Task-blocked cumulative learning rule](NEXUS_SEED_CUMULATIVE_LEARNING_RESULTS.md):
  new rule trained across nine source tasks/fold and assessed on three excluded
  tasks. Only .31% gain over source-trained static; worse than replay/bounded
  fixed. Practical source screen FAILED, retention passed. Reused-source data,
  three update-rule seeds, one frozen core; no fresh validation or promotion.
  [Protocol](NEXUS_SEED_CUMULATIVE_LEARNING_PROTOCOL.md), execution5235599.

- [Bounded source correction](NEXUS_SEED_BOUNDED_CORRECTION_RESULTS.md):
  stabilization passed (13.5% versus unchanged learned), strong-replay and
  learned-specific practical screens failed. Reused source evidence only;
  no runtime promotion. [Protocol](NEXUS_SEED_BOUNDED_CORRECTION_PROTOCOL.md),
  execution269bcb6. Original receipt's legacy adapter label is documented;
  future host metadata corrected without rewriting the old receipt.

- [Source update-magnitude diagnosis](NEXUS_SEED_UPDATE_DIAGNOSIS_RESULTS.md):
  large norm ratio12.55×,but only5/12source tasks harmed; registered broad-harm
  pattern not supported. Reused source evidence,not new validation or causation.
  [Protocol](NEXUS_SEED_UPDATE_DIAGNOSIS_PROTOCOL.md), execution9c379aa.

- [Nonlinear-feature learned update rule](NEXUS_SEED_NONLINEAR_LEARNING_RESULTS.md):
  combined development screen FAILED; retention passed; no reliable advantage
  over static and replay; learned/static/fixed control actions identical.
  [Protocol](NEXUS_SEED_NONLINEAR_LEARNING_PROTOCOL.md), execution73d1dcd.

- [EXPERIMENTAL workflow engineering](NEXUS_EXPERIMENTAL_MODE.md): owner budgets,
  typed candidate training, independent assessment routes, retain/rollback and
  read-only GUI. Authored numeric QA only; no scientific result or new simulation.

- [Frozen spatial-transfer development](NEXUS_SEED_SPATIAL_TRANSFER_RESULTS.md):
  screen passed versus frozen ranking; greedy stronger; boundary/diagonal
  limitations. One core,no updates. [Protocol](NEXUS_SEED_SPATIAL_TRANSFER_PROTOCOL.md).

- [Nonlinear action readout and surprise](NEXUS_SEED_SURPRISE_READOUT_RESULTS.md):
  development screen passed; greedy stronger; future-edit credit ties
  historical-best. [Protocol](NEXUS_SEED_SURPRISE_READOUT_PROTOCOL.md).
- [Fresh learning/action/meaning validation](NEXUS_SEED_LEARNING_VALIDATION_RESULTS.md):
  learned plasticity lost to scaled replay; object gates failed; transfer not run.
  [Protocol](NEXUS_SEED_LEARNING_VALIDATION_PROTOCOL.md).
- [Memory-aware local learning](NEXUS_SEED_MEMORY_AWARE_RESULTS.md):
  implementation functional; meaningful learned-update improvement not established.
- [Shared state/memory/value contract](NEXUS_SEED_CONTRACT_RESULTS.md):
  correctness improved; decision screen failed.
- [Grounded architecture pilot](NEXUS_SEED_GROUNDED_RESULTS.md):
  connected neural paths; limited control/language evidence.
- [Finite S0–S1](NEXUS_SEED_RESULTS.md): comparison incomplete, no rerun.

Raw metrics/configurations/checkpoint references remain in artifacts/ and configs/.
A completed implementation is not a successful research hypothesis.

## Learning-to-learn decision

Require measured faster/better adaptation on untouched tasks versus strong
source-informed simple baselines at equal teaching/search budgets, with
forgetting, compute and uncertainty reported. Fitting an action scorer, saving
knowledge, changing proposal probabilities or selecting a winning edit once is
insufficient. Preserve negative results.

## Historical tracks

The [complete previous registry](history/seed-focus-2026-10-20/NEXUS_FULL_RESEARCH_REGISTRY.md)
and [machine-readable registry](../artifacts/nexus_research_registry.json) retain
earlier control, lookahead, cross-family, H12–H17 and Evolution records.
The [history guide](history/README.md) explains old checkpoint availability.
Keep closed seeds/splits, original artifact paths and frozen models unchanged.
No historical experiment is scheduled by this registry.
