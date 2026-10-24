# Wave 15 — support-gated piecewise protocol

Status: pre-assessment code freeze. Starting revision
`ea176084de46ec428806ffd1064ff728a3128501`; branch
`cursor/seed-wave15-pre-piecewise-residual-support-abort`.
Waves 12–14 remain Developmental / Invalid (Failed Single-Shot Blind Gates;
Preserved Unamended). The Wave14 postmortem distinguishes actual task totals
from split totals and does not invent unrecorded transform coverage.

## Owner-resolved physical registration details

The owner explicitly allowed the required runner in Commit 1; the filename
prohibition applies to **fresh holdout definitions**, not the runner.
Before this freeze no Wave15 fresh definition exists anywhere in this working
tree, including ignored paths. The only matching assessment path is
`scripts/run_wave15_support_gated_assessment.py`.

Keep 18 tasks: archive introduction, two archive distractors and delayed reuse
are four archive tasks. Interleave one task from a different split between
introduction and reuse to provide the third non-use episode. This resolves the
original five-events/four-tasks inconsistency without shrinking the suite.
No fresh task rules or token vocabularies are specified in this commit.

## Hypothesis and unchanged mechanisms

Cached partial transform coverage can prevent unsupported piecewise search,
while retaining supported two-branch solutions. Competing explanation: extra
macro processing or limited grammar coverage still makes the full learner more
expensive or incorrect. Source fixtures establish implementation correctness,
not transfer. No learning-to-learn claim follows from these authored tasks.

Reuse Wave14 typed AST/interpreter, typed macro library, MDL compression,
role/schema routines, public channel probe, dynamic constant extraction, report
and dual-cost contracts. The historical module is not edited. No lambda AST,
task/split labels, private examples or task literals enter the learner.
Tier0 retains its old strict size boundary. Active and cold operators precede
atomic discovery; all five methods have identical synthesis rules.

Initial strict residuals exclude identity outputs. Every evaluated transform
caches initial outputs once and stores each nonempty coverage mask with the
lowest primitive-cost, macro-preferred AST. Exact beta-expanded AST keys also
reuse identical atomic/macro outputs; cache hits incur no fictional AST calls.
Primitive counts describe executed opcodes, not expanded hypothetical programs.

Before drawing piecewise probes, cached masks must show a first transform with
at least two strict matches and a second covering the remaining nonempty strict
residual. The gate uses no AST evaluation; bitmask checks are nevertheless
charged as synthesis work. Failure returns abstain with zero piecewise calls
and opcodes. Success evaluates only covering transforms on newly read rows;
each full residual branch needs at least two matches. Guards are built once
only after full cover succeeds, and both branches require separate public
confirmation. Confirmation slots are reserved by the public `confirm_` naming
contract, not private labels. Mask snapshots record the evidence at gate time.

**Source-driven scheduling adjustment:** Tier3 first tests its guards against
already evaluated Tier0/active/cold transforms. If these provide a complete
cached piecewise certificate, it attempts that certificate before full atomic
rediscovery. Otherwise it performs atomic enumeration and repeats the gate.
This is an additional search-order optimization relative to literally exhausting
all Tier3 atomic candidates before every piecewise attempt. It is applied
equally to all methods and frozen here, before fresh tasks exist. Do not attribute
any eventual benefit solely to the abort, or claim unchanged exhaustive search
order. The retained AST language is unchanged.

**Archive complexity:** archive discovery still scans archived operators, charged
one lookup per entry plus actual AST execution. Reactivating an identified entry
uses a dictionary pop, but end-to-end cold discovery is O(archive size), not O(1).
A passing outcome gate cannot establish the requested stronger lookup-complexity
claim. No unmeasured constant-time claim is permitted.

## Single-shot assessment after this commit

Only after Commit1, author a new `mechanism_wave15_fresh_assessment.py` with
18 unique w15f_* IDs: base/dynamic literals 3; relational analogy 2;
unassisted subtree/L2 5; piecewise 2; delayed archive 4; OOG/ambiguous 2.
Use fresh tokens and structural compositions, not a renamed closed suite.
The public API exposes no evaluator labels. Private outputs become accessible
only after a program/status is locked. Record public and private replay data,
selected ASTs, support masks and every cost component.

Execute the shared runner once at seeds 0,1,2, all five methods: 270 cells.
Task correctness includes correct abstention/ambiguity; distinguish that from
private prediction accuracy on solvable tasks. Lock requirements:
full correctness on all cells, zero false unique locks, full cold reactivation
at least once per seed, correct ambiguity, OOG abstention with zero piecewise
cost, and full suite work AND primitive steps strictly below every baseline.
No outcome-dependent omission, retry, budget shrink or code repair.

The standalone verifier replays ASTs, masks, public/private consistency, locked
grid, independent summary arithmetic, both cost identities, original runtime
hash, holdout hash and Phase1 zero diff. Missing/tampered evidence invalidates
execution; a valid execution can still fail the scientific screen.
It writes verification separately. Failed/incomplete attempts retain their
marker, partial JSONL and failure record; never automatically retry.

## Pre-freeze tests actually run

Environment: Python3, existing `.deps` (pytest unavailable without PYTHONPATH),
CPU, `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`.
Command prefix:
`PYTHONPATH=.:src:/Users/ajayghimire/Projects/nexus-ai/.deps PYTHONDONTWRITEBYTECODE=1`.

- Wave15 focused pytest: **21 passed**, 3.29 s. Includes populated-macro OOG
  overhead <5%; ten seeds correct piecewise with <1500 work; 18-task source
  suite full correctness, archive reuse and strict domination of all baselines;
  standalone verifier; private-data isolation; exact macro cache reuse;
  missing-row/seed/private/mask/cost tamper rejection.
- Combined Wave11–15 source invocation: **42 passed, 3 failed**, 4.35 s.
  The failures are historical Wave12/13/14 tests calling their pre-freeze
  `verify_commit1_blindness(None)` on a later checkout containing committed
  assessment modules. They fail for repository phase, not new learner behavior.
  No closed assessment was imported for scoring or rerun.
- Relevant historical source tests with those three phase-specific assertions
  deselected: **21 passed, 3 deselected**, 0.94 s.
- During source development initial runs had 11 then 2 failures; fixes were made
  before freezing. None was a fresh holdout attempt. Historical code/tests remain
  unchanged. No full-repository test pass is claimed.

## Resource boundary and provenance

Track B CLOSED: 0 model calls, 0 frozen-ledger debit.
`local_model_runtime.py` SHA256:
`5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781`.
No neural training, simulator collection, imagined neural transitions or
checkpoint changes. The symbolic authored-world public/private calls and AST
opcodes are separately reported; they are real CPU work, not model inference.
Runner caps: 120 s process CPU and 120 s wall, single attempt, local CPU only.
Measure CPU/wall/peak RSS; preserve partial data on failure. No grant increase.
Carry the registry's recorded frozen ledger 3128.309460455996 s used /
471.690539544004 s remaining, unchanged; this does not erase older contradictory
chronological balances in other documents or pretend that symbolic CPU is free.

Freeze four source/script/test files. Results commit may add fresh definitions,
artifacts and documentation only; all Phase1 source/script/test content remains
byte-identical. Never amend, rebase, reset, merge main, or modify old artifacts.
Push both configured remotes after the separate results commit.

## Frozen SHA256 digests

- `src/nexus/seed/wave15_support_gated_piecewise_learner.py`: `3ec2afe813c7a4d45338dc47e974af754161172a3fab4fe7bb104122f4d7ecef`
- `scripts/run_wave15_support_gated_assessment.py`: `ae18fc7dc8c0c3bd842567aa5495ecd06b0be8abe0a725067a520ad9024ec31b`
- `scripts/verify_wave15_support_gated_enumerator.py`: `8c3058878dc2658be5d6589fe6221fa391a2c78fd4235b3599a810aebbeb6925`
- `tests/test_seed_wave15_support_gated.py`: `3eeb70434b980a9b9f284d3102fac4ff645bf184aacdb6638b065f62c4b2c281`

