# NEXUS Phase 7: learning from incomplete programs, method consolidation and transfer (NOT LOCKED)

**Starting revision:** `e97a4c7` on `codex/nexus-data-engineering`, verified equal to `origin` and `github`; `main` =
`d7ac8c5` (untouched). **Status:** exploration with a frozen one-use evaluation. NOT LOCKED.

**Research question.** Can sustained experience teach NEXUS which incomplete programs to retain, how to combine them into
reusable methods, and when to use those methods on unfamiliar projects?

---

## §0 Pre-registration

Committed before any Stage 2 outcome. The source checkpoints, their hashes and the target manifest hash are committed
before target evaluation.

### 0.1 Verified environment and budget

**Machine:** Apple M4 (10 cores), 16 GB RAM, CPU only.

**Software:** Python 3.13.5, DuckDB 1.1.3, PySpark 4.0.1 (local JVM), sqlglot 26.16.4, SQLite 3.50.4.

**Grant arithmetic (`artifacts/agi7_grant.json`, registered once and idempotently):**

| Item | Seconds | Source |
|---|---|---|
| New owner grant | 2,200 | owner Phase 7 instruction |
| Released: Phase 6 grant remaining | 718 | verified by `agi6_budget.remaining()` |
| Released: earlier mi pot remaining | 218 | verified by `mi_budget.left()` |
| **Phase 7 pool** | **3,136** | |
| Phase 7 hard cap | 2,600 | |
| Reserve if the full cap is used | 536 | |

How the books are kept:
- The released balances are spent only through `a7-` ledger rows (`scripts/agi7_budget.py`).
- `agi6_budget` and `mi_budget` keep their own records unchanged; they do not see `a7-` rows.
- The Phase 7 pool is therefore the single authority for those seconds. Nothing is counted twice.
- The Phase 6 cap and records are unchanged.

**Allocation** (`artifacts/agi7_allocation.json`, ceilings plus logged forward transfers):

| Stage | Ceiling | What it pays for |
|---|---|---|
| S1 | 300 s | Implementation, diagnostic, rehearsal. Closed at 276.6 s; 23 s moved to S4. |
| S2 | 1,250 s | 4 jobs × 300 s cap (startup and checkpointing included) + 50 s staging |
| S3 | 0 s | Deferred (see 0.6) |
| S4 | 950 + 23 s | 72 targets × 9 endpoints = 648 rows |
| S5 | 100 s | Scoring, protection, report |

Metering:
- Every development search, rehearsal, test run, job and evaluation runs through `scripts/agi7_exec.py`. It records wall
  time, CPU, peak RSS and status.
- About 5 s of generator checks ran before the meter was wired. They were debited after the fact (`a7-s1-uncharged-dev-adjustment`).
- Parallel jobs are charged the sum of their wall times.

### 0.2 Stage 1: reachability diagnostic (development data only)

**Data:** 16 `agi7de/dev` projects from Tiers 1–2 plus composites (`scripts/agi7_diag.py`, `artifacts/agi7_dev/diag*.json`).

**Witness method:** a reference-assisted greedy witness that reads the hidden truth specs. It is used only for diagnosis:
it never enters learner memory and never counts as an invented method.

**Baseline counts** (16 projects):

| Search | Verified | Wrong | Ambiguous | No candidate |
|---|---|---|---|---|
| Phase 6 search, 1 s | 8 | 1 | 1 | 6 |
| Same search, extended language | 8 | 1 | 1 | 6 |
| First Phase 7 archive search (before the fixes below) | 8 | 1 | 1 | 6 |

**Witnesses:**
- Found for 9 / 16 projects in the Phase 6 language and 13 / 16 with the added parameterisation.
- 5 of the 13 contain a neutral or temporarily worse step: Phase 6's retention rule could not follow those routes.
- A witness failure is not proof of inexpressibility.

**Failure categories found:**

| Category | Finding |
|---|---|
| (a) Missing expressiveness | `ops.candidates` never offers dedup by `id`, the intended repair of duplicate-id / fan-out mechanisms (erratum item 10). |
| (b) Evaluator / gate defect | The `corruption` invariant rejected every grouped-aggregate candidate, correct ones included (erratum item 11). |
| (c) Search budget / ranking | Operator-by-operator enumeration spent 4,000 runs on ~24–90 expansions (~165 children each) and never reached witnessed 2–3-step repairs. |
| (d) Unresolved intent | 1 dev P7 project has no correct submission (`wrong` from search alone). |

**After the fixes in 0.3**, on the 6 previously failing or regressed projects: 2 verified, 1 ambiguous (a decision point
for the investigation), 1 wrong (search alone; no barrier), 2 still without a candidate.

**Barrier check on real projects:** on 2 dev legacy-contradiction projects the coverage barrier created the obligation.
The minimal procedure abstained; the fixed strategy read the documents and verified (`a7-s1-dbg6`).

**Not every failure is a training-time problem.** (a) and (b) are system defects shared by every arm. Their share of the
Phase 6 target failures cannot be measured without reopening frozen targets, which is not done.

### 0.3 Human additions (disclosed; identical for every arm and control)

1. **`ops7`:** the parameterisation `dedup_first` on `id` when `id` is not unique. A general primitive (drop exact
   re-deliveries of a row identity), registered at runtime; Phase 4 / 6 files are unchanged.
2. **`accept7.invariants7` (de_accept_v7 gate repair):** stress rows also receive fresh group-key values, so they form new
   groups. Registered as `pipeline6.invariants`; it is used by the search gate and by the repair closure.
3. **`search7`, a bounded archive of intermediate programs:**
   - retention of improving, neutral (novel behavioural signature) and temporarily worse (by at most `worse_delta`)
     programs, with duplicate detection;
   - capacity 48 open programs, depth 8;
   - a deterministic work budget (engine executions);
   - progressive widening (at most 40 children per expansion; re-expansion continues);
   - children interleaved across operators (weighted round-robin by evidence weight);
   - a SQLite screen of the de_accept_v7 invariants before the declared-engine run.

   Outcomes are classified as improvement / neutral / worse / regression / error. Only regressions lower an operator's
   evidence weight.
4. **`accept7.coverage`, the requirement-coverage barrier.** Every documented subject is matched to every filter, in
   edited and unedited stages. Current behaviour is compared with the reversed boundary on a distinguishing single-row
   probe. A difference becomes an obligation; agreement is recorded as a limited equivalence.
   - The barrier never resolves an obligation: legacy behaviour is an observation, never an authority, and an
     "undetermined" answer leaves the obligation open.
   - It applies to every arm at `submit_or_abstain`, and its probe runs are charged.
   - `check_coverage` is also a procedure action. A procedure that checks coverage early can discharge obligations by
     reading documents, through calibrated trust, or with the single question.
5. **Projects:** `world7.legacy_flip`, the generic "legacy behaviour contradicts an explicit requirement" transform, on top
   of the unchanged Phase 6 arena.

### 0.4 What NEXUS learns (`lineage7`) and the cohorts

**Per source project** (both cohorts, real execution, Tiers 1–2): NEXUS investigates with its **current** procedure and
gets hidden-batch verification as feedback. It then updates:
- evidence weights (operators of verified repairs up; regressions down);
- calibrated trust (verified, refuted-then-verified, clarification, undetermined);
- skill sources: verified repairs, and the **best retained intermediate program of an unsolved project** (`#partial`).

**Every 6 projects, one cycle:**
1. **Consolidation.** `skills7.invent7` builds compatible clusters by operator shape **and** literal, which fixes the
   skills6 hazard of dropping a whole group when one literal differs. Novelty is accounted by canonical form (aliases
   collapse), as a single-operator specialisation or a multi-operator composition. Then `admit_skill` checks admission on
   2 applicable admission projects. It uses a deterministic work cost and traces whether the skill was bound, executed
   and responsible.
2. **Full only: one procedure round** (`procedure7.learn_round`).
   - **Proposals:** typed insertions and pairs, plus sampled delete / swap / parameter / wrap / call edits, from the
     palette read / read_all / search / check_coverage / resolve / ask / submit_or_abstain.
   - **Scoring:** replay of executed experience on a 6-project **proposal-selection pool**: approved-vs-draft conflict
     (P5), legacy-contradicts-contract (P7), undecided (P1), missing requirement (P7), a benign project (P2) and a
     composite (X1), with documents in varying files. Confirmation projects are drawn from the full 10-spec pool list,
     which adds explicit, a second legacy contradiction, P3 and an X2 conflict.
   - **Admission rule `admit7`:** never more wrong; never fewer correct; never a lost completion; no equal-zero cost
     promotion.
   - **Confirmation:** the round is kept only if it is not worse on 3 **untouched, single-use** confirmation projects.
   - A round's adopted block becomes a named reusable procedure. The new procedure acts on the **next** batch.
   - **Retention check:** the new procedure is replayed on every earlier round's caches.
3. **Full only: archive policy.** A delayed-utility update of the expansion / eviction weights. A verified solution's
   archived ancestors (including neutral or worse intermediate steps) count as positives; other expanded programs count
   as negatives. Each update records its provenance.

**Cohorts** (2 independent repetitions each; equal 300 s job caps; identical exogenous stream per repetition,
`seeds7.block(rep)`):

| Cohort | Procedure | Archive policy |
|---|---|---|
| **Full** | learned, starting from SEED = `[search(whole, off), submit_or_abstain]` | learned |
| **FixedLearner** | `FIXED_STRATEGY` = `read_all → search(whole, on) → check_coverage → resolve(calibrated) → if unresolved ask(conflicted) → resolve(calibrated) → submit_or_abstain` | fixed diversity / beam rule `FIXED_W` |

- Both cohorts have the same language, archive capacity, evidence memory, skill machinery, trust and engines.
- Whole-pipeline mode was chosen over decompose on development data (s7 verified 8 vs 7 of 16).
- The FixedLearner does not compose procedures, so it may see more source projects in the same 300 s. That is the
  matched-compute design, disclosed.
- **M (the improver) is fixed at M0 for both cohorts.** A paired M comparison must span several complete cycles per
  clone, which a 300 s job cannot hold. `lineage7.meta_compare` / `judge_edit` implement the comparator: an edit is
  "untested" unless its field reached its triggering event (`touch` counters) **and** the two trajectories differ. It is
  unit-tested; its campaign is deferred.

### 0.5 Stage 4: 72 one-use targets (`agi7de/target` 71000–71199)

**Manifest:** 8 per paradigm (`seeds7.target_manifest`).

| Tier | Paradigms | Targets |
|---|---|---|
| 1 | P1–P3 | 24 |
| 2 | P4–P7 | 32 |
| 3 | P8, P9 A/B/C (held out of all source, admission and selection) | 16 |

**Requirement modes:**
- In P1 / P5 / P7: explicit, missing, conflict-approved, undecided, visible, explicit-with-legacy-contradiction, missing,
  conflict-approved.
- For Tier 3: the same mode cycle.

**Frozen manifest counts:** 5 targets request "undecided" (unresolved intent; a submission cannot be correct there) and 3
request legacy-contradicts-requirement. The realised undecided flags are recorded per row.

**Nine endpoints per target, 648 rows (`scripts/agi7_eval.py`):**

| Endpoint | Memory | Procedure / search |
|---|---|---|
| A0 | fresh | FIXED_STRATEGY |
| A1_r{0,1} | FixedLearner checkpoint | FIXED_STRATEGY |
| A2_r{0,1} | Full checkpoint | its learned procedure + learned archive policy |
| A3_r{0,1} | the same Full checkpoint | FIXED_STRATEGY, fixed archive rule, skills enabled |
| A4_r{0,1} | as A3 | minus the learned skills only |

**Shared settings:**
- Work budget `W_EVAL` = 3,000 engine executions; wall cap 6 s.
- Acceptance barrier v7; one clarification; same engines.
- Frozen memories, deep-copied per row; arm order rotated per target.
- Identical search inputs are reused within a chunk, disclosed as `shared`.

**Interpretation:**
- A2 vs A0 / A1: end-to-end learning benefit.
- A2 vs A3: learned target-time decisions (procedure + archive policy) on the same checkpoint.
- A3 vs A4: the skill library under a procedure that permits retrieval.
- A1 vs A0: experience under the fixed learner.

None of these isolates failure memory. No Solved-Only cohort is funded, so no failure-memory claim is made.

### 0.6 Stage 3 decision (made before any Stage 2 outcome)

**Deferred.** The rehearsal projects ~1.2 s per evaluation row, so the 648 main rows need about 800 s of Stage 4.
Moving up to 520 s to Stage 3 could not leave Stage 4 able to cover all main rows **and** 108 panel rows with a margin.

The comparator is implemented and tested. `agi7de/panel` stays unopened, and the improver claim is reported as untested.

### 0.7 Metrics, tests and decision rules

**Unit of analysis.** The target is the unit. A1–A4 are averaged over the two repetitions **per target**, and only
targets with both repetitions present are used (complete denominators; interrupted rows are missing). Per-repetition
differences are reported as well.

**Test.** A two-sided paired sign-flip permutation test (20,000 draws) on the per-target differences in verified
completion. The primary family is **A2 − A0 and A2 − A1** (overall), with Holm correction at α = 0.05.

| # | Goal | Pass condition |
|---|---|---|
| 1 | Safety | 0 accepted wrong repairs in every arm. Abstentions and answerability are reported separately. |
| 2 | Primary | A2 exceeds **both** A0 and A1 by ≥ +10 pp overall, each Holm p < 0.05. Tier 3 ≥ +15 pp is a separate stretch target. |
| 3 | Contribution | A2 − A3 (learned decisions) and A3 − A4 (skills), with binding / execution / responsibility traces. An inert ablation (no skill ever bound) is reported as lack of exposure. |
| 4 | Cost | Deterministic cost (engine executions × 0.004 s + 2 s per question) on the same non-empty set of correct completions, A2 vs A1 per repetition. Break-even only if a real advantage exists. |

**Secondary measures:** distinct useful methods (5 is a stretch goal, not a quota); the causal chain for each claimed
invention (experience → executable change → where it ran → verified outcome changed → cost repaid).

**Statistical caveat.** Two source repetitions and two Tier-3 paradigm families: no claim of broad generality.

**Stopping and missing rules:**
- A job that times out keeps its last complete-cycle checkpoint, reported as is.
- No source lineage, target row or one-use claim is rerun.
- If a needed endpoint is missing, its contrasts use only complete targets and the gap is reported.

### 0.8 Exact commands

**Stage 2** (4 parallel jobs):

```
python scripts/agi7_jobs.py var/agi7_src_jobs.json var/agi7_src_status.json 4 330
```

Each job is `scripts/agi7_source.py COHORT REP 295` with a 300 s cap.

**Freeze:**

```
python scripts/agi7_eval.py freeze_source
```

**Stage 4** (8 chunks):

```
python scripts/agi7_eval.py run CHUNK 8
```

**Scoring:**

```
python scripts/agi7_eval.py score
```
