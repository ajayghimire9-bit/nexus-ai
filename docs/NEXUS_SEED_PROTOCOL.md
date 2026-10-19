# Seed S0–S1 authored development protocol v1

Base fbee9819b2edfff5927400e85f353e5b7d215742, verified GitHub branch
codex/e4-five-family-ppo-benchmark. Separate worktree and branch
codex/nexus-seed-s0-s1. Two original untracked adapter files are excluded.
This protocol and tested implementation must be committed before the one
development comparison. No Gym construction, model inference/training, closed
control episodes or confirmation outcomes are used.

## Mechanism and hypotheses

English subset: `move [the] WORD DIRECTION [1..128]`, up to eight clauses joined
by `then`; inspect/look/help/stop. Invalid language returns unsupported. Domain
requests additionally teach/correct labels, ask questions, select scenes, define
an explicit predicate, stop/resume and inspect. Unknown words require teaching;
uncertain extensions and multiple matches require clarification, never a guess.

Grammar: eight property atoms (3 colors/3 shapes/2 sizes), their eight negations,
and21 conjunctions of positive atoms on different properties:37 predicates,
maximum syntax depth3. No learned visual perception. All18 property combinations
are permissible generated question cards, explicitly shown as authored examples.
Learner retains predicates consistent with active positive/negative labels.
Disagreement chooses minimum absolute yes/no vote imbalance, deterministic ID
tie-break; random chooses uniformly among discriminating cards. Same learner,
same grammar and answer budget. If no example distinguishes meanings, report it.
Correction appends a superseding label; old label and journal hash persist.

H-teach: finite-grammar inference enables more correct held-out movement programs
than exact-example memorization. H-question: disagreement questions yield more
correct held-out programs and fewer remaining hypotheses than random questions
at the same answer budget. These may fail. No significance test or population
generalization claim from four authored tasks. Ties and wrong/abstained programs
are retained; no posthoc rule change or expanded teaching budget.

## Development split and comparisons

`configs/seed_s0_s1.json` is executable source of truth. Four authored semantic
tasks/templates: atomic color, atomic shape, conjunction and negation; randomized
invented word per task. They are not paraphrase replications. GUI demonstration
uses a separate color/shape/size conjunction example and is not a selection stage.
No parameters are fit or chosen on these development query outcomes. Configured
question/layout seeds are authored fixture RNG, not new scientific holdout seeds.

Each method gets3 charged teacher labels per task (48 total across16 cells).
A exact labeled property-tuple memorization, unknown tuples abstain; B random
discriminating questions; C balanced-disagreement questions; D clearly privileged
oracle given the actual grammar predicate plus the same3-label opportunity budget.
No non-oracle learner receives target metadata. Teacher correctness and oracle
privilege are authored, not inferred. Repeated tasks/conditions are paired, not
independent discoveries. User sessions never enter the comparison.

Two held-out layouts/task contain one positive and two distractors; coordinates
and command/concept combinations differ from teaching cards. First command is
single right movement; second sequences right/down. Every method receives the
same world and expected true referent. All actual program traces and failed,
ambiguous or abstained outcomes retained. Count correct programs (8/method),
remaining hypotheses, teacher labels, candidate consistency scans, actual
predicate tests, generated example presentations, program evaluations and
primitive sandbox actions. Oracle is an upper reference, not a learned baseline.
No claim of untouched confirmation: these are small authored development tasks.

## Budget, provenance and decision

One exclusive capture, hard30s, <=200 labels, <=10000 hypothesis scans and
<=10000 individual learner predicate tests, <=128 primitive sandbox actions.
Each increment reserves before work; partial failures retain reserved costs.
Teacher-side predicate evaluations are disclosed separately. Supplied example
generation is metered, not free hints. Per-request2s cooperative cancellation,
<=512 candidates, depth<=3, <=128 primitive steps and8 clauses; session256 labels,
2048 events; server500 requests and16 sessions. Historical fixtures have their
old independent limits. No automatic background worker or simulator backend.

Report p50/p95 measured engine operations, peak core RSS, hardware/versions,
source/config hashes and execution SHA. Targets: ordinary p95<500ms, RSS<512MiB,
excluding browser. Not an energy measurement. Regression-test fixture costs are
separate from the comparison. Carried ledger1835.6321034559958 used,
1764.3678965440042 remaining; comparison and arithmetic-audit wall charged
conservatively after execution; tests/browser engineering reported separately.

Complete means all16 task/method cells,48labels,32query programs and finite
metrics, caps satisfied and historical artifacts unchanged. Incomplete and invalid
are distinct from a complete negative result. Save partial capture on failure;
do not rerun or retune it. An independent stdlib saved-result verifier recomputes
truth, action endpoints, accuracy and accounting without importing the learner.

## Persistence and local boundaries

Same Lab server origin/Host/header checks; opt-in --allow-seed. Snapshot directory
is chosen by local CLI, never by language or HTTP messages. Opaque IDs select
sessions, schema-restricted JSON and journal replay reconstruct derived state.
Append-only exclusive revision files, hash links and optional externally saved
head detect corruption/staleness; not adversarial authentication against a local
owner rewriting everything. Snapshots are private files under ignored runs/.
Stop cancels cooperatively; no arbitrary tools or network capability.

Before comparison run focused core, restart, schema, HTTP and Lab regression
tests; real Chrome QA if available. Do not run old simulator tests as a side
effect. Later S2–S7 goals are proposals only.
