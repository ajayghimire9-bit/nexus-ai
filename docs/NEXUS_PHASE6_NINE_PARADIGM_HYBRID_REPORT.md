# NEXUS Phase 6 — Nine-Paradigm Multi-Language Arena, Calibrated Epistemic Trust, Invented Skills and Hybrid Transfer

**Status: NOT LOCKED.** Branch `claude/s456-work` (pushed as `codex/nexus-data-engineering`), started from `ed6fabf`.
`main` (`d7ac8c5`) is untouched, and checker kernels v1–v5 are pinned.

**Owner's standing priority:** NEXUS must **invent its own methods**: self-evolution, transfer, learning to learn,
meta-learning. Hand-written logic is the substrate or a baseline and is disclosed as such.

§0 is the pre-registration, committed before any Stage 2 source-learning outcome and before any one-use target was built.

---

## §0 Pre-registration

### 0.1 Phase 5 (`ed6fabf`) audit, verified against source

- **Over-confident trust:** memory + F0 made 4 / 6 / 1 accepted wrong repairs.
  - The trust weights used file / date / version cues (`de_phase5/investigate.py` `claim_features`).
  - "Undetermined" answers never produced a trust record (`lineage5.train_pass`).
- **No room above F0:** the learned procedures matched F0 on single-decision projects.
- **The Phase 5 multi-filter closure extension** lived outside the frozen gate (`investigate.decision_points`).

### 0.2 Ledger and grant

- **Previous allowance:** the mi ledger has 218 s (`scripts/mi_budget.py`), untouched.
- **Owner grant:** +4,000 s (`artifacts/agi6_grant.json`), metered under the new prefix `a6-` by `scripts/agi6_exec.py`.
- **Executor:** it **refuses any run beyond its stage ceiling**, which closes the Phase 5 overrun loophole.
- **Cap and reserve:** Phase 6 cap 3,600 s (`artifacts/agi6_allocation.json`), so the reserve is 400 + 218 = 618 s.
- **Stage ceilings:**

  | Stage | Ceiling |
  |---|---|
  | s1 | 600 s |
  | src | 1,250 s |
  | meta | 500 s |
  | eval | 1,050 s |
  | rep | 200 s |

- **Stage 1 used 536 s**, including a **75 s post-hoc ledger debit** for development smoke searches I had run outside the
  executor (row `a6-s1-uncharged-dev-adjustment`). It also includes a 240 s run that timed out on a slow generator check,
  since fixed.
- **Not charged:** installing `duckdb 1.1.3`, `pyyaml 6.0.2` and `jinja2 3.1.4`; generator timing checks (no learner).
- **Inconsistency in the instruction:** Stage 2 text says 4 × 3 × 180 s = 2,160 s but allocates 1,250 s. The ceiling binds:
  12 lineages × 98 s.

### 0.3 What was built (`src/nexus/de_phase6/`; tests `tests/test_agi6_arena.py`, 8 passed)

**Multi-language substrate** (`ir6.py`, `engines6.py`):
- **Legacy inputs:**
  - SQLite SQL;
  - Hive / Postgres / Snowflake SQL, produced and **lifted by real `sqlglot` transpilation** (the dialect's semantics are
    kept, e.g. Hive real division and `CAST(.. AS INT)`, and normalised);
  - PySpark `.py`;
  - dbt-style Jinja models (`{{ config }}` / `{{ ref }}`, rendered by `jinja2`) with `schema.yml` tests;
  - **read-only legacy Scala** Spark jobs, lifted by a lexical Scala → Python rewrite plus the `ast` lifter.
- **Engines:** SQLite, **DuckDB** (native `TRY_CAST` / regex validity tests), and Spark 4.0.1 ANSI (127.0.0.1 bind).
- **New operations:** `le`, `nonempty`, column-to-column comparisons.
- **New operators:** `filter_cmp` (`<`, `<=`), `col_compare`, `require_nonempty`.
- The Phase 4 modules are extended at run time; their files are unchanged.

**Nine-paradigm arena** (`world6.py`): a project is a pipeline of 1–3 stages, each with its own legacy language, engine and
target language. Stage k reads stage k−1's clean output.

| Tier | Paradigms |
|---|---|
| 1 | P1 batch (chunk window with an end-boundary decision point, duplicate-batch protection, conserved sums); P2 CDC (latest version, tombstones); P3 ELT (ANSI-safe parse: quarantine or default) |
| 2 | P4 analytical (join fan-out dedup, normalised dimensions); P5 streaming (watermark and checkpoint decision points, replay dedup); P6 reverse-ETL (required-field rejection, normalisation); P7 MLOps (point-in-time `feature_ts <= label_ts` decision point, NaN-safe ratio); plus two **source compositions** X1 = ELT→CDC and X2 = MLOps→reverse-ETL |
| 3 (held out) | **P8** lift-and-refactor of legacy Scala / Hive jobs to DuckDB / PySpark; **P9** hybrids A streaming→batch (Spark→DuckDB), B CDC→ELT→analytical (SQLite→DuckDB→Spark), C analytical→MLOps→reverse-ETL (DuckDB→Spark→SQLite) |

- **Intermediate stages** carry `schema.yml` tests (unique / not_null / accepted_values).
- **Decision points** use the Phase 5 modes with documents carrying provenance; the business answer is drawn per project.
- **Generator checks:**
  - per-fault identifiability;
  - truth = engines;
  - a later dedup that is redundant after an earlier one is dropped;
  - the conventional window start is always evidenced;
  - a coincidence check on decision-point columns and final-stage values;
  - boundary visibility exactly as declared;
  - hidden batches always test every boundary.

**Investigation and the unified gate `de_accept_v3`** (`pipeline6.py`):
- **Search modes:** whole-pipeline or **stage-decomposed** search (the earliest stage with failing `schema.yml` tests
  first), optional **invented-skill chaining**.
- **Prescreening:** stages are prescreened on SQLite and verified on the declared DuckDB / Spark engines, with
  engine-native continuation after an ANSI failure. This is fixed in every arm (disclosed; not a learnable switch).
- **The gate:**
  - held-back golden folds;
  - pipeline invariants on the declared engines (ANSI no-crash, order invariance, stress rows, empty batch, relabelling
    invariance, types, unique key);
  - closure at edit distance 1 over all stages, compared on boundary rows **and single-row probes from every visible row**.
    That is **Fix 2**: the Phase 5 multi-filter detector now inside the gate.
- **Disclosed modelling assumption:** inserted filters are hypotheses only on subjects the documents mention, and never
  when vacuous on the visible stage input. Every fault is visible by construction.

**Calibrated trust** (`trust6.py`, **Fix 1**):
- **Features:** only status:approved, authority:contract, consensus. File names, dates and versions are never features
  (an invariance check is tested).
- **Negative evidence:** "undetermined" answers are recorded against both claims.
- **Resolution:** only when a verified, legitimate feature with support ≥ min_support separates the winner from the loser.
  **Draft vs draft is never resolved.**
- **Scope:** nothing about the business **answer** is stored as a default.

**Method invention** (`skills6.py`):
- Verified repairs, and in the Full cohort verified partial *stage* repairs of unsolved projects, are rewritten in **role
  form**: column parameters become the roles those columns play (integer / dirty / text / low-cardinality / unique /
  duplicated / state-ranged / blanks).
- Stage-local sub-sequences recurring in ≥ min_support projects are **anti-unified into skills**.
- Skills are admitted by the corrected rule on admission projects their precondition applies to, **re-bound to an unseen
  project's columns** at use, and **chained across stages**.
- No paradigm, family or column name appears in the module.
- In dev the system invented, among others, "exclude a low-cardinality text column's value `'D'`" and "deduplicate a
  duplicated text key by an integer order column".

**Procedure composition** (`procedure6.py`):
- The Phase 5 typed language: `search(whole | decompose, skills on | off)`, `read` / `read_all`,
  `resolve(none | calibrated)`, `ask(first | unclaimed | conflicted)`, `submit_or_abstain`, `if`, `repeat`, `call`.
- **F0:** read all → `search(whole, skills on)` → `resolve(calibrated)` → ask if unresolved → submit.
- **Composition is automatic**, from `SEED = [search(whole, off), submit_or_abstain]`: typed exhaustive insertions on the
  inlined program plus sampled edits, each in its own comparison under the corrected rule, with stored procedures and
  execution coverage. It is evaluated by replay of recorded validation experience.

**Evolvable improver M** (`lineage6.py`):
- M sets how NEXUS learns: skill invention support / length / role granularity, trust margin / support, procedure cycles /
  typed pairs, source search budget / stall, curriculum.
- Full and Solved-Only lineages **evolve M** by paired rollouts. Both clones continue the same next source projects and
  are evaluated on the same rollout projects; adoption follows the corrected rule (**no equal-zero / cost-only adoption**).

### 0.4 Stage 2 — four cohorts (`scripts/agi6_source.py`)

- **Repetitions:** r = 0, 1, 2. Every cohort of a repetition sees the **same exogenous source stream**
  (`seeds6.lineage_block`: train / admission / rollout blocks).
- **Cohorts:**
  - **Full:** everything on, M evolves.
  - **Solved-Only:** no refutation weights, no refuted-submission trust records, no partial-stage skills; its own
    procedure and M.
  - **Fixed:** the procedure stays F0 and M stays M0 (memory still learns).
  - **Scrambled:** the same executions with every feedback association permuted (verification, trust labels, skill
    provenance). Specified here, before evaluation.
- **Budget:** 98 s per lineage, executor cap 102 s (12 × 102 = 1,224 ≤ 1,250).
- **Execution:** three waves of 4 parallel jobs, one per cohort, so the CPU contention is matched across cohorts.

### 0.5 Stage 3 — improver vs improver (`scripts/agi6_meta.py`)

- 3 reps × {M* (the evolved M of Full_r), M0, M_rand} = 9 clones.
- Each runs a full 40 s trajectory from the identical Full_r endpoint: Tier-2 source learning, skill invention / admission,
  then procedure composition under its own M. Executor cap 42 s.
- **Panel:** the 18-project Tier-2 panel (`seeds6.panel_manifest`, one-use), run in the meta stage with caps ≤ 120 s in total.
- **Learning curves** (verified source projects vs projects seen) are recorded for the learning-to-learn analysis.

### 0.6 Stage 4 — frozen evaluation (`scripts/agi6_eval.py`)

**Targets:** 72 one-use targets (`seeds6.target_manifest`).

| Tier | Paradigms | Projects |
|---|---|---|
| 1 | P1–P3 × 8 | 24 |
| 2 | P4–P7 × 8 | 32 |
| 3 (held out) | P8 × 8 + P9 × 8 | 16 |

- Mixed engines and languages, held-out column names on half, and **10 undecided-requirement projects** (abstention test).

**Arms:**

| Arm | Definition |
|---|---|
| A1 | Fresh memory + F0 |
| A2_r | Fixed-cohort memory + F0 |
| A3_r | Full: memory + learned procedure + library |
| A4_r | Solved-Only endpoint |
| A5_r | A3 without invented skills (procedure only) |
| A6_r | Scrambled endpoint |

- **Episode:** search budget **1.0 s** per episode, one 1-row clarification at 2.0 cost-s, `de_accept_v3`, and the evaluator
  executes the submitted target files of every stage.
- **Pre-registered size rule:** the dev rehearsal cost about 2 s per arm-episode, and the full 16 arms × 72 does not fit
  1,050 s.
  - The **primary arms A1, A2_r0–2, A3_r0–2** run on all 72 targets.
  - The **attribution arms A4, A5, A6** run on **r0** on all 72 targets. They extend to r1 / r2 only if a recorded transfer
    (unused s1 / src / meta / rep) covers the cost predicted from the measured primary-arm cost.

### 0.7 Pre-registered targets (owner's) and decision rules

**Unit and test:** the target project. Lineage arms are averaged over the available reps. Paired sign-flip test, Holm over
the 3 primary completion contrasts.

1. **Safety:** 0 accepted wrong repairs in every arm, on all 72.
2. **Completion:** Full − Fresh F0 ≥ +10 pp overall **and** ≥ +15 pp on Tier 3, Holm p < 0.05.
3. **Procedure:** learned procedure (A3) − Fixed F0 (A2) > 0 on Tier 2+3, Holm p < 0.05.
4. **Cost:** ≥ 25 % lower cost (runs + questions, and cost-seconds) on shared solves vs Fresh F0. The payback horizon is
   reported against total training cost.

**Attribution (descriptive with p-values):**
- A3 − A4 (failure memory);
- A3 − A5 (invented skill library);
- A3 − A6 (placebo);
- Stage 3: M* vs M0 vs M_rand on the panel, plus learning curves.

**Recovery and one-use:** crashed jobs may resume only rows never written; one-use rows are never rerun; build failures
are logged as rows.
