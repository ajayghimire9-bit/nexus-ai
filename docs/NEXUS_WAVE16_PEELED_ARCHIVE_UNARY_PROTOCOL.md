# Wave16 — peeled archive index and unary completeness

Pre-assessment code freeze. Branch
`cursor/seed-wave16-peeled-archive-index-and-unary-completeness`;
actual verified starting SHA `9db4dc9492bd23ec053e11ba6f67404c3ce52f12`.
GitHub and Origin both matched this SHA before branching; clean worktree.
Other checkouts and unrelated files are preserved.

## Physical two-commit boundary and prior clarifications

The owner previously resolved the identical Wave15 contradictions: allow the
required assessment **runner** before Commit1, forbid all fresh holdout
definitions; retain 18 tasks by interleaving a task from another split as the
third archive-aging distractor. This protocol carries those interpretations
forward. No new human answer is fabricated or represented as received.

No Wave16 fresh task definitions have been created, drafted or executed before
this freeze. The only matching assessment filename is the required runner
`scripts/run_wave16_peeled_archive_assessment.py`. Commit1 must not contain
`mechanism_wave16_fresh_assessment.py` or Wave16 result artifacts.
After this commit only, author a new 18-task w16f_* suite, run once and verify.
No Phase1 source/script/test changes between this commit and results.
The three repaired historical test files are also frozen and hashed below.

Waves12–15 remain **Developmental / Invalid (Failed Single-Shot Blind Gates;
Preserved Unamended)**. Never amend, rebase, reset or rescore closed suites.
No old learner, assessment, verifier, artifact, checkpoint or runtime is changed.

## Hypotheses and alternatives

1. One-step cold macro composition restores the active/cold solve-set invariant
   that failed in Wave15, including unary projections and affixes.
2. A common structurally ordered unary/affix atomic search removes gaps at size3
   and outer sizes6–7 without method-specific ordering.
3. Indexed candidate restriction saves full suite work and executed primitive
   steps while retaining full fresh accuracy.
Alternatives: verification/index construction outweighs savings; equivalent
public signatures hide useful programs; pruning still changes reachability;
the bounded grammar fails a new composition. Any such failure stays recorded.

Source tests are implementation evidence, not evidence of broad transfer,
neural learning, language understanding or learning-to-learn.

## Reused architecture and exact candidate semantics

Reuse Wave14 AST, interpreter, macro/MDL ownership, schema routines, report
contracts, and Wave15 residual support/cache/probe contracts. No duplicate
memory framework or mutation of imported modules. Label-blind public method
remains `solve_unfamiliar_task(self, env, public_budget)`. Static TOK constants
remain empty; output literals come only from public observations.

All five methods use the same enumerator and tier order. Size3 now includes
unary-of-unary. Generate bounded unary, affix and core CONCAT constructions,
including both operands through core size5; outer unary/affix layers reach
size6–7. Public length-delta feasibility is conservative, accounting for empty
projection clamps and variable-length fallback. Affix filtering requires
possible support on observed non-default rows; partial branch evidence must not
be removed just because another branch has a different suffix.

Order is AST size, expanded opcode/argument canonical structure, then AST key.
Signature dedup keeps the first structural representative. Tier0 retains the
old size boundary, followed by active macros, cold candidates, full shared
atomic search, then support-gated piecewise search. Wave15's early cached
piecewise certificate shortcut is removed. All actual evaluations are charged.

Active and cold macros both support bare, REVERSE, TAIL, INIT/DROP_LAST,
PREPEND_TOK and APPEND_TOK. Cached macro outputs allow exact outer-opcode
execution; tests compare cached outputs against the ordinary AST interpreter.
Repeated candidate/guard consistency checks are cached on identical public
pairs. Cache hits do not count as new AST executions.

## Archive indexes, safe incompleteness and accounting

Eviction at age3 stores guard truth-table signatures and transform output
signatures. Reuse the canonicalized existing universal reference panel plus
minimal palindrome/equal-endpoint witnesses (five sequences). Index guards by
truth signature with a positive-coordinate inverted lookup. Transform
signatures are bucketed by a conservative abstract output-length-delta domain;
unknown/variable-length domains enter a wildcard bucket.

Known token-renaming-invariant guard input patterns use hashed projection.
Literal-dependent guards and unknown input patterns retain safe candidates
and require public verification; a reference collision is not evidence of
equivalence. Transform lookup probes observed delta, delta−1, delta+1 and
wildcard buckets. Verify direct, reverse-peeled, affix-peeled and projection
possibilities against actual public outputs. Each cold macro body execution,
reference signature construction and hash probe has a separate receipt.

An exact one-public-point necessary test defers cold macros that cannot solve
the single-branch task through any permitted one-step wrapper. It chooses the
longest strict public input deterministically. A failed point test **never
discards** that macro: recover its complete partial support before piecewise
search. First-point results are cached; all actually executed wrapper trials
are charged. No new question or private result is used by this screening.

Reference/index construction is charged on the task that causes eviction.
Reactivation by macro ID uses a dictionary. Lookup is expected O(1) **per hash
access**, plus bucket traversal, collisions, public rows and AST work.
End-to-end verification and unknown-pattern fallback are NOT globally O(1).
This qualification is necessary; do not claim that a finite reference table
certifies arbitrary unseen programs or inputs at constant cost.

Cold public evaluations, including later piecewise rows and guards, use archive
work/opcode counters. Outer cached wrapper operations are charged once per
actual execution. Per-operator active admission checks are now charged as
gate work, for pruned and unpruned methods alike. The old shared-prerequisite-
only count understated these inspections; the work identity is unchanged.
Report source/reference work, public calls, final verification, private
evaluator calls and wall/CPU separately; no cost disappears during caching.

## Source tests and phase-correct historical tests

Exact command:
`PYTHONPATH=.:src:/Users/ajayghimire/Projects/nexus-ai/.deps
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 -m pytest -o addopts='' -q tests/test_seed_wave8*.py
tests/test_seed_wave9*.py tests/test_seed_wave10*.py tests/test_seed_wave11*.py
tests/test_seed_wave12*.py tests/test_seed_wave13*.py
tests/test_seed_wave14*.py tests/test_seed_wave15*.py
tests/test_seed_wave16*.py`.

**83 passed, zero failed, 25.47 s.** This is the full requested Wave8–16 range,
not a claim that the entire repository suite ran.

Included: all six cold composition paths; independent size3/6/7 witnesses;
shared canonical ordering; four delayed curriculum categories (guard, reverse,
tail, affix) with all tasks solved and cold reactivation on each delayed task;
lower aggregate gate/synthesis/work/opcode costs including their source/index
construction; full 18-task ×3seed ×5method source mini-suite with 54/54 full
correct outcomes and strict cost domination; OOG zero-piecewise/no-false-unique;
private isolation; unknown-pattern fallback; exact point/wrapper reuse; recovery
of deferred branch support; archive incremental metering; missing entire
seed/task/method and tampered cost/index receipts rejected; standalone AST replay
and independently summed summaries. Cost comparisons for the delayed curriculum
are over the entire equally weighted four-category block, not a guarantee that
every individual task is cheaper. All signature construction is included.

The initial Wave8–15 invocation had 54 passed/3 failed (4.70 s). Exactly three
historical tests incorrectly called their pre-freeze checker with None in a
post-assessment checkout. They now resolve and check their actual original
freeze SHA. No skip, historical data change or evaluator change. Intermediate
source development exposed real cost failures; those were fixed/tested before
fresh tasks exist, not hidden or treated as fresh assessment attempts.

## Locked fresh suite, gates and single attempt

After Commit1 only: 18 new w16f_* tasks, split counts 3 base/dynamic, 2 relational
analogy, 5 unassisted subtree/L2, 2 piecewise, 4 archive, 2 OOG/ambiguous.
For archive aging count the interleaved other-split task as the third distractor.
Seeds0/1/2, five methods, 270 required cells. Fresh tokens, rules/compositions
and public/private rows; no import or rescore of w12f_*–w15f_*.

Lock each program/status before four private checks. Correct outcomes include
refusals on two unsolvable/ambiguous cases per seed; also report solvable-only
prediction accuracy. Retain public probe records, ASTs, masks, index receipts
and private replay outcomes. Ambiguity may concern the public result channel;
do not equate channel refusal with semantic guard-uncertainty understanding.

Pass only if full solves all planned cases, every method has no false unique,
full has correct ambiguity and at least one cold reactivation per seed,
OOG abstains with zero piecewise evaluations/opcodes, and full suite work AND
primitive steps are strictly below EACH baseline. No cell dropping. Accuracy
failure invalidates the scientific screen regardless of cost gains.
Completeness/integrity failure and a valid execution with negative results
must remain distinct labels.

Runner creates an exclusive one-attempt marker and incremental fsynced rows.
Cap: 120 s CPU and 120 s wall, within existing standing authority; no increase.
On timeout/error preserve partial rows and an incomplete record. No automatic
retry. Verifier replays ASTs, masks, archive receipts, dual identities, full grid,
original runtime, frozen files, holdout hash and physical Commit1 absence.

## Resource and provenance boundary

Track B CLOSED, 0 model calls and **0 s frozen-ledger debit**.
Runtime SHA256:
`5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781`.
No neural training/inference, checkpoint replacement or physics simulator.
Authored symbolic-world reads and interpreter operations are actual computation
and must be counted. Measure run CPU/wall/peak RSS; source test and verifier
costs are additional. Registry frozen balance is carried unchanged:
3128.309460455996 used /471.690539544004 remaining. Wave15 additionally recorded
1.613301 s symbolic experiment CPU, not erased by changing branches.
Older conflicting ledger chronology is not silently reset or replaced.

Commit implementation/protocol first. Results commit adds fresh definitions,
raw artifacts and report only, with zero diff on all frozen code/scripts/tests.
Preserve old evidence; push both origin and github; never merge main.

## Exact SHA256 freeze

- `src/nexus/seed/wave16_peeled_archive_unary_learner.py`: `744ea7e31bb6438d77f428b0b7a36bd9d3410ea8343dec8853a87cb41b600297`
- `scripts/run_wave16_peeled_archive_assessment.py`: `8c4488bc2042d1fccef1b469b4c4fc42191a9dceeb18fb5b7cf368b429b11701`
- `scripts/verify_wave16_peeled_archive_enumerator.py`: `db59e56ffdae7110fdaa11f9750df9ac3abc6b9783ff1afff4251cde0ad1a882`
- `tests/test_seed_wave16_peeled_archive.py`: `0cce72c54356091da3bd2258a34fad0f0538717c17d46d8e257868ebb385448e`
- `tests/test_seed_wave12_subtree_opcode.py`: `d757474f2ae459d60999490d6397e120b3c60b3a52b50dcdb66c5aa8f22d1cd5`
- `tests/test_seed_wave13_bounded_subtree.py`: `827a459945267da549e71127c8295bb4e0d63562b535c27b898b4c8321a74d51`
- `tests/test_seed_wave14_piecewise_archive.py`: `e9ebcf550955101581b03875f01b38cc7ea9e75d5127cf52cd3d6d4de8bf4178`

