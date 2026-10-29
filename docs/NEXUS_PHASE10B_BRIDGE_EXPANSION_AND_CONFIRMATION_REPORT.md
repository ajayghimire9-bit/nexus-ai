# NEXUS Phase 10B: zero-gain bridge expansion, valley-crossing macros, confirmation (NOT LOCKED)

**Starting revision.** `e3739da`, verified equal to `origin` and `github`. `main` = `d7ac8c5`. Frozen Phase 1–10
artifacts are protected (`artifacts/agi10b_protected_hashes_before.json`: 2,032 files, 0 violations).

## Corrections to the brief's premises (from the Phase 10 raw rows)

1. **The "57 % average run reduction (197 → 85)" held on the 4 P6 screen projects only.** On P2, P4 and X1 the library
   cost about +5 runs or changed nothing.
2. **The +12.5-point gain** is C1@N120 (32 / 48) minus B3@N3 (26 / 48). C1 was 33 at N25 and N60; fresh A1 was 25.
3. **Multi-table joins, MERGE / QUALIFY and Debezium envelopes (fix 5) are not implemented in the arena.** Adding them
   needs new IR, generator mechanisms, lowering for SQLite / DuckDB / Spark, legacy-dialect lifting and evaluator support.
   No such targets exist, so none are claimed; the Migration / Hybrid tasks are the existing P8 / P9 multi-stage,
   multi-engine pipelines.

---

## §0 Pre-registration

Committed before any training outcome and before opening `agi9de/confirm` or `agi10bde/eval`.

### 0.1 Budget (`artifacts/agi10b_grant.json`, registered once)

| Item | Seconds |
|---|---|
| Owner grant | +1,500 |
| Verified carry | 2,292.334 |
| **Pool** | **3,792.334** |
| **Cap** | **1,800** |

**Ceilings:** S1 250, S2 350, S3 600, S4 450, S5 150; unused earlier funds roll forward, logged.

**Feasibility boundary** (measured before any outcome). One 120-task repetition costs about 430–500 s, so two
repetitions do not fit S3 600 s plus the S1 leftover of about 144 s. Pre-registered response:
- each repetition is capped at **370 s**;
- **N3 = the last completed task count (≤ 120)**, saved as `repN.final.json`;
- the actual N is reported;
- no rerun.

### 0.2 Shared fixes (human; every arm; `de_phase10b/fixes10b.py`)

1. **ROUND primitive.** `round_uncast` maps `cast_int(E)` with a real division inside to `round2(E)`.
   - Dev check: the Phase 10 audit's missing-primitive task P7 77303 now has a 2-step witness, and under the full F0
     investigation it **verifies**.
   - Search alone, without the barrier, submits a wrong pipeline; the barrier is what makes it safe.
2. **Idempotent coverage application.** The chosen boundary effect is enforced as a target predicate on the obligation's
   probe row after closure rebinding, and flipped only if it does not already hold.
   - Dev check: the Phase 10 wrong-repair configuration (84005, now development data) **verifies** instead of submitting
     wrong.
3. **M\* validation gate.** Clones are compared over validation tasks that were built for every clone. The edited M must
   add 0 new build or truncation failures. A clone counts as truncated only when stopped by the deadline.

### 0.3 Learning mechanisms (`search10b`, `lineage10b`)

**Bridge expansion** (only in arms whose ranker carries `bridge = true`):
- A child with Δscore = 0 that the learned ranker places in its node's top 5 is a **bridge**.
- 3 of every 10 expansion slots go to the best open bridge, evaluating its top-3 ranker-predicted follow-up steps.
- The other slots expand by (score, ranker) with children mixed 4:3 between ranker order and the unpruned fallback order:
  about 40 % guided / 30 % bridge lookahead / 30 % fallback.
- Nothing is pruned (progressive widening).
- Dev check on the two neutral-first-step audit tasks: 13 and 19 bridges marked, 6 bridge expansions each; outcome equal
  to the ranker without bridges (one ambiguous candidate on 77300, none on 77302).

**Valley-crossing macros.** Every verified path is replayed step by step. A consecutive pair with Δscore(a1) ≤ 0 and
Δscore(a1 ∘ a2) > 0 is recorded as a bridge skill source. Sleep abstraction considers bridge candidates first; the MDL +
LOPO admission rule is unchanged.

**Budget settings:**
- 1 abstraction candidate per sleep;
- the M\* round compares M0 vs M′ only (no M_rand);
- dreams on SQLite / DuckDB repositories only;
- π\* rounds disabled (never adopted in Phases 8–10).

**Repetitions:** rep0 and rep1 have **independent** exogenous Repos_Train streams (`manifest10b.train(rep)`). Each runs
an M\* round at N25 and keeps checkpoints at N25, N60 and N3.

### 0.4 Gate control 6, as redefined by the owner (skill / bridge-macro / ranker utility; `scripts/agi10b_gate6.py`)

**Arms:**
- **learned** = the Phase 10 main N120 library + its learned ranker **with bridge expansion**;
- **plain** = no library, fixed order;
- same total work budget; ROUND and idempotent fixes for both.

**Screen:** 14 development projects with zero-gain first steps (all-fault P1 / P5 / P4 / X1 / P7).

**Rule (completion-based):** every spec where learned verified and plain did not is replicated on 3 fresh seeds. The gate
passes iff learned verifies strictly more than plain on the replication seeds, with 0 wrong.

**Controls 1–5** passed in Phase 9B and are not rerun.

### 0.5 Confirmation (only if the gate passes)

**`agi9de/confirm`**: 18 one-use projects (6 strata × 3), never opened. **Arms:** A1 (fresh), plus Full_r and
TrustOnly_r for both repetitions (the two parents): 90 rows, with a per-parent paired comparison.
`scripts/agi10b_eval.py confirm` **refuses to run unless the gate passed.**

### 0.6 Evaluation (`agi10bde/eval` 85000–85047)

**Targets:** 48 fresh one-use targets with the Phase 10 structure: 24 seen families on held-out-name repositories (8
multi-conflict), 20 P8 / P9, and 4 held-out `require` mutation targets.

**11 arms (528 rows):**

| Arm | Composition |
|---|---|
| A1 | fresh |
| Full_r (r = 0, 1) | trust + L\* + bridge ranker + P\* top-3 |
| noLib_r | Full without the library |
| noBridge_r | Full with the ranker but without bridge expansion |
| noRanker_r | Full with the fixed guide |
| noTrust_r | Full without trust |

**Reported:**
- per-repetition and mean contrasts (two-sided sign-flip per target);
- P8 / P9 completion;
- accepted wrong repairs (target 0);
- candidate-starved rescues;
- full training costs.

**Two repetitions are a replication check, not a population estimate.**

---

## §1 Results (NOT LOCKED)

**Commits:**
- protocol `87c32e0`;
- transfer + job file;
- gate record + checkpoints + freeze `77a6f0c` (before either one-use set opened);
- results: this commit.

**Raw data:**
- `artifacts/agi10b_train/`
- `artifacts/agi10b_dev/` (checks, gate6, gate6_libonly)
- `artifacts/agi10b_eval/rows_c*.jsonl` (528) and `confirm_c*.jsonl` (90), plus `result.json` / `confirm_result.json`

### 1.1 Budget and execution events

| Stage | Used | Ceiling after logged transfers |
|---|---|---|
| S1 | 106 | 106 (250; 144 → S3) |
| S2 | 142 | 200 (350; 150 → S4) |
| S3 | 661 | 661 (744; 83 → S4) |
| S4 | 607 | 683 |
| S5 | ~45 | 150 |
| **Total** | **~1,560** | **1,800** |

**Pool remaining ≈ 2,232 s.** The +1,500 s grant was registered once.

**Events:**
1. **Repetitions hit the pre-registered 370 s cap.** rep0 reached N3 = **78** tasks, rep1 **40**. rep1's M\* round cost 215 s vs 115 s for rep0. **Exposure is not matched** across repetitions.
2. **Three evaluation chunks timed out** at 88 s. They were **resumed once**; the written rows stayed byte-identical (`cmp`), and 53 never-executed rows were run. No completed row was rerun.
3. All 528 evaluation rows and all 90 confirmation rows are present; no build failures.

### 1.2 What the learner did

| | rep0 | rep1 |
|---|---|---|
| Tasks (N3) | 78 | 40 |
| Verified / wrong at source | 63 / 0 | 31 / **1** (an X2 composite, training-time) |
| Valley crossings detected | 1 (`dedup_first → filter_file`: +0.0 then +0.1) | 1 (`filter_file → filter_cmp`: +0.0 then +1.4) |
| Methods promoted (MDL + LOPO) | 5 (one multi-step: CDC latest → drop tombstone); **0 valley-crossing** | 3; **1 valley-crossing** (window start + end filter pair) |
| **M\* round** (fixed gate) | **adopted for the first time:** MDL threshold 0 → 10; 9 vs 8 on 10 fully built validation tasks; no build or truncation failures | 9 vs 9 tie; not adopted |

### 1.3 Gate 1 and the one-use confirmation set

**Gate control 6** under the owner's 10B definition (L\* + ranker with bridge vs plain, unguided search) **passed**: the
all-fault X1 composite was solved 3 / 3 vs 0 / 3 on fresh replication seeds, with 0 wrong. Controls 1–5 passed in 9B.
So **agi9de/confirm was opened.**

**Two-parent paired confirmation (18 projects × 5 arms, 0 wrong):**
- every arm verifies **11 / 18**: A1 fresh, Full_rep0, Full_rep1, TrustOnly_rep0, TrustOnly_rep1;
- all contrasts are 0.0 pp;
- only one of its 18 projects realised K ≥ 2;
- **the learned systems did not outperform fresh search on this set in either parent.**

**Addendum correction.** The addendum requires control 6 to remove *macros only*, leaving bridge search and guidance
unchanged. That library-only check was run as a post-hoc development diagnostic (`artifacts/agi10b_dev/gate6_libonly.json`)
on the same replication seeds:

| Arm | X1 solved | P7 solved |
|---|---|---|
| Learned ranker + bridge, **no macros** | **3 / 3** | 0 / 3 |
| Macros + fixed guide | **0 / 3** | 0 / 3 |
| Plain search | 0 / 3 | 0 / 3 |

The method queue never accepted a macro. **The gate-6 pass was produced by learned ranking, not by library value.**
Under the addendum's definition the gate would have stood at **5 / 6**, and the confirmation set would not have been
opened. Its result (a null) is reported as is; nothing is reopened or rerun.

### 1.4 48 fresh one-use targets × 11 arms (528 rows)

| Arm | Verified / 48 | Seen / 24 | Tier 3 / 20 | Mutation / 4 | Multi-conflict | No candidate | Wrong |
|---|---|---|---|---|---|---|---|
| A1 fresh | 25 | 14 | 7 | 4 | 0 / 5 | 16 | 0 |
| **Full rep0 / rep1** | **31 / 31** | **20 / 20** | 7 / 7 | 4 / 4 | **4 / 5** | 14 / 15 | **0 / 0** |
| noLib | 31 / 31 | 20 | 7 | 4 | 4 / 5 | 14 / 15 | 0 |
| noBridge | 31 / 31 | 20 | 7 | 4 | 4 / 5 | 14 / 14 | 0 |
| noRanker (fixed guide) | 28 / 28 | 17 | 7 | 4 | 3 / 5 | 16 | 0 |
| noTrust | 27 / 27 | 16 | 7 | 4 | 0 / 5 | 14 / 15 | 0 |

**Contrasts** (identical in both repetitions; per-target sign-flip):

| Contrast | Result |
|---|---|
| **Full − A1** | **+12.5 pp** (rep0 p = 0.029; rep1 p = 0.030). Gained 85000, 85003, 85005, 85006, 85016, 85020; lost none. |
| **Learned ranking + bridge (Full − noRanker)** | **+6.2 pp**, 3 targets (85003, 85016, 85020), p = 0.26 |
| **Calibrated trust (Full − noTrust)** | **+8.3 pp**, 4 targets (85000, 85003, 85005, 85006), p = 0.12 to 0.13 |
| **Learned macros (Full − noLib)** | **0.0 pp** |
| **Bridge expansion (Full − noBridge)** | **0.0 pp**: bridge lookahead added nothing beyond the learned ranker |
| **Tier 3 (P8 / P9)** | **7 / 20 in every arm.** The Migration / Hybrid ceiling did not move. |

**Accepted wrong repairs: 0 / 528, and 0 / 90 in the confirmation set.** The idempotent coverage fix held on every row.

**Candidate-starved searches.** A1 had 16. Learned-ranker arms rescued 1–2; fixed-guide arms rescued 0.

### 1.5 Answers

**Repeatable advantage.** Full beats fresh by +12.5 pp in **both** repetitions, with identical target sets. It comes from:
- **calibrated trust** (+8.3 pp; multi-conflict 0 / 5 → 4 / 5);
- **learned ranking** (+6.2 pp).

**What did not help:**
- **Learned macros** (L\*, including the one valley-crossing macro): 0. The method queue accepted no macro on the gate's
  replication seeds.
- **Bridge expansion:** 0 beyond the ranker.
- **Tier 3:** no transfer gain.
- **The 18-project confirmation set:** a null for every learned arm.

**What this means.**
- **Experienced memory and guidance:** the repeatable gain comes from what NEXUS learned (trust from documents and
  outcomes; a search ranker from its own verified repairs and dreams), not from the shared fixes.
- **Shared fixes:** ROUND and idempotent coverage are given to every arm, so they cannot explain a difference between
  arms.
- **Reusable abstractions:** NEXUS has not shown that its invented abstractions solve unfamiliar compositions.
- **Valley crossings:** they were rare in source experience (1 per repetition), so the abstraction mechanism had almost
  nothing to promote.

## §2 Addendum responses and the registered follow-up (not run; the affected targets were already open)

The addendum arrived after both one-use sets had been claimed and opened, so its changes were **not** applied to them.

| Addendum item | Status |
|---|---|
| Same bridge capability for controls | **Not met** by this evaluation. Bridge search here is active only with the learned ranker; fixed-guidance arms use the old search. Follow-up: a ranker-free bridge criterion (top-k flat steps by fixed order) so all four cells A–D use the bridge machinery. |
| A–D 2 × 2 (all with bridge) | Partly available: B = noLib, D = Full, C = noRanker **without bridge**, A = A1 **without bridge**. A matched 2 × 2 is registered as the follow-up. |
| Unfamiliar compositions | **Not met.** The split withholds repositories (names) and families (Tier 3, `require`), not repair compositions. New seeds and renamed schemas do not establish compositional novelty. Follow-up: withhold composition families (fault-mechanism pairs) from source, dreams and admission; include neutral- and worsening-prefix targets plus a broad ordinary-repair comparison set. |
| Cost accounting | Macro and bridge steps are charged as engine executions in `work`. Ranking and feature computation are charged in wall / CPU, not in `work`. Queue shares are enforced by **expansion counts, not measured work**, and fallback work was not logged separately. Follow-up: work-based queue allocation with a per-queue work log. |
| ROUND check | `round_uncast` does remove the enclosing integer cast: it maps `cast_int(E)` → `round2(E)`, unlike `round2`, which wraps `cast_int(E)`. Verified on development task 77303: 2-step witness; verified under F0. |
| Improver stream | Clones built their streams independently; shared vs candidate-induced build failures are distinguished (`new_build_failures`); none occurred. Follow-up: prebuild one common valid stream. The Phase 10 9-vs-8 candidate was **not** retro-adopted; rep0's adoption is a new, fully built comparison. |
| Multi-table / MERGE / CDC | Kept separate; not implemented. |
| Throughput | 120 tasks per repetition was not achievable within the cap: 78 and 40 were measured. |

**Registered follow-up (Phase 10C):**
1. A matched 2 × 2 with bridge search for all four cells (fixed vs learned guidance × no vs learned macros), with trust,
   procedure and improver held fixed.
2. A composition-withheld split, frozen before evaluation.
3. Work-based queue allocation with logs.
4. A common prebuilt improver stream.
5. A new one-use evaluation range, sized from measured throughput.
