# NEXUS Phase 10D: out of the sandbox — multi-table wide-schema DAGs, joins, Polars, MERGE reconciliation

**NOT LOCKED.** Branch `codex/nexus-data-engineering`.

- **Start:** `09ed162`.
- **Substrate + Gate 0:** `289e8ae`.
- **Amendments 1–4:** `4723ae6`.
- **Training v2 + freeze:** `3d630de` (before any target was opened).
- **`main`:** `d7ac8c5`, untouched.
- **Protocol:** `docs/NEXUS_PHASE10D_PROTOCOL.md`.
- **Reporting:** exact counts only.

## 1. Results at a glance

| Question | Result |
|---|---|
| Gate 0 (five out-of-sandbox requirements) | **PASSED 100 %**, twice: v1 on the original substrate, v2 on the amended one |
| Held-out multi-node compositions (of 24), A1 / A2 / A3 / A4 / A5 | rep0: **14 / 18 / 14 / 18 / 18**; rep1: **14 / 18 / 14 / 18 / 17** |
| Ordinary multi-table repairs (of 24), A1 / A2 / A3 / A4 / A5 | rep0: 20 / 21 / 20 / 21 / 21; rep1: 20 / 20 / 20 / 21 / 21 |
| Learned guidance (G_learned) | **+4 held-out completions in both repetitions** (A2 − A1 and A4 − A3), the pre-registered "replicated positive". Sign-flip p ≈ 0.12 per repetition (4 discordant targets each) |
| Learned macros (L\*) on wide schemas | **0 net completions** beyond learned guidance (A4 − A2 = 0 held-out in both; +0 / +1 ordinary) and 0 with fixed guidance (A3 − A1 = 0): "replicated null". Macros sit on 2–6 verified evaluation paths, but each such target was also solved without them |
| Guidance × macros synergy | **0** targets needed both |
| DAG localisation (A5 − A4) | 0 (rep0), −1 (rep1) |
| Learning curve, held-out (N0 / 30 / 60 / 120) | rep0 **14 / 17 / 18 / 18**; rep1 **14 / 18 / 18 / 18**. Search work on held-out targets fell from 9,891 to 5,703 / 5,659 executions. 0 forgetting |
| Wrong repairs | **Evaluation: 0 of 528 rows.** Training v2: 0 of 240 tasks. Training v1 (superseded before any target, disclosed): 3 |
| Never solved by any arm | 9 targets (6 held-out, 3 ordinary). **Every one contains the `replay` fault** (latest item per replayed batch) |
| Budget | **936 of 2,400 s** charged; 0 protection violations |

## 2. Gate 0 (`artifacts/agi10d_gate0.json`, `artifacts/agi10d_gate0_v2.json`)

Produced by `verify_out_of_sandbox_gate0()` on 10 development projects (agi10dde/dev 97000–97009).

| Requirement | Exact counts (v2, on the amended substrate) |
|---|---|
| 1. Multi-table schemas with join bugs | tables per project 5, 5, 5, 5, 4, 4, 3, 5, 5, 4 (cdc_customers, orders, order_items, + payments, + fx_rates). 9 / 10 projects carry a join bug (fan-out, inner-drop or text key cast), each individually effective |
| 2. Wide schemas | columns per workspace 112, 80, 86, 103, 70, 107, 110, 117, 74, 63 (all within 60–120) |
| 3. Three-node DAGs | 3 / 3 nodes and 3 node files in every project. Upstream (stg_ / int_) faults propagating to fct_: 10 / 10 |
| 4. Polars first-class (and the other engines) | the truth DAG equals the reference interpreter on every node output and every batch for DuckDB 10 / 10, SQLite 10 / 10, Polars 10 / 10, PySpark 4.0.1 4 / 4. Verified executions: 40 / 40 / 40 / 16. Generated Polars code uses `filter`, `with_columns`, `group_by().agg`, `join`, `join_asof`, `rank().over()`, `unique` and `cast(strict=False)` |
| 5. MERGE / QUALIFY / CDC envelopes | MERGE executed in the truth DAG 10 / 10; legacy-text MERGE INTO / Delta merge 9 / 10 (the 10th is an `overwrite` fault). QUALIFY or ROW_NUMBER dedup 10 / 10. Debezium `{op, before, after, ts_ms}` payloads 10 / 10 |
| Legacy lifting | 10 / 10 projects lift back exactly to the legacy DAG (Snowflake, Postgres, Hive, dbt, Scala) |

Versions: polars 2.1.0, pyspark 4.0.1, duckdb 1.1.3, sqlite 3.50.4, sqlglot 26.16.4.

**Engineering equivalents (disclosed):**

- DuckDB 1.1.3 has no MERGE INTO. The upsert runs as set operations inside one transaction; SQLite does the same.
- The legacy texts carry real MERGE INTO statements; Scala uses the Delta merge API.
- The Scala lifter has no as-of form, so an as-of fault never gets Scala legacy.
- dbt models are multi-statement scripts with Jinja `config` / `ref`, not single-SELECT models.

## 3. What was built (`src/nexus/de_phase10d/`)

- **The DAG:** `stg_` unpacks CDC envelopes (after / before coalesce), keeps the latest version per key and drops
  tombstones **after** dedup, quarantines dirty totals and keeps the latest replayed item. `int_orders` pre-aggregates
  child tables to order grain before joining, uses LEFT joins with typed keys and an as-of fx rate. `fct` aggregates per
  customer and runs MERGE INTO the prior target, with soft-delete detection by anti-join and delete / update / insert
  branches.
- **13 fault mechanisms:**
  - stg: qualify_order, tombstone, tomb_early, cdc_key, dirty, replay;
  - int: fanout, inner, keycast, asof_dir;
  - fct: merge_delete, merge_update, overwrite.
- **Contracts:** dbt-style, per node.
- **NEXUS's inputs:** the lifted legacy text, visible data and contracts only.
- **12 generic, column-parameterised L0 operators.** Their enumeration grows with the schema: a 110-column project gives
  more than 300 root candidates (unit test).

**Held-out compositions** have faults in two or more nodes. None occurs in training, dreams or admission (leakage check:
0 violations over 1,000 specs).

| Family | Faults |
|---|---|
| C1 | tombstone + fanout |
| C2 | replay + keycast |
| C3 | cdc_key + merge_delete |
| C4 | fanout + merge_update |
| C5 | qualify_order + inner + merge_delete |
| C6 | dirty + keycast + overwrite |
| C7 | tomb_early + fanout |
| C8 | replay + inner + merge_update |

## 4. Training (2 numeric-seeded repetitions × 120 tasks; v2)

| | rep0 | rep1 |
|---|---|---|
| Tasks reached / verified / wrong | 120 / 108 / 0 | 120 / 107 / 0 |
| Cost: wake / abstraction / dreams / ranker | 71.4 / 5.7 / 35.7 / 0.2 s | 77.7 / 17.5 / 39.5 / 0.2 s |
| L\* admitted (mechanism-matched modular admission) | 4: set_dedup → add_filter; add_filter → json_coalesce_before; add_filter → set_dedup; json_coalesce_before → add_filter | 6: add_filter → move_filter; merge_add_update → merge_add_delete; pre_aggregate → cast_keys; add_filter → move_filter → set_dedup; set_dedup → add_filter; add_filter → set_dedup |
| Macros on verified training paths | 10 | 17 |
| Unsolved in training | S_replay 6, T_dirty+replay 6 | S_replay 7, T_dirty+replay 6 |

**The Phase 10C admission flaw is fixed.** 10 macros were admitted here, against 0–1 in Phase 10C, because validation now
uses any training-family project where the macro binds.

## 5. Evaluation (48 one-use targets, agi10dde/eval 99000–99047, opened once; 528 rows; 0 build failures)

**Held-out per family.**

- Guidance gained 2 targets in C5 (99036, 99038) and 2 in C6 (99040, 99041), in both repetitions.
- Both are 3-node, 3-fault compositions that fixed L0 search could not finish within 600 executions.
- C2 and C8 (both contain `replay`) were 0 / 3 in every arm.
- Every other held-out family was solved by every arm.

**Ordinary.** Guidance gained S_dirty 99008. Unsolved in every arm: S_replay 99002 and 99021, and T_dirty+replay 99018.

**Engines and legacy languages, best arm (A4_rep0) versus A1:**

| Engine | A4_rep0 | A1 |
|---|---|---|
| DuckDB | 11 / 12 | 8 / 12 |
| SQLite | 9 / 12 | 8 / 12 |
| Polars | 9 / 12 | 8 / 12 |
| PySpark | 10 / 12 | 10 / 12 |

| Legacy language | A4_rep0 | A1 |
|---|---|---|
| Snowflake | 10 / 11 | 9 / 11 |
| Postgres | 8 / 10 | 6 / 10 |
| Hive | 7 / 10 | 7 / 10 |
| dbt | 7 / 9 | 5 / 9 |
| Scala | 7 / 8 | 7 / 8 |

**Marginal contribution of L\* on wide schemas.** On these 60–120-column workspaces the admitted macros did not add a
single completion beyond learned guidance with primitives. The learned ranker already put the right column-parameterised
primitive near the top. The completions that remained out of reach (`replay`) need a `set_dedup` on a relation that had
no dedup, with the right key and order columns. No admitted macro covers that: no replay repair was ever verified in
training, so there was nothing to abstract.

## 6. Disclosures and deviations

1. **Specialised operators trivialised the task** (development data, before training). The first operator set made fixed
   L0 search solve all 12 dev projects. Operators were made generic and column-parameterised, and role columns were
   shuffled among distractors.
2. **Training v1 (kept in `artifacts/agi10d_train_v1/`) produced 3 wrong training submissions.** A macro-bound or
   search-chosen `set_dedup` ordered by a column that coincided with the truth on the single visible batch. Amendments
   1–4 (protocol §Amendments: minimal-change dedup ordering, Occam pruning, two visible batches, about 2× rows) were
   recorded and committed **before any target opened**. Both repetitions were retrained once (v2); v1 was never evaluated.
3. **The job runner refused to start v2 rep1 in parallel** (stage reservation). It ran separately, with the same code
   and seeds.
4. **Spark** reuses the Phase 4 `SparkCode` session. Training uses DuckDB / SQLite / Polars; PySpark appears in Gate 0
   and in 12 of the 48 evaluation targets.
5. **Scope of the substrate.** The generator, data and fault mechanisms are synthetic, written by us. "Out of the
   sandbox" means real engines, real dialects and real MERGE / QUALIFY / CDC semantics at multi-table, wide-schema scale.
   It does not mean real customer repositories.
6. **Polars 2.1.0** was installed with pip into the active venv, as the owner authorised.
7. **Unmetered work:** none for experiments. All runs went through `scripts/agi10d_exec.py`.

## 7. Budget and protection

| Stage | Used / ceiling (s) | Notes |
|---|---|---|
| s1 | 138 / 400 | Gate 0 dev runs, Gate 0 v1 and v2, dev searches / training, tests |
| s2 | 446 / 950 | training v1 (149 s), diagnostics, amendment checks, training v2 (113 + 135 s) |
| s3 | 350 / 850 | 528 evaluation rows in 12 chunks |
| s4 | 1 / 200 | score, protection |
| **Total** | **936 / 2,400** | grant pool remaining 3,688 s |

- **Protection** (`artifacts/agi10d_protect_after.json`): 0 violations; frozen Phase 1–10C files unchanged; checkers v1–v5
  pinned; `main` = `d7ac8c5`.
- **One-use:** `agi10dde/eval` was claimed once, and no written row was rerun.

## 8. Recommended next experiment

A **replay-composition test with a targeted curriculum**. The one mechanism no arm ever solves (replay → `set_dedup` on a
relation without one) should be tested by asking whether a learner that receives verified replay repairs in training then
abstracts a dedup macro that transfers to C2 / C8-style compositions. That is the clean test of whether L\* can add
completions beyond learned guidance; this phase could not test it, because training never verified a replay repair.
