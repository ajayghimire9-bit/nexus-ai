# Wave17 — exact interpreter cache and boundary invariance: results

**Complete, valid single-shot execution; failed preregistered efficiency screen.**
Closed as **Developmental / Invalid (Failed Single-Shot Blind Gates; Preserved
Unamended)**. Here the historical umbrella label means the overall improvement
screen failed; it does **not** mean semantic replay failed. All270 saved cells
pass independent verification. The fresh suite is closed: no repair or retry.

## Provenance and physical separation

- Branch: `cursor/seed-wave17-exact-interpreter-cache-and-boundary-invariance`.
- Actual clean base: `8738029a1f06d796a2b1d3aefbe8b835d65801da`.
- Tested implementation/protocol freeze:
  `4f4deaa6978292d6f2f1e74c8f6c38b4bf215ed6`.
- [Frozen protocol](NEXUS_WAVE17_EXACT_CACHE_BOUNDARY_PROTOCOL.md), SHA256
  `76c1f6c39d973c97e3113e9a28a77ff237cb52b60a1d08ac4a2c611ef99ae89d`.
- Fresh definition SHA256:
  `e60532760a13847f720ee37bcdbdb9a3d92c5b425703d9368040d9f7709eb39a`.
- The fresh module and this results document were absent from Commit1. The
  explicitly allowed runner is the sole `*wave17*assessment*` filename exception.
  No claim of literal filename-pattern absence is made.
- All Phase1 learner/script/test files retain their exact frozen hashes. No
  amend, rebase, reset, historical assessment rerun or main merge occurred.

The [phase-boundary receipt](../artifacts/seed_wave17_phase_boundary_audit.json)
and [result manifest](../artifacts/seed_wave17_results_summary.json) record
hashes, source/data dependencies, per-task/per-seed arithmetic and resources.
The result commit is the separate Git commit adding this report; no circular
self-commit hash is embedded in the report.

## Implementation and pre-freeze checks

Reused the existing immutable typed AST, macro/MDL ownership, five methods and
cost contracts. The local Wave17 extension adds exact task/boundary caches,
interpreter-derived masks, bounded observation-gated FILTER/MAP/DEDUP nodes,
typed integer and canonical state-record inputs, public-input guard clarification,
lock-only cold restoration and multi-task MDL tenure. No neural runtime changed.

The owner-requested three surgical fixes were completed **before** Commit1.
All **108/108 Wave8–17 tests passed, zero failures,174.91s**. The exact command
and hashes are in the frozen protocol. Tests include boundary differential
cases, archive reachability, active clarification, loop/state synthesis, cost
accounting and the source18-task comparison. Its source full54/54 result beat
all four baselines on both costs. Earlier failed source iterations remain in
the [source receipt](../artifacts/seed_wave17_source_preflight.json); no failing
efficiency gate was waived. The117.79s source comparison is part of174.91s,
not additional time. Engineering-test CPU was not metered.

After freeze, authored new rules/vocabulary and validated explicit fixture ASTs.
The first fixture-only validation passed; before **any learner execution**, two
public priority/guard witnesses were added (even palindrome and odd equal-endpoint
non-palindrome). Both authoring snapshots and validator receipts are retained.
This is transparent post-freeze fixture construction, not a post-outcome change.

Executed exactly once each:

```text
python3 scripts/run_wave17_exact_cache_assessment.py
python3 scripts/verify_wave17_exact_cache_enumerator.py
```

The standalone verifier returned0, `valid=true`, `errors=[]`, replayed270 rows.
It checks the locked complete grid, fixture semantics, public/private program
outputs, coverage masks, cold receipts, budgets, both cost identities, split
summaries and payload digest. It does not rerun the learner. No repeat assessment
was made after learning that the efficiency gate failed.

## Fresh results

Correct outcomes include unique-task solutions, correct OOG abstention and
correct ambiguity declarations. They are not54 independent accuracy samples.

| Method | Correct outcomes/54 | Total work | Primitive opcode steps | Cold task flags |
| --- | ---: | ---: | ---: | ---: |
| equal_typed_scratch |51|4,828,147|13,627,839|0|
| ordinary_persistent_memoization |51|4,831,048|13,641,024|0|
| nexus_whole_macro_only |54|3,678,145|10,716,310|12|
| nexus_typed_without_pruning |54|3,705,610|10,847,898|0|
| nexus_typed_full |54|3,693,757|10,793,719|12|

Full solved48/48 unique task-seed outcomes, with192/192 private I/O checks;
correctly abstained3/3 OOG and declared3/3 ambiguous. False unique locks0;
cached coverage mask errors0; maximum learned hierarchy depth2. The independent
verifier replayed the saved coverage records, including2,119 full-method records.
OOG piecewise evaluations and piecewise primitive steps were both0.

The delayed archive task specifically reactivated a cold macro in **3/3** seeds.
The12 suite-wide flags also include other tasks; they are not12 delayed-reuse
replications. The interleaved base task supplies the third aging distractor,
preserving the agreed18-task count.

**Full exceeds whole-macro by15,612 work units (+0.424453%) and77,409 primitive
steps (+0.722348%).** These two strict comparisons fail the locked gate.
Lower costs against scratch, memoization and no-pruning cannot override them.

| Full-method split | Correct outcomes | Work | Opcode steps |
| --- | ---: | ---: | ---: |
| Base/dynamic literals |9/9|45,732|167,448|
| Integer/relational analogy |6/6|6,261|9,087|
| Unassisted subtree and L2 |15/15|1,910,463|5,200,005|
| Priority multi-branch |6/6|1,416,330|4,249,029|
| State/distractors/delayed archive |12/12|109,938|457,623|
| OOG/ambiguous |6/6|205,033|710,527|

All individual task/method/seed rows and ASTs are preserved in
[raw JSONL](../artifacts/seed_wave17_rows.jsonl), the
[full result](../artifacts/seed_wave17_exact_cache_enumerator.json), and the
[compact independent summaries](../artifacts/seed_wave17_results_summary.json).

## Focused diagnosis from saved traces only

The intended shared size5 core was
`FILTER_NEQ(ROT_RIGHT(TAIL(x)), "vexel")`, with different prepend/append
wrappers and a third fresh wrapper. This construction did **not** guarantee
the same literal core would appear in independently synthesized ASTs.

For seed0, both whole-macro and full instead selected factorizations including:

```text
Task1: FILTER_NEQ(DROP_LAST(PREPEND_TOK("nemi", SWAP_ENDS(x))), "vexel")
Task2: APPEND_TOK(DROP_LAST(FILTER_NEQ(SWAP_ENDS(x), "vexel")), "yavo")
Task3: FILTER_NEQ(DROP_LAST(PREPEND_TOK("porel", SWAP_ENDS(x))), "vexel")
```

The shared intended subtree is not literally present in both learned trees.
Task3 costs211,720/575,704 work/opcodes for whole-macro, versus211,723/575,707
for full. Later reversal and projection reach depth2, but do not recover the
missing suite-wide efficiency gain. This is evidence of a syntactic extraction
limitation on these authored examples, not proof that the programs are equivalent
on all inputs. Guard conditions and empty/boundary semantics matter.

## Resources and accounting

- Assessment:165.303840 CPU seconds /165.577548 wall seconds, below both200s caps.
- Peak assessment RSS154,927,104 native macOS bytes (147.75MiB).
- Fixture validations:2.621557 and2.616493 CPU seconds; both retained.
- Standalone verification:4.235353 CPU /4.241264 wall seconds.
- Total newly measured symbolic CPU174.777243s; prior Wave15+16 symbolic
  CPU13.264430s; cumulative measured symbolic CPU188.041673s.
- Python3.13.5, macOS26.6.2 arm64; full environment details are in the artifact.
- Zero model calls, simulator steps, neural updates and Track B debit.
  `local_model_runtime.py` retains SHA256
  `5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781`.
- The frozen ledger remains3128.309460455996s used /471.690539544004s remaining,
  as explicitly required by the protocol. Symbolic CPU is disclosed separately,
  not represented as free computation or a fresh grant. Earlier engineering
  CPU is unavailable; the measured symbolic subtotal is not total project CPU.

## Interpretation and one next recommendation

Wave17 repairs the measured boundary/cache correctness failures and demonstrates
these typed symbolic mechanisms on a narrow authored suite. It **does not** pass
the complete improvement screen. The three seeds permute vocabulary on shared
rules; they are not independent learned-model replications. Work and opcode
counters are related proxies, not two independent scientific confirmations.
Supplied integer rules and state-token policies are not broad mathematical,
conversational or cross-modal intelligence. Learning-to-learn remains unestablished.
Waves12–16 remain closed and unmodified, as does Track B.

**One recommendation:** conduct a source-only audit of guarded, boundary-safe
canonicalization before MDL subtree extraction, using saved traces and synthetic
witnesses to test whether equivalent factorizations can expose reusable structure
without changing semantics. Do not rerun this fresh suite or start that audit
as another experiment in this branch.
