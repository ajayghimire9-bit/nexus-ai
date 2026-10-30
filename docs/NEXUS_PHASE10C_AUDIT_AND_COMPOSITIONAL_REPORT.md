# NEXUS Phase 10C (revised): audit, deliberately withheld compositions, external audit, shared-stream improver test

**NOT LOCKED.** Branch `codex/nexus-data-engineering`; start `34c1109`; protocol commit `579991f` (before any Stage 2
outcome); `main` = `d7ac8c5`, untouched. Protocol: `docs/NEXUS_PHASE10C_PROTOCOL.md`. Exact counts only: no capability
percentages are given.

## 1. Results at a glance

| Question | Result |
|---|---|
| Phase 10B X2 training slip | **Cause found and fixed** for every arm (`fixes10c`). Both known cases now abstain. No pollution of Phase 10B rep1 memory |
| Log reconciliation | **Two earlier statements corrected:** Phase 10 had **7** (not 9) of 16 methods with partial support; "197 → 85" covers **2** P6 projects (not 4). Phase 10B's 5 / 3 promoted methods confirmed |
| Shared random streams | **Demonstrated.** Two differently named clones with identical M gave identical wake trajectories (10 / 10) and identical final memories (same SHA-256). A retrained learner reproduced its 20 wake rows exactly |
| Withheld compositions, learned macros (L\*) | **No effect measured.** Draw A: A3 − A1 = 0, A4 − A2 = 0. Draw B: 0, 0. **But** the learners admitted almost no macros (rep0: 0, rep1: 1), so this mainly shows **macro admission failing**, not that macros do not transfer |
| Withheld compositions, learned guidance (G_learned) | **+0 (Draw A) and +1 (Draw B)** withheld targets; inside the pre-registered null band (≤ 1). Ordinary: +1 on Draw A |
| Targets needing guidance **and** macros together | **0** on either draw |
| Learning curve on withheld targets (N0 / 15 / 30 / 60) | Draw A 3 / 3 / 3 / 3 of 8; Draw B 2 / 3 / 3 / 3 of 6; 0 forgetting |
| Errors | **Training wrong: 0** (120 tasks). **Stage 2 evaluation wrong: 0** (154 rows). **Stage 4 evaluation wrong: 1** (Draw C 96088, a new verifier gap, §5) |
| External audit (16 real-pattern tasks) | NEXUS ingests **0 of 16** as written. First failure: 10 loader / dialect, 2 multi-table, 4 expressiveness. Behind an alias adapter: 1 genuine repair, 1 verifier / visible-sample gap, 3 not representable in L0 |
| Improver (M\*) | M′ (`dream_ratio` 0.6) tied M0 at 6 vs 6 → **not adopted**; discovery cost 96 s. Downstream check: incomplete and inconclusive (rejected M′ 3 vs M0 2 on the 7 common Draw C targets) |
| Budget | **1,426 of 1,800 s** charged; 0 protection violations |

## 2. Stage 1: reconciliation, X2 verifier slip, numeric streams

**X2 slip** (Phase 10B rep1, training task 22, P6.X2 seed 88021). Reproduced by `scripts/agi10c_diag.py x2_10b`.

- **The decision:** the point-in-time decision had options `le` / `lt`, but both had the same profiled end-to-end effect,
  `['excluded', 'excluded']`, on the candidate.
- **Why that mattered:** the requirement was never actually tested on the candidate. The documented effect was then
  mapped to the first option with that effect: `le`, where the truth is `lt`.
- **A second error in the same candidate:** a normalisation sat in the wrong stage; this also passed visible checks.
- **Same class on dev target 91940 (H5):** a duplicate window-end filter in stage 3 shadowed the stage-1 boundary.
- **Fix (`src/nexus/de_phase10c/fixes10c.py`):** a candidate is not submitted while any resolved decision point has
  indistinguishable effects. It applies to every Phase 10C arm and to training. Both cases now abstain.
- **Pollution check of Phase 10B rep1:**

| Memory component | Entries from the wrong X2 repair |
|---|---|
| Skill sources | 0 |
| Ranker pairs | 0 |
| Trust records | 0 |
| P\* hypotheses | 0 |
| Library support | 0 |
| P\* boundary-witness log (feeds no learner) | 1 |

**Reconciliation** (`artifacts/agi10c_reconcile.json`, from the raw logs):

- **Phase 10 main lineage:** 26 candidates and 16 promoted. 7 have partial-program support; none rely on partials only;
  11 are multi-step.
- **Phase 10B rep0:** 8 candidates, 5 promoted (3 with partial support, 1 multi-step, 0 valley-crossing).
- **Phase 10B rep1:** 4 candidates, 3 promoted (2 with partial support, 1 multi-step, 1 valley-crossing).
- **The M\* clone files** hold separate rollouts and are not counted in these totals.
- **"197 → 85":** the two P6 screen projects went 205 → 85 and 189 → 85, mean 197 → 85. On the other 14 screen projects
  the library cost about +5 runs (X1 +20), with 0 completion changes.

**Stage 1 forensic audit** of the 13 Phase 10B held-out targets unsolved in every arm (`artifacts/agi10c_audit.json`):

- **Abstentions and language gaps:** 0 undecided-requirement abstentions; 0 out-of-language targets.
- **Primary cause:** 7 search-depth exhaustion (witness depth ≥ 4); 5 monolithic macro; 1 other.
- **Monolithic macros overall:** in 10 of the 13, bound library paths made stage-local progress but never passed all
  checks.
- **Work budget:** all 13 exhausted it.
- **Witness depth:** 2–5 for the unsolved targets versus 1–3 for the solved ones.

**Numeric random streams** (`src/nexus/de_phase10c/rng10c.py`):

- Every Phase 10C seed is derived from integer tuples.
- Tests (`tests/test_agi10c.py`, 9 passing) show identical ranker samples, splits and streams under renaming.
- Frozen Phase 10 / 10B files keep their old name-seeded calls; Phase 10C does not use them.

## 3. Stage 2: matched 2×2 on deliberately withheld compositions

**Setup.**

- **Training, dreams and admission:** only P1–P7 single-stage plus the pairs X1 (P3 → P2) and X2 (P7 → P6). These allow
  14 mechanism pairs.
- **Withheld families:** H1 (P2 → P1), H2 (P3 → P7), H3 (P5 → P6), H4 (P1 → P4), H5 (P1 → P3 → P6), H6 (P5 → P4 → P7).
- **Withheld pairs:** every built withheld target carries at least one fault pair (F_i, F_j) that never co-occurs in
  training, and each of F_i and F_j is trained separately. For example 96010 has (latest, window) and (tombstone,
  window), and 96061 has (parse, pit).
- **Leakage:** 0 violations over 2,000 training specs.
- **Held fixed in every arm:** trust (Phase 10B rep0 final), F0, M0, the search10c bridge machinery, the shared fixes,
  1,500 executions and a 4 s wall cap per search, and no root method queue.

**Training.** Each stream reached N3 = 60 tasks within the 175 s cap.

| Stream | Verified | Wrong | Training cost (wake / abstraction / dreams / ranker) | L\* admitted |
|---|---|---|---|---|
| rep0 | 44 / 60 | 0 | 68.3 / 41.3 / 22.1 / 0.1 s | 0 (of 8 candidates) |
| rep1 | 47 / 60 | 0 | 62.9 / 45.7 / 24.2 / 0.1 s | 1 (of 10; require_nonempty → normalize_text) |

**Why almost no macros were admitted.** 17 of 18 candidates found no leave-one-paradigm-out project where they bind. A
mechanism-specific macro (for example CDC latest → drop tombstone) binds only in families containing that mechanism.
Leave-one-paradigm-out excludes exactly those families. This is a structural flaw in the pre-registered admission rule.
It was found after training and was **not amended**: there was no budget to retrain, and amending after outcomes is not
allowed.

**Evaluation.**

- **Draw A** (stream rep0, 96000–96015): 2 withheld targets could not be generated (96006 H1, 96015 H6). They are
  recorded and not replaced, leaving 8 withheld + 6 ordinary.
- **Draw B** (stream rep1, 96050–96065): 1 build failure (96065 H6). 4 targets were not run because the Stage 2 ceiling
  was reached: 96054 X1, 96056 H1, 96062 H3 and 96064 H5. That leaves 6 withheld + 5 ordinary.

Withheld solved:

| Arm | Draw A (of 8) | Draw B (of 6) |
|---|---|---|
| A1 fixed + L0 | 3 | 2 |
| A2 learned + L0 | 3 | 3 |
| A3 fixed + L0 ∪ L\* | 3 (library empty, so the same as A1) | 2 |
| A4 learned + L0 ∪ L\* | 3 (same as A2) | 3 |

Ordinary solved:

| Arm | Draw A (of 6) | Draw B (of 5) |
|---|---|---|
| A1 fixed + L0 | 3 | 4 |
| A2 learned + L0 | 4 | 4 |
| A3 fixed + L0 ∪ L\* | 3 | 4 |
| A4 learned + L0 ∪ L\* | 4 | 4 |

- **Marginal effects on withheld targets:**
  - G_learned: A2 − A1 = 0 (A) / +1 (B, 96061); A4 − A3 = 0 / +1.
  - L\*: A3 − A1 = 0 / 0; A4 − A2 = 0 / 0.
  - Interaction: 0 / 0.
  - Every sign-flip p is 1.0.
- **Attribution on withheld targets:**
  - Solved by A1: 3 + 2.
  - Gained by guidance alone: 0 + 1.
  - Gained by macros alone: 0 + 0.
  - Only with both: 0 + 0.
  - Solved by no arm: 5 (A) and 3 (B).
- **Macro use:** the one rep1 macro landed on a verified path in A3 and A4, but changed no completion.
- **Errors and regression:** 0 evaluation wrong submissions in 154 rows; 0 ordinary regressions of A4 against A1.

**Decision rules (pre-registered):**

- **L\*: "replicated null"** (|diff| ≤ 1 in both replications). Its scope is narrow: Draw A tested an empty library and
  Draw B a one-macro library. So this is **not** evidence about compositional transfer of a real library. What it shows
  is that this phase's admission rule did not produce one.
- **G_learned: null band** (+0, +1).

**Learning curve on withheld targets.** Cumulative training cost at each checkpoint (wake + abstraction + dreams):

| Draw / stream | Point | Solved (withheld) | Training cost |
|---|---|---|---|
| A / rep0 | N0 | 3 of 8 | 0 |
| | N15 | 3 | 27.5 s |
| | N30 | 3 | 61.4 s |
| | N60 | 3 | 131.8 s |
| B / rep1 | N0 | 2 of 6 | 0 |
| | N15 | 3 | 16.9 s |
| | N30 | 3 | 66.8 s |
| | N60 | 3 | 132.9 s |

Forgetting: 0.

## 4. Stage 3: external development audit (16 tasks; `artifacts/agi10c_external.json`)

**Task pack.**

- **Patterns** (written offline from public practice; synthetic rows; nothing downloaded): dbt jaffle_shop
  (stg_payments, customers, orders pivot), order-items fan-out, Snowflake QUALIFY / MERGE / TRY_TO_NUMBER, a Debezium JSON
  envelope, Hive '/' division, Postgres DISTINCT ON, a NULL-unsafe filter, PySpark dropDuplicates, a Polars pipeline,
  Scala when/otherwise, an ISO-timestamp month window and replayed duplicates.
- **Run 1's automatic rule was wrong.** It labelled loader-convention errors as expressiveness. Run 2 keeps the run-1
  labels and adds an explicit error → class map and an alias-adding adapter; both were written after run 1 and are
  disclosed.

**First failure on the adapted path (exactly one class per task):**

| Class | Tasks | Examples |
|---|---|---|
| 1 Ingestion / parser / dialect | 10 | loader accepts only `CREATE TABLE clean AS SELECT <aliased cols> FROM raw` (6); QUALIFY / DISTINCT ON latest-per-key rejected as "derived table" (2) although the IR has dedup-latest; PySpark `dropDuplicates` chain; no Polars lifter |
| 2 Specification / grounding | 2 | jaffle_shop customers (3 tables), orders × order_items fan-out (2 tables): the IR has one input |
| 3 Primitive / expressiveness | 4 | MERGE (parsed as a raw Command), JSON paths (Debezium), CASE pivot, Scala when/otherwise |
| 4 Search horizon / ranking | 0 | — |
| 5 Verifier | 0 at this level | — |

**Behind the alias adapter (level 2): 6 tasks lift.**

| Task | Result |
|---|---|
| T09 Snowflake dirty cast | **Solved:** `default_fill amount=0`, verified on all rows |
| T16 replayed duplicates | **Verifier / visible-sample gap:** the visible rows held no duplicate, so the unchanged pipeline passed the public checks and is wrong on all rows |
| T11 NULL-unsafe filter | **Invalid as built:** the CSV text cannot carry NULL, `'' <> 'cancelled'` is true, and the legacy query was already correct ("solved" is vacuous) |
| T01 cents → dollars | No verified candidate; exhaustive depth-3 L0 enumeration finds **no** program reproducing the reference → class 3 |
| T08 Hive division | Same as T01 → class 3 |
| T15 ISO-timestamp window | Same as T01 → class 3 |

**Engineering ledger (most frequent first):**

1. a loader that accepts only NEXUS's own lowering convention;
2. no multi-table input;
3. no MERGE / JSON / CASE in the IR;
4. no Polars lifter;
5. no NULL in the text data model;
6. public checks blind to duplicates that are absent from the visible sample.

## 5. Stage 4: shared-stream improver test (`artifacts/agi10c_mstar/`)

**Identity check.**

- Two clones named idA and idB, both with M0, ran from the rep0 N30 checkpoint on the same shared streams.
- **Result:** wake rows 10 / 10 identical, final memory digests identical, validation identical.
- The retrained alternative learner (resume) reproduced its first 20 wake rows exactly.

**Clone round** (96 s, which is the discovery cost).

- **Edit:** M′ = `dream_ratio` 0.6, drawn by `rng(4, 0, 0)`.
- **Validation:** 8 common tasks; M0 6, M′ 6, wrong 0 / 0.
- **Decision:** **not adopted** (a tie).

**Downstream test.**

- Fresh learners with M_selected = M0 and M_alternative = M′ trained on one common 20-task stream, then evaluated on the
  unopened **Draw C** (96080–96091).
- **Run history:**
  1. The first run hit its 195 s cap after the selected learner's 11 rows (96084 did not build) and the alternative's 4
     rows.
  2. A resume mode was added after the timeout (disclosed). It retrained the alternative identically and added 3 rows
     before Stage 4's ceiling.
- **On the 7 targets both learners completed:** M0 2, M′ 3. The difference is X1 96082.
- **Unrun:** the alternative's other 4 rows; 96084 also failed to build.
- **Verdict: inconclusive.** A difference of 1 on 7 neither supports nor refutes the rejection. Discovery seconds per
  extra completion is undefined (no gain for the selected M).

**Wrong evaluation submission: Draw C 96088 (H1), selected learner.** Reproduced by `scripts/agi10c_diag.py c96088`.

- **What was wrong:** the window-end filter was placed in stage 1 (the CDC stage), **before** dedup-latest, instead of
  stage 2. The window-start filter was missing entirely.
- **Why it passed:** the decision point's effects were distinguishable (`['excluded', 'kept']`), so `fixes10c` does not
  apply. The public checks cannot tell the two placements apart; hidden batch 2 can.
- **Open defect:** the verifier has no check that a predicate commutes with an upstream dedup or stage boundary.
- **Proposed fix (not implemented and not rerun here):** probe rows with several versions per key whenever a filter moves
  across a dedup.

## 6. Defensible scorecard (demonstrated / not demonstrated / unresolved)

**Demonstrated in this phase (exact counts):**

- **Numeric shared streams:** identical clone trajectories and memories.
- **The X2 / H5 verifier defect class:** diagnosed and closed; 2 / 2 cases now abstain.
- **Errors:** 0 training wrong in 120 tasks; 0 Stage 2 evaluation wrong in 154 rows.
- **External audit:** a 16-task failure taxonomy.
- **External repair:** 1 genuine end-to-end repair (T09) behind an adapter.

**Not demonstrated:**

- compositional transfer of learned macros;
- a learned-guidance effect beyond ±1 on withheld targets;
- a guidance × macro synergy;
- a useful autonomous improver edit;
- ingestion of real-world SQL as written.

**Unresolved:**

- **L\* transfer** given a non-empty library. This needs an admission rule that validates mechanism macros on other
  families containing the **same mechanism** (leave-one-family-out with a mechanism match).
- **The remaining Draw B and Draw C rows.**
- **The predicate-placement verifier gap** (96088).

## 7. Budget and protection

| Stage | Used / ceiling (s) | Notes |
|---|---|---|
| s1 | 193.5 / 200 | Stage 1A audit, dev training, diagnostics; charged before the revision, carried |
| s2 | 730.1 / 750 | tests, dev rehearsal, fix checks, 2 × 136 s training, eval |
| s3 | 24.3 / 300 | external audit runs 1–2 + expressibility check |
| s4 | 396.2 / 400 | clone round 96 s, downstream 195 s (TIMEOUT), resume 105 s (TIMEOUT) |
| s5 | 82 / 150 | reconciliation, score, 96088 diagnostic (81 s), protection |
| **Total** | **1,426 / 1,800** | |

- **Grant:** +1,600 s, replacing the original +1,500 s; recorded as one amendment, not a second grant.
- **Grant pool remaining:** 2,424 s (3,850 − 1,426): 374 s unused under this phase's cap plus 2,050 s beyond it.
- **Unmetered:** one pytest run of unit tests before metering began (a few seconds, no experiment).
- **Protection** (`artifacts/agi10c_protect_after.json`):
  - 0 violations;
  - frozen Phase 1–10B files unchanged;
  - checkers v1–v5 pinned;
  - `main` = `d7ac8c5`.
- **One-use and reruns:**
  - `agi10cde/eval` was claimed once.
  - Within it, 96000–96015, 96050–96065 and 96080–96091 were opened; the other seeds in the range were never built.
  - No written row was rerun.

## 8. Recommended next experiment

The one experiment that would answer the open L\* question:

- **Admission change:** leave-one-**family**-out admission with a **mechanism match**. A macro is validated on held-out
  training families that contain its mechanism.
- **Verifier change:** the predicate-placement probe from §5.
- **Evaluation:** repeat the Stage 2 design on fresh draws, budgeted for complete draws, about 300 s of evaluation.
- **Phase 10D:** the multi-table / Polars / MERGE add-on you sent is queued to start only after this report is
  committed. The external audit's ledger above, led by the loader convention and single-input IR, is its concrete
  starting list.
