# Wave16 — peeled archive/unary single-shot results

**CLOSED: Developmental / Invalid (Failed Single-Shot Blind Gates; Preserved
Unamended).** All 270 cells completed, but cached-coverage replay failed.
This is an **invalid completed execution**, not an incomplete run or a valid
efficiency result. No post-result correction, relabeling, retry or main merge.

Base `9db4dc9492bd23ec053e11ba6f67404c3ce52f12`.
Code/protocol freeze `23e9ad949770dbc64721f3e233f2f239de723968`.
Branch `cursor/seed-wave16-peeled-archive-index-and-unary-completeness`.
[Protocol](NEXUS_WAVE16_PEELED_ARCHIVE_UNARY_PROTOCOL.md).

## Implementation and tests

Reuse Wave14 typed AST/library/report ownership and Wave15 residual/probe/cache
contracts. Add indexed cold composition, metered public verification, exact
point screening with deferred-branch restoration, and shared structural
unary/affix enumeration. Remove Wave15's early piecewise shortcut. Expected
O(1) hash access is explicitly distinct from bucket traversal and verification;
arbitrary-input end-to-end O(1) retrieval was not established.

Three historical tests now verify their original freeze commits instead of
requiring holdout absence in the later checkout. Historical learners, verifiers,
assessments and artifacts remain unchanged.

Before Commit1 the full requested Wave8–16 pytest range passed **83 tests,
zero failures, 25.47 s**. It covered all six cold wrapper paths, independent
size3/6/7 expression witnesses, source curriculum correctness/cost domination
including index construction, private isolation, deferred branch restoration,
archive metering, incomplete grids and standalone replay. This is not a claim
that every repository test ran. Earlier source failures were fixed before the
freeze; none was a fresh holdout attempt. The initial historical invocation had
54 passed/3 failed, corrected through the phase-aware test calls.

The passing tests missed empty-token semantics. They did not establish fresh
correctness; independent replay subsequently caught that omission.

## Single-shot suite and raw results

Only after Commit1, author 18 fresh w16f_* tasks: 3 base/literal, 2 relational,
5 subtree/L2, 2 piecewise, 4 archive and 2 OOG/ambiguous; three token-permutation
seeds ×five methods =**270 cells**. The new internal core prepends HEAD(x) to
REVERSE(x), with unary/affix and hierarchical embeddings, plus new endpoint,
length and stride-partition rules on tree-name tokens. No closed suite was
imported or rerun. Programs/statuses lock before four private checks.

Carry the earlier owner clarifications: Commit1 permits the required runner,
but no fresh definitions; an interleaved base task supplies the third archive
distractor while preserving 18 tasks. This is authored development, not an
independently curated confirmation set.

| Method | Correct /54 | Solvable prediction /48 | Work | Primitive steps | Cold flags |
|---|---:|---:|---:|---:|---:|
| Scratch | 42 | 36 | 552306 | 2095917 | 0 |
| Memoization | 42 | 36 | 553119 | 2098428 | 0 |
| Whole macro | 48 | 42 | 491487 | 1838562 | 3 |
| Typed without pruning | 48 | 42 | 469014 | 1724457 | 0 |
| Typed full | **48** | **42** | **459630** | **1712487** | **3** |

Correct outcomes include six expected refusals per method. Raw full costs are
below every baseline, but **invalid cached evidence cannot support an efficiency
claim**. Zero recorded false unique locks; all 198 unique programs replay their
saved public/private outputs correctly. Do not treat 270 correlated cells as
independent model replications: seeds only permute tokens on the same rules.

Two declared-solvable tasks fail in all three seeds for full and no-pruning:
`w16f_equal_ends_intro` (abstain, 16696 work) and
`w16f_last_prefix_distractor` (abstain, 10731 work).
The intended archive introduction failed; its delayed reuse therefore did not
test the registered introduction/eviction/reactivation chain. Full's three
cold flags instead occur in `w16f_piece_core_reverse`. Any-task flags must not
be presented as successful delayed archive transfer.

Full split outcomes/work/opcodes:
- Base/literals: 9/9; 93417; 359664.
- Relational analogy: 6/6; 67173; 254526.
- Subtree/L2: 15/15; 64329; 229029; maximum depth2.
- Piecewise: 6/6; 75477; 283722.
- Archive/distractors: **6/12**; 132153; 480903.
- OOG/ambiguity: 6/6; 27081; 104643.

All methods report zero OOG piecewise evaluations/opcodes and 3/3 ambiguous
refusals. The ambiguity case has two public channels whose guard rules agree
on public lengths but differ at a longer even length. Refusal identifies an
ambiguous interface; it does not establish general semantic uncertainty.

## Verification failure and focused diagnosis

The single standalone verifier returns **valid=false**, 270 replayed rows:
nine `coverage_replay` and nine `gate_snapshot` errors. Manifest, holdout hash,
Commit1 absence, Phase1 zero diff, frozen hashes, unchanged runtime and
lambda_count0 pass. Independent arithmetic confirms both cost identities,
archive receipts and saved summary sums, without collecting new outcomes.

The nine discrepancies are the last-prefix task for three macro methods ×three
seeds. A representative cached AST is
`APPEND_TOK(EvolvedMacro(TAIL(x)), ConstTOK(""))`.
Stored coverage includes row0, while interpreter replay gives empty coverage.
Every affected seed/method/AST is saved in the independent audit.

The interpreter deliberately treats empty-token APPEND/PREPEND as a no-op.
Wave16's fast cache instead constructs `value + ("",)` or `("",) + value`.
That optimization is **not mathematically equivalent** at this boundary.
The first-point helper contains the same unchecked affix construction.
Source tests used nonempty literal constants and missed this sentinel.

I also made an authored-fixture semantic error:
- The endpoint fixture treats two empty HEAD/LAST sentinels as equal; frozen
  TOK_EQ requires both operands nonempty.
- The even-LAST-prefix fixture emits an empty-string token for empty input;
  frozen PREPEND_TOK deliberately suppresses that token.

These intended one-guard/one-step targets disagree with their claimed typed
expressions on empty input. The latter creates a dynamic empty constant and
exposes the cache bug; the former can require an unsupported guard composition.
They are not fair tests of the intended constructions. **Do not relabel the
tasks, drop them, recompute adjusted accuracy or claim a model-quality failure.**
The unchanged registered result remains 48/54 and invalid.

The common core helper also emits an empty HEAD token when called directly on
empty input; its odd guards keep that boundary outside the scored core branch.
Static review additionally finds that the length-domain helper adds one for an
affix even when its token can be empty. Conservativeness of that index filter
is therefore not established at this boundary. No rerun quantifies its impact.

This run neither confirms nor refutes the broader cold-index/unary hypothesis.
Other replay successes and lower raw totals cannot upgrade it.

## Resources and immutable evidence

Experiment CPU **11.651129 s**, wall **11.673473 s**, within120 s caps.
Peak RSS65863680 bytes (**62.81 MiB**) on macOS. Source tests and verification
consume additional CPU and are reported separately. No neural inference,
training, physics simulator or checkpoint changes. **Track B:0 calls/0 frozen
debit**. Registry balance unchanged at3128.309460455996 used /
471.690539544004 remaining. Prior Wave15 symbolic CPU1.613301 s plus this
run totals **13.264430 s**, separately recorded rather than reset by branching.

Actual authored-world calls:5640 public /792 private evaluator. Reported
primitive steps9469851, plus10737 public final-verify steps outside the
historical main opcode identity. Archive work5421 /archive opcodes9597.
These are actual symbolic computation and interactions, not zero-cost work or
imagined neural control transitions. Saved-data replay is additional verification.

Artifact SHA256 digests:

- `artifacts/seed_wave16_peeled_archive_enumerator.json`: `b40fb724f999d5d80fb39cc00e7a328f2df15f4ecfd421e9e02100ca6528bbef`

- `artifacts/seed_wave16_rows.jsonl`: `f50cbfb0402476eaff45ba96cc408bbee8f4bd29a9b7e2cbca712c8be217e972`

- `artifacts/seed_wave16_attempt.json`: `34bdd93bba6a8404965bbf813ef53502aacf63a9528ffdb673d15971e4166e55`

- `artifacts/seed_wave16_verification.json`: `d69eec9f60f9294a9b4cd115803a9ecdcb039077f646852c9dba40e3cbf46f6f`

- `src/nexus/seed/mechanism_wave16_fresh_assessment.py`: `8aa0d9c9b565a5d03a78f6255cd96e15c7baddc64be4c01903af5c37b656d133`

The exclusive attempt marker, raw JSONL, full JSON, failed verification and
independent arithmetic audit are preserved. Runner and verifier both returned
nonzero. All Phase1 source/scripts/tests remain byte-identical. No amend,
rebase, reset, main merge, historical artifact edit or retry occurred.

## One next experiment

A **source-only differential semantic audit** of every fast cache and fixture
constructor, including length-domain abstractions, against the typed interpreter over exhaustively enumerated short
sequences and empty/nonempty token constants. Require exact agreement before
authoring another blind suite. Keep Wave16 closed; this invalid execution does
not justify an architecture expansion or another simulation.

