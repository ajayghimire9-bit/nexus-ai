# NEXUS Phase 11 — pre-registered protocol (NOT LOCKED)

Committed **before** Stage A source learning, before any Stage B training, and before any Suite 1 target opens.

## Revision, machine and budget

| Item | Value |
|---|---|
| Branch | `codex/nexus-data-engineering`, start `99d45dd`; `main` `d7ac8c5` untouched |
| Machine | Apple M4, 16 GB RAM, 10 cores, macOS 26.6.2 |
| Interpreter | CPython 3.13.5 (arm64); single-threaded pure Python, no MPS / GPU involvement |
| Engines | DuckDB 1.1.3, SQLite 3.50.4, Polars 2.1.0, PySpark 4.0.1; sqlglot 26.16.4 |

- **Grant:** `artifacts/agi11_grant.json`, a **new 1,800 s** grant and hard cap.
  - The older surplus (925.931 s) is recorded and **not** consumed.
  - Ceilings: s1 300, s2 450, s3 450, s4 450, s5 150. No transfers.
- **Metering:** every execution of Phase 11 code runs through `scripts/agi11_exec.py` (prefix `a11-`). That covers tests,
  conformance, probes, profiling, development timing, generation, search, learning and evaluation.
  - Charged = each metered process's wall time. Concurrent processes each charge their own wall time; child CPU is recorded
    separately.
  - **Uncharged:** source editing; read-only inspection (reading files and logs, git); ledger bookkeeping (`scripts/agi11_ledger.py
    export / verify`); budget status.
- **Ledger:** `docs/NEXUS_COMPUTE_LEDGER.json` stays append-only.
  - `scripts/agi11_ledger.py verify` runs the frozen 10C–10G verifier unchanged, plus a separate `phase11` section.
- **Protection:** Phase 1–10G files frozen (`scripts/agi11_protect.py`; `artifacts/agi11_protect_before.json`, 0 violations).
  - All new code is in `src/nexus/de_phase11/`.

## Frozen core (src/nexus/de_phase11/core11.py; the docstring is the published inventory)

**Physical types:** int (int64; overflow gives ERR), num (double), str, bool. Everything is nullable. Relations are bags with
ordered schemas.

**Three outcomes:** value, NULL or ERR. ERR propagates through every operator except an unchosen arm of a lazy branch, and a
relation that hits ERR fails as a whole.

**Operator families and sub-operations:**

| Family | Sub-operations |
|---|---|
| const, col, is_null | — |
| compare | eq ne lt le gt ge (SQL three-valued); and / or / not (Kleene) |
| arith | add sub mul (int stays int, else num); div (always num); mod (int, sign of the dividend); by zero → NULL |
| branch | lazy CASE |
| json_get | str → str; NULL on NULL / invalid / missing / JSON null; normalised number text; minified object text |
| cast | explicit only: str→int, str→num (regexp-checked; else NULL), int→num, int→str |
| call / param | library functions, inlined |
| rel, project_map, filter_rows | — |
| fold_group | NULL keys are one group; sum count count_star min max; no keys → exactly one row |
| rank_window | ROW_NUMBER ≤ k, NULLS LAST, ties broken by every column |
| join_rel | inner left semi anti; identical key types; NULL keys never match |
| union_rel | UNION ALL by name |

**Declared unsupported:** transactional MERGE (a pure next-state upsert is expressible but not equated with MERGE), set union,
output ORDER BY, recursion, arbitrary fold accumulators, num→str and other casts. Polars and PySpark native adapters are not
implemented (coverage gaps).

**Expanded size:** structural node count after inlining. Every arm has the same `SIZE_LIMIT = 40` and the same scalar `SC_SIZE = 8`.
A library call never makes a program legal that its expansion would not be (unit-tested).

**Types vs roles:** no role detector exists in Phase 11 search, so roles never restrict a type-correct operation.

## Stage 1 results (development fixtures only)

**Engine probe** (`artifacts/agi11_engine_probe.json`). DuckDB returns `inf` for division by zero, so the core defines NULL and the
compiler guards it explicitly. JSON number normalisation matches Python's float repr. Out-of-range casts and overflow are engine
errors, so the core gives ERR.

**Conformance** (`artifacts/agi11_conformance.json`, 30 fixture programs × full and empty inputs):

| Engine | Conforming | Note |
|---|---|---|
| DuckDB | **60 / 60** | — |
| SQLite | 58 / 60 | JSON number / boolean text differences, declared |
| Polars, PySpark | 0 / 60 | not implemented |

**Unit tests** (`tests/test_agi11.py`, 8, all pass):
- three-valued logic, NULL / false / ERR, lazy branch, division and modulo by zero, casts, JSON;
- NULL groups, empty folds, tie-break, NULL and duplicate join keys, union;
- DuckDB conformance;
- observational regressions:
  - `x` vs `branch(x < 10, x, 0)` collapse on the 10-row slice, and refinement recovers the branch on the full rows;
  - NULL / ERR / false are kept apart;
  - bag multiplicity is in the fingerprint;
- anti-unification binding and matching, project counting, wrapper classification, size invariance under calls;
- no reference / family leakage into learner tasks; numeric seeds; both ledgers verify; Suite 3 NOT READY.

**Development timing** (`artifacts/agi11_dev*.json`; dev seeds 110000–110999).
- The synthesizer was iterated over about 25 metered development runs; this history is disclosed.
- Final configuration, F0 with no library:
  - source families: 8 / 8 solvable within the Stage A budget (preagg 2.95 s, upsert 5.9 s);
  - compositions at the evaluation work caps: 4 / 14 verified, 2 wrong (threshold underdetermination), mean about 1.4 s per search.
- The realisation memo, depth limit and cap of 400 were set at the very end of Stage 1 and are **not re-timed**. A row whose wall
  safety binds is logged.

## Synthesizer (synth11; identical machinery in every arm)

**Relational search:** one best-first cost order over three kinds of item.
- Relational children, evaluated lazily when popped.
- Lazy pair tokens for joins and unions.
- Escalation items deepening a node's scalar pool: cost = node cost + 2 × tier; tier caps 1,500 / 6,000 / 15,000 / 25,000
  micro-evaluations.

**Relational classes:** keyed by column names plus visible bags. Alternatives are retained (cap 48) and tried on an evidence
counterexample.

**Final step:** deductive projection (passthrough alignment plus per-column scalar matching) or aggregation (key detection plus
agg(e) per group).

**Scalar pool:**
- Bands of production cost; OE classes keyed on a **10-row micro-slice** (encoded values; NULL / ERR / type distinguished).
- Members stored over child-class ids (cap 48) and regenerated diagonally (cap 400). The representative is checked on full rows,
  then the alternatives (refinement).
- A sound prefilter on groups fully inside the slice.
- Enumeration shape: child sizes are limited per operator; pool branches take leaf arms (no threshold quantiles).
- Deductive branch unification for projection targets.

**Declared heuristics:**
- joins need ≥ 20 % key-value overlap on some visible batch;
- no fold on a duplicate-free key (a no-op rank is skipped, which is sound);
- constants are mined only from permitted observations: 0 and 1, low-cardinality strings, per-column quantiles of numeric inputs,
  small output value sets, JSON keys.
- **Generator assumption:** task thresholds are drawn from those quantile constants.

**Evidence:** one shared fixed policy for every arm. Request the evidence batch once, at the first visible-consistent candidate;
the candidate must reproduce it, and a counterexample triggers refinement, then the search continues.

**Work caps:**

| Stage | Relational pops | Micro-evaluations | Wall safety |
|---|---|---|---|
| Stage A | 6,000 | 1.2 M | 12 s |
| Stage B | 2,000 | 350 k | 6 s |
| Suite 1 evaluation | 1,500 | 250 k | 5 s |
| Suite 2 | 750 | 125 k | 2.5 s |

## Abstraction (abstr11)

- **Candidates:** typed anti-unification of solved, verified, expanded ASTs from two different projects. Parameters are rel /
  scalar / name / lit with consistent alpha-binding. Tags never become parameters, and top-level project_map nodes are not
  candidates.
- **Support:** matching instances across distinct projects, with **k_min = 3**. Pairwise generalisation plus matching keeps
  role-consistent subgroups.
- **Compression:** must be > 0.
- **Admission:** every support project's solution, rewritten to call the function, reproduces its separate validation batch and
  its visible batches. At most 3 admissions per sleep, best compression first.
- **Classes:** wrapper (one primitive operator), multi (≥ 2), composite (calls an earlier function).
- **No dreams** are used, and no generator demonstrations.

## Stages, arms and suites

**Stage A** (`scripts/agi11_stageA.py`): 2 streams × 60 source tasks (`agi11/sourceA`; 8 families in shuffled cycles), sleep every
10 tasks.

**Stage B** (`scripts/agi11_stageB.py`): libraries frozen; 2 streams × 80 tasks (`agi11/stageB`; B1–B6), solved with F1.
`G_A0` is fitted on expanded records, `G_M` on the same records rewritten with the library (`guide11`).

**Arms** (Suite 1 and Suite 2):

| Arm | Search | Library |
|---|---|---|
| F0 | fixed | none |
| F1_r | fixed | L_r |
| L0_r | learned `G_A0_r` | none |
| L1_r | learned `G_M_r` | L_r |

- F0 is shared, so there are 7 arm-runs per target.
- All 7 arms of a target run in one process; the order rotates by target index.

**Suites:**
- **Suite 1:** 24 one-use withheld compositions (W1–W8 × 3, held-out names, `agi11/suite1` 113000–113023). Native DuckDB
  verification on 2 hidden batches; SQLite native execution recorded as coverage.
- **Suite 2:** the 16 Phase 10C / 10E development tasks.
  - Ingestion coverage of the legacy texts.
  - The 10 tasks with a reference repair run as I/O tasks (all 7 arms, half caps); the other 6 are reported as not posable.
  - Prior labels preserved.
- **Suite 3, External_Holdout_24: NOT READY** (`artifacts/agi11_suite3_provenance.json`). The BIRD-Critic 1.0 SQLite references
  are released only by email, which is not authorised; no task content was opened.

**Stage 4 plan:** Suite 1 complete first (6 chunks of 4 targets, 7 arms each, cap 90 s per chunk), then Suite 2. Projection:
about 250 + 50 s of 450 s. Rows are flushed immediately and never rerun.

## Pre-registered decision rules

**Source-learning gate**, per stream: at least **2 distinct non-wrapper functions** (class multi or composite), with support and
admission evidence. Distinctness is alpha-canonical; semantic equivalence is not tested and is disclosed.
- If a stream fails the gate, its abstraction-transfer test is reported as **acquisition failure**.
- Its arms are still evaluated, because the matrix is pre-registered, but no library-benefit claim is made for it.
- k_min is never reduced.

**Library benefit (Suite 1, per stream):**
- F1 − F0 estimates the library benefit under fixed search; L1 − L0 the library plus its associated guide.
- *Positive:* ≥ +2 verified targets in **both** streams, with no more wrong submissions than the comparator.
- *Null:* \|d\| ≤ 1 in both.
- *Negative:* ≤ −2 in both.
- Otherwise *mixed*.
- Neither contrast alone proves a modified learning algorithm.

**Search efficiency:** relational pops, micro-evaluations and search wall on targets both arms verified (descriptive).

**Coverage:** DuckDB native verification; SQLite native execution; Suite 2 ingestion stages (descriptive).

**Wrong submissions** are reported per arm, with submissions as the denominator, in Stage A, Stage B, Suite 1 and Suite 2.

Two streams sharing targets are not two independent task-set replications. No retro-adoption, no rerun of a written row, no reuse
of the one-use range.
