# Wave 15 — single-shot support-gated piecewise results

**CLOSED: Developmental / Invalid (Failed Single-Shot Blind Gates; Preserved
Unamended).** Execution is complete and internally valid; the scientific
accuracy gate FAILED. Do not reopen w15f_* or repair the frozen implementation
using these outcomes.

Starting revision `ea176084de46ec428806ffd1064ff728a3128501`.
Execution / Commit1: `4810ae6533ed970a330b09261b1ce4bf511b9a08`.
Branch: `cursor/seed-wave15-pre-piecewise-residual-support-abort`.
[Protocol](NEXUS_WAVE15_SUPPORT_GATED_PIECEWISE_PROTOCOL.md).
No amend, rebase, reset, old suite rerun or main merge.

## What ran

After the physical Commit1 freeze, a new evaluator module introduced 18 tasks
and shuffled fresh token vocabularies at seeds 0,1,2. All five methods ran all
tasks: **270/270 cells**, no retry. The fresh core is left rotation under odd
parity, embedded and hierarchically wrapped; the source mini-suite used right
rotation under even parity. New literal, length-relation, palindrome-tail/init
and separator-interleaving compositions retain the same finite typed language.
This is authored developmental assessment, not independently curated broad
generalization or untouched scientific confirmation.

The owner resolved both registration contradictions before Commit1: the runner
is allowed in Commit1; only fresh holdout definitions are forbidden. Archive
introduction, two same-split distractors and reuse retain four archive tasks,
with a base-split task interleaved as the third non-use episode.
Split counts remain 3/2/5/2/4/2. Public piecewise rows include at least four
examples per parity branch and separate confirmation rows.

## All-method outcomes and dual costs

| Method | Correct outcomes /54 | Solvable prediction /48 | Work | Primitive steps | Cold archive |
|---|---:|---:|---:|---:|---:|
| Scratch | 39 | 33 | 111852 | 313002 | 0 |
| Persistent memoization | 39 | 33 | 112509 | 315417 | 0 |
| Whole macro | 51 | 45 | 68136 | 184017 | 3 |
| Typed, no pruning | 54 | 48 | 72456 | 200094 | 0 |
| Typed full | **51** | **45** | **60510** | **161604** | **3** |

Correct outcomes include six expected OOG/ambiguous refusals, so 51/54 is
**not** 51 correct prediction programs. Full is 45/48 on solvable cases.
All methods have zero false unique locks and 3/3 correct ambiguous refusals.
No-pruning achieves the strongest accuracy. Full's lower costs do not compensate
for failing an accuracy gate. Cross-wave cost ratios are not controlled
comparisons because the task suites differ.

Full costs are below every baseline: 45.90% less work than scratch, 46.22% less
than memoization, 11.19% less than whole-macro and 16.49% less than no-pruning.
Primitive steps are also strictly lower. These are descriptive suite totals,
conditional on unequal achieved accuracy.

## Split-level saved results

Full correct/work/primitive steps:
- Base/dynamic literals: 9/9; 3264; 7164.
- Relational analogy: 6/6; 10413; 27339.
- Subtree/L2: 15/15; 23409; 68007; maximum hierarchy depth 2.
- Two-branch piecewise: 6/6; 4722; 13182; per-cell work 696 or 878,
  both below 1500.
- Archive/distractors: **9/12**; 9543; 20436; reuse succeeds 3/3.
- OOG/ambiguity: 6/6; 9159; 25476.

Detailed per-task/seed/method ASTs, errors and costs are in the JSON and JSONL.
The same task fails across all three seeds:
`w15f_even_two_init_distractor`, full abstain versus expected unique,
1407 work each. Scratch, memoization and whole-macro also abstain;
no-pruning solves it in all three seeds. Token permutations are not independent
neural-model replications; do not construct a generalization confidence interval
by treating 270 correlated cells as independent experiments.

Full OOG work is 3021 per seed versus scratch 2882 (4.82% extra).
**Every method has zero piecewise evaluations and primitive steps on the OOG
case.** All pass the OOG refusal gate. Full delayed palindrome reuse is 683 work
and reactivates a cold operator once per seed.

## Focused failure diagnosis from saved evidence and source

The missed transform is two applications of INIT/DROP_LAST on even lengths.
The successful no-pruning AST is:
`DROP_LAST(EvolvedMacro(DROP_LAST(x)))`, guarded by even parity.
Its retained single-step operator permits that composition in the macro beam.

In the frozen atomic enumerator, the size-3 candidate list includes CONCAT and
literal affixes, but not unary-of-unary programs. Its subsequent loop starts at
size 4. Thus the supposedly available typed expression can fall through a
search-generation hole after the useful operator is pruned. Cold discovery
also does not apply the active wrapping beam to every cold sequence operator.
These static observations and the saved successful AST support a
search-completeness / pruning-interaction diagnosis; they do not prove every
aspect of the failure causally. No new evaluation or code repair was run.

The supported result is narrower: cached support gating avoids this suite's
unsupported OOG piecewise search, and retained macros enable low-cost piecewise
solutions, but full correctness did not survive the new distractor.
There is no demonstrated learning-to-learn breakthrough.

## Verification and tests

Before Commit1:
- Wave15 focused tests: **21 passed**, 3.29 s.
- Wave11–14 relevant source tests: **21 passed, 3 deselected**, 0.94 s.
- Earlier combined invocation: **42 passed, 3 failed**, 4.35 s. The three
  historical failures assume old pre-freeze checkouts with no committed holdout
  module; they are documented rather than edited or hidden.
- Initial source-development failures were corrected before freeze, never on
  these fresh outcomes. No full-repository pass is claimed.

Single-shot commands:
`python3 scripts/run_wave15_support_gated_assessment.py`;
`python3 scripts/verify_wave15_support_gated_enumerator.py`.
Use the protocol's existing-dependency PYTHONPATH and single-thread settings.
Runner and verifier each return nonzero because the scientific screen fails.
Verifier output: **valid=true, 270 replayed rows, scientific_gates_passed=false**;
all AST/mask replays, grid, independent summary sums, cost identities, Commit1
holdout absence, Phase1 zero diff, file hashes, runtime hash and lambda_count=0
checks pass. Valid data is distinct from a passing scientific result.

A separate read-only Python arithmetic audit recomputed all cost identities,
per-method summaries, cell sets, solvable accuracy, calls and failure IDs.
It reports no discrepancies. No learner or evaluator was rerun in that audit.

## Resources and immutable evidence

Main experiment CPU **1.613301 s**, measured wall **1.618624 s**, within the
120 s CPU/wall caps. Peak RSS 62849024 bytes (**59.94 MiB**) on this macOS host.
Additional source tests and standalone evidence verification consume CPU too;
their times are separately reported above, not included in the experiment timer.
No model inference, neural training, physics simulator or imagined neural
transitions. Track B is closed; frozen-ledger debit **0**. The carried registry
balance remains 3128.309460455996 used /471.690539544004 remaining.
This does not imply the symbolic work consumed zero compute.

Across methods: **5604 authored-world public reads**, **816 private evaluator
calls**, **1174134 reported primitive steps**, plus **10578 public final-verify
primitive steps**. The retained cost contract reports final verification
separately. These are pure symbolic authored-world evaluations; do not
misrepresent them as zero interactions or neural control episodes.
Verification replays are additional evidence-checking work, not fresh outcomes.

Artifact:
`artifacts/seed_wave15_support_gated_enumerator.json`,
SHA256 `4158530927bfb789cff53b3cb2f27858e9ba5432e19ba5a91fc57b8c6f848992`.
Raw rows:
`artifacts/seed_wave15_rows.jsonl`,
SHA256 `9cffea06bc404a932e2187ebaf6551d0fb58311023545d83071fd350b7ebbe00`.
Holdout SHA256:
`6837dab46a9b69d0a8f199d0fd7b06365f51676c3e088c3ab3b40fe28b90be94`.
Attempt, standalone verification and independent audit are separate JSON files.
Original Wave14 artifact hash and runtime hash are unchanged.

## Limits and one next experiment

The precommitted cached-piecewise scheduling optimization means this is not a
pure abort-only ablation or an unchanged exhaustive Tier3 order. Archive
candidate discovery remains linear; O(1) end-to-end lookup was **not** delivered.
The ambiguous case also duplicates result channels, so successful refusal
does not isolate uncertainty about two agreeing guards. Relational source roles
are inherited finite schema routines, not unrestricted cross-domain learning.

**One next experiment:** a source-only grammar-completeness audit comparing
active, cold and scratch enumeration on bounded unary compositions, with
independent exhaustive expression witnesses. Test whether pruning changes which
in-grammar programs can be constructed before considering another fresh suite.
Do not reopen this suite or launch that experiment in this branch.

