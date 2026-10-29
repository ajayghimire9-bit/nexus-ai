# NEXUS Phase 10: unified Phase 9B completion and wake–sleep self-evolution (NOT LOCKED)

**Actual starting revision.** `e205c7a`, verified equal to `origin` and `github`. The instruction named `7f67a83`, but
**Phase 9B had already run** on top of it: the 12-project gate was rebuilt and scored 5 / 6 (`2587e22`, `e205c7a`).
`main` = `d7ac8c5` (untouched). Frozen Phase 1–9B artifacts are protected
(`artifacts/agi10_protected_hashes_before.json`: 1,926 files, 0 violations).

---

## §0 Pre-registration

Committed before any Stage 3 outcome and before opening `agi9de/confirm` or `agi10de/eval`.

### 0.1 Budget (`artifacts/agi10_grant.json`, registered once)

| Item | Seconds |
|---|---|
| New owner grant | +3,000 |
| **Verified** carried balance (Phase 9B pool 1,212.586 − 148.571 charged) | 1,064.015 |
| **Pool** | **4,064.015** |
| Cap | 3,500 |
| Reserve after the cap | ≥ 564.015 (≥ 362.185 required) |

The owner text pooled 862.185 s, which is the balance **before** Phase 9B. The Phase 9B +350 s is inside the verified
balance and is not added again.

**Stage ceilings:** S1 650, S2 450, S3 1,300, S4 900, S5 200. Unused earlier funds roll forward into S3 / S4, logged
before the targets open. Every row is appended and flushed.

### 0.2 Stage 1A: expressiveness audit of the 5 / 9 no-candidate Phase 9 development tasks

Source: `artifacts/agi10_dev/audit_5of9.jsonl`. The witness is reference-assisted and used for development diagnosis
only.

| Task | Faults | Witness | Standard 3,000 | 4× budget (12,000) | Class |
|---|---|---|---|---|---|
| P5 77300 | watermark, checkpoint, replay | depth 3; first step `dedup_first` **neutral** | none | none | expressible; not reached even at 4× (search ranking) |
| P1 77302 | window, dup_id | depth 3; first step `dedup_first` **neutral** | none | none | expressible; ranking |
| P1 77305 | window | depth 2 | none | ambiguous (found) | expressible; budget-limited |
| P7 77303 | ratio | **none**; the truth replaces an outer `cast_int` by `round2`, and no operator removes an integer cast | none | none | candidate **missing primitive** |
| P5 77306 | (undecided) | – | – | – | unresolved intent; no correct submission exists |

**Conclusion.** 3 / 5 are search-ordering or budget failures, two of them behind a **score-neutral first step**, which a
score-greedy order defers. That supports a learned contextual ranker. One is a genuine expressiveness gap, which ranking
cannot fix. One is undecided intent.

### 0.3 The owner's "de_accept_v4" checks (shared by all arms; versioned here as coverage v10, `procedure10`)

1. **Unimplemented documented requirements block.** This is the coverage v8 "absent" rule: no input column depends on
   the documented threshold, so the obligation blocks. Already in force since Phase 8.
2. **Legacy-baseline conflict.** The unedited legacy pipeline's boundary behaviour is profiled at each implemented
   obligation's threshold.
   - If every attached claim is **unapproved** (not approved, not from the contract) and disagrees with the legacy
     behaviour, the boundary is **not settled by that claim**. It becomes a conflict for calibrated trust, the single
     question, or abstention.
   - An approved or contract claim still overrides legacy behaviour: legacy is evidence, never authority.
   - Tests: `tests/test_agi10.py`.

### 0.4 Gate 1 (Phase 9B)

**Controls 1–5 passed** on the rebuilt 12-project development set (`artifacts/agi9b_dev/gate.json`). They are not rerun,
because nothing they measure has changed.

**Control 6** (skill removal) failed in 9B. No admitted method enabled a completion that base search missed (24 screen
projects); the methods cut work by 56 % on P6 but changed no completion. Only the library can change this, so control 6
is **retested after Stage 3** with the wake–sleep library (`scripts/agi10_gate6.py`):
- the same completion-based rule (a fresh-seed replication must show with-L\* > without-L\*, with 0 wrong);
- new development seeds;
- screen specs include the budget-binding regime from 0.2.

**The 18-project one-use confirmation set (`agi9de/confirm`) opens only if control 6 then passes.** In that case a
two-parent protocol is committed before opening.

### 0.5 Stage 2: substrate (`artifacts/agi10_dev/substrate.jsonl`)

**Coverage check.** 28 development projects across P1–P7 × SQLite / DuckDB / PySpark 4.0.1 (ANSI), plus P8 (Scala lift)
and P9 hybrids A / B / C, X1 and X2:
- legacy languages encountered: PySpark 10, Postgres 6, Snowflake 6, dbt Jinja-SQL + `schema.yml` 6, SQLite 5, Scala 2;
- **all 23 decided truth pipelines execute** through every stage's declared engine under the independent evaluator;
- the 5 others have an undecided requirement (unverifiable by design).

**Not implemented (listed, not simulated):**
- multi-table schemas and joins;
- Polars (not installed);
- Debezium-style nested CDC envelopes;
- MERGE and snapshot reconciliation;
- QUALIFY;
- ingestion of external repositories (none available offline; no download).

The "multi-file" targets are therefore multi-stage, multi-engine pipelines (dbt models + `schema.yml`, P9 hybrids). They
are **not** multi-table repositories.

**Splits** (`manifest10`):
- **Repositories:** Repos_Train = base-name schemas; Repos_Eval = held-out-name schemas.
- **Held-out families:** Tier 3 (P8, P9) and the mutation family `require`, which training generation rejects.
- **Seeds:** disjoint ranges per use.

### 0.6 Stage 3: the wake–sleep learner (`lineage10`, `guide10`, `memory10`)

**Wake.** The learner uses F0 or π\* with memory: trust, evidence weights w = **G_count**, library **L\***, and the
ranker **G_learned** once trained. Hidden verification is the feedback.

Updates after each task:
- trust, and w;
- skill sources (verified repairs; partial stage repairs **only if P\* is on**);
- **P\***: partial and failed hypotheses with support / refute counts and Beta(1 + s, 1 + r) 90 % intervals; boundary
  witnesses x_diff; unresolved claims;
- ranker pairs along every verified path.

**Sleep (every 10 tasks and at each checkpoint)**

**Abstraction.** At most 2 candidates per sleep. Promotion into L\* requires both of:
- **ΔMDL > M.mdl_threshold** under the declared bit model (a primitive step costs log2 14 + log2 10 bits; single-operator
  specialisations need ≥ 4 supporting tasks, two-step compositions ≥ 2);
- **leave-one-paradigm-out (LOPO)** validation on 2 applicable + 1 retention project from paradigms absent from the
  support: no added wrong submission, no lost completion.

**Dreams.** M.dream_ratio × 10 Repos_Train tasks per sleep, but only if the task's **truth passes the v7 invariants and
the hidden evaluator** (the contract guard). Each yields witness-path ranker pairs; the generator's specification is used
as training supervision only, never as a target.

**Ranker.** A pairwise logistic model over sparse tokens (operator × evidence feature, × parameter schema role, × stage).
Sibling candidates are censored, not refuted. Accuracy is measured on a project-grouped held-out 20 %.

**Search with G_learned.** Children come **70 % in ranker order and 30 % in unpruned fallback order**, interleaved. With
progressive widening, every child stays reachable. The ratio is an M field.

**π\* rounds (N1, N2).** Counterfactual replay of typed procedure proposals on an 8-project cached pool (4 multi-conflict,
K ≥ 2). Unsupported counterfactuals are skipped as unknown. Each cycle uses admit7. A change is adopted only if it is not
worse, with 0 wrong, on a separate 6-project confirmation pool (4 multi-conflict).

**M\* round (N1).** Clones run 20 tasks (2 sleeps) under M0, M′ (one seeded single-field edit of mdl_threshold,
guided_ratio or dream_ratio) and M_rand, on a common stream. Their frozen memories are validated on 10 tasks with F0.
- M′ is adopted only if every clone completed the stream, M′ verifies **strictly more** tasks than M0 (at least 1), and
  adds no wrong submission.
- A truncated or zero-solve comparison is uninformative.

**Lineages** (one repetition each; one exogenous stream):

| Lineage | Settings |
|---|---|
| **main** (C1) | P\* on; π\* and M\* rounds |
| **C2** | P\* discarded; π\* rounds; main's M\* decision applied at N1, so that only P\* differs |
| **C3** | only if main adopts M\*: continues from main's pre-M\* N1 checkpoint with M locked at M0 |

**Checkpoints:** N1 = 25, N2 = 60, N3 = 120. **Measured development throughput:** wake ≈ 1–3 s; π\* round ≈ 38 s;
M\* round ≈ 3 × (20 tasks + 2 sleeps).

### 0.7 Stage 4: 48 one-use targets (`agi10de/eval` 84000–84047; `manifest10.eval_manifest`)

**Targets:**
- **24 seen families on unfamiliar (held-out-name) repositories:** 8 multi-conflict P5, plus 16 P1–P7 / X1 / X2 with
  mixed requirement conditions.
- **24 held out:** P8 × 8, P9.A × 4 (multi-conflict modes), P9.B × 4, P9.C × 4, and P6 × 4 with the held-out `require`
  mutation family.
- **12 targets are built for K ≥ 2.** The realised K is recorded per row.

**624 pre-registered rows, 13 arms:**

| Arm | Library | Guide | Trust | Procedure | Lineage / checkpoint |
|---|---|---|---|---|---|
| A1@N0 | L0 | fixed | none | F0 | fresh |
| A2 | L0 | count | removed | F0 | N3 (main, or C3 if M\* adopted) |
| A3 | L0 | learned | removed | F0 | N3 |
| B1 | L0 ∪ L\* | fixed | removed | F0 | N3 |
| B2 | L0 ∪ L\* | count | removed | F0 | N3 |
| B3 | L0 ∪ L\* | learned | removed | F0 | N1, N2, N3 |
| C1 | L\* + strongest P\* hypotheses | learned | kept | π\* | main N1, N2, N3 |
| C2 | as C1 | learned | kept | π\* | C2 lineage N3 |
| C3 | as C1 | learned | kept | π\* | C3 lineage N3; identical to C1 by construction if no M\* was adopted |

**Reported:**
- factorial marginal effects (L\*, G_count, G_learned, the interactions, full B3 − A1);
- self-evolution contrasts (C1 − B3, C1 − C2, C1 − C3);
- learning curves N0 → N3 (overall / seen / held-out) and forgetting between checkpoints;
- candidate-starved searches rescued (A1 "no repair candidate" vs each arm);
- accepted wrong repairs (target 0);
- full amortised cost from the training logs.

**Test:** two-sided paired sign-flip on per-target differences. One lineage repetition means **no claim of generality
across lineages**. Missing rows stay missing; no chunk outcome is rerun.

### 0.8 Not attempted

- **Neural models:** no transformer or neural ranker. The ranker is a logistic model sized to the data.
- **No external API** use.
- **No multi-table arena.**
- **Independent cross-domain transfer:** not attempted; no shared executable interface exists (Phase 8 finding).

---

## §1 Results (NOT LOCKED)

**Commits:**
- Commit 1 (protocol + code) `5ed57fe`; S2 → S3 transfer committed separately;
- lineages, gate-6 retest and freeze `03eb439` (before `agi10de/eval` opened);
- results: this commit.

**Raw data:**
- `artifacts/agi10_train/*.jsonl|json`
- `artifacts/agi10_dev/`
- `artifacts/agi10_eval/rows_c*.jsonl` (576 rows) and `result.json`
- `artifacts/mi_logs/a10-*.log`

### 1.1 Budget (charged wall s)

| Stage | Used | Ceiling after logged transfers |
|---|---|---|
| S1 | 56 | 350 (650; 300 → S4) |
| S2 | 203 | 203 (450; 247 → S3) |
| S3 | 999 (main 576, C2 422) | 1,547 |
| S4 | 505 (8 chunks, all COMPLETE, no resume) | 1,200 |
| S5 | ~10 | 200 |
| **Total** | **~1,773** | **3,500** |

**Pool remaining ≈ 2,291 s,** which includes the ≥ 564 s reserve.

**Training cost, main lineage:** wake 163, abstraction 90, dreams 52, ranker 0.1, π\* rounds 91, M\* round 168.
**C2:** wake 179, abstraction 86, dreams 53, π\* rounds 92.

### 1.2 Stage 1: Phase 9B Gate 1 and the two-parent confirmation

- **Controls 1–5:** passed in 9B.
- **Control 6 retest:** the 16-method wake–sleep library plus every earlier method (`artifacts/agi10_dev/gate6.json`):
  - **no screen project** where the library verified and the base did not (16 projects, including the budget-binding
    P1 / P5 regime);
  - P6 work fell again, from ~197 to 85 runs, with no completion change;
  - **Gate 6 fails again.**
- **The 18-project `agi9de/confirm` set remains UNOPENED;** the two-parent comparison was not run.

### 1.3 Stage 3: what the wake–sleep learner did (main lineage)

**Training outcome:** 119 tasks (one task could not be generated with the held-out family excluded), **96 verified, 0
wrong.** Source verification rose 17 / 25 → 28 / 35 → 51 / 59; the stream order confounds this.

**Method invention (MDL + LOPO):**
- 26 candidates; **16 promoted into L\*.**
- Every single-operator specialisation with fewer than 4 supporting tasks was refused by the MDL test, as designed.
- Promoted methods include compositions such as dedup → window filter, normalize → dedup, `real_div → round2`, and the
  CDC latest → drop-tombstone method.
- **9 of the 16 have partial-program (P\*) support.**

**Search guide and dreams:**
- **Ranker:** grew to 1,728 pairs; project-grouped held-out pair accuracy 0.83–0.97.
- **Dreams:** 39 generated, 35 passed the contract guard, 31 gave witness paths.

**Self-evolution:**
- **π\*:** both rounds (N25, N60) found **no admissible procedure change**; F0 retained.
- **M\*:** M′ (MDL threshold 10) verified 9 vs M0 8 vs M_rand 7 of 10 validation tasks. **Not adopted:** one stream task
  failed to generate in all three clones (19 / 20 each), and the implemented completeness check treated that as
  truncation.
  - This is a rule-implementation discrepancy, disclosed rather than retro-adopted.
  - The margin is a single task.
  - The main lineage ran under M0 throughout, so **C3 ≡ C1 by construction** (not run).

**C2 (P\* discarded):** 120 tasks, 13 methods, P\* empty, no π\* adoption.

### 1.4 Stage 4: 48 one-use targets × 12 arms (576 rows; C3 ≡ C1; no build failures)

| Arm | Verified / 48 | Seen / 24 | Tier 3 / 20 | Held-out mutation / 4 | K ≥ 2 | No candidate | Questions | Wrong |
|---|---|---|---|---|---|---|---|---|
| A1@N0 fresh, L0, G_fixed | 25 | 14 | 7 | 4 | 0 / 7 | 15 | 12 | 0 |
| A2 L0 + G_count | 25 | 14 | 7 | 4 | 0 / 7 | 15 | 12 | 0 |
| A3 L0 + G_learned | 26 | 15 | 7 | 4 | 0 / 7 | 13 | 13 | 0 |
| B1 L\* + G_fixed | 25 | 14 | 7 | 4 | 0 / 7 | 15 | 12 | 0 |
| B2 L\* + G_count | 25 | 14 | 7 | 4 | 0 / 7 | 15 | 12 | 0 |
| B3@N3 L\* + G_learned | 26 | 15 | 7 | 4 | 0 / 7 | 13 | 13 | 0 |
| B3@N25 / @N60 | 27 / 27 | 15 / 15 | 8 / 8 | 4 / 4 | 0 / 7 | 12 / 12 | 14 / 13 | 0 |
| **C1@N25 / N60 / N120** (trust + L\* + G_learned + P\* + π\*) | **33 / 33 / 32** | **21 / 21 / 21** | 8 / 8 / 7 | 4 | **6 / 7** | 12 / 12 / 13 | 12 / 7 / 7 | 0 / **1** / 0 |
| C2@N3 (P\* discarded) | 32 | 21 | 7 | 4 | 6 / 7 | 13 | 7 | 0 |

The factorial cells remove trust in all six arms, by pre-registration.

**Factorial attribution at N3** (per-target paired; sign-flip):

| Effect | Result |
|---|---|
| L\* (B1 − A1) | **0.0 pp** |
| G_count (A2 − A1) | **0.0 pp** |
| G_learned (A3 − A1) | **+2.1 pp** (1 target, 84016; p = 1.0) |
| L\* given G_count (B2 − A2) | 0.0 pp |
| L\* given G_learned (B3 − A3) | 0.0 pp |
| G_learned vs G_count, given L\* | +2.1 pp |
| Full wake–sleep (B3 − A1) | **+2.1 pp** |

**Candidate-starved searches.** A1 had 15. G_learned arms made 2–3 of them reachable or solved (the 30 % fallback keeps
every child reachable); count and library arms rescued 0.

**Self-evolution and memory:**

| Contrast | Result |
|---|---|
| **C1 − B3** | **+12.5 pp, p = 0.032.** Gained the 6 multi-conflict targets 84000 / 01 / 03 / 04 / 06 / 07; lost none. |
| C1 − C2 (P\*) | **0.0 pp** |
| C1 − C3 (M\*) | identical by construction (M\* not adopted) |
| C1 − A1 | +14.6 pp, p = 0.017 |

C1 and B3 differ by calibrated **trust**, P\* hypotheses and π\*. π\* was not adopted, and P\* contributes 0 (C1 = C2 on
every target). So the C1 − B3 gain is the **calibrated trust acquired from experience**. It resolves approved-vs-draft
conflicts and frees the single question: 6 / 7 multi-conflict targets vs 0 / 7 without trust.

**Learning curve and forgetting:**
- **Values:** C1 33 → 33 → 32 and B3 27 → 27 → 26 at N25 → N60 → N120, against 25 at N0.
- **Saturation:** the benefit is reached by N25 and does not grow.
- **Forgetting:** single-target swaps between checkpoints (84040 / 84041); the N120 dips are one target each.

**Held-out generalisation:**
- **Tier 3:** 7–8 / 20 in every arm. No learning component improved migration or hybrid targets.
- **Held-out mutation family `require`:** 4 / 4 in every arm. The base search already solves it, so it does not test
  transfer.

**Accepted wrong repairs: 1 / 576** (C1@N60 on 84005; every other arm abstained). Post-hoc diagnosis
(`scripts/agi10_posthoc.py`; no outcome changed) found a **defect in the shared acceptance machinery I wrote**:
- The same documented checkpoint boundary appeared twice: as a repair-closure decision point (whose options mixed two
  thresholds, so it carried no single subject and coverage did not deduplicate it) and as a coverage obligation.
- The clarification set the closure point to `ge`; trust correctly chose the approved "kept" claim on the obligation.
- Both decisions meant "keep boundary rows". But the coverage choice is applied as a **relative flip after** the closure
  rebinding, so `ge` became `gt`.
- This is a latent defect for every arm, exposed by one draw. **Fix** (not applied to any scored row): apply coverage
  choices as the target boundary effect, or recompute coverage after closure rebinding.

### 1.5 Pre-registered measurements

1. **Gate 1 / two-parent confirmation:** 5 / 6. Control 6 fails twice; the confirmation set is unopened.
2. **Learning curve:**
   - N0 25 → C1 33 / 33 / 32 (seen 14 → 21; Tier 3 7 → 8 / 8 / 7);
   - minimal forgetting (single swaps);
   - amortised training cost ≈ 576 s (main), plus 422 s (C2) and 505 s of evaluation.
3. **Factorial:** L\* 0; G_count 0; G_learned +2.1 pp (n.s.) and 2–3 starved searches rescued.
4. **Self-evolution:** π\* not adopted; P\* 0; M\* not adopted (discrepancy disclosed).
   - Trust from experience: +12.5 pp (p = 0.032).
   - Accepted wrong repairs: 1 (a shared-infrastructure defect).

### 1.6 What NEXUS did and did not do

**Autonomous outputs:**
- 16 MDL- and LOPO-promoted executable methods; 9 had support from incomplete experience (P\*).
- A contextual search ranker trained on its own verified repairs and contract-guarded dreams.
- Calibrated trust that generalises to unfamiliar repositories.

**Verified benefit on unseen targets:**
- Trust gives +6 multi-conflict targets.
- The ranker gives +1 target and rescues 2–3 starved searches.

**Not shown:**
- Any completion value of the invented library.
- Any value of P\*.
- An improved procedure (π\*) or improver (M\*).
- Transfer to Tier 3.

**Most supported next step.** The library and the ranker affect *how cheaply* reachable repairs are found, not *which*
repairs are reachable. The audit's residual failures are a missing primitive (integer cast → rounding) and
neutral-first-step search depth. The next experiment should therefore:
1. Fix the coverage-application defect.
2. Add ranker-guided *depth* (expanding score-neutral steps the ranker prefers) under the same 30 % fallback.
3. Measure starved-search rescue on Tier 3 directly.
