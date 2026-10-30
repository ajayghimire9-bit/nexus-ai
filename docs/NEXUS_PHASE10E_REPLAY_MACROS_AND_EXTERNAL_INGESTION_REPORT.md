# NEXUS Phase 10E: replay verification, dedup macros on wide DAGs, the 96088 verifier gap, external ingestion

**NOT LOCKED.** Branch `codex/nexus-data-engineering`.

| | Revision / file |
|---|---|
| Start | `a148f81` |
| Commit 1: protocol, substrate, fixes, loader, frozen manifest; before any training outcome or target | `26c5d68` |
| Training + freeze (before the draw opened) | `df03782` |
| `main` | `d7ac8c5`, untouched |
| Protocol | `docs/NEXUS_PHASE10E_PROTOCOL.md` |

All figures are exact counts.

## 1. Results at a glance

| Question | Result |
|---|---|
| Target 96088 verifier gap | **Closed, with a corrected diagnosis.** The Phase 10C report blamed a filter placed before the dedup. It was not: the Phase 4 IR runs a stage's dedup before its filter, and moving the predicate changes nothing. The cause was a **missing window-start predicate**. New guard: 0 false accepts on 96088 and 0 false abstains on 342 Phase 10C dev / training truths. The requested shadow-sequence witness is also implemented and unit-tested |
| Why Phase 10D training verified 0 replay repairs | **Reachability, not verification.** The truth repair passed visible checks 25 / 25 and hidden checks 25 / 25. It sat at fixed-order position 294–961 (median 513; budget 600), had a median of 29 role-identical twins, and was a single 3-parameter edit, so it could never become a macro |
| Replay repairs verified in training (after the shared fix) | **rep0: 6 of 7 S_replay tasks; rep1: 5 of 7**, all through `add_partition → set_dedup` |
| Replay macro admitted into L\* | **rep1: yes** (L5 = `add_partition → set_dedup`). **rep0: no**: the candidate lost its key role and was rejected, so the L\* question is **untestable in rep0** (pre-registered precondition) |
| Held-out replay compositions (of 24), A1 / A2 / A3 / A4 | rep0: **0 / 21 / 0 / 22**; rep1: **0 / 21 / 18 / 24** |
| Do replay macros add completions beyond learned guidance? | **rep1 (the one testable repetition): yes.** A4 − A2 = **+3**, from the three hardest 3-fault compositions, each solved only with L5 as one atomic step. A3 − A1 = **+18**. Not replicated: rep0 had no replay macro |
| Learned guidance (G_learned) | Replicated positive. A2 − A1 = **+21 in both repetitions**; A4 − A3 = +22 / +6 |
| Wrong repairs | **Evaluation: 0 of 336 rows.** Training: 1 of 238 tasks (rep1, a T_cdc_key+dirty task) |
| Ordinary targets (of 24), A1 / A2 / A3 / A4 | rep0 19 / 23 / 20 / 24; rep1 19 / 23 / 22 / 24 |
| External audit (16 tasks), funnel | **Ingested natively 16** (Phase 10C: 0) → **expressible 10** → **candidate reached 4** → **verified 3** (only **1** is a genuine repair: T09) + **1 wrong** (T16) |
| Budget | **928 of 1,400 s** charged (from the 1,838.4 s surplus; 910 s remain). Protection: 0 violations |

## 2. Stage 1A: Target 96088

**Forensic run.** `scripts/agi10e_c96088.py`, output `artifacts/agi10e_c96088.json`. The consumed target was rebuilt only to
execute four fixed specifications; no new evaluation row was produced and no learner was involved.

| Variant | Hidden batch 1 | Hidden batch 2 |
|---|---|---|
| V0, the Phase 10C submission: window-end predicate merged into the CDC stage's filter | ok | **differs** |
| V1, the same predicate moved into the window stage | ok | **differs**; reference outputs identical to V0 |
| V2, V0 plus the window-start predicate `evt_time >= start` | ok | **ok** |
| V3, truth | ok | ok |

**The Phase 10C attribution was wrong.** It said "a filter moved before dedup-latest". But a Phase 4 / 6 stage applies its
dedup **before** its filter, so the predicate was already after the dedup. The real gap:

- the workspace declares `batch.json {start, end}`;
- the candidate implemented only `end`;
- no visible row lay before `start`, so no check could fail.

**Fix 1, `de_phase10e.fixes10e`.** A candidate that reads some key of a state file but leaves a sibling key unreferenced is not
submitted. It is installed on top of the Phase 10C barrier. Checked by `scripts/agi10e_fix_check.py`
(`artifacts/agi10e_fix_check.json`):

- **96088:** V0 and V1 are blocked; V2 and V3 pass. **0 false accepts.**
- **Truths:** **0 false abstains** on the 342 Phase 10C dev / training workspaces (37 of them declare a `batch.json` window).

**Fix 2, the requested shadow-sequence witness.** It is implemented as asked, in two places:

- `dag10e.stale_witness`, for pre-dedup filters in the DAG substrate;
- `fixes10e.stale_witness`, for a filter in an earlier stage than a latest-per-key dedup.

It synthesises a boundary key with versions r_old and r_new. r_new is the latest version, fails the predicate and r_old
satisfies it. Filter-then-dedup and dedup-then-filter are then compared on that key. Unit tests:

| Test | Result |
|---|---|
| Filter before dedup resurrects r_old | **rejected** |
| Filter after dedup | passes |
| A predicate on the key itself (commutes with the dedup) | passes |
| The 96088 specs | correctly **no** violation |
| A synthetic chain that filters in an earlier stage than the dedup | rejected |
| The faulty `tomb_early` legacy (tombstone filter before dedup) | flagged |
| Truth | flagged in **0 / 26** dev projects |

## 3. Stage 1B: why 0 replay repairs, and the shared fix

**Diagnostic.** `scripts/agi10e_diag_replay.py` → `artifacts/agi10e_diag_replay.json`, on the 25 Phase 10D training tasks
containing `replay`, with the frozen Phase 10D code.

| Measure | Value |
|---|---|
| Truth repair passes visible checks / hidden batches | 25 / 25 / 25 / 25 |
| Truth position in the fixed root order | 294–961 (median 513; 8 beyond 600) |
| Root candidates | 673–1,097 |
| Role-identical `set_dedup` twins | median 29 (19–131) |

**Fix** (shared by every arm, by training, dreams and admission; `de_phase10e.dag10e`; designed on agi10ede/dev data):

1. **Discriminative roles.** `ckey` is a column with a `unique` test in `schema.yml`. `arrival` is an int column that increases
   with landing order inside every duplicate group of a `ckey`. On 9 dev replay projects the truth key has 0 twins and the truth
   order has 1 (a quantity column that also increases).
2. **Two-step dedup.** `add_partition(rel, key)`, then `set_dedup`'s minimal-change ORDER BY change.
3. **`deterministic_dedup`.** A partition tied at the top of its ORDER BY is never acceptable, so the partition-only state is
   never submitted.
4. **Admission.** Up to 30 draws (previously 10), plus retries when a candidate binds nowhere.

**Effect.** Fixed-guide A1 reaches the partition step but **not** the ordering step within 600 executions: every
`stg_customers` re-ordering comes first in the fixed order. **Learned guidance does reach it:** S_replay wake tasks verify in
84 executions, and in 44 when the replay macro is used.

## 4. Training (2 numeric-seeded repetitions × 120 tasks; `artifacts/agi10e_train/`)

| | rep0 | rep1 |
|---|---|---|
| Tasks reached / verified / wrong | 118 / 113 / 0 (2 tasks lost to the deadline) | 120 / 114 / **1** |
| S_replay wake verified | 6 / 7 | 5 / 7 (4 of them with the macro, 44 executions each) |
| L\* admitted | 11 macros, **none containing `add_partition`** | 10 macros, including **L5 = `add_partition → set_dedup`** (validated on 2 S_replay admission projects, progress 2 / 2) |
| Cost: wake / abstraction / dreams / ranker | 86.1 / 36.6 / 32.1 / 0.2 s | 83.2 / 40.5 / 30.5 / 0.2 s |
| Unsolved | S_replay 1, S_dirty 2, T_cdc_key+dirty 2 | S_replay 2, S_dirty 2, T_cdc_key+dirty 2 |

**Why rep0 has no replay macro** (`scripts/agi10e_diag_ckey.py`). The candidate's `add_partition` key role was `{dupes, int}`:
it had lost `ckey`, so it bound the first int columns with duplicates and made no progress at admission.

- All 3 of its sources do carry `ckey` on the truth key at the root, so the roles themselves are not the problem.
- One source was a **dream**. The greedy truth-distance witness (unchanged from Phase 10D) ties `add_partition(key)` against
  `add_partition(sequence)`, since both reduce the distance equally. Here it partitioned by the sequence first and fixed the key
  afterwards.
- Role intersection then dropped `ckey`. rep1's first candidate had only wake / dream sources that partitioned by the key, and it
  was admitted.

**The rep1 training wrong** (T_cdc_key+dirty 101524): `json_coalesce_before + add_partition + add_filter` passed every visible
check and was wrong on the hidden batches. A partition on an orders relation removed rows in a way the visible batches could not
distinguish. This is an open verifier gap; it is not in evaluation.

## 5. Evaluation (48 fresh one-use targets, agi10ede/eval 102000–102047, opened once)

336 rows, 0 build failures, 0 wrong.

**Held-out replay compositions, per family** (verified / 3):

| Family | A1 | A2 r0 / r1 | A3 r0 / r1 | A4 r0 / r1 |
|---|---|---|---|---|
| R1 replay + fanout | 0 | 3 / 3 | 0 / 1 | 3 / 3 |
| R2 replay + keycast | 0 | 3 / 3 | 0 / 3 | 3 / 3 |
| R3 replay + merge_update | 0 | 3 / 3 | 0 / 3 | 3 / 3 |
| R4 replay + merge_delete | 0 | 3 / 3 | 0 / 3 | 3 / 3 |
| R5 replay + fanout + merge_update | 0 | 1 / 1 | 0 / 1 | 2 / **3** |
| R6 replay + keycast + merge_delete | 0 | 3 / 3 | 0 / 3 | 3 / 3 |
| R7 replay + inner + merge_update | 0 | 3 / 3 | 0 / 3 | 3 / 3 |
| R8 replay + dirty + keycast | 0 | 2 / 2 | 0 / 1 | 2 / **3** |

**What the macro added in rep1** (A4_rep1 versus A2_rep1). Each of these targets was solved only with L5 as an atomic step:

| Target | Family | A4_rep1 path | A4_rep1 executions | A2_rep1 | rep0 arms |
|---|---|---|---|---|---|
| 102036 | R5 | `pre_aggregate, [L5: add_partition, set_dedup], merge_add_update` | 126 | 600, not solved | A2_rep0 and A4_rep0 solved it in 412 without a macro |
| 102038 | R5 | same | 166 | 600, not solved | unsolved by every rep0 arm |
| 102045 | R8 | `[L5], add_filter, cast_keys` | 126 | 600, not solved | unsolved by every rep0 arm |

- **Replay macro on verified paths:** in **24 / 24** of A4_rep1's held-out completions and **18 / 18** of A3_rep1's.
- **A4_rep0's +1 over A2_rep0** (102037, R5) uses no replay macro, since rep0 has none. A2_rep1 also solves it.
- **Search work.** On the 21 held-out targets both A2 and A4 solve, the executions were:

  | | A2 | A4 |
  |---|---|---|
  | rep1 | 3,853 | **2,200** |
  | rep0 | 4,462 | 4,379 |

  Over all 24 held-out targets: A1 14,400; A2 6,262 / 5,653; A4 5,997 / **2,618**.
- **Engines, A4_rep1:** DuckDB 12 / 12, SQLite 12 / 12, Polars 12 / 12, PySpark 12 / 12. **A1:** 4 / 5 / 4 / 6 (out of 12 each).

**Pre-registered verdicts:**

| Question | Verdict |
|---|---|
| L\* | **Untestable in rep0.** Positive in rep1: A4 − A2 = +3 (sign-flip p = 0.25, descriptive) and A3 − A1 = +18, with 0 wrong in A3 / A4. Both are at least +2, but the "replicated" verdict needs both repetitions, so it is **not replicated** |
| G_learned | **Replicated positive:** A2 − A1 = +21 and +21; A4 − A3 = +22 and +6 |
| Ordinary | A4 = 24 / 24 versus A1 = 19 / 24 in both repetitions (non-regression holds) |

## 6. Stage 4: external dev audit re-test (`artifacts/agi10e_external.json`; loader `de_phase10e.extload10e`)

| Funnel stage | Phase 10C (as written) | Phase 10E (as written, general loader) |
|---|---|---|
| Total | 16 | 16 |
| Ingested natively | **0** (10 loader / dialect + 2 multi-table + 4 expressiveness first failures) | **16** |
| Expressible in the stage IR | — | **10** |
| Candidate reached (passes public checks) | 3, behind a human adapter (T09, T11, T16) | **4** |
| Verified on all rows | 2 behind the adapter, 1 genuine (T09) | **3**, but only **1** genuine (T09); see below |
| Wrong repair | 1 (T16, behind the adapter) | **1** (T16) |

**Per task:**

| Task | Outcome |
|---|---|
| T01 (dbt `source` + cents → dollars), T08 (Hive `/`), T10 (DISTINCT ON, ASC bug), T12 (PySpark `dropDuplicates`), T15 (ISO timestamp window) | ingested and expressible; **no candidate** within budget |
| T05 (QUALIFY, ASC bug) | **verified with an empty path, which is vacuous.** In its data each customer's status never changes across versions, so the oldest and latest rows agree and the ordering bug cannot show |
| T09 (dirty numeric cast) | **the one genuine repair** (`default_fill amount = 0`) |
| T11 | already found **invalid as built** in Phase 10C ("solved" is vacuous) |
| T13 (Polars filter + `unique(keep='last')`) | ingested as a 2-stage pipeline (rule R7); has no reference repair |
| T16 (replayed duplicates) | **wrong**: the visible rows contain no duplicate (the same visible-sample gap as in Phase 10C) |
| T02, T03, T04, T06, T07, T14 | ingested; **not expressible** in the frozen stage IR: joins of aggregated derived inputs, CASE, COUNT(col), MERGE, JSON path, `when / otherwise` |

The **multi-table binder** ingests T02 and T04; both then stop on missing aggregates (MIN, COUNT), not on input binding.

**Disclosure.** The loader rules were developed against these same 16 texts, so this is a development measurement, not held-out
ingestion. No rule names a task. Tests use synthetic texts only.

## 7. Disclosures and deviations

1. **The 96088 premise in the owner's instruction came from my Phase 10C report and was wrong.** It is corrected above. The
   requested witness is still implemented and tested, and the actual cause is fixed separately.
2. **The two-step dedup decomposition is human design**, shared by all arms. It is what makes a replay repair a 2-step path
   that Sleep can abstract. It also explains why fixed-guide A1 is 0 / 24 on held-out targets (the ordering step sits deep in the
   fixed order). Phase 10D and 10E arm numbers are therefore **not directly comparable**.
3. **Stage 1 ceiling.** s1 ended at 229 / 250 s; it included a 90 s timeout of the first fix check, which rebuilt Phase 6 dev
   projects. The second development training rehearsal (55 s) was therefore charged to s2.
4. **The job runner refused chunk c11** (reservations for chunks still running). It then ran alone with the same code; no
   written row was rerun.
5. **Witness and rule checks** are uncharged spec / visible-data analyses.
6. **Spark** is evaluation-only, as in Phase 10D.
7. **The substrate is synthetic** (Phase 10D's generator). The external tasks are small synthetic tables in practitioner code
   forms.

## 8. Budget and protection

| Stage | Used / ceiling (s) | Notes |
|---|---|---|
| s1 | 229 / 250 | diagnostics, 96088 forensic, development checks, fix checks, tests, 1 development rehearsal |
| s2 | 366 / 500 | development rehearsal 2, training (2 × 157 s, parallel), `ckey` diagnostic, freeze |
| s3 | 322 / 350 | 336 evaluation rows in 12 chunks |
| s4 | 9 / 180 | loader development, final re-test |
| s5 | 1 / 120 | score, protection |
| **Total** | **928 / 1,400** | 910 s of the 1,838.4 s surplus remain |

- **Protection** (`artifacts/agi10e_protect_after.json`): 0 violations. Frozen Phase 1–10D files are unchanged, checkers v1–v5
  are pinned, and `main` = `d7ac8c5`.
- **One-use:** `agi10ede/eval` was claimed once.

## 9. Recommended next experiment

**Replicate the L\* result with a tie-free dream witness.** rep0's replay macro was lost to a tie in the greedy truth-distance
dream witness, which partitioned by the sequence instead of the key. Two candidate fixes:

- prefer the edit that fixes a failing contract on the visible data;
- or break ties by minimal change in role-form generality.

Either should be committed **before** retraining. Then retrain both repetitions and test A4 − A2 on a fresh replay-composition
draw. This is the cheapest way to turn the single-repetition +3 into a replicated (or refuted) result.
