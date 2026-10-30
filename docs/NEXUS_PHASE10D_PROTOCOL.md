# NEXUS Phase 10D — pre-registered protocol (NOT LOCKED)

Committed **before** any Stage 2 training outcome and before the 48 one-use targets are opened.

- **Branch:** `codex/nexus-data-engineering`; start revision `09ed162`; `main` = `d7ac8c5` (untouched).
- **Grant:** `artifacts/agi10d_grant.json`: +2,200 s on the 2,424.272 s carried from Phase 10C; hard cap 2,400 s.
- **Stage ceilings:** s1 400, s2 950, s3 850, s4 200. No transfers.
- **Polars:** 2.1.0, installed into the active venv by pip, as the owner authorised.

## Substrate (`src/nexus/de_phase10d/`, Stage 1)

| Module | Contents |
|---|---|
| `ir10d` | 3-node DAG IR (`stg_` → `int_` → `fct_`) and a reference interpreter. Features: CDC envelope unpacking (Debezium `op`/`before`/`after`/`ts_ms`, after/before coalesce); latest-per-key dedup (QUALIFY ROW_NUMBER) with pre / post-dedup filters; joins (left / inner, child pre-aggregation to the parent grain, typed keys, as-of); aggregation; MERGE INTO the prior target (soft-delete detection by anti-join; delete / update / insert branches) |
| `engines10d` | Real lowerings: DuckDB 1.1.3 SQL (QUALIFY; the upsert is transactional because DuckDB 1.1 has no MERGE), SQLite 3.50, Polars 2.1 LazyFrame code (`filter`, `with_columns`, `group_by().agg`, `join`, `join_asof`, `rank().over()`, `unique`, `cast(strict=False)`), PySpark 4.0.1 DataFrame code |
| `legacy10d` | Legacy input languages, each lifted back into the IR: Snowflake / Postgres / Hive SQL (real MERGE INTO, QUALIFY or ROW_NUMBER, dialect JSON functions; sqlglot 26.16.4 in the source dialect), dbt Jinja models with schema.yml, Scala Spark with the Delta merge API |
| `world10d` | Projects with 3–5 tables (cdc_customers, orders, order_items, payments, fx_rates) and 60–120 columns, including audit / metadata / status / numeric distractors, with role columns shuffled among them; 13 fault mechanisms over the three nodes, each individually effective; per-node dbt-style contracts; one visible and two hidden batches |
| `dag10d` | What NEXUS sees: lifted legacy, visible data, contracts. Residual-symptom evidence. 12 **generic, column-parameterised** L0 operators (set_dedup, add_filter, move_filter, json_coalesce_before, pre_aggregate, set_join_type, cast_keys, asof_backward, coalesce_out, merge_add_delete, merge_add_update, add_merge) |
| `search10d` | The Phase 10C unified search: macros as atomic children; residual-symptom tokens; one bridge machinery for all arms; acceptance = public checks + every node contract + a re-run on the declared engine |
| `lineage10d` | The wake–sleep learner (below) |

**Design iteration on development data (disclosed).** The first operator set was specialised (one-candidate operators such
as `dedup_desc` and `set_left`). On it, fixed L0 search solved all 12 dev projects in 42–248 executions, so guidance and
macros could not matter. The operators were therefore made generic and column-parameterised, and role columns were
interleaved with distractors. This was done before any training or evaluation.

**Gate 0** (`artifacts/agi10d_gate0.json`; `scripts/agi10d_gate0.py`, `verify_out_of_sandbox_gate0`) **PASSED 100 %**:

| Check | Result |
|---|---|
| Projects | 10 |
| Tables per project | 3–5 |
| Columns per workspace | 63–117 |
| DAG nodes per project | 3 |
| Legacy languages lifting back exactly | 10 / 10 |
| Truth equal to the reference interpreter on every node output and every batch | DuckDB 10 / 10, SQLite 10 / 10, Polars 10 / 10, PySpark 4.0.1 4 / 4 (30 + 30 + 30 + 12 verified executions) |
| CDC envelopes | 10 / 10 |
| QUALIFY / ROW_NUMBER dedup | 10 / 10 |
| MERGE executed in the truth DAG | 10 / 10 (legacy-text MERGE 9 / 10; the 10th is an overwrite fault) |
| Upstream (stg / int) faults propagating to `fct` | 10 / 10 |
| Join-bug projects | 9 |

## Families and the held-out split

**Training, dreams and admission** use only training families: every single mechanism, plus within-node pairs:

| Node | Training pairs |
|---|---|
| stg | tombstone + qualify_order, dirty + replay, cdc_key + dirty |
| int | fanout + inner, keycast + fanout |
| fct | merge_delete + merge_update |

**Held-out multi-stage compositions** have faults in two or more **different** nodes. No cross-node pair occurs in any
training, dream or admission spec (`manifest10d.leakage()`: 1,000 specs, 0 violations).

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

**Evaluation (one-use `agi10dde/eval`, 99000–99047): 48 targets.**

- **Ordinary:** 24 targets from training families.
- **Held-out:** 24 targets, 3 per held-out family.
- **Schema names:** held-out.
- **Engines:** DuckDB / SQLite / Polars / PySpark rotate.
- **Legacy languages:** Snowflake / Postgres / Hive / dbt / Scala rotate (an as-of fault never gets Scala).

## Learner and arms

- **Held fixed in every arm, training included:**
  - the procedure (search → visible checks + contracts → declared-engine re-run → submit; documented requirements, so no
    trust decision arises);
  - M0;
  - the bridge machinery;
  - the search budget: 600 executions and a 4 s wall cap.
- **Training streams:** 2 repetitions, numeric-seeded `(rep, step, task)`, 120 tasks each; checkpoints N = 30 / 60 / 120;
  N3 = tasks reached within each stream's cap.
- **L\* admission (mechanism-matched; the Phase 10C fix):**
  - a macro is validated on up to 2 training-family admission projects other than its sources, wherever it binds with its
    precondition;
  - it must make modular progress on at least one;
  - base-vs-trial search must lose no completion and add no wrong submission.
- **Rankers:** G_L0 on primitive step pairs; G_L\* on the same records rewritten over L0 ∪ L\*.

| Arm | Guidance | Library | Extra |
|---|---|---|---|
| A1 | fixed | L0 | — |
| A2_r | learned G_L0 | L0 | — |
| A3_r | fixed | L0 ∪ L\* | — |
| A4_r | learned G_L\* | L0 ∪ L\* | — |
| A5_r | as A4_r | as A4_r | expands only the first DAG node whose contract fails (bonus diagnostic) |

- **Learning curve:** A4_r at N30 and N60 on the 24 held-out targets; N0 = A1 and N3 = A4_r.
- **Verification:** every submission is checked on the project's declared engine against 2 hidden batches.

## Decision rules (per repetition, on the 24 held-out compositions)

- **L\* replicated positive:** A3 − A1 ≥ +2 **and** A4 − A2 ≥ +2 in **both** repetitions, with 0 evaluation wrong in A3 /
  A4.
- **L\* replicated null:** every |diff| ≤ 1 in both repetitions.
- **Otherwise:** mixed / inconclusive.
- **G_learned:** the same rules with A2 − A1 and A4 − A3.
- **Wide-schema L\* question:** answered by A4 − A2 (net completions from macros beyond learned guidance with L0), on
  held-out and on ordinary targets.
- **Ordinary non-regression:** A4 loses at most 1 versus A1.
- **Reporting:** localisation (A5 − A4), the attribution table, the 4-point full-cost curve, and training versus
  evaluation wrong counts reported separately.
- **Sign-flip p-values:** descriptive only.
- **No retro-adoption, and no rerun of written rows.**

## Amendments (recorded after training v1, BEFORE any evaluation target is opened)

Training v1 (`artifacts/agi10d_train_v1/`, kept as a record) produced **3 wrong training submissions**, all on tombstone
families. Diagnosis (`scripts/agi10d_diag.py`): a macro-bound or search-chosen edit coincided with the truth on the single
visible batch but not on hidden data. The cause was a dedup ordered by a correlated or distractor column, or a spurious
filter.

The fixes are shared by **every arm and by training**. They were checked on the 3 wrong projects (now 3 / 3 correct under
both fixed L0 and the v1 A4 memory) and on 12 dev projects (0 wrong):

1. **Minimal-change ordering.** `set_dedup` candidates are ordered by the number of changed fields, so a direction flip
   comes before column swaps.
2. **Occam pruning at acceptance.** Every edit of an accepted path whose removal keeps all visible checks and contracts
   passing is dropped (each trial is one charged execution).
3. **Two visible batches.** `data/` and `data/b/` each have their own target state and golden `fct` rows. Public checks
   and node contracts must pass on both. One charged execution = one candidate evaluated on all visible batches.
4. **About twice the rows per batch** (the generator's size parameter), so coincidental matches on aggregated outputs
   become rare.

Also:

- **Output-identical speed-ups:** a hash-indexed join and a node-memoised prescreen interpreter (tested to be identical).
- **Gate 0 re-run on the amended substrate:** `artifacts/agi10d_gate0_v2.json`, PASSED 100 %. Spark 4 / 4; 40 / 40 / 40 / 16
  executions over 4 batches.
- **Retraining:** both repetitions are retrained once with the amended code into `artifacts/agi10d_train/` (v2). Training
  v1 is never evaluated. Everything else in this protocol is unchanged.
