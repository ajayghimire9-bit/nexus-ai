# NEXUS Phase 4 — Dedicated Data-Engineering & PySpark Scaling, Adversarial Acceptance, Multi-Fault Failure Learning

**Status: NOT LOCKED.** Branch `claude/s456-work` (pushed as `codex/nexus-data-engineering`), started from `7521bf5`.
`main` (`d7ac8c5`) untouched. Checker kernels v1–v5 read-only and pinned. The synthetic six-world puzzle tasks are frozen:
Phase 1–3 world files are protected and not used in Phase 4.

§0 is the pre-registration, written and committed before any Stage 2 source-learning outcome and before any one-use
target project was built. §1 onward is added after the runs.

---

## §0 Pre-registration

### 0.1 Audit of `7521bf5` (Phase 3) — what it achieved and where it fell short

**Achieved:**
- A real-pipeline repair cycle on SQLite and Spark 4.0.1 (ANSI mode).
- Learned repair skills that transfer from SQLite to Spark and across families.
- 37–58 % fewer candidate runs than the fixed-order baseline at matched completion. On the dev batch it was 269 runs with
  memory against 488 with memory reset, and 435 with the skill removed.

**Fell short in four ways:**
1. **Spark budget.** The 1.2 s Spark budget allowed about 30 executions, so Spark verified 1/6 against 5/6 on SQLite.
2. **Training ceiling.** Two of three Full lineages solved every training project. That left nothing for the failure
   archive P to learn from, and 0 of 3 improver edits were adopted, so M* = M0.
3. **Visible-batch overfit.** All 23 arms accepted the same wrong watermark repair (`>` where `>=` was required). The
   visible batch had no row exactly at the threshold.
4. **No real files.** Pipelines were declarative configs, not real `.sql` / `.py` files.

### 0.2 Ledger and allocation

- **Ledger:** 2,113 s carried at `7521bf5`, checked with `scripts/agi3_budget.py` and `scripts/mi_budget.py`.
- **Phase 4 cap:** 1,800 charged s (`artifacts/agi4_allocation.json`, guard `scripts/agi4_budget.py`, run prefixes
  `mi-agi4-*`). Every run is metered by `scripts/mi_exec.py`.
- **Stage ceilings:**

  | Stage | Ceiling |
  |---|---|
  | s1 | 350 s |
  | src | 600 s |
  | meta | 350 s |
  | eval | 380 s |
  | rep | 120 s |

- **Inconsistency in the instruction:** Stage 2 text says 4 cohorts × 3 reps × 150 s (= 1,800 s) but allocates 600 s.
  The 600 s ceiling binds, so 12 lineages share it.
- **Stage 1 actually used** 340 s over 25 metered runs. That covers probes, benchmarks, dev smoke tests, calibration,
  debugging and the operating cycle. All logs are in `artifacts/mi_logs/mi-agi4-s1-*`.
- **Not charged:** installing `sqlglot 26.16.4` (pure Python), like JDK 17 / PySpark in Phase 3.

### 0.3 What was built (`src/nexus/de_phase4/`, tests `tests/test_agi4_de.py`)

**Real-file adapter** (`adapter.py`, `ir.py`):
- Each project ships an executable `pipeline.sql` (SQLite 3 script: one TEMP VIEW per stage, `CREATE TABLE clean` /
  `rejects`, state files as `state_*` tables) or `pipeline.py` (PySpark 4 DataFrame script, `run(spark, raw, state)`,
  executed with `spark.sql.ansi.enabled=true`).
- Legacy files are written in varied styles: keyword case, view / variable names, comments, `filter` / `where`.
- The learner LIFTS the file into a stage IR with real parsers: sqlglot for SQL, Python `ast` for PySpark.
- It inspects stages and clauses: CAST / `try_cast`, COALESCE, NULLIF, ROUND, GLOB / `rlike` validity tests,
  `ROW_NUMBER() OVER` / `Window.partitionBy` dedup, checkpoint / watermark state reads, GROUP BY / `groupBy().agg`.
- Candidate repairs are lowered back to the project's language. The engine executes the TEXT.
- A repair is written as `submission/pipeline.{sql,py}` plus `PATCH.diff`. The independent evaluator executes that
  submitted file on 2 hidden batches.
- Anything outside the supported subset raises `Unsupported` and the learner abstains (ABSTAIN_UNSUPPORTED).
- Honest limit: the search edits the lifted IR and re-emits whole files, so comments are not preserved in a patch.

**Multi-fault curriculum** (`world.py`): 8 mechanism families, each a business rule with a correct form and a legacy-defect
form.

| Group | Family | Mechanism |
|---|---|---|
| Source | F1 | parse |
| Source | F2 | ratio |
| Source | F3 | latest-version dedup |
| Source | F4 | exactly-once replay |
| Source | F5 | default-label fill |
| Source | F6 | watermark lateness |
| Untouched | F7 | case / whitespace key normalisation |
| Untouched | F8 | SCD-2 tombstone deletes |

- A project has a primary family and k = 1–4 faults (the primary plus k−1 compatible mechanisms), optionally plus
  mechanisms the legacy file already gets right. Shapes are row-level, entity (latest per key) and aggregate.
- **Per-fault identifiability:** reverting any single fault must change the visible result on the real SQLite engine.
- The business truth must run identically on SQLite and in the pure-Python reference.
- F7 / F8 are refused by every builder except the Stage 4 target builder. This is unit-tested.
- **Calibration** (dev projects, empty memory, source budgets 0.5 s SQLite / 2.5 s Spark; `artifacts/agi4_dev/calib_53700.json`):
  - verified 18/36 = 50 % (k1 11/12, k2 4/12, k3 2/6, k4 1/6);
  - this is inside the 40–60 % target, so the source curriculum spans k = 1–4.

**`de_accept_v2`** (`accept.py`), used by every evaluated arm:
1. **Held-back split.** Golden rows and quarantine ids are split into 5 folds of 20 %. A search scores only the 80 %
   synthesis split, and a candidate must reproduce the held-back fold it never saw. If it fails, the search restarts with
   the next fold (K-fold rotation).
2. **Invariant probes.** No crash (ANSI), contract column types, unique key, order invariance (reversed landing order),
   non-corruption (fresh-keyed dirty / zero-denominator / empty-text / non-terminating-ratio rows must not change visible
   keys), an empty batch, and **relabelling invariance**: visible + a copy with identity columns relabelled must give the
   visible output plus its relabelled copy, or doubled sums. That catches dedup keys that fit the visible batch by
   coincidence.
3. **Ambiguity closure.** Every competing repair at edit distance 1 that passes 1 and 2 is compared with the candidate on a
   boundary batch (rows at T−1, T, T+1 of every filter threshold) and on the stress rows:
   - any disagreement means the visible evidence under-determines the repair;
   - the gate submits only if a learned preference (from verified / refuted source submissions) separates the choice by
     the improver's margin; otherwise it abstains (UNDER_SPECIFIED_WARNING);
   - a closure cut by its caps or the budget also abstains.

**Failure archive P and learning** (`learner.py`):
- Refutations go to negative pi_de weights.
- **Verified partial repairs** (more synthesis checks and no loss on the held-back fold) of unsolved projects go to P,
  with their stage and the evidence features they removed, plus positive weights on those features.
- **Refuted submissions** (hidden-batch failures during source learning) update disambiguation preferences: −1 for the
  choice and +0.5 for the alternatives it beat. A verified choice adds only +0.25, because the alternative was not tested.
- P partials that removed the same evidence in ≥ 2 unsolved projects are promoted to provisional stage skills, admitted
  only after the separate admission test.
- The Solved-Only cohort learns only from verified solves (unit-tested).

**Search budgets and Spark** (`world.py`):
- Per-project caps in Stage 4: 2.5 s SQLite / 10 s Spark.
- Spark start-up is 2–3.5 s per worker, against 33 s in Phase 3. That was the macOS hostname lookup; the fix is binding
  the driver to 127.0.0.1. The session is warmed before any project clock starts.
- Execution cost is 17.9 ms per script (whole-stage codegen and adaptive execution off, input cached on 1 partition) against
  28.9 ms default (`mi-agi4-s1-sparkbench-b2`).
- Cross-engine mode `sqlite_first`: candidates are screened on SQLite, and only SQLite-passing candidates execute on Spark.
  Spark-native search continues only from Spark failures (ANSI semantics).
- Stall rule: stop when the best score has not improved for max(0.25 s, stall_frac × budget).

**Improver M** (`lineage.py`): 7 statements, all read by running code, with 35 single-parameter edits.

| Statement | What it controls |
|---|---|
| `search` | localisation order, whole vs stage-wise decomposition, depth, stall, cross-engine mode |
| `memory` | P retrieval priority, skill match, max skills, pruning |
| `learn` | learning rates |
| `ambiguity` | preference vs abstain, margin |
| `admit` | admission speed-up threshold |
| `curriculum` | curriculum rule |
| `schedule` | admission period |

- Each Full and Solved-Only lineage evaluates distinct not-yet-tried edits. The first four target localisation,
  decomposition, failure-archive priority and cross-engine adaptation; the target is at least 10 per lineage.
- **Rollout protocol:** two clones learn 2 projects and are then evaluated on 4 rollout projects (2 Spark projects for a
  cross-engine edit).
- **Adoption rule:** M′ is adopted iff it verifies more, or as many with ≤ 90 % of the runs and no more silent errors.
- The lineage continues from the winning clone.

### 0.4 Stage 1 development history (dev seeds 53600–53999 only)

The gate was developed on dev projects and changed after each finding. On the 16-project smoke set the silent-error count
moved as follows:
- **Smoke 1 (Phase 3-style rounding):** the visible checks compared reals at 2 decimals, hiding missing ROUND repairs.
  Reals now compare at 6 decimals.
- **Smoke 2:** a single fixed held-back fold left the search blind when the only exposing row was held back. That led to
  the K-fold rotation.
- **Smoke 3:** probe rows appended to the visible rows fabricated impossible replays. Comparisons now use separate batches.
- **Smoke 4:** dedups on a measure column fit the visible batch by chance. That led to the relabelling invariant.
- **Smoke 4:** a column with many malformed values was not treated as numeric. A column is now integer-like if the legacy
  file casts it, or if at least half its values are integers.
- **Smoke 6:** gate on — 11/16 verified, 0 silent; gate off (Phase 3 behaviour) — 13/16 verified, 3 silent.

The cycle runs found three more problems:
- A probe row was quarantined for an unrelated malformed value. Probe rows now get valid values elsewhere.
- **Soundness bug:** the closure capped competitors at 6, then claimed "unique". A cut closure now abstains.
- Vacuous filter thresholds outside the observed range manufactured disagreements. They are now pruned.

**Operating cycle** (`artifacts/agi4_cycle.json`, run `mi-agi4-s1-cycle4`):
- Project A (`F2.k3.sqlite.53900`, 3 faults, `pipeline.sql`) was investigated: lifted into 3 stages, legacy failures
  recorded.
- It was attempted twice. The repair it found (dedup latest + watermark filter + real division + ROUND) passed every
  visible, held-back and probe check. The closure found the `>` vs `>=` watermark ambiguity, and with no learned preference
  yet, it abstained instead of guessing.
- So the cycle did not reach verify / admit on A, and this is recorded as such.
- **Reuse batch:** learn on 12 dev projects, then test 8 others at eval budgets (4 `.sql`, 4 `.py`). 0 silent errors in
  every condition.

  | Condition | Verified (of 8) |
  |---|---|
  | Full | 5 |
  | Memory-Reset | 4 |
  | Solved-Only | 3 |
  | Full-minus-skills | 6 |

  The two multi-fault Spark projects F3.k2 and F4.k3 were verified only by Full and Full-minus-skills. The learned policy,
  not the skills, carried that gain.

### 0.5 Stage 2 — four-cohort source learning (`scripts/agi4_source.py`)

- **Repetitions:** r = 0, 1, 2. Seed block `seeds.src_block(r)`: agi4de/source 54100 + 500 r; learning 0–249,
  admission 250–349, rollouts 350–499.
- **Cohorts:**
  - **Full:** failure memory on, meta on.
  - **SolvedOnly:** own cohort from t = 0, failure memory off, own curriculum and meta checks.
  - **Fixed-M0:** M frozen, replays Full_r's learned-project sequence.
  - **Random-Proposal:** matched random M and random skill proposals, replays Full_r's sequence.
- **Budget:** lineage budget 44.5 s, `mi_exec` cap 49.5 s (12 × 49.5 = 594 ≤ 600).
- **Execution:** two waves of 6 parallel jobs (Full + SolvedOnly, then Fixed-M0 + Random-Proposal) through
  `scripts/agi4_jobs.py`, which enforces the stage ceiling.
- Source lineages are never rerun. A crashed lineage is reported as crashed.

### 0.6 Stage 3 — improver versus improver (`scripts/agi4_meta.py`)

- 3 reps × {M* (the Full endpoint's adopted M), M0, M_rand (seeded matched random)} = 9 clones.
- Each starts from the identical frozen Full_r endpoint and runs a complete 33.5 s trajectory under its own M: curriculum,
  search, P priority, cross-engine mode, admission, pruning.
- Paired seed blocks: `seeds.meta_block(r)`, agi4de/source_meta. `mi_exec` cap 38 s.

### 0.7 Stage 4 — frozen one-use evaluation (`scripts/agi4_eval.py`)

**Targets** (`seeds.eval_manifest()`, agi4de/eval 56100–56123, one-use):
- 6 families (F1, F3, F4, F6 new instances; F7, F8 untouched) × {SQLite k1, SQLite k3, Spark k1, Spark k3}.
- 24 projects: 12 SQLite + 12 Spark.

**Improver panel** (`seeds.panel_manifest()`, agi4de/panel 56200–56211, one-use):
- the 6 source mechanisms × {SQLite, Spark}, k = 2 (12 projects);
- evaluated for the 9 improver clones.

**Arms** (17):

| Arm | Count | Definition |
|---|---|---|
| Full_r | 3 | frozen Full endpoint |
| SolvedOnly_r | 3 | Solved-Only cohort endpoint |
| Fixed_r | 3 | Fixed-M0 endpoint |
| Rand_r | 3 | Random-Proposal endpoint |
| Placebo_r | 3 | Full's M* with matched irrelevant memory: skills, weights, preferences and P permuted / randomised |
| Init | 1 | Memory-Reset: empty memory, M0 |
| Baseline | 1 | no memory, fixed engineer order, same tools / gate / budgets |

**Episode:** budgets 2.5 s SQLite / 10 s Spark wall after a warm session, no exploration, `de_accept_v2`, independent
evaluator on the submitted file.

**One-use claim:** under an fcntl lock (`agi4-eval`). No target is rebuilt or rerun after its row is written.

**Budget plan:** `plan` predicts the cost from the Stage 1 eval-budget measurements. Unused Stage 1 / Stage 5 ceiling may
be transferred to Stage 4 by a committed allocation entry before any Stage 4 outcome. If the ceiling is reached anyway, the
unfinished rows are reported as not run.

**Primary targets** (decided per pre-registered rule; Full pooled over r = 0–2, family-clustered bootstrap 95 % intervals
reported):
1. **Completion:** Full − X ≥ +10 pp exact independently-verified completion for each of X = Memory-Reset (Init),
   Placebo, Baseline. Also reported on the Spark half.
2. **Cost:** at matched completion (projects verified by both), Full needs ≥ 20 % fewer candidate runs than both Init and
   Baseline (pooled over reps).
3. **Separation:**
   - P — Full − SolvedOnly completion (and cost at matched completion) > 0;
   - M — ≥ 1 adopted edit per Full lineage, and M* > M0 on the improver panel (solved, then runs).
4. **Zero silent errors:** 0 accepted wrong repairs across the 24 targets, counted over every arm.

Everything not listed is descriptive.

### 0.8 Protection

- `scripts/agi4_protect.py` snapshot before (`artifacts/agi4_protected_hashes_before.json`): 1,472 frozen files, 0
  violations, `main` = `d7ac8c5`, checkers v1–v5 pinned.
- An after snapshot must show 0 violations.
- Phase 1–3 test files are unchanged. Each phase's test file runs in its own process, because every seed registry asserts
  its ranges are above all others registered in that process.

**Tests:** `tests/test_agi4_de.py` 11 passed; `tests/test_agi3_campaign.py` 9 passed; checker kernels 42 passed.

---

## §1 Results (NOT LOCKED)

**Commits:**
- protocol `2701de8`;
- Stage 2 deviation (Full_r2 truncation) `c6755bd`;
- source freeze `a9ed328`;
- pre-evaluation freeze (meta clones, plan, budget transfers) `499d6e5`;
- results: this commit.

**Raw data:** `artifacts/agi4_src/`, `artifacts/agi4_meta/`, `artifacts/agi4_eval/*.jsonl` (408 main + 108 panel rows),
`artifacts/agi4_eval/result.json`.

### 1.1 Budget (charged wall seconds, `scripts/agi4_budget.py`)

| Stage | Used | Ceiling (after recorded transfers) |
|---|---|---|
| s1 dev / adapter / gate / cycle | 340 | 341 (350) |
| src four-cohort learning | 518 | 518 (600) |
| meta improver clones | 285 | 286 (350) |
| eval Stage 4 + panel | 276 | 615 (380 + transfers) |
| rep score + protection | 1 | 40 (120) |
| **Phase 4 total** | **1,419** | **1,800** |

- The carried balance is now **694 s**, above the 313 s reserve.
- The Stage 4 transfers went beyond the pre-registered wording (Stage 1 / 5 only) to include unused src / meta ceiling.
  They were recorded and pushed before any target was built, and Stage 4 used only 276 s of the 615 s.

**Disclosed execution events:**
1. **Full_r2 truncated.** Full_r2 was killed by its 49.5 s cap: six concurrent JVM starts took ~6.5 s each. It was not
   rerun. Its last between-steps snapshot (50 projects, 8 meta-edits) is the endpoint (`Full_r2.truncation.json`).
2. **Panel Spark chunk launched late.** The Spark half of the improver panel was refused at first launch. The job runner
   reserves each running job's full cap, and four jobs were running. The chunk had never started and had no rows; it was
   launched once afterwards (54 rows).
3. **Stage 3 trajectories shortened.** Stage 3 clones ran 31 s trajectories instead of 33.5 s, recorded before they ran.

### 1.2 Stage 2 — source learning on multi-fault projects

Verified / projects in source learning (exploratory submissions under ambiguity count as silent there, by design):

| Cohort | r0 | r1 | r2 |
|---|---|---|---|
| Full | 34/57 | 38/58 | 37/50 (truncated) |
| Solved-Only | 27/49 | 36/55 | 33/54 |
| Fixed-M0 | 33/57 | 39/58 | 39/50 |
| Random-Proposal | 40/57 | 31/49 | 38/50 |

**Training ceiling removed:**
- Full verified 60–74 % of its source projects; by fault count k1 47/53, k2 39/54, k3 17/38, k4 6/20. Phase 3 Full had
  100 % in two of three lineages.
- So P received unsolved multi-fault projects: 80 records per Full lineage (the bound).
- Admitted full-repair skills: 3, 3, 0.

**No stage skill from P.** P-promoted stage skills were proposed 0 times in Full, because no operator removed the same
evidence in ≥ 2 unsolved projects within one lineage. P acted only through policy weights and preferences.

**Learning from refuted submissions:**
- All three Full lineages learned `filter_file:ge:sub` > `gt:sub` (+1.25 / −0.5, +0.75 / −0.75, +4.0 / −1.0). This is
  the Phase 3 watermark lesson: `>=` is right.
- The Solved-Only lineages, which cannot learn from refutation, learned the **opposite** (`gt:sub` +1.25, +0.5, +1.75).
  A `>` submission that happens to pass the hidden batches is weak evidence they can't correct.

**Improver.** Full evaluated **9, 8 and 8** distinct edits, below the target of ≥ 10 (budget-limited). It adopted **1, 0
and 1**:
- r0 `admit.speedup = 0.3`;
- r2 `search.cross_engine = off`.

The r2 adoption is a **degenerate win**. Both clones solved 0 of the 2 Spark rollout projects, and "off" used 75 runs
against 689 because Spark-native search gives up sooner. The adoption rule (as many solved with ≤ 90 % of the runs) rewards
giving up when nothing is solved. This flaw is now known; see 1.6.

### 1.3 Stage 4 — 24 unseen projects, 17 arms (2.5 s SQLite / 10 s Spark, `de_accept_v2` for every arm)

| Arm | All 24 | SQLite 12 | Spark 12 | Instances 16 | Untouched F7/F8 8 | Silent | Ambiguous abstain |
|---|---|---|---|---|---|---|---|
| Full r0 / r1 / r2 | 13 / 13 / 11 | 5 / 5 / 5 | 8 / 8 / 6 | 9 / 8 / 7 | 4 / 5 / 4 | 0 | 10 / 10 / 10 |
| Solved-Only | 11 / 11 / 11 | 5 / 5 / 5 | 6 / 6 / 6 | 7 / 8 / 7 | 4 / 3 / 4 | 0 | 10–11 |
| Fixed-M0 | 14 / 13 / 13 | 5 / 5 / 5 | 9 / 8 / 8 | 9 / 8 / 9 | 5 / 5 / 4 | 0 | 9–10 |
| Random-Proposal | 10 / 10 / 14 | 4 / 5 / 5 | 6 / 5 / 9 | 7 / 6 / 9 | 3 / 4 / 5 | 0 | 9–12 |
| Placebo | 11 / 12 / 11 | 5 / 5 / 5 | 6 / 7 / 6 | 8 / 8 / 7 | 3 / 4 / 4 | 0 | 11 |
| Init (Memory-Reset) | 11 | 5 | 6 | 8 | 3 | 0 | 11 |
| Baseline | 11 | 5 | 6 | 8 | 3 | 0 | 11 |

**Pre-registered targets:**

| # | Target | Result | Verdict |
|---|---|---|---|
| 1 | Completion ≥ +10 pp vs Init, Placebo and Baseline | Full − Init **+5.6 pp** [95 % CI −4.2, 15.3]; Full − Placebo **+4.2** [−2.8, 11.1]; Full − Baseline **+5.6** [−4.2, 15.3]. Spark half: +11.1 / +8.3 / +11.1 pp, CIs include 0. Untouched F7 / F8: Full − Init **+16.7** [8.3, 25.0], Full − Placebo **+8.3** | **Not met** |
| 2 | Cost ≥ 20 % fewer runs vs Init and Baseline at matched completion | Pooled saving 6.1 % vs Init, 2.2 % vs Baseline. r0 / r1 save 9–14 %; r2 is 42–43 % *more* expensive (its adopted `cross_engine = off`) | **Not met** |
| 3a | Failure memory: Full − Solved-Only > 0 | **+5.6 pp** [2.8, 8.3] (r0 +8.3, r1 +8.3, r2 0), +11.1 pp on Spark; cost difference ≈ 0 (−0.6 %) | **Positive, small** |
| 3b | Improver: ≥ 1 adopted edit per Full lineage, and M* > M0 on the panel | Adopted 1 / 0 / 1. Panel solved M* / M0 / M_rand: r0 11 / 11 / 10, r1 11 / 11 / 6, r2 9 / 10 / 9 | **Not met** |
| 4 | 0 accepted wrong repairs | **0** across all 408 main rows and 108 panel rows. The gate trades completion for safety: about 10 of 24 targets per arm ended in an ambiguity abstention | **Met** |

Notes on the targets:
- **Target 1:** the untouched-family gain is the one interval that excludes 0.
- **Target 3a:** this is the first Phase-campaign evidence that incomplete experience adds completion. It is a 1-project
  difference on 24 per repetition, so it is suggestive, not established.
- **Target 3b:** in r0 and r1, M* behaves exactly like M0 (r1 M* = M0; r0's admission edit never acts at evaluation). In
  r2, M* is worse. No improver gain.
- **Target 4:** compare Phase 3, where every arm accepted the same wrong watermark repair, and Stage 1 dev, where the gate
  off had 3 / 16 silent.

**Comparison with Fixed-M0.** Full − Fixed-M0 is **−4.2 pp**: the improver's edits hurt slightly. Fixed-M0 shares Full's
learned project sequence without the edits.

**Spark bottleneck.** Even memory-free Init verifies 6 / 12 Spark projects, against 1 / 6 in Phase 3. The 10 s budget,
SQLite screening and the 127.0.0.1 start-up fix are what changed. The best arms reach 8–9 / 12.

### 1.4 What the evidence establishes

**Established:**
- Real `.sql` / `.py` repair at scale on SQLite and Spark 4 ANSI, with zero accepted wrong repairs on 24 unseen projects
  under an acceptance gate that abstains when the visible evidence under-determines the repair.
- Spark is no longer the bottleneck.

**Suggestive, not established:**
- Failure memory: +5.6 pp over Solved-Only, with the interval above 0, but on 24 projects with 1-project differences.
- An untouched-mechanism gain over memory reset: +16.7 pp.

**Not established:** the ≥ 10 pp completion target, the ≥ 20 % cost target, and any improver gain (M* ≤ M0).

**Unknown:** whether the gain persists with more targets per family; whether a better adoption rule finds useful edits.

### 1.5 Protection

`artifacts/agi4_protected_hashes_after.json`:
- 0 violations;
- 1,472 frozen files unchanged (Phase 1–3 included);
- checkers v1–v5 pinned;
- `main` = `d7ac8c5`;
- the 29 additions are this phase's run logs;
- the one-use claims `agi4de/eval` and `agi4de/panel` were made once (run id `agi4-eval`).

### 1.6 Recommended next experiment

**Ambiguity-resolving acceptance with a better improver criterion.**

About 10 of 24 targets per arm end in a correct-but-unresolved `de_accept_v2` abstention. That is the largest remaining
completion loss, and it is exactly where failure memory showed its signal. Next:
- (a) allow a single bounded stakeholder clarification per project (counted), against preference resolution;
- (b) change the meta-adoption rule so equal-zero-solved rollouts never adopt on run count;
- (c) use ≥ 6 targets per family so 1-project differences can be resolved.
