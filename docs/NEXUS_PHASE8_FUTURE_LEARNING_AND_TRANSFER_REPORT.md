# NEXUS Phase 8: learning to learn through future transfer (NOT LOCKED)

**Starting revision:** `5db8fee` on `codex/nexus-data-engineering`, verified equal to `origin` and `github`; the working
tree was clean. `main` = `d7ac8c5` (untouched).

**Hypothesis.** A procedure selected for the knowledge it helps a learner acquire over several rounds produces a better
learner on later unfamiliar tasks than one selected for immediate completion.

---

## §0 Pre-registration

Committed before any Stage 2 outcome.

### 0.1 Environment and budget

**Machine:** Apple M4 (10 cores), 16 GB, CPU only. **Software:** Python 3.13.5, DuckDB 1.1.3, PySpark 4.0.1, sqlglot
26.16.4, SQLite 3.50.4.

**Pool (`artifacts/agi8_grant.json`, registered once and idempotently):**

| Item | Seconds |
|---|---|
| New owner grant | 1,500 |
| Phase 7 pool remainder (exact, `agi7_budget.remaining()` = 3,136 − 2,046.598) | 1,089.402 |
| **Phase 8 pool** | **2,589.402** |
| Cap | 2,100 |
| Kept after the cap | ≥ 489.4 |

Notes:
- The Phase 6 718 s and mi 218 s were already inside the Phase 7 pool and are not added again.
- No binding reserve exists in any ledger or grant file. The Phase 7 instruction's "536 s reserve" referred to Phase 7.
  The owner-computed Phase 8 plan uses 47 s of it; this is disclosed here.

**Allocation** (`artifacts/agi8_allocation.json`):

| Stage | Ceiling | Content |
|---|---|---|
| S1 | 250 s | Implementation, development checks, rehearsal |
| S2 | 1,000 s | 4 × 250 s source jobs, inclusive |
| S3 | 0 s | Deferred (see 0.7) |
| S4 | 750 s | 648 rows in 9 chunks × 80 s caps |
| S5 | 100 s | Scoring, protection, report |

Every development check, test run, rehearsal and job runs through `scripts/agi8_exec.py`. Parallel jobs are charged the
sum of their walls.

### 0.2 Audit of the Phase 7 premises (raw rows; all Phase 7 targets are now development data)

All six stated observations hold.
- **Completion:** Full 49 / 46, fresh 51, trained fixed 49 / 53. Full had 0 wrong; this is not a general guarantee.
- **Methods:** six methods were admitted. The failure-supported normalize→require composition belongs to FixedLearner_r0.
  Its provenance does not establish causal necessity.
- **Trust:** Full's procedure never read documents and kept 0 trust records, vs 32 / 38.
- **Confirmation:** Phase 7 confirmation replayed tasks with frozen memory.
- **Archive negatives:** archive-policy negatives were unverified.
- **Displacement, sharpened:** the three r0 P4 targets (71025 / 27 / 28) were lost by **both** A3_r0 and A1_r0, with
  4 skill paths bound each time. The displacement is a property of the shared skill routing, not of Full.

**Narrow positives:**
- **71058** (held-out Scala, P8): both trained fixed learners resolved its approved-vs-draft conflict by **calibrated
  trust**, which freed the single question for the second decision point. Fresh and Full spent their question on the
  conflict and abstained.
- **71039** (P5): FixedLearner_r1 resolved **both** coverage conflicts by calibrated trust, with 0 questions.

**Conclusion of the audit.** The only target-level learning gains in Phase 7 came from trust evidence. That evidence is
acquired only by procedures that read documents and record verified outcomes. A procedure therefore changes what future
learning can observe.

### 0.3 Shared acceptance repair: coverage v8 (`de_phase8/accept8.py`; a human repair given to every arm)

**How it works.** For each documented threshold, single-row probes at t − 1, t and t + 1 run through the **whole**
pipeline, across all integer-like input columns.
- **Implemented:** a column whose crossing of t changes the kept / excluded outcome **consistently**, on every evaluable
  base row (≥ 2 when available). The outcome at exactly t is the implemented boundary effect.
- **Absent:** no such column. The obligation **blocks**, and no question is spent on it.
- **Reversal option:** offered only when a comparison on the subject exists syntactically and the probe confirms that
  reversing it flips the effect.
- **Status** is recorded per obligation: satisfied, refuted, conflict or insufficient.
- **Authority:** legacy behaviour is evidence, never authority. Drafts and "undetermined" answers never become
  requirements.
- **Ask:** the single clarification only goes to an obligation that a probe can settle.

**Development cases** (`artifacts/agi8_dev/accept_cases.json`; constructed from generator truth in the harness only):

| Case | Result |
|---|---|
| Absent | blocks, 3 / 3 |
| Misleading column comparison | blocks, 3 / 3 (the first version missed 1 / 3 through a coincidental cut on one row; fixed by the consistency rule) |
| Equivalent with a different expression shape | implemented, correct effect, 3 / 3 |
| Threshold moved to a later stage (X2) | implemented |
| Legacy disagreement | submit, verified |
| Underspecified | abstain |
| Conflicting documents | abstain (the candidate also lacked an implementation) |

### 0.4 Shared method routing (`de_phase8/search8.py`)

- **Method queue:** bound skill paths are tried in a separate bounded queue (≤ 20 % of the shared total work budget).
  The first path that passes full acceptance is returned. Failures never enter the base frontier.
- **Base search:** gets the remainder; with an empty library or unused slice, it gets the full budget. No
  monotonic-solve guarantee is made.
- **Archive rule:** `FIXED_W` is frozen for everyone, and the Phase 7 archive-weight updates are disabled.

### 0.5 The experiment (`de_phase8/lineage8.py`, `scripts/agi8_source.py`)

**Cohorts.** Both start from **F0** (= the Phase 7 fixed strategy; an explicit shared prior) and an empty memory, with
M0 and the archive rule frozen.

**Shared learner:** evidence weights, calibrated trust, skill sources (verified repairs and partial programs), and one
method candidate per 4-project cycle. Method admission uses applicable projects **outside the support** plus one
retention project. A method is admitted iff it enables a completion, or cuts work by ≥ 20 % on the same non-empty correct
set; it must never add a wrong submission or lose a completion. Each admission traces bound / executed / on-path /
caused.

**Full only: future-learning rounds.** A round runs after every 8 main projects while ≥ 85 s remain.

1. **Screen.** About 465 typed proposals are replayed on a 6-project pool. The screen keeps proposals whose **behaviour
   signature** (decision and choices, documents read, questions, how each point was resolved, effective search
   configuration) differs on ≥ 1 task, that add no wrong submission and lose ≤ 1 correct outcome. Ranking: correct, then
   number of tasks whose behaviour differs, then cost. If no supported proposal qualifies, an unsupported counterfactual
   is taken to live exploration.
   - **Stage 1 fixes:** the action-log criterion picked no-ops (both rehearsal rollouts were identical), and the label
     "skills on" with an empty library was a no-op. After the fixes the dev screen shortlisted "ask (first) before the
     calibrated resolve".
2. **Rollout.** Two clones of the parent run incumbent vs candidate, each fixed within its trajectory, on the **same**
   12-project stream (3 cycles), with real learning and consolidation and no nested auditions. The edit must be
   exercised with ≥ 2 complete cycles after it, else the round is "uninformative".
3. **Downstream.** Both frozen memories are evaluated with **F0** on 6 disjoint projects.
4. **Win rule.** No added wrong submission (trajectory or downstream), and more downstream verified projects (or the
   same non-empty set at ≥ 10 % lower cost).
5. **Confirmation.** On 6 further disjoint projects the winner must not be worse.
6. **Adoption.** Only the procedure is adopted; clone memories are discarded.

Every round logs the causal chain: edit → evidence (reads, questions, trust records, skill sources) → memory → per-project
downstream decisions → verified outcome.

**Measured throughput** (development, before any outcome): main project ≈ 1.2 s; consolidation cycle ≈ 4.6 s; one round
≈ 52–74 s.

**Partitions:** `seeds8` gives disjoint train / admit / pool / roll / down / conf blocks per repetition, all Tier 1–2 and
composites. The one-use `agi8de/target` and the unopened `agi8de/panel` are separate. All earlier targets are development
data.

### 0.6 Evaluation (`scripts/agi8_eval.py`)

**Targets:** 72 fresh one-use targets, 76000–76071, with the Phase 7 structure: 24 / 32 / 16 by tier, family = paradigm
(P9 per hybrid), and 5 unanswerable (undecided) by manifest. The manifest is frozen with the checkpoint hashes before
opening.

**Nine endpoints (648 rows):**

| Endpoint | Memory | Procedure |
|---|---|---|
| A0 | fresh | F0 |
| A1_r | FixedLearner | F0 |
| A2_r | Full | its learned procedure |
| A3_r | Full | F0 |
| A4_r | as A3, invented methods removed (slice returned to base search; trust and evidence kept) | F0 |

Settings: frozen archive rule; work budget 3,000; wall cap 6 s; per-target memories isolated; rotated arm order.

**Contrasts:** A2 − A0, A2 − A1 (primary), A3 − A1, A2 − A3, A3 − A4, A1 − A0, plus Tier 3 and per-family sensitivity.
**Test:** two-sided paired sign-flip on per-target differences (A1–A4 averaged over both repetitions), with Holm over the
two primary contrasts.

**Pass rules:**
- **Primary net benefit:** both primary contrasts ≥ +10 pp, Holm p < 0.05, **and** positive in both repetitions.
- **Learning to learn** additionally requires A3 − A1 > 0 and at least one exercised, adopted longitudinal comparison
  whose downstream advantage was confirmed.
- **Skill benefit:** A3 − A4 > 0, or a defensible cost saving at comparable correctness.

**Missing rows:** they are missing, never failures. A timed-out chunk may be resumed once from leftover evaluation funds;
the resume skips written rows. No lineage is selected after results.

### 0.7 Untested by design

- **The improver (M\* vs M0 vs random):** S3 = 0 s. A complete improver allocation (2 × 3 clones, ≥ 2 cycles after each
  exercised edit, plus a downstream panel) cannot fit beside the primary campaign. The panel stays unopened.
- **Failure memory:** no Solved-Only cohort is funded.
- **Cross-domain transfer.** The only non-data-engineering environments (`campaign/worlds`, worlds A–F) expose a
  program-induction `TaskView`: labelled pairs, a metered oracle, a simulator predicate. They have no documents,
  requirement claims, pipeline repair search or probe-row clarification. So there is no semantics-preserving adapter for
  the procedure language's read / check_coverage / resolve / ask actions, and the probe is not run. This is an
  architectural finding.
