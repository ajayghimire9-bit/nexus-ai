# NEXUS Phase 3: real-pipeline operating cycle (SQLite + Spark 4 ANSI), incomplete experience, multi-round improvers

Status: **NOT LOCKED**. The protocol and the Stage 1 milestone below are committed before any Phase 3 one-use target is
opened; results follow in a separate commit.

## 0. Pre-registration

### 0.1 Start, environment, budget

* **Start:** `a1fd9eb` (Phase 2 complete) on `claude/s456-work`, which is pushed as `codex/nexus-data-engineering`; both
  remotes are equal. No campaign process was running.
* **Hardware:** Apple M4, 10 cores (4 performance), 16 GB, Python 3.13.5. No local model is used anywhere in Phase 3.
* **Runtimes, installed unattended:**
  * OpenJDK 17.0.21, via the Homebrew *formula* `openjdk@17` (no sudo, no cask, no system symlink);
  * PySpark 4.0.1 in the project venv;
  * `JAVA_HOME` and `PATH` are set inside the runner (`campaign3/de_world.SparkRuntime`);
  * the session is `local[2]`, 1 shuffle partition, UI off, ANSI on (the Spark 4 default), with quiet logging.
* **Install time** is not charged, per the owner's instruction. **JVM start-up inside experiments is charged** (≈ 33 s per
  Spark worker process). It is kept out of every per-project search budget by a warm session.
* **Budget:** at most **3,200 charged s** of the carried 4,618 s (≥ 1,418 s stay untouched), with no new grant
  (`scripts/agi3_budget.py`). Stage 1 used 487 of 550 s.

  | stage | ceiling (s) |
  |---|---|
  | s1 | 550 |
  | src | 1,350 |
  | meta | 450 |
  | eval | 650 |
  | rep | 200 |

* **Protection snapshot:** `artifacts/agi3_protected_hashes_before.json` shows 0 violations over 1,355 frozen files:
  MI-1 / MI-2 / X7 / MI-3, Phase 1, **Phase 2**, `de_*` and `shared_brain`. Checkers v1–v5 are pinned; `main` is at
  `d7ac8c5`.

### 0.2 What Phase 2 (`a1fd9eb`) achieved, and where it fell short

* **Achieved (reused unchanged here):**
  * the expressivity audit, with the lambda-cap exclusion removed;
  * the full-rollout M evaluation harness, which really executes the edited curriculum / schedule / admission;
  * graded admission and the locked acceptance barrier;
  * draft-origin tags;
  * fcntl-locked one-use claims.
* **Fell short:**
  * The provisional archive P made **every** proposal provisional, and all 83 were refused, so the P cohorts ended with no
    R / L items.
  * Every Full endpoint was equal to Init, and all arms scored 2 of 32.
  * 0 of 3 meta-edits were adopted, so M* = M0.
  * B / D scored 0 of 4 and the untouched families 0 of 16.
  * The diagnosis: the search budget makes every learning signal too sparse.

### 0.3 Upgrades in Phase 3 (`src/nexus/campaign3/`, extending `campaign2`, not rebuilding it)

* **A. Evaluator-side B / D audit** (`scripts/agi3_bd_audit.py`, `artifacts/agi3_bd_audit.json`). The reference programs
  are evaluator-side witnesses only and never enter a learner.

  | property | result |
  |---|---|
  | (1) interpreter expressibility | **16 of 16** B / D instances |
  | (2) enumerator reachability (lazy lambda pools, cost ≤ 18; focused 5 s search) | **8 of 16** |
  | (3) budget discoverability (full grammar), at 1.5 s and at 0.6 s | **2 of 16** both times (B1 runsum, D1 k = 1) |

  * The larger cap bought less than one cost level, so the source cap stays at **0.6 s**: this contradicts the Phase 2
    recommendation, on measured evidence.
* **B. Crowding-out fix:** a world proposal is provisional only when no solved program supports it.
* **C. Real-pipeline DE world** (`de_world.py`). Each project is a workspace with:
  * a visible CSV batch;
  * state files (checkpoint / watermark);
  * a legacy declarative pipeline, rendered to the runtime's real SQL;
  * `contract.json` with public, machine-checkable checks, including the stakeholder's golden rows for the visible batch;
  * 2 hidden batches plus a pure-Python reference, used only by the independent evaluator, which runs the submission on the
    real runtime and compares output and quarantine tables exactly.

  **Families:**

  | family | mechanism | role |
  |---|---|---|
  | G1 | type-parse migration (SQLite's silent prefix `CAST` against Spark ANSI `CAST_INVALID_INPUT`) | source |
  | G2 | derived metric (integer truncation; Spark ANSI `DIVIDE_BY_ZERO`) | source |
  | G3 | latest-version dedup | source |
  | G4 | exactly-once recovery from a checkpoint | source |
  | G5 | default fill | **holdout** |
  | G6 | watermark lateness | **holdout** |

  Generators enforce per-defect identifiability: every defect is exposed in output-reaching visible rows, and the golden
  output has at least 2 rows.
* **D. DE learner** (`de_learner.py`) on the shared experience / admission / M interfaces:
  * **The cycle:** investigate (incl. differential execution of the legacy pipeline on SQLite for Spark projects) →
    best-first repair search over 9 generic edit operators → learn from failure → repair → verify → reuse.
  * **The search:** best-first search, ordered by the learned evidence-feature → operator weights π_de, with type-aware
    graded credit. Missing or constant outputs earn 0.
  * **Memory:**
    * L_de skills: verified operator sequences with evidence preconditions, admitted only if they cut search cost by
      ≥ 20 % on separate DE admission projects;
    * P_de: refutations and partial successes. Solved-Only uses neither.
* **E. New untouched families C7, C8, E7, E8** (`worlds3.py`; only the generator self-check ran, 12 of 12 OK).
  C5 / C6 / E5 / E6 are reported **as Phase-2 comparison / instance generalisation**.

### 0.4 Stage 1 milestone — one complete operating cycle on real pipelines (`scripts/agi3_cycle.py`, `artifacts/agi3_cycle.json`; development projects only)

1. **Project A, G1.L2 on SQLite: investigate → attempt → learn from failure → repair → verify.**
   * The legacy pipeline fails `row_count` and `quarantine_ids`. Its evidence is `diff:extra_rows` + the failing checks.
   * There were 28 failed candidates, 15 of them refutations.
   * The repair is `quarantine_invalid(units)` + `quarantine_invalid(list_price)`. It passes every public check on SQLite,
     and the independent evaluator passes both hidden batches.
   * The operator sequence was admitted as a skill: 54 → 14 runtime executions on 2 separate admission projects.
2. **Reuse** (verified, runtime executions):

   | project | Full | Memory-Reset | Solved-Only | Full − skill |
   |---|---|---|---|---|
   | B: same family on **Spark 4 ANSI** | ✓ 58 | ✓ 75 | ✓ 74 | ✓ 58 |
   | C: G2.L2 on SQLite | ✓ 16 | ✓ 41 | ✓ 16 | ✓ 41 |
   | D: G2.L2 on Spark | ✓ 83 | ✓ 102 | ✓ 83 | ✓ 83 |

   * B was retrieved through differential investigation: Spark raises where SQLite silently returns wrong rows.
3. **Development batch** (learn on 8 SQLite projects, test on 8 others, 4 SQLite + 4 Spark):

   | condition | verified | runtime executions | silent |
   |---|---|---|---|
   | Full | 6 / 8 | **269** | 1 |
   | Memory-Reset | 6 / 8 | 488 | 0 |
   | Solved-Only | 6 / 8 | 274 | 1 |
   | Full-minus-skill | 6 / 8 | 435 | 1 |

   * Full needs **45 % fewer executions** at equal completion.
   * Removing the admitted skills removes most of the advantage, which is causal evidence that the skills carry it.
   * Failure memory adds little beyond solved-only learning here.
   * 1 silent error: a G4.L2 Spark repair that passed the visible golden batch but not a hidden batch.

### 0.5 Cohorts, Stage 3, Stage 4 manifest (frozen; `artifacts/agi3_eval_plan.json`)

* **Stage 2:** 4 cohorts × 3 repetitions × 100 s.

  | cohort | definition |
  |---|---|
  | Full | learns everything; own curriculum over world cells + DE G1–G4 cells; full-rollout M checks |
  | SolvedOnly | **trained as its own cohort from t = 0**: the identical algorithm with failure memory off; paired seed streams |
  | Fixed-M0 | replays Full's learned sequence |
  | Random-Proposal | replays Full's learned sequence |

* **Stage 3:** 9 clones × 45 s, each running a complete trajectory controlled by M*, M0 or M_rand; paired streams.
* **Stage 4 arms (23 per task):** Full, SolvedOnly, Fixed, Rand, LibOnly, ProcOnly, Placebo per repetition, plus Init
  (Memory-Reset) and Baseline.
  * **Baseline (strong conventional):**
    * worlds: the tuned scratch configuration, which is Init's;
    * DE: an engineer-ordered fixed operator sequence with exact caching.
* **Manifest:**

  | part | tasks |
  |---|---|
  | worlds | **16**: 8 untouched C7, C8, E7, E8 (L1–L2) + 2 each of C1–C4 / E1–E4 instance, Phase-2 comparison, withheld, retention |
  | DE | **12** unseen projects: G1–G4 new instances + G5 / G6 holdout, each on SQLite and on Spark |
  | improver panel | 12 tasks × 12 arms |

  * DE budget per arm-project: SQLite 0.4 s, Spark 1.2 s, warm session. The predicted total is 627 s of 650.
* **Primary target, unchanged from the plan:** ≥ +10 pp exact completion against Memory-Reset, Placebo and Baseline with no
  more accepted errors, **or** ≥ 20 % lower cost at matched completion against Fixed-M0 and Baseline.
* **Improver target:** M* beats both M0 and M_rand on the panel.

## 1. Results

This section was added after the run (NOT LOCKED). The source endpoints are `5bdb15b`, the meta clones `10ad20e`, and the
one-use evaluation ran on the frozen `9209c0c` code.

### 1.1 Real-pipeline cycle trace (Stage 1, development projects; §0.4 has the full trace)

* **Investigate:** the G1.L2 SQLite legacy pipeline fails `row_count` and `quarantine_ids`. Its evidence is
  `diff:extra_rows` + the failing checks.
* **Attempt / learn from failure:** 28 failed candidates, 15 of them refutations.
* **Repair:** `quarantine_invalid(units)` + `quarantine_invalid(list_price)`.
* **Verify:** all public checks pass on SQLite, and the independent evaluator passes both hidden batches.
* **Admit:** the sequence became skill S0. It cut runtime executions on 2 separate admission projects from 54 to 14.
* **Reuse:**
  * the same family on **Spark 4 ANSI** was verified with 58 executions, against 75 for Memory-Reset;
  * G2 on SQLite was verified with 16, against 41;
  * G2 on Spark with 83, against 102.
* **Development batch:** Full 269 executions against Memory-Reset 488 at equal 6 of 8 verified. Removing the skill
  (Full-minus-skill) gives 435.

### 1.2 What NEXUS produced

**DE skills L_de\*** (all `origin = pure_synthesis`; DE has no draft code):
* **Full r0:** S0 = `dedup_first → filter_file`, precondition {`diff:value`, `fail:example_rows`}, admitted at 86 → 50
  executions.
* **Full r1:**
  * S0 `dedup_first` (169 → 58);
  * S1 `filter_file` (169 → 68);
  * S2 `filter_file → dedup_first` (75 → 42);
  * S3 `dedup_latest`, precondition {`diff:dup_keys`, `diff:value`, `fail:row_count`, `fail:unique`} (32 → 22).
* **Full r2:** none.

**Other learned state:**
* **π_de\*:** weights over 8 evidence features in every Full lineage.
* **P_de:** 20 refutation / partial records in r1, 0 in r0 and r2 (every DE project those lineages met was solved, so
  there was no failure to record).
* **World L\* / R\*:** the crowding-out fix let items through. Full r1 has L `filter(\x. lt($0, x), $1)`. Fixed-M0 r1 and
  r2 admitted 2 and 1 items; Random-Proposal r1 admitted 8.
* **M\*:** M0 in every repetition.
  * 0 of 6 full-rollout edits were adopted across Full and Solved-Only: `archive.min_score = 0.2`,
    `schedule.period = 10`, `add propose_L(max_size = 6)`.
  * One rollout diverged in curriculum (SolvedOnly r1), and none won on the held-out rollout tasks.

### 1.3 Where knowledge transferred

**(1) Real data-engineering projects** (12 unseen: G1–G4 new instances + G5 / G6 holdout, on SQLite and on Spark;
verified out of 12):

| arm | r0 | r1 | r2 | SQLite | Spark | silent |
|---|---|---|---|---|---|---|
| Full | 6 | 6 | 6 | 5 / 6 | 1 / 6 | 1 |
| Solved-Only | 6 | 6 | 6 | 5 / 6 | 1 / 6 | 1 |
| Fixed-M0 | 6 | 6 | 6 | 5 / 6 | 1 / 6 | 1 |
| Memory-Reset (Init) | 6 | | | 5 / 6 | 1 / 6 | 1 |
| Baseline (fixed engineer order) | 6 | | | 5 / 6 | 1 / 6 | 1 |
| Placebo | 7 / 5 / 7 | | | | | 1 |
| LibOnly | 6 / 7 / 7 | | | | | 1 |
| ProcOnly / Rand | 6 | 6 | 6 | | | 1 |

* **Completion difference, family-clustered, pooled:**
  * de_instance, Full − Init: **+12.5 pp** (+1 project in every repetition, CI [0, 37.5]);
  * de_holdout, Full − Init: **−25 pp** (Init solved the G5.L2 Spark project; Full did not).
  * Full − Baseline is 0 on both panels.
* **Primary completion target** (≥ +10 pp against Memory-Reset, Placebo **and** Baseline): **not met**.
* **Cost at matched completion** (runtime executions on projects that both arms solved):

  | Full against | r0 | r1 | r2 | ≥ 20 % |
  |---|---|---|---|---|
  | Baseline | 37.7 % | 58.4 % | 37.0 % | met in 3 of 3 |
  | Memory-Reset | 10 % | 50 % | 11.3 % | met in 1 of 3 |
  | Fixed-M0 | 0 % | 4.5 % | **−40.6 %** | not met |
  | Solved-Only | 63.6 % | 24.7 % | −26 % | met in 2 of 3 |

  * The cost target ("≥ 20 % lower than Fixed-M0 **and** baseline controls") is **not met**, because Fixed-M0 does as well
    as Full. M never changed, so Full and Fixed differ only in timing and sequence.
* **Spark:** every arm is limited by the 1.2 s per-project budget (about 30 executions). Only G3.L2 (20 of 23 arms) and
  G5.L2 (Init, LibOnly, Placebo) were solved; 4 of 6 Spark projects were unsolved by all arms.
* **The single silent error in every arm** is the holdout G6.L1 (watermark lateness) on SQLite: a repair that passes the
  visible golden batch fails the hidden batches. All 23 arms made it.
* **Skill reuse fired** on G3.L1 (2 arms), G4.L1 (6) and G6.L1 (6). Retrieval is evidence-gated.

**(2) Untouched mechanisms C7, C8, E7, E8 (8 tasks):** **0 of 8 for every arm.**

**(3) Instance generalisation C1–C4 / E1–E4 (2) and the Phase-2 comparison C5 / C6 / E5 / E6 (2):** 0 for every arm.

**(4) Withheld A / B / D / F (2) and retention (2):** 0 for every arm. **B / D after the Stage 1 audit:** no B / D task was
solved by any arm, in evaluation or in source learning beyond the degenerate counters.

### 1.4 Causal ablation verdict

* **Failure memory (Full against Solved-Only, which is its own cohort):** completion is equal on every panel. Cost is mixed
  (−26 % to +64 %).
  * In two of the three Full lineages, P_de stayed empty, because every DE project met was solved.
  * No validated world item came from P.
  * Result: no demonstrated value of failure memory.
* **Persistent memory (Full against Memory-Reset):**
  * DE completion: +1 on new instances, −1 on holdouts.
  * DE cost: 10–50 % fewer executions at matched completion.
  * Stage 1 development batch: 45 % fewer at equal completion, with the advantage removed when the skill is removed.
  * This is the one consistent, causally attributed effect, and it is a cost effect, not a completion effect.
* **Replacing learned procedures:**
  * Placebo matches or slightly beats Full on completion (7 / 5 / 7).
  * ProcOnly and LibOnly equal Full.
  * Baseline's fixed engineer order costs more than both π0's order and Full.

### 1.5 Multi-round improver verdict

* M′ edits did alter a trajectory in one rollout (curriculum divergence in SolvedOnly r1).
* **0 of 3 edits were adopted across the 3 Full lineages**, so M* = M0.
* Improver panel, M* / M0 / M_rand: r0 3 / 3 / 3, r1 1 / 1 / 2, r2 3 / 3 / 2. M* does not beat M0 (identical) and ties or
  loses to M_rand.
* **Cost:** the incremental 45 s plus the 100 s acquisition bought no panel gain.

### 1.6 Budget, protection, beta readiness

* **Budget:**

  | stage | used (s) | ceiling (s) |
  |---|---|---|
  | s1 | 487 | 550 |
  | src | 1,123 | 1,350 |
  | meta | 381 | 450 |
  | eval | 513 | 650 |
  | rep | 1 + this step | 200 |

  * Phase 3 total: **2,505 of 3,200 s**. Carried balance: **2,113 s** (≥ 1,418 s floor kept).
  * Ledger CPU excludes the Spark JVM (a grandchild process): eval CPU is 329 s against 513 s wall.
* **Protection after-check:** 0 violations over 1,355 frozen files; checkers v1–v5 are pinned; `main` is at `d7ac8c5`.
  The one-use claims were made once each, under the fcntl lock (4 rows).
* **Disclosed events:**
  1. All 9 Stage 3 clones first failed at start-up (an assertion used the Phase 2 digest function; 0 tasks run, about
     0.1 s each, same run ids). They were fixed and launched once.
  2. Spark logs contain benign PySpark daemon shutdown tracebacks.
  3. No human intervention during any stage.
* **What a December pilot user can run today:**
  * a local command-line cycle (`scripts/agi3_cycle.py`-style) on a workspace with a CSV landing batch, a declarative
    pipeline and a machine-checkable contract with golden rows, on SQLite or Spark 4 ANSI.
  * NEXUS investigates, repairs with 9 generic operators, verifies, submits only when every public check passes, and
    reuses admitted skills.
  * **Measured:** SQLite completion is 5 of 6 unseen projects. Spark is 1 of 6 at a 1.2 s search budget; a pilot needs
    larger budgets.
  * The accepted-error rate is 1 of 12 projects (a visible-batch overfit on the watermark holdout), so independent hidden
    checks or human review remain necessary.
  * It does not yet read free-form SQL / PySpark code (pipelines are declarative specs rendered to SQL), ask stakeholders
    questions, or cover orchestration / MLOps.

**Recommended next step:** make the DE learner the primary vehicle, since it is the only place learning shows a causal
(cost) effect.
* Give Spark a realistic search budget, for example 10 s per project.
* Add held-back public examples to fight visible-batch overfitting (the G6 silent error).
* Run a larger frozen DE panel with ≥ 6 projects per family, so that ±1-project differences can be resolved.
