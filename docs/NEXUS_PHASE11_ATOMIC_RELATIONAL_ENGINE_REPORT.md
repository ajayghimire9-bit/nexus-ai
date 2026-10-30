# NEXUS Phase 11 — autonomous program acquisition and reusable relational abstraction (NOT LOCKED)

## Revisions, machine and scope

| Item | Value |
|---|---|
| Start | `99d45dd` |
| Commit 1: core, compiler, synthesizer, abstraction, protocol | `1a9d117` |
| Generic bug fix before the training freeze; Stage A rerun | `7751696` |
| Stage A / B artifacts, evaluation amendment and freeze, before any target opened | `c35f1cd` |
| `main` | `d7ac8c5`, untouched |
| Machine | Apple M4, 16 GB RAM, macOS 26.6.2 |
| Runtime | CPython 3.13.5, pure single-threaded Python, no pretrained weights, no external API |
| Engines | DuckDB 1.1.3, SQLite 3.50.4, sqlglot 26.16.4 |

- **Protocol:** `docs/NEXUS_PHASE11_PROTOCOL.md`, including its amendments section.
- **Raw data:** `artifacts/agi11_*`, `artifacts/agi11_stageA/`, `artifacts/agi11_stageB/`, `artifacts/agi11_eval/` and
  `artifacts/agi11_report_data.json`.

**The question.** Can NEXUS construct executable functions absent from its initial library, keep them through experience, and
improve on fresh tasks over an equally expressive solver without them, with developer code frozen?

## Answer

**Partly, yes, in one specific and narrow way.**
- **Construction:** from its own solved source programs, NEXUS built a **pure next-state upsert** function,
  `union(anti_join(P0, P1, k, k), P1)`. It did so independently in both streams (F4 in rep0, F6 in rep1).
- **Transfer:** on the 24 fresh withheld compositions, with the library frozen, the fixed search with the library (F1) verified
  **8 / 24** against **5 / 24** without it (F0), in both streams, with **0 losses**.
- **Attribution:** all 3 gains are the W8 compositions (upsert, then coalesce), and each verified F1 path **calls the learned upsert
  function**.

**But the pre-registered verdict is "mixed", not "positive".** F1 also made one more wrong submission than F0 (5 against 4).

**Elsewhere, no benefit:**
- the library plus learned guide versus the guide alone (L1 − L0) is **+1 / +1, null**;
- the learned guides gave no benefit at all (L0 = F0 on completions), having been fitted on only 13–14 Stage B records;
- most of the other learned functions are near-duplicate coalescing shapes, and none of them was used on a held-out success.

**Wrong-submission rates are high** (4–5 wrong per arm of 24 targets). Most come from threshold constants that visible and evidence
data cannot pin down.

## 1. Gates reached

| Gate / objective | Status |
|---|---|
| Stage 1 readiness | **met**, at 282 of 300 s. DuckDB conformance 60 / 60; observational-refinement regressions pass; one grammar and one size limit for every arm; complete Stage 4 plan |
| Source-learning gate (≥ 2 distinct non-wrapper functions per stream) | **met** in both streams. They reduce to 4–5 mechanisms; the semantic overlap is disclosed |
| Stage A, 2 × 60 source tasks | **complete**, after a disclosed generic bug fix and rerun |
| Stage B, 2 × 80 transfer-training tasks | **incomplete**: 40 and 42 reached within 450 s; 14 and 13 verified records |
| Suite 1, 24 withheld compositions × 7 arms | **complete**: 168 / 168 rows, 0 missing |
| Suite 2, 16 development tasks | **complete**: ingestion audit 16 / 16; I/O runs 10 posable tasks × 7 arms; 6 not posable |
| Suite 3, External_Holdout_24 | **NOT READY**: BIRD-Critic references are released only by email (not authorised); no task content opened |
| Polars / PySpark native adapters | **not implemented**, a coverage gap |
| Wide-DAG repair of the Phase 10D kind | **not tested** in Phase 11; this is a new I/O synthesis world |

## 2. The frozen core and what the machinery does

**Human-written** (`src/nexus/de_phase11/`): everything except the learned functions and guides.
- **core11:** typed relational core with a published inventory: NULL / ERR / three-valued semantics, lazy branch, explicit casts,
  JSON, bag folds, deterministic rank, joins, union.
- **sql11:** native DuckDB and SQLite compiler.
- **synth11:** the synthesizer.
  - Best-first relational search with lazy pairs and pool escalation.
  - Deductive projection / aggregation solving.
  - A vectorised scalar pool with recoverable observational-equivalence (OE) classes and refinement.
  - Deductive branch unification.
  - Declared heuristics: join overlap, fold keys, constant mining.
- **abstr11:** typed anti-unification, admission, classification.
- **guide11:** production-cost fitting.
- **tasks11, manifest11:** task generator (hidden reference programs) and seed namespaces.

**Learned:** the library bodies (Stage A), and the `G_A0` / `G_M` production-cost tables (Stage B).

**Not learned:** roles (none are used), the operator inventory, the search procedure, the abstraction algorithm and the evidence
policy (one fixed request).

## 3. Learned executable functions

All functions were built by abstr11 from NEXUS's own verified source solutions, each with ≥ 3 distinct verified source projects, and
admitted on separate validation batches. Sizes are expanded size, with parameters counted as size-1 placeholders.

**rep0** (60 tasks, 58 verified, **0 wrong**; per family 7–8 / 7–8; upsert 6 / 8).

| Fn | Class | Body | Size | Support families | Acquired after task | Later uses (Stage A / Suite 1) |
|---|---|---|---|---|---|---|
| F0 | multi | `branch(isnull(col p0), p1, col p0)` (coalesce) | 5 | coalesce, preagg | 30 | 0 / 0 |
| F1 | multi | `branch(isnull(col p0), p1, col p2)` | 5 | coalesce, preagg | 30 | 0 / 0 |
| F2 | multi | `branch(isnull(col p0), col p1, col p0)` | 5 | coalesce | 30 | 0 / 0 |
| F3 | multi | `branch(isnull(col p0), 0, col p1)` | 5 | preagg | 40 | 0 / 0 |
| **F4** | multi | **`union(anti_join(p0, p1, (p2), (p2)), p1)`** (pure next-state upsert) | 7 | upsert | 40 | 3 / **3** |
| F5 | multi | `cast(json(col p0, p1), int)` | 4 | json | 40 | 0 / 0 |
| F6 | multi | `branch(isnull(col p0), 0, col p0)` | 5 | preagg | 50 | 0 / 0 |
| F7, F8 | multi | `cast(json(col p0, 'b' / 'd'), int)` | 4 | json | 50 | 0 / 0 |
| F9 | multi | `filter(p0, col p1 > p2)` | 5 | filtmap | 60 | 0 / 0 |
| F10 | multi | `branch(col p0 = p1, p2, 0)` (conditional-sum arm) | 6 | condsum | 60 | 0 / 0 |
| F11 | wrapper | `anti_join(p0, p1, (p2), (p2))` | 5 | upsert | 60 | 0 / 0 |

**rep1** (60 tasks, 54 verified, **2 wrong**: one flag, one condsum; 4 unsolved: three upsert, one preagg).

| Fn | Class | Body | Notes |
|---|---|---|---|
| F0–F4 | multi | the same five coalescing variants | — |
| F5, F7, F8 | multi | JSON extract-and-cast | — |
| **F6** | multi | **the same upsert body as rep0's F4** | acquired after task 40; 2 Stage A uses and **3 Suite 1 uses** |
| F9, F10 | multi | `filter(p0, col p1 > p2)` and `filter(p0, col p1 = p2)` | F9: 2 Stage A uses |

**How substantive they are (my reading):**
- **The upsert** is a genuine two-operator relational composition (anti-join feeding a union with shared key binding). It is the
  only function behind a held-out gain. It is new to NEXUS, not new to computer science: a human-designed MERGE / upsert idiom.
- **Coalescing variants** are small two-operator scalar macros. They are near-duplicates: alpha-distinct, but F0 subsumes several.
- **JSON-cast** is a two-operator pipeline. F7 and F8 hard-code a key, an overfitting artefact.
- **`filter(p, col > lit)` / `filter(p, col = lit)`** are predicate-shaped filters, close to direct primitive wrappers.
- **F11** is a direct primitive wrapper.
- **No composite function** (one calling an earlier function) was admitted.
- **Not discovered** in either stream: a dedup / rank function and a pre-aggregated-join function. The source solutions for preagg
  were join-then-aggregate programs, and the abstraction kept only their coalescing piece.

## 4. Suite 1: 24 fresh withheld compositions (one-use 113000–113023, held-out names)

Each arm uses the same core, refinement, evidence policy (1 request), verifier and work caps (1,000 pops / 150,000
micro-evaluations / 5,000 full checks). Verification is native on DuckDB, against 2 hidden batches.

| Arm | Verified | Wrong | Submitted | Pops | Micro-evals | Full checks | Search wall (s) | SQLite native OK |
|---|---|---|---|---|---|---|---|---|
| F0 fixed, no library | 5 | 4 | 9 | 7,151 | 1.12 M | 91.6 k | 10.1 | 5 |
| F1_rep0 fixed + library | **8** | 5 | 13 | 6,649 | 1.09 M | 84.4 k | 22.0 | 8 |
| F1_rep1 | **8** | 5 | 13 | 6,590 | 1.11 M | 86.0 k | 19.7 | 8 |
| L0_rep0 guide, no library | 5 | 2 | 7 | 9,112 | 0.63 M | 108.0 k | 6.7 | 5 |
| L0_rep1 | 5 | 2 | 7 | 8,748 | 0.65 M | 108.8 k | 6.3 | 5 |
| L1_rep0 guide + library | 6 | 2 | 8 | 9,890 | 0.49 M | 101.6 k | 24.2 | 6 |
| L1_rep1 | 6 | 2 | 8 | 9,868 | 0.46 M | 102.6 k | 20.1 | 6 |

**Verified by composition** (3 each, all arms): W6 (json + coalesce) 3 / 3 and W4 (json → flag) 2 / 3 everywhere. W8
(upsert → coalesce) is **3 / 3 for F1, 1 / 3 for L1, 0 / 3 for F0 / L0**. W1, W2, W3, W5 and W7 are 0 / 3 everywhere.

**Pre-registered contrasts:**

| Contrast | rep0 | rep1 | Gains | Losses | Verdict |
|---|---|---|---|---|---|
| F1 − F0 | +3 | +3 | T113007, T113015, T113023 (all W8, all via the upsert function) | 0 | **mixed** (+1 wrong) |
| L1 − L0 | +1 | +1 | T113015 | 0 | **null** |
| L0 − F0 | 0 | 0 | — | — | — |

**Wrong submissions:**
- W4 T113003: wrong in all arms.
- W7 T113006 / 014 / 022: wrong in F0 and F1, abstained in L0 / L1. A threshold-label constant agrees on every visible and evidence
  row.
- W3 T113018: wrong in F1, L0 and L1; F0 did not submit.

**Efficiency:** the library arms spend about twice the search wall time of F0 (library-argument generation) at a similar pop count.
Total training cost: Stage A 72 + 98 s, Stage B 200 + 201 s.

**Comparator:** the strongest Phase 10F / 10G atomic solver was **not applicable**. It repairs Phase 10D legacy DAG projects, while
Phase 11 tasks are I/O synthesis over a new core, so this is old-language coverage, not a learning comparison.

## 5. Suite 2: the 16 Phase 10C / 10E development tasks (diagnostic)

**Ingestion of the legacy text as written** (parse → bind → represent → native → conformance):

| Outcome | Tasks |
|---|---|
| Reaches conformance | **5**: T05, T09, T11, T15, T16 |
| Stops at represent | T03 (CASE arms mixing types), T04 (multi-table), T07 (JSON operator), T08 (int / str arithmetic: the text divides string columns), T10 (DISTINCT ON) |
| Stops at bind | T02 (CTE names), T06 (MERGE target table not provided) |
| Stops at parse | T01 (dbt Jinja; no renderer in Phase 11) |
| No SQL front end | T12, T13, T14 (PySpark, Polars, Scala) |

**I/O synthesis.** T02, T04, T06, T07, T13 and T14 have no reference repair and are not posable.

| Arm | Verified | Wrong |
|---|---|---|
| F0 and both F1 | **4 / 10**: T05, T09, T10, T12 | 2 (T03, T16) |
| L0 / L1 | 3 / 10 (lose T09) | 2 |

- **Prior labels:** T05 is vacuous and T11 invalid; T09 is the genuine repair.
- **Caveat:** T10 and T12 (latest per key) verify here as I/O synthesis from examples, not as repairs of the legacy code.
- **History unchanged:** Phase 10C's native ingestion was 0 / 16, with one genuine repair behind a human adapter.

## 6. Coverage

| Engine | Conformance fixtures | Notes |
|---|---|---|
| DuckDB | **60 / 60** | — |
| SQLite | 58 / 60 | JSON number / boolean text, declared; every verified Suite 1 submission also ran correctly natively on SQLite |
| Polars, PySpark | — | not implemented |

**Compiler disclosures:**
- division and modulo by zero are guarded explicitly;
- folds compile to GROUP BY with monoid aggregates;
- rank compiles to ROW_NUMBER with an all-column tie-break;
- upsert is only its union / anti-join expression; no MERGE is emitted.

## 7. Wrong submissions, every stage

| Stage | Wrong / submitted |
|---|---|
| Stage A | rep0 0 / 58; rep1 2 / 56 |
| Stage B | rep0 0 / 14; rep1 0 / 13 |
| Admission | 0 rejections for validation failure (every admitted function reproduced its validation batches) |
| Suite 1 | F0 4 / 9; F1 5 / 13 (each stream); L0 2 / 7; L1 2 / 8 |
| Suite 2 | F0 / F1 2 / 6; L0 / L1 2 / 5 |

There is no zero-error guarantee.

## 8. Disclosures

- **Development history:** the synthesizer was iterated on development fixtures over about 25 metered runs in Stage 1, with large
  design changes (lazy evaluation, pair tokens, a unified cost order, diagonal realisation).
- **Stage A rerun:** the bug fixed between the runs was a typing bug in library literal arguments. Run 1 is preserved.
- **Pre-opening amendment:** full checks became a work cap, caps were lowered, and library-argument enumeration was bounded.
  Development timing had shown hardware-dependent wall-bound searches. Applied to every arm, with no library, guide or task changed.
- **Stage B:** it ran at half the planned task count, so the guides are weak.
- **Task-world assumption:** thresholds lie among quantile constants.
- **Uncharged work:** source editing, file reading, git and ledger bookkeeping.

## 9. Budget, ledger, protection, tests

- **Budget:** **1,161.6 of 1,800 s** (s1 282.5, s2 306.0, s3 402.1, s4 156.7, s5 14.3); child CPU 1,158.3 s.
  - The older surplus (925.9 s) was not touched.
  - 53 metered rows: 47 complete, 5 failed, 1 timeout. The failed and timed-out rows are failed development tests and debugging
    runs, all charged.
- **Ledger:** `python scripts/agi11_ledger.py verify` passes the Phase 11 section and runs the frozen 10C–10G verifier, which also
  passes. The hash chain is intact.
- **Protection:** 0 violations; 2,775+ frozen Phase 1–10G files unchanged; checkers v1–v5 match their pins; `main` is `d7ac8c5`.
- **Tests:** `tests/test_agi11.py` (9), `tests/test_agi10g.py` and `tests/test_checker_kernel.py` all pass.

## 10. One next architectural question

The only learned function that transferred was a relational composition. The search failed on deeper compositions (W1, W2, W3, W5,
W7 at 0 / 3) and on threshold ambiguity.

**Next question:** can abstraction over relational sub-pipelines, rather than scalar fragments, become the dominant learned
representation, and remove the ambiguity that causes wrong submissions? Two concrete parts:
- **Primitive vs abstracted search:** a pre-registered test of whether k_min = 3 relational abstractions, with an
  ambiguity-abstention rule (submit only when every visible-and-evidence-consistent alternative agrees), raise held-out completions
  and lower wrong submissions over the primitive search.
- **Upstream fix:** a guide trained on enough records (Stage B needs a budget at least twice this one) to test L1 − L0 honestly.
