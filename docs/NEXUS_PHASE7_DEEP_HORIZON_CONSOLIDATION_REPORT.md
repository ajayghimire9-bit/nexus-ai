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

---

## §1 Results (NOT LOCKED)

**Commits:** protocol + implementation `46e1e7f` (before any Stage 2 outcome); source checkpoints + freeze + target
manifest `91b591a` (before target evaluation); results: this commit.

**Raw data:**
- `artifacts/agi7_src/*.json` (4 checkpoints, sha256 in `artifacts/agi7_freeze_source.json`)
- `artifacts/agi7_eval/targets_c*.jsonl` (648 rows) and `result.json`
- `artifacts/agi7_dev/` (Stage 1)
- `artifacts/mi_logs/a7-*.log`

### 1.1 Budget and execution events (charged wall s, `scripts/agi7_budget.py`)

| Stage | Used | Ceiling (after logged transfers) |
|---|---|---|
| S1 | 276.6 | 277 (300; 23 → S4) |
| S2 | 1,113.4 | 1,114 (1,250; 136 → S4) |
| S3 | 0 | 0 (deferred) |
| S4 | 654 | 1,109 |
| S5 | ~3 | 100 |
| **Phase 7** | **~2,047** | **2,600** |

The pool has **~1,089 s** left: 536 s of promised reserve plus ~553 s of unused cap. The Phase 6 records are unchanged
(3,282 / 3,600 s, 718 s shown there), but those 718 s were released into the Phase 7 pool, so they must not be spent
twice.

**Events:**
1. About 5 s of uncharged generator checks were debited after the fact.
2. **Chunk c2 timed out** (130 s cap) after 44 of 81 rows. It was **resumed once** (`a7-eval-c2-resume`, 58 s). The
   resumable evaluator skipped the 44 written rows, which stayed byte-identical (checked with `cmp`), and ran only the 37
   never-executed rows. No completed outcome was rerun.
3. All 648 main rows are present; there were no build failures.
4. The `agi7de/panel` range was not opened.

### 1.2 Stage 2: what NEXUS learned at source (two repetitions per cohort, 300 s each)

| | Full_r0 | Full_r1 | FixedLearner_r0 | FixedLearner_r1 |
|---|---|---|---|---|
| Source projects (unique, new) | 37 | 36 | 94 | 98 |
| Verified at source | 24 | 23 | 63 | 75 |
| Wrong first submissions | 0 | 0 | 1 | 0 |
| Complete cycles | 5 | 6 | 14 | 16 |
| Skill candidates tried / admitted | 10 / 3 | 12 / 1 | 27 / 3 | 28 / 3 |
| Candidates whose support includes a partial program | 2 | 5 | 11 | 11 |
| Archive-policy updates (delayed utility) | 24 | 23 | – | – |
| Procedure rounds / changes adopted | 5 / 1 | 6 / 1 | – | – |

**Invented methods.** There are 6 distinct canonical methods; aliases were collapsed by canonical form.

| # | Method | Kind | Admitted in |
|---|---|---|---|
| 1 | `dedup_latest(key: text role, order: int role)` | single-operator specialisation | Full_r0, FixedLearner_r0 |
| 2 | `default_fill(int-dirty column, 0)` | single-operator specialisation | Full_r0, FixedLearner_r0 |
| 3 | `require_nonempty(text column)` | single-operator specialisation | Full_r0, FixedLearner_r1 |
| 4 | `exclude_value(low-card text, 'D')` | single-operator specialisation | FixedLearner_r1 |
| 5 | `dedup_latest → exclude_value 'D'` (a CDC "latest version, drop tombstones" method) | **multi-operator composition** | Full_r1, FixedLearner_r1 |
| 6 | `normalize_text → require_nonempty` | **multi-operator composition** | FixedLearner_r0 |

Notes on the methods:
- Method 6's support **includes the best retained intermediate program of an unsolved project** (`from_partial`): an
  unsuccessful experience that became an admitted method.
- Every admission passed by the corrected rule, as "cheaper by ≥ 20 % (deterministic work) on the same correctly
  completed admission projects". Each trace shows the skill bound, executed and on the verified path.
- All six are recombinations of authored operators. No new executable structure outside the supported language was
  produced.

**The learned procedure.** Both Full repetitions independently adopted the same round-0 change: insert
`check_coverage → ask(first)`, packaged as the reusable `proc1`.
- It was confirmed on untouched projects: correct 1→2 (r0), 2→2 (r1), wrong 0→0.
- The final program is `search(whole, skills off) → proc1 → submit_or_abstain`. **It never reads a requirement
  document, and it switches its own skills off.**
- No later round found an admissible change.
- Retention checks never showed a regression.

**Did the learned procedure change subsequent learning?** Yes, mechanically: every later source project ran under it
(2 procedure digests per lineage). Source verification went from 2 / 6 before the change to 22 / 31 and 21 / 30 after.
That comparison is confounded by the stream order (the first batch is P1 / P2), so it is not a causal estimate.

**The improver.** M stayed at M0 by design; no M edit was tested.

### 1.3 Stage 4: 72 one-use targets × 9 endpoints (648 rows, all present)

| Endpoint | Verified / 72 | Tier 1 / 24 | Tier 2 / 32 | Tier 3 / 16 | Accepted wrong | Justified abstentions | Questions | No candidate |
|---|---|---|---|---|---|---|---|---|
| A0 fresh + fixed strategy | **51** | 23 | 23 | 5 | 1 | 4 | 12 | 13 |
| A1_r0 / r1 FixedLearner | 49 / 53 | 23 / 23 | 20 / 24 | 6 / 6 | 1 / 1 | 4 / 4 | 9 / 8 | 16 / 13 |
| A2_r0 / r1 **Full, learned** | 49 / 46 | 22 / 20 | 22 / 21 | 5 / 5 | **0 / 0** | 4 / 4 | 16 / 14 | 14 / 17 |
| A3_r0 / r1 Full ckpt + fixed strategy | 48 / 51 | 23 / 23 | 20 / 23 | 5 / 5 | 1 / 1 | 4 / 4 | 12 / 12 | 16 / 13 |
| A4_r0 / r1 as A3, skills removed | 51 / 51 | 23 / 23 | 23 / 23 | 5 / 5 | 1 / 1 | 4 / 4 | 12 / 12 | 13 / 13 |

**Pre-registered contrasts** (per-target mean over repetitions; sign-flip, two-sided):

| Contrast | Mean | r0 / r1 | p | Holm p |
|---|---|---|---|---|
| **A2 − A0** (primary) | **−4.9 pp** | −2.8 / −6.9 | 0.063 | 0.125 |
| **A2 − A1** (primary) | **−4.9 pp** | 0.0 / −9.7 | 0.172 | 0.172 |
| A2 − A0, Tier 3 | 0.0 pp | | 1.0 | |
| A2 − A1, Tier 3 | −6.2 pp | | | |
| A2 − A3 (learned target-time decisions) | −2.8 pp | +1.4 / −6.9 | 0.44 | |
| A3 − A4 (skill library) | −2.1 pp | −4.2 / 0.0 | 0.25 | |
| A1 − A0 (experience, fixed learner) | 0.0 pp | −2.8 / +2.8 | 1.0 | |

**Verdicts against the goals:**

| # | Goal | Result | Verdict |
|---|---|---|---|
| 1 | 0 accepted wrong repairs in all arms | 7 wrong rows, all on **one** project (P5, seed 71032), in every fixed-strategy endpoint; A2 had 0 (it abstained there) | **Not met** |
| 2 | Full ≥ +10 pp over both A0 and A1 (Tier 3 ≥ +15 pp) | −4.9 pp and −4.9 pp; Tier 3 0 and −6.2 pp | **Not met** |
| 3 | Demonstrated contribution of learned decisions or skills | A2 − A3 −2.8 pp, A3 − A4 −2.1 pp (see below) | **Not met** |
| 4 | Cost at matched correctness | The correct sets differ (A2 vs A1 not the same set), so there is no cost claim; on shared solves A2 cost 92.5 vs 86.4 s (r0) and 73.3 vs 59.1 s (r1) | **No advantage** |

Notes on goal 3:
- The skills **were exercised**: bound in 42 / 11 A3 rows and on the verified solution path in 20 / 8. But A4, without
  skills, solved as many or more of the same projects. The admitted methods did not add completions on unfamiliar
  targets; in r0 they displaced better repairs.
- The learned procedure never uses skills (`search off`), so A2 cannot benefit from them.
- The secondary target of five distinct useful methods: six were invented and admitted, but none was shown useful at
  transfer.

### 1.4 What changed relative to Phase 6, and why

**The base system got better, from shared infrastructure.** The same kind of fresh, fixed-procedure endpoint solved
35 / 72 in Phase 6 and **51 / 72** here. The targets are different draws, so this is an indication, not a paired
estimate.

That gain belongs to the human infrastructure that every arm shares:
- the dedup-on-`id` parameterisation;
- the de_accept_v7 gate repair;
- the archive search (widening, interleaving, neutral / worse retention);
- the coverage barrier.

**None of it is learning by NEXUS.**

**Wrong repairs fell** from 29 rows on 3 projects to 7 rows on 1 project. The legacy-contradicts-requirement targets were
solved by every fixed-strategy arm, and A2 solved 2 / 3 per repetition.

**The remaining wrong project** (post-hoc analysis, `a7-rep-posthoc`; no outcome changed). No option combination of the
search's candidate verifies:
- The search replaced a missing checkpoint filter with a spurious column-to-column comparison (`rev ≤ log_pos`) that
  fits the visible batch.
- The clarification was spent on that spurious decision point.
- The documented checkpoint subject had **no implementing filter at all**. `accept7.coverage` records such subjects as
  "uncovered" but does not make them obligations.

That is a barrier design gap: **a documented requirement with no implementation must block or demand evidence.**

**Why learning did not help:**
1. **The learned procedure optimised for its pool, not for transfer.** `check_coverage → ask` without reading documents
   is admissible on a 6-project pool where one question resolves the single obligation. On targets with two or more
   open points it abstains (A2: 12 + 2 rows "unresolved decision point(s)" vs A0's 4 + 1). The pool-and-confirmation
   guard prevented wrong submissions; it did not prevent a narrower procedure.
2. **The learned archive policy reduced search success.** A2 has more "no repair candidate" rows than A0 (31 over two
   repetitions vs 13). Delayed-utility updates on ~24 verified source solves increased the weight on depth (1.8) and on
   stage-operator features. That generalised poorly.
3. **Admitted skills are cost-admitted shortcuts.** They are cheaper on 2 admission projects but not broader. On targets
   they redirect search to a bound skill path that the fixed search would have found or beaten.
4. **Full's exposure was limited.** Full spent most of its 300 s on procedure rounds (37 / 36 projects vs 94 / 98 for
   FixedLearner). This is the matched-compute design; it is still a confound for skill and trust learning (Full recorded
   0 trust records, because its procedure never reads documents).

### 1.5 Answers to the closing questions

- **What did NEXUS invent?** Six admitted methods: four specialisations and two multi-operator compositions (a CDC
  latest-then-drop-tombstones method; normalise-then-require-nonempty). It also composed one reusable investigation
  sub-procedure (`check_coverage → ask`) and a learned archive-expansion policy. All are recombinations of human-authored
  operators and actions.
- **Which unsuccessful experiences became useful?** The best retained partial program of unsolved projects supported 2–11
  skill candidates per lineage. One became an admitted method (normalise → require-nonempty, FixedLearner_r0). Neutral and
  worse intermediate programs appear on verified solution paths and were the positive examples of the archive-policy
  updates. None of this produced a target-level gain.
- **Did a learned procedure change subsequent learning?** Yes in the mechanical sense: the adopted procedure ran on every
  later source batch, and later rounds kept it under retention checks. Its causal effect on learning was not isolated.
- **Which discoveries helped unfamiliar projects?** None measurably. The skill library was exercised but net −2.1 pp; the
  learned decisions were −2.8 pp.
- **Did the benefits survive strong controls and repay their cost?** There was no benefit to repay. The fresh,
  strong-fixed-strategy control (A0) was not beaten by any learned endpoint.
- **What failed or remains untested?**
  - Failed: every primary learning target; zero wrong repairs (1 project).
  - Untested: the improver (M fixed, Stage 3 deferred, panel unopened); failure memory (no Solved-Only cohort).
  - External cross-domain transfer is not established; everything is inside one authored arena.

### 1.6 Protection

`artifacts/agi7_protected_hashes_after.json`: **0 violations**.
- 1,765 frozen files (Phases 1–6) unchanged.
- Checkers v1–v5 match their pins.
- `main` = `d7ac8c5`.
- `agi7de/target` claimed once; `agi7de/panel` unopened.

### 1.7 Recommended next experiment

**One experiment: transfer-shaped procedure admission plus barrier completeness.**
1. Make documented-but-unimplemented subjects obligations in the barrier: the single remaining wrong case. This is a
   versioned barrier change for all arms, tested on development data first.
2. Admit procedure and archive-policy changes only on a **held-out-family** validation set (leave one source paradigm
   out per round). That way "check, then ask once" and depth-heavy policies are refuted when they fail to transfer, not
   only when they cause errors.
3. Admit skills on breadth (applicability across ≥ 2 paradigms), not on cost alone.
4. Keep A0 = fresh + strong fixed strategy as the bar. It is now the strongest arm.
