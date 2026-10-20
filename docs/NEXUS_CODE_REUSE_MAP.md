# NEXUS Seed — Code Ownership and Reuse

## Active runtime

- Shared labs: seed/shared_brain.py is an adapter over Session, not another agent
  state store. seed/skill_library.py derives typed skill revisions and source-only
  rule feedback from that SAME E1 Journal; existing storage saves them.
- Typed skills: seed/skill_programs.py reuses core Predicate/GRAMMAR/Move and adds
  bounded list operators. seed/relations.py extracts the old Relation primitives
  with semantic_lessons public aliases intact. Existing planning.to_cell and the
  original authored reward serve the World Lab reference.
- meta/kind_statistics.py is the original EpsilonGreedyController numeric core,
  shared by that controller and the lab adapter. No second bandit framework.
- Optional representation/retrieval is the existing frozen SeedRSSM encoder/key/
  query network; new domains have supplied sensor schemas, unvalidated neural
  semantics. No GRU, normalization, recurrent contract or checkpoint is changed.

- Finite concepts, typed programs, correction, evidence: src/nexus/seed/core.py.
- Durable sessions and bounded local requests: seed/storage.py, seed/lab.py.
- Recurrent state: seed/state_contract.py over world/seed_rssm.py.
- Neural execution: seed/grounded_agent.py; data-only replay: grounded_records.py.
- Existing planning: seed/latent_planner.py adapts world/planning.py.
- Action scorer: seed/action_readout.py; do not replace with another planner.
  Its frozen nonlinear33-feature bridge reuses PlasticityController/correction;
  no new optimizer stack or runtime adapter is enabled by that API.
- Local adaptation: seed/plasticity.py and adaptive_state.py.
- Vetted edits and rollback: seed/structural_edits.py.
- Surprise/one-use acceptance: seed/surprise.py.
- Source-only future-learning credit: grounded_meta.py wraps the existing
  meta/controller.py EpsilonGreedyController. Do not open a parallel controller.
- Shared provenance: evolution1/catalogue.py canonical/digest and
  evolution1/fixtures.py Journal. Do not delete these as obsolete Evolution code.

## Verification versus experiments

Question utility: seed/question_utility.py adapts question_selection's variance
orders/fixed damping and question_headroom's counterfactuals, plus the existing
nn/ridge primitive. Current-outer-fold source constants/normalization are reused
for all training cases, avoiding other folds' held-task contributions. Query
answers and unasked labels are absent from the public selector API. Same
EXPERIMENTAL host/worker/ledger; no new learner framework or neural model.
scripts/verify_seed_question_utility.py reuses the earlier stdlib variance solver.

Larger query bank: seed/query_replication.py reuses the EXACT saved headroom
states/normalization and nonlinear_learning.fresh_world/score_basis/Meter.
It collects only source query starts, with all selection choices persisted
before checking. No new learner, world, optimizer, memory or runtime policy.
scripts/verify_seed_query_replication.py replays stored scalar arithmetic with
stdlib only. Existing EXPERIMENTAL caps/ledger/one-use manifests remain enforced.
scripts/validate_seed_query_replication.py is an OFFLINE arithmetic/accounting
validator for the unchanged initial capture; it does not reopen or rerun it.

Question-pool headroom: seed/question_headroom.py is an evaluator adapter over
saved question_selection states, its shared damped_step/assess helpers, frozen
source pack and existing cumulative posterior. It adds no runtime questioner.
Oracle choices are computed after all independent counterfactual fits; query
blocks derive from hashed original records. Same EXPERIMENTAL host and ledger.
scripts/verify_seed_question_headroom.py checks recorded equations using the
prior verifier's numeric audit primitive; no new learner/framework or collection.

Question choice: seed/question_selection.py reuses sequential source/hash/fold
validation, the existing constant damping and cumulative posterior, anchor fit,
paired intervals and EXPERIMENTAL host. Input-only variance chooses a requested
saved teaching row; an oracle adapter reveals only its label. Fit and assessment
functions have separate arguments. No new learner, memory, model or simulator.
scripts/verify_seed_question_selection.py independently checks recorded equations
and original-order replication using stdlib only. No live promotion.

Learning choices: seed/learning_choice.py performs one roll-in/reference refit
through existing prefix_consistency helper options and cumulative trajectories.
seed/learning_decision.py is a pure immutable advisory over predicted benefit,
observed-anchor damage and budget; it does not replace Session/concept questioning.
Same EXPERIMENTAL host, ledger and Lab. Ask waits for the next scheduled label;
no autonomous active-query efficacy established. No live promotion. Stdlib-only
scripts/verify_seed_learning_choice.py checks fitted equations and decision math.

Sequential frozen selector: seed/sequential_consistency.py reuses cumulative
posterior/folds, prefix_consistency.features/predict, update_diagnosis trajectories/
paired intervals and bounded protection. Same EXPERIMENTAL host/worker and Lab;
no new optimizer, memory or resource framework. Frozen source-fitted state is
tracked JSON; scripts/verify_seed_sequential_consistency.py checks complete
sequential arithmetic without fitting, neural imports or private binaries.

Teaching-prefix informativeness: seed/prefix_consistency.py uses existing source
packing, cumulative folds/posterior, anchor initialization and task intervals.
The original E2.25 ridge math is extracted to nn/ridge.py; original public APIs
delegate to it with identical numerical results. No new regression framework.
Same EXPERIMENTAL host/worker and Lab; saved vectors/normal equations allow
stdlib-only verification without fits. This is retrospective local utility,
not a runtime update-policy promotion or another world-model training stack.

Scalar update/retain gate: seed/update_gate.py reuses PlasticityController(1)
logits, nonlinear_learning.fit_source's model factory, cumulative_learning's
posterior/fold/summary/validator helpers and update_diagnosis.trajectory. Same
metered host and Lab, no runtime promotion or parallel learning framework.
scripts/verify_seed_update_gate.py reuses the existing checkpoint verifier;
explicit audits fail on missing files, tracked weights allow exact restoration.

Task-blocked cumulative learning: seed/cumulative_learning.py uses the original
PlasticityController and the existing fit_source optimizer via a curve callback.
Its small dual solve assimilates permitted prefix/anchor rows. Four source folds
fit training-only preprocessing and new small rules; no historical weights are
retrained. Existing host/worker/runner handle caps, logs and immutable results.
Stdlib verifier reconstructs all24 new JSON checkpoints without retraining.

Bounded source comparison: seed/bounded_correction.py wraps the existing update
and reuses update_diagnosis trajectory/grid/arithmetic helpers. Its limiter
accepts only observed rows; it is not enabled in runtime adaptation. Same host,
worker and runner entry; cached baselines are verified rather than re-executed.

Source-only update diagnosis: seed/update_diagnosis.py reuses LessonTask,
initial/update/scaled and existing frozen PlasticityController weights. Its
fixed adapter uses the SAME EXPERIMENTAL host/meter; stdlib replay recomputes
recorded arithmetic without model inference or collection. No new learner.

Owner-controlled experimental host: seed/experimental.py and the fixed numeric
worker seed/experimental_worker.py reuse E1 Journal/canonical hashes, the existing
nn.factory and Learning Lab server. Run data stays under runs/experimental.
This is process supervision/development routing, not a second learner or memory.
New planner/simulator/GPU workers need reviewed metering before execution.
The vetted nonlinear-learning adapter (seed/nonlinear_learning.py) now routes a
single registered Seed study through that SAME host. It reuses existing update
math and frozen features. seed/nonlinear_learning_audit.py is stdlib-only for
complete-grid/resource arithmetic and fresh-clone GUI replay; no verifier fits
or collects data. Historical runner math remains unchanged.

Data-only audits: grounded_audit, contract_audit, learning_validation_audit,
readout_validation. Neural studies have explicit runner/config/protocol files.
A verifier must never silently fit a model or collect new scientific data.
The old original action-readout runner remains historical/unrun; the corrected
runner is scripts/run_seed_surprise_readout.py. Its one-run artifact is closed.

## Shared dependencies

The neural factory/expressions, existing meta-controller, planning interfaces
and running statistics have historical names but live Seed dependencies.
Use the source-only dependency audit before any removal. A static unreferenced
module is only a review candidate: dynamic imports and reproduction scripts may
still require it. No automatic code deletion based only on an import graph.

[Prior full map](history/seed-focus-2026-10-20/NEXUS_CODE_REUSE_MAP.md) retains
all older tracks and original module ownership. No generic memory, learning,
resource, planner or evolution framework is replaced.
