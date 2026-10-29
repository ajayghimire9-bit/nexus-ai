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
