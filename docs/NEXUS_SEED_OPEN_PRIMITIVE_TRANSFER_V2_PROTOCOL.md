# Open Primitive Transfer v2 — prospective repair protocol

**Status: incomplete implementation; unauthorized; not an executable locked
scientific protocol.** No final targets or outcomes exist. Configuration:
`configs/seed_open_primitive_transfer_v2.json`, `authorized: false`.
Base: `8d62ce23722bafea9c355cde4f306ca23dad3584`.

This document records the requested design and unchanged 17 acceptance gates
while identifying missing implementation. It must not be cited as completion
of the requested pre-run Commit 1. A future completed, tested protocol and
implementation must be clean and pushed before authorization or final generation.

## Question and alternatives

Can a source-evolved frozen rule discover and safely acquire bounded code
primitives on mechanism-disjoint tasks with better efficiency than strong
executed search policies? Alternatives include sufficient handwritten search,
an unnecessary promotion abstraction, no transferable source rule, and an
indistinguishable benchmark. Each is an acceptable negative result.

## Reuse and implemented boundary

The unchanged `open_primitive_transfer.ImmutableTrustedKernel` remains private.
The new environment subclasses `CommonEnvironmentAdapter` without its legacy
private-test constructor and constructs `TransitionReceipt` instances. The
legacy `LearnerTaskView`, `EvaluatorTaskPrivate`, `PrimitiveProposal`, old retention
suites and E1 Journal remain required integration points, not completed new
experiment components. No parallel RL, neural, memory or evolution framework
is introduced.

`LearnerProcess`, `EnvironmentProcess`, and `PrivateEvaluatorProcess` are fresh
subprocesses with closed JSON command/reply schemas, no pickle, hard CPU limits
and bounded RPC deadlines. The macOS child sandbox denies network and writes.
Learner/environment cannot read registered artifacts, configurations, docs,
runs or the new private-evaluator module; the learner also cannot read the
legacy answer-bearing module. The private evaluator currently supports only
status/fingerprint. No process has a final-generation API in this revision.

The runner imports neither the private evaluator implementation nor a result
builder. A typed transport alone cannot prove semantic noninterference: allowed
strings can contain secrets, and permitted visible target observations reveal
information intentionally. Gate 1 must mean zero **unauthorized** private raw
inputs, outcomes, implementation or identity payloads, with explicit public
reveal and promotion-status declassification. It cannot literally forbid every
value shared by a public example and a private test (e.g. integer 0). Before
execution, provenance/taint tests must cover all declassification routes.
No hostile-root/same-UID debugger security claim is made.

## Frozen design to implement

Four disjoint partitions: evolution training (flat lists and boolean circuits),
curriculum development (string transducers), frozen-rule selection (integer
pairs), final transfer (stateful streams, nested records, graph/path aggregation).
Planned seed blocks are in the config; none have been instantiated. Final
tasks require eight independent libraries in each of three families, at least
three decoys and three plausible patch sites, neutral regenerated identifiers,
private edge cases, and canonical/behavioral disjointness checks. Only public
hashes/generation metadata may leave the private task archive.

Source evolution must exercise the new AST-patch opcode. Fitness uses training
feedback only. Development may inform curriculum choices, never be called
untouched transfer. Freeze one winner per source seed before selection-family
scoring. Selection is a predeclared gate, not an opportunity to retune winners.
Freeze all winners before final target generation. The twelve planned methods
are explicit in the config and all non-oracle methods receive identical public
interfaces, 64 actions, 64 DSL instructions and four reveal opportunities.

The rule must select inspections, learner-generated probes, compositions,
primitive source, patch sites, validation and stopping. The current fixture
interpreter supports inspection, testing public helper hypotheses, filtering,
and source-derived AST patches only. It does NOT yet implement this full rule.

Private promotion must validate bounded ASTs, resource use, determinism, public
evidence, withheld and adversarial outcomes, real before/after retention and
definition-plus-call-site MDL. Never return private counterexamples to the
learner. The existing kernel's entire proposal record must stay private.
Do not substitute caller-supplied expected answers or booleans for execution.

No-propose must still attempt inline composition/patching. No-sleep retains
the same acquisition abilities. Random evolution selection cannot receive the
winner's score. The evaluator-only oracle is excluded from promotion comparisons.
Methods must genuinely execute: no table constants or reused successes.

Cross-lab evaluation requires one to four public demonstrations for an invented
word, candidate execution over promoted capsules, and separate compiled
Language/Coding/Reasoning interfaces to a shared typed representation. World
is not applicable unless the type permits it. Compare shared, isolated,
scratch, name-only and demonstration-only controls. The frozen global library
cannot learn from private assessment. None of this is implemented yet.

## Proposed resources, missing host integration

Local CPU only: proposed 300 s wall/aggregate CPU, 2,048 MB aggregate RSS,
100,000 maximum sandbox actions, zero neural training, zero real-environment
steps and zero imagined transitions. These are proposed caps, not an allocation.
Carry 2078.632103455996 s used / 1521.3678965440042 s remaining unchanged.
The existing host meters only its direct worker RSS; actor descendants require
aggregate enforcement before it can authorize this run. Per-process 10 s CPU
limits in boundary tests do not solve aggregate scientific accounting.

Required receipts: inspected bytes/AST nodes, calls, tests, candidates, DSL
instructions, patches, proposal validations, private tests, retention executions,
memory bytes, wall and CPU time. Preserve failed attempts. Record sandbox actions
separately from environment interactions. Roll up measured increments; do not
record limits as usage. Hash-linked logs require independent replay checks and
bounded/chunked storage. One-use authorization must bind the clean pushed source,
config/protocol hashes, remaining ledger and exact host cap before generation.
No retry or smaller grid after seeing outcomes.

## Statistics and prospective gates

For each method/task retain raw outcomes, failures and all receipt costs.
Average the three family tasks inside each independent source-learning seed;
report per-family and per-task results too. Eight seed blocks are the primary
paired units, not executions or private test cases. Report means, medians,
Student-t 95% intervals (df=7), paired block-bootstrap intervals (20,000 resamples;
seed 112233), and Holm-adjusted baseline-comparison p values. Identical paired
differences trigger a benchmark warning, not automatic acceptance.

The strongest baseline is the highest success; ties choose lower measured
candidate executions. Success noninferiority margin is 0.02: lower paired
95% difference bound must be at least −0.02. An acquisition ablation difference
of at least 0.05 is material. Cost advantage is baseline minus primary in
executed candidates or real query experiments, with a positive lower interval.
All costs remain reported; no fabricated weighted proxy.

All 17 requested gates remain mandatory; currently **not evaluated**:

1. No unauthorized private payload reaches the learner.
2. Runner has no evaluator-private access.
3. Frozen rule chooses all Stage-B actions.
4. No learner-visible correct patch/helper/post-operation.
5. Mean final hidden accuracy at least 0.95.
6. At least two final families reach 0.90.
7. Noninferiority to the strongest executed baseline.
8. Positive paired 95% cost or experiment advantage.
9. Removing proposal materially removes acquisition success.
10. Removing evolved rule materially removes success or efficiency.
11. Shared capsules beat isolated and scratch cross-lab controls.
12. Actual retention at least 0.98; worst-family regression at most 0.02.
13. Every promotion completes privately executed lifecycle checks.
14. All metrics reconstruct from raw receipts.
15. Independent verifier imports no result builder.
16. Identifier-renaming/decoy-shuffling replay preserves results.
17. No automatic live-agent promotion.

Missing, nonfinite, duplicate or shortened grids are **incomplete/invalid**, not
a scientific failure or inconclusive interval. An executed complete grid may
fail scientific gates honestly. No gate is deemed passed by implementation tests.
Even a clean acquisition success without a supported strong-baseline efficiency
advantage does not establish useful learning-to-learn.

## Required completion work and entry checks

`python3 scripts/run_seed_open_primitive_transfer_v2.py --readiness` reports ten
missing capabilities and exits 2. Running without that switch refuses execution.
The config cannot enable missing code by changing `authorized` to true. This is
intentional: the current revision is not ready for authorization.

Before scientific Commit 1: complete the private generator and full DSL,
proposal/retention/MDL pipeline, equal-budget baselines, grounded cross-lab
assessments, actor-aware host and independent 17-gate verifier. Add adversarial
integration and full renaming replay tests. Only then push clean Commit 1,
authorize once through the existing host, execute the registered run and commit
results separately. No final outcomes are manufactured for the partial code.
