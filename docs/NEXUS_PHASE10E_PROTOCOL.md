# NEXUS Phase 10E — pre-registered protocol (NOT LOCKED)

This protocol is committed **before** any Phase 10E training outcome, before the 48 one-use evaluation targets are opened, and
before the final Stage 4 external re-test.

- **Branch:** `codex/nexus-data-engineering`, starting at revision `a148f81`.
- **`main`:** `d7ac8c5`, untouched.
- **Budget:** `artifacts/agi10e_grant.json`.
  - The owner authorised at most **1,400 charged seconds** from the unused Phase 10C and 10D surplus, which is **1,838.4 s**
    (Phase 10C used 1,425.736 of 1,800 s and Phase 10D used 935.864 of 2,400 s). No new grant.
  - Stage ceilings (`artifacts/agi10e_allocation.json`): s1 250, s2 500, s3 350, s4 180, s5 120. No transfers.
  - Every run is metered by `scripts/agi10e_exec.py` (prefix `a10e-`) in the shared ledger.
- **Frozen code:** Phase 1–10D files are protected (`scripts/agi10e_protect.py` adds every Phase 10D file to the frozen set).
  All Phase 10E code is new, in `src/nexus/de_phase10e/`.

## Stage 1 findings (development and forensic data only; already run and committed with this protocol)

### 1A. Target 96088: the Phase 10C diagnosis was wrong

Source: `scripts/agi10e_c96088.py`, `artifacts/agi10e_c96088.json`. The already-consumed target was rebuilt only to execute
four fixed specifications. This produced no new evaluation row.

| Variant | Hidden verdict |
|---|---|
| V0, the submitted specs: window-end predicate in the CDC stage | wrong (hidden2) |
| V1, the same predicate moved to the window stage | wrong (hidden2); outputs identical to V0 |
| V2, V0 plus the missing window-start predicate | **verified** |
| V3, truth | verified |

The Phase 4 IR applies a stage's dedup **before** its filter, so the predicate was never placed before the dedup. The real cause:

- the workspace declares the window as `batch.json {start, end}`;
- the candidate implements only `end`;
- no visible row lies before `start`.

**Fix 1, `de_phase10e.fixes10e` (Phase 6–10C procedure substrate).** A candidate that references some key of a state file
while leaving a sibling key of the same file unreferenced is not submitted ("state parameter untested").

| Check (`scripts/agi10e_fix_check.py`, `artifacts/agi10e_fix_check.json`) | Result |
|---|---|
| Phase 10C dev and training truths flagged (342 projects; 37 declare a `batch.json` window) | **0** false abstains |
| 96088 wrong variants V0 and V1 | blocked |
| 96088 correct variants V2 and V3 | pass |
| False accepts on 96088 | **0** |

**Fix 2, the requested shadow-sequence witness.** It is implemented in both substrates:

- in the DAG substrate (`dag10e.stale_witness`), for every **pre-dedup** filter;
- in the stage substrate (`fixes10e.stale_witness`), for a filter in an earlier stage than a latest-per-key dedup.

The witness synthesises a boundary key with two versions, r_old and r_new. r_new is the latest version, fails the predicate
and r_old satisfies it. If filter-then-dedup disagrees with dedup-then-filter on this key, the candidate is rejected. Unit tests
(`tests/test_agi10e.py`) cover three cases:

- filter-before-dedup resurrects r_old and is rejected;
- filter-after-dedup passes;
- a predicate on the key itself, which commutes with the dedup, passes.

On 96088 the witness correctly finds no violation; Fix 1 is what blocks it.

### 1B. Why Phase 10D training verified 0 replay repairs

Source: `scripts/agi10e_diag_replay.py`, `artifacts/agi10e_diag_replay.json`; the 25 Phase 10D training tasks containing
`replay`, rebuilt on the frozen Phase 10D code.

- **The repair was correct but unreachable.** The generator's replay repair passes visible checks in **25 / 25** tasks and
  verifies on the hidden batches in **25 / 25**. The bottleneck was reachability, not verification.
- **It sat deep in the fixed order.** In the fixed root order the repair was at position **294–961** (median 513), while the
  search budget is 600 executions.
- **Role twins hid it.** Each task had a median of **29** `set_dedup` candidates whose role form was identical to the truth's.
  Neither a role-form ranker nor a macro could tell the item key and the ingest sequence apart from the int distractors.
- **The repair is one 3-parameter edit,** so Sleep could never abstract it into a multi-step macro.

## Substrate changes (shared by every arm, by training, dreams and admission; none is learned)

Module: `de_phase10e.dag10e`. The design was iterated on agi10ede/dev data, recorded in `artifacts/agi10e_dev1.json` and
`artifacts/agi10e_dev2.json`.

1. **Discriminative schema roles.** Both are computed from visible information only and are name-agnostic.
   - `ckey`: the column carries a `unique` test in `models/schema.yml`.
   - `arrival`: an int column that strictly increases with landing order inside every duplicate group of a `ckey`.
   - On the 9 dev replay projects, the truth key has **0** role twins and the truth order column has **1** (a quantity column
     that also increases).
2. **Two-step dedup.** A relation without a dedup is offered `add_partition(rel, key)`, meaning
   `QUALIFY ROW_NUMBER() OVER (PARTITION BY key) = 1`. The existing `set_dedup` then sets the order; its minimal-change order
   tries the one-field ORDER BY change first. The replay repair therefore becomes the 2-step path
   `add_partition → set_dedup`.
3. **Acceptance rules.** These are checks on the spec and the visible rows and are not charged as executions. A violation
   blocks acceptance but leaves the graded score unchanged.
   - `deterministic_dedup`: no partition may have two different rows tied at the top of its ORDER BY. This makes the
     partition-only interim state impossible to submit.
   - `latest_state_witness`: the shadow-sequence witness above.
   - The truth passes both rules in **26 / 26** dev projects, covering every family.
4. **Admission amendment** (`lineage10e`). Mechanism-matched admission draws up to **30** admission projects (Phase 10D drew 10)
   to find at most 2 where a candidate binds. A candidate rejected only because it bound nowhere is retried at later sleeps,
   for at most 3 attempts. S_replay is 1 of 18 training families, and a replay macro otherwise found no binding project in about
   56 % of attempts and was never retried.

**Development effect** (dev data, fixed-guide L0 A1, 600 executions):

- A1 reaches the partition step at root position 20, but not the ordering step. In the fixed order every `stg_customers`
  re-ordering comes first.
- A1 verifies **0** of 9 dev replay projects.
- In the dev training rehearsals, learned guidance verified an S_replay wake task through
  `add_partition → set_dedup` in 84 executions.
- No replay macro was admitted within the 42 tasks a rehearsal reached.

## Families (`de_phase10e.manifest10e`)

- **Training, dreams and admission** use every single mechanism, including `S_replay`, plus the Phase 10D within-node pairs
  **except** `dirty + replay`. Replay is seen only as a single-mechanism source task.
- **Held-out replay compositions:** 24 targets, 3 per family. Each contains `replay` plus faults in at least one other node.
  None occurs in training, dreams or admission (`manifest10e.leakage()`: 1,000 specs, 0 violations).

| Family | Faults |
|---|---|
| R1 | replay + fanout |
| R2 | replay + keycast |
| R3 | replay + merge_update |
| R4 | replay + merge_delete |
| R5 | replay + fanout + merge_update |
| R6 | replay + keycast + merge_delete |
| R7 | replay + inner + merge_update |
| R8 | replay + dirty + keycast |

- **Ordinary targets:** 24, from training families, with held-out schema names.
- **Engines:** DuckDB / SQLite / Polars / PySpark 4.0.1 rotate. **Legacy languages:** Snowflake / Postgres / Hive / dbt /
  Scala rotate.
- **Evaluation draw:** fresh, one-use `agi10ede/eval` 102000–102047. The frozen manifest is `artifacts/agi10e_manifest.json`
  (sha256 `3e26dae9…`). The Phase 10D range 99000–99099 is never reused.

## Training (Stage 2) and arms (Stage 3)

**Training:**

- 2 repetitions × 120 tasks, numeric-seeded `(rep, step, task)` (`agi10ede/train` 101000 + 500 r).
- Sleep every 10 tasks.
- Lineage design as in Phase 10D (`lineage10e` is a copy of `lineage10d` bound to Phase 10E, plus the admission amendment).
- Search budget: 600 executions and a 4 s wall cap.
- Every submission is verified on the declared engine against 2 hidden batches.

**Evaluation arms.** Each runs once per target, with the same procedure, M0 and bridge machinery.

| Arm | Guidance | Library |
|---|---|---|
| A1 | fixed | L0 |
| A2_r | learned G_L0 | L0 |
| A3_r | fixed | L0 ∪ L\*_r |
| A4_r | learned G_L\* | L0 ∪ L\*_r |

That gives 7 arm-runs × 48 targets = 336 rows. Rows are appended and flushed, and no written row is rerun.

## Decision rules (per repetition, on the 24 held-out replay compositions)

**Precondition (the L\* question is testable in repetition r):**

- at least 1 verified S_replay repair in r's training (wake);
- **and** at least 1 admitted L\*_r macro containing `add_partition`.
- If either is missing, the L\* question for r is reported as **untestable** (not null).

**Primary question.** Do learned replay macros add completions beyond learned guidance alone?

| Verdict | Rule |
|---|---|
| L\* replicated positive | A4 − A2 ≥ +2 **and** A3 − A1 ≥ +2 in **both** testable repetitions, with 0 evaluation wrong in A3 / A4 |
| L\* replicated null | every \|A4 − A2\| and \|A3 − A1\| ≤ 1 in both |
| Mixed / inconclusive | otherwise |

**Mechanism attribution.** For every target that A4 verifies and A2 does not, report whether a replay macro (one containing
`add_partition`) is on the verified path.

**G_learned:** A2 − A1 and A4 − A3, with the same rules.

**Also reported:**

- ordinary targets (A4 loses at most 1 versus A1);
- the attribution table;
- wrong counts in training and in evaluation, separately;
- costs (wake / abstraction / dreams / ranker; evaluation work).

**Sign-flip p-values** are descriptive only. **No retro-adoption.**

## Stage 4 external re-test (16 Phase 10C dev-audit tasks; diagnostic, trains nothing)

**Loader:** `de_phase10e.extload10e`, general and task-agnostic. Its rules:

| Rule | What it does |
|---|---|
| R1 | dbt rendering |
| R2 | model statement |
| R3 | CTE inlining |
| R4 | single-input binding plus the multi-table binder (the FROM / JOIN clause is materialised by DuckDB over the provided tables) |
| R5 | aliases; `COUNT(*)` → `SUM(1)` |
| R6 | QUALIFY / ROW_NUMBER derived table / DISTINCT ON → dedup; an ASC order on an all-integer column is read as DESC on (0 − int) |
| R7 | filter-then-dedup → 2 stages |
| — | PySpark top-level wrapping, `dropDuplicates`, string `select` |
| — | a Polars lifter |
| — | Scala free-relation binding |

**Funnel:**

| Stage | Definition |
|---|---|
| Total | 16 |
| Ingested natively | the text as written parses and every relation it reads binds to a provided table |
| Expressible | the bound legacy lifts into the stage IR |
| Candidate reached | search10c under the Phase 10C A1 configuration (fixed, L0, 1,500 executions, 4 s) submits a candidate passing every public check; needs a reference repair |
| Verified | equal to the reference on all rows; a submitted but wrong candidate is a wrong repair |

**Disclosure.** The loader rules were developed against these same 16 texts (Stage 4 development runs
`a10e-s4-loaderdev*` and `a10e-s4-extdev1`), so the re-test funnel is a development measurement, not held-out ingestion.

## Disclosures recorded before outcomes

- **Ceiling overflow.** Stage 1's ceiling (250 s) was nearly exhausted by forensics, development checks and a 90 s timeout of
  the first fix check, which rebuilt Phase 6 dev projects. The second development training rehearsal (55 s) is therefore
  charged to s2.
- **Witness and rule cost.** The witness and rule checks are uncharged spec / visible-data analyses.
- **Spark** is evaluation-only, as in Phase 10D.
