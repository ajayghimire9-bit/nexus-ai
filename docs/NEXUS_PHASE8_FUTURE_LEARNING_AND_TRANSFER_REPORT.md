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

---

## §1 Results (NOT LOCKED)

**Commits:**
- protocol `ef5eaa3`, plus the pre-registered threshold fix and job file `6291f34`;
- checkpoints, freeze and target manifest `7f68548`;
- results: this commit.

**Raw data:**
- `artifacts/agi8_src/*.json` (sha256 in `agi8_freeze_source.json`)
- `artifacts/agi8_target_manifest.json`
- `artifacts/agi8_eval/targets_c*.jsonl` (648 rows) and `result.json`
- `artifacts/agi8_dev/`
- `artifacts/mi_logs/a8-*.log`

### 1.1 Budget reconciliation (charged wall s)

| Stage | Used | Ceiling after logged transfers |
|---|---|---|
| S1 | 199.4 | 200 (250; 50 → S4) |
| S2 | 921 | 922 (1,000; 78 → S4) |
| S3 | 0 | 0 |
| S4 | 438 (9 chunks, all COMPLETE, no resume) | 878 |
| S5 | ~3 | 100 |
| **Phase 8** | **~1,562** | **2,100** |

**Pool remaining ≈ 1,027 s** (2,589.4 − 1,562), above the ≥ 489 s floor. No missing, interrupted or resumed rows; no
build failures.

**Disclosed process error.** I did not take a Phase 8 *before* protection snapshot. Protection was therefore verified
against the starting commit `5db8fee` instead (1.7).

### 1.2 Stage 2: what each lineage did (250 s caps)

| | Full_r0 | Full_r1 | FixedLearner_r0 | FixedLearner_r1 |
|---|---|---|---|---|
| Main-lineage projects | 16 | 18 | 64 | 74 |
| Verified at source | 15 | 15 | 49 | 54 |
| Wrong | 0 | 0 | 0 | 0 |
| Consolidation cycles | 4 | 4 | 16 | 17 |
| Trust records | 1 | 9 | 21 | 39 |
| Skill sources | 16 | 15 | 62 | 71 |
| Methods admitted / candidates | 0 / 4 | 0 / 4 | **1 / 16** | 0 / 17 |
| Seconds in future-learning rounds | 195 | 186 | – | – |

**Rounds:**

| Round | Shortlisted edit | Trajectory comparison | Downstream | Result |
|---|---|---|---|---|
| Full_r0 #0 | `wrap read_all in if multi_unresolved` | candidate read **0** documents vs 36, trust records **1 vs 5**, verified 10 vs 10, cost 32.0 vs 35.6 | 5 / 6 vs 5 / 6 | rejected (tie) |
| Full_r0 #1 | `wrap read_all in if asked` | the candidate clone hit the job deadline after 5 projects (1 cycle after exercise) | – | **uninformative** |
| Full_r1 #0 | `insert ask(unclaimed)` | **identical** trajectories on the real stream (it differed only on the screen pool) | 4 vs 4 | rejected (tie) |
| Full_r1 #1 | `delete` the second `resolve(calibrated)` | 4 questions vs 2, otherwise the same memory | 3 vs 3 | rejected (tie) |

- **No procedure change was adopted.** Both Full checkpoints end with F0.
- **The admitted method:** FixedLearner_r0's `dedup_latest → exclude_value 'D'` composition was admitted for cutting
  deterministic work by ≥ 20 % on the same correct set. Of 66 method candidates in all lineages, 15 had partial-program
  support; none of those was admitted.

### 1.3 Stage 4: 72 fresh one-use targets × 9 endpoints (648 rows, all present)

| Endpoint | Verified / 72 | Tier 1 / 24 | Tier 2 / 32 | Tier 3 / 16 | Wrong | Justified abstentions | Questions | No candidate |
|---|---|---|---|---|---|---|---|---|
| A0 fresh + F0 | 51 | 23 | 22 | 6 | **0** | 5 / 5 | 15 | 13 |
| A1_r0 / r1 FixedLearner + F0 | **53 / 53** | 23 | 24 | 6 | **0** | 5 / 5 | 9 / 9 | 13 |
| A2_r0 / r1 Full + its procedure (= F0) | 51 / 51 | 23 | 22 | 6 | **0** | 5 / 5 | 15 | 13 |
| A3_r0 / r1 Full memory + F0 | 51 / 51 | 23 | 22 | 6 | 0 | 5 / 5 | 15 | 13 |
| A4_r0 / r1 as A3, methods removed | 51 / 51 | 23 | 22 | 6 | 0 | 5 / 5 | 15 | 13 |

**Contrasts** (per-target mean over repetitions; sign-flip, two-sided):

| Contrast | Mean | r0 / r1 | p (Holm) |
|---|---|---|---|
| **A2 − A0** (primary) | **0.0 pp** | 0.0 / 0.0 | 1.0 (1.0) |
| **A2 − A1** (primary) | **−2.8 pp** | −2.8 / −2.8 | 0.51 (1.0) |
| A3 − A1 (memory from Full's training process) | −2.8 pp | −2.8 / −2.8 | 0.51 |
| A2 − A3 (target-time effect of the learned procedure) | 0.0 pp | | (A2 ≡ A3: no adopted edit) |
| A3 − A4 (skill library) | 0.0 pp | | (Full admitted no method) |
| A1 − A0 (experience, fixed procedure) | **+2.8 pp** | +2.8 / +2.8 | 0.50 |
| Tier 3: A2 − A0 / A2 − A1 | 0.0 / 0.0 pp | | |

**Family sensitivity:** every family shows 0.0 except P5, where A2 − A1 = −25 pp (2 of 8 P5 targets).

**Verdicts:**

| Goal | Result | Verdict |
|---|---|---|
| Safety: 0 wrong | **0 accepted wrong repairs in all 648 rows.** All 5 unanswerable targets were justified abstentions in every arm. Coverage v8 recorded 4–5 satisfied and 1–2 conflict obligations per arm and no absent obligations on these targets, so the repair was never tested by a target that needed it. | **Met** for these draws (not a general guarantee) |
| Primary net benefit | 0.0 and −2.8 pp | **Not met** |
| Learning to learn | No adopted, confirmed longitudinal improvement; A3 − A1 −2.8 pp | **Not shown** |
| Skill library | A3 − A4 0.0 (Full admitted none). FixedLearner_r0's method was accepted by the method queue in 8 rows, all also solved by A0, with no measurable cost difference (A1_r0 315.3 vs A1_r1 316.7 s). | **Not shown** |
| Cost | No advantage to repay; break-even undefined | – |

### 1.4 Strongest causal traces

**Positive (experience under a fixed procedure).** On 76034 and 76039 (both P5), both FixedLearner memories resolved
**both** conflicting requirement points by **calibrated trust**, with 0 questions, and verified. Fresh and Full abstained:
they spent their single question on the first conflict, and the second stayed unresolved.

The chain is complete:
- **F0 reads every document** → 21 / 39 verified-outcome trust records at source → at the target, trust resolves
  approved-vs-draft conflicts → the question budget is freed → a verified completion.
- This is the same mechanism as Phase 7's 71058 / 71039. **It is learning from experience, not learning to learn:** the
  procedure is the human-chosen F0.

**Negative (the core experiment).** Full_r0 round 0 exercised its edit from the first project and ran 3 complete cycles
after it.
- **Evidence changed:** 0 documents read vs 36.
- **Memory changed:** 1 trust record vs 5.
- **Downstream behaviour did not change:** the 6 downstream projects produced the same decisions and the same 5 / 6.
  None of them needed trust to resolve a conflict.

So the future-learning comparison **detected a change in memory but had no downstream task able to reveal its value.**
The edit was rejected as a tie. The opposite edit ("read more, record more") was never shortlisted, because F0 already
reads everything.

**Overhead.** Full spent 186–195 s of its 233 s in rounds, so its main memory came from 16–18 projects instead of 64–74.
That is the whole A3 − A1 gap: Full's memory held 1 / 9 trust records against 21 / 39, and it lost exactly the two
trust-dependent P5 targets.

### 1.5 Answers to the required questions

1. **What did NEXUS produce without a human writing it?** One admitted method: FixedLearner_r0's `dedup_latest →
   exclude 'D'` composition, re-invented from experience as in Phase 7. It also produced calibrated trust records and
   evidence weights. **No learning procedure:** all four procedure candidates were rejected or uninformative.
2. **What different evidence did it acquire because of a procedure?** In the Full_r0 round-0 clone, 0 documents read
   instead of 36, so 1 trust record instead of 5. In Full_r1 round 1, 4 questions instead of 2.
3. **What changed later?** In the clones: trust-record counts, while the skill sources were identical. In the main
   lineages: nothing procedural, because no edit was adopted.
4. **Which unfamiliar tasks benefited or regressed?** Gains for experience under F0 (A1 vs A0): 76034, 76039 (P5).
   Nothing gained or lost for Full vs fresh. Relative to A1, Full lost 76034 and 76039.
5. **Did it survive the controls?** No advantage exists to test. A2 = A0; A2 < A1.
6. **Did it repay its cost?** No. The rounds cost about 380 s of source compute across the two Full lineages, displaced
   about 100 source projects of experience, and produced no adopted change.
7. **What remains untested?**
   - Meta-learning: no adopted, confirmed procedure.
   - Self-evolution of the improver M (S3 = 0 s; panel unopened).
   - Failure memory (no Solved-Only cohort).
   - Cross-domain transfer: no shared executable interface (0.7).
   - Interface or mechanism transfer beyond the data-engineering arena.

### 1.6 Decision

**Edits changed memory but did not help, and overhead consumed the learner's experience.** Where it failed:

- **Evidence acquisition worked mechanically.** The edits changed what was read, what was asked and what was recorded.
- **The measurement of future value failed.** Six random downstream projects almost never contain the conflict-type tasks
  where trust records matter, so every exercised comparison tied. A comparison that cannot distinguish 1 from 5 trust
  records is insensitive, not evidence of equality.
- **The economics failed.** Each round cost about 90–105 s, roughly 40 % of a lineage, for a 6-project verdict.

**Recommended next experiment: one, general.**
- Make the downstream evaluation of a future-learning comparison **evidence-stratified**. Draw it from a fixed proportion
  of each evidence type the procedure language can change: documented conflicts, absent documents, legacy disagreement,
  undecided and benign.
- Run the incumbent clone **once per parent** and share it across candidates. This is output-equivalent, so the cost
  account stays honest.
- Spend the saving on longer rollouts rather than more rounds.

Language extension is not the bottleneck. The language could already express "read less" and "ask more". What it could
not get was a test that sees their consequences.

### 1.7 Protection

Against the verified starting commit `5db8fee`:
- **0 tracked files modified or deleted** (`git diff --name-status 5db8fee` shows additions only).
- All 7 protection manifests show 0 differences.
- Checkers v1–v5 match their pins.
- `main` = `d7ac8c5`.
- `agi8de/target` was claimed once; `agi8de/panel` is unopened.
- All earlier frozen artifacts and historical reports are unchanged.
