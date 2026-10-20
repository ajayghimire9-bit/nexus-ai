# Optional executable world model

This is a bounded experimental extension, not a replacement for Seed's core.
Read the [locked first study](NEXUS_SEED_EXECUTABLE_WORLD_PROTOCOL.md) and
[completed results](NEXUS_SEED_EXECUTABLE_WORLD_RESULTS.md). Historical
question-utility failures remain intact; their reliability audit is still unrun.

## Working implementation

`structure/state.py`: typed scalar entities, typed relations and observed events.
An observation replaces current visible entities/relations, remembers previous
entities with source/time, and appends strictly timed events. IDs bind entities
within an episode, not learned task meanings. Reset clears graph/history but
preserves library; remembered entities never become current by inference.
32 entities,64 relations,32 retained events. Truncation is explicit; absent
historical evidence becomes unknown where necessary. Derived features are pure
functions, distinct from observation. No simulator handle or privileged state.

`features.py`, `learning.py`: finite pure predicates and recurrence detection.
Learned features distinguish two observational histories that the base key
collapsed. The grammar and search procedure are supplied; the selected predicate,
its acceptance and conditional empirical predictions come from source experience.
Changing table counts, adding a feature, changing applicability and installing a
different mechanism are distinct code paths. The first study learns features
and empirical parameters only, not new arbitrary graph laws. The current router
is deterministic applicability testing, not a learned router.

`mechanisms.py`: supplied/learned provenance, typed preconditions, scalar set/add
effects, uncertainty, evidence and counterexamples. Bound entity variables replace
name-based effects. Unknown/precondition/type failures are explicit. Effects are
atomic predictions, never applied to the real simulator by calling the model.
Legacy compatible programs use skill_programs.run. Boolean outcomes use an
explicit Bernoulli prediction interface. Numeric residuals cannot impersonate a
categorical transition.

Graph BFS: depth<=4,<=16 mechanisms/branch,<=128 expanded nodes,<=1024
instructions,<=.5s; defaults3/64/512/.05s. Rejected applicability tests are charged.
No hidden outcomes are available to planning. No automatic plan execution is
enabled in the original World Lab. External actuators still use Session.execute;
their next observed consequence must enter through the same sensor interface.

`neural.py`: optional new8-hidden-unit bounded numeric residual using nn.factory;
source RMS scaling, clipped observed residual targets, tanh output. New JSON
checkpoint, strict load; no frozen GRU or old checkpoint replacement. Not active
in the first study. No architecture-level benefit inferred from a unit test.

`investigation.py`: source-trace entropy decision-tree compression over permitted
probe answers. It learns probe selection, branches and stop/abandon leaves from
source traces; fixed order is labeled supplied. Probe callbacks must return
observations, not predictions; each answer consumes one real probe. Source trace
labels are identified hypotheses, not hidden target answers. Max16 candidate
probes/depth3/15 nodes, source128 traces. Target history cannot update the library.
The integrated first version compresses observed source binary outcomes into
conditional probe trees. It does not yet learn a policy for discovering competing
mechanistic explanations through new environment experiments.
Scientific investigation-transfer evaluation remains unrun, including its fixed
and exhaustive-search comparisons. Merely saving a template is not learned reuse.

`runtime.py` derives state, examples, library revisions and investigation records
from the SAME Session/E1 Journal. `seed_structure` events use existing storage.
Restore deterministically checks/reconstructs the finite source induction and
trace compression, never runs probes, steps a simulator, or trains a network.
Inspection never advances either neural or structured state. Explicit rollback
restores the previous feature library; evidence and consumed validation stay.
These local owner-authored records are not authenticated external scientific proof.

## Use through existing API and chat

Existing `/api/seed` envelopes support `structure_inspect`, `structure_reset`,
`structure_observe`, `structure_example`, `structure_review`, `structure_predict`,
`structure_install`, `structure_plan`, `structure_learn_investigation` and
`structure_rollback`, `structure_investigate`, `structure_install_numeric` and
`structure_predict_numeric`. These are OPTIONAL, bounded, typed calls, not inferred
commands hidden in chat. The chat Evidence button's experimental-model view
shows actual current state/library/costs; empty means no observed records yet.
The current checked skills, chat and four labs remain usable and baseline-default.

An example record uses current observed state and explicit owner-observed outcome;
review accepts source IDs and separate one-use source-validation IDs only. No
final-outcome role is accepted. APIs are development tools, not a cryptographic
guarantee that an owner truthfully labels data. Source/library hashes and the
registered runner enforce scientific data flow for the study.

## Transfer and status boundaries

Implemented/tested: typed observation, execution, bounded planning, conflict
induction/retention/rejection, numeric residual, trace compression, journal
persistence, inspectable opt-in API and rollback. First experiment: source
prediction only. Not established: learned graph transition discovery, interactive
planning success, feature transfer, investigation transfer, a second domain,
general learning-to-learn or AGI. Target support and final query feedback must
remain separate in any later experiment; global library freezes before it.
Renamed codes require observable binding evidence; no hidden correspondence.

## Prior work and originality boundary

Structured world models and object-oriented MDPs provide precedents for factored
state; recurrent modular mechanisms study modular recurrent computation;
DreamCoder studies executable abstraction libraries and learned search. This
implementation claims no novel theory from combining these ideas. Its specific
testable contribution is bounded conflict-triggered history-feature selection,
with one-use validation and auditable integration in Seed's existing journal.
Any advantage must be measured against recurrence, all-history regression and
replay, not inferred from the architecture name. References and final outcomes
will be added to the result report without rewriting this protocol.

Primary references: [object-oriented MDPs](https://icml.cc/Conferences/2008/papers/571.pdf),
[Recurrent Independent Mechanisms](https://arxiv.org/abs/1909.10893), and
[DreamCoder](https://arxiv.org/abs/2006.08381). These are precedents, not claims
that Seed reproduces their scope or results.
