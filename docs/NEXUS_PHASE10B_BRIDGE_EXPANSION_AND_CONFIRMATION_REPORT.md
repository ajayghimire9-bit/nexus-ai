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
