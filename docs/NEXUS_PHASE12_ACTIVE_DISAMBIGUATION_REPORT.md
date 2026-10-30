# NEXUS Phase 12 — autonomous distinguishing-input construction and active hypothesis falsification (NOT LOCKED)

## Revisions and scope

| Item | Revision |
|---|---|
| Start | `111417c` |
| Commit 1: frozen Suite 1 manifest, core fixes, protocol, before any tuning | `79b1a3d` |
| Commit 2: development readiness gate and evaluation freeze, before Suite 1 opened | `66d9f26` |
| `main` | `d7ac8c5`, untouched |

- **Machine:** Apple M4, CPython 3.13.5; no external LLM API, no pretrained weights.
- **Protocol:** `docs/NEXUS_PHASE12_PROTOCOL.md`, including the development record.
- **Raw data:** `artifacts/agi12_eval/` (suite1 / suite2 / dev rows and results) and `artifacts/agi12_freeze.json`.

**Question.** When several consistent programs fit the observations, can NEXUS construct a small valid input on which they disagree,
query a budgeted reference, falsify the contradicted ones, and beat Fixed and Random evidence selection under identical library,
synthesizer, abstention rule, query allowance and work caps?

## Answer

**The constructor works; the experiment's pre-registered verdict is "mixed", and NEXUS was not safer.**
- **Constructor:** every query NEXUS issued split the surviving candidates and falsified at least one. That was 8 / 8 and 9 / 9 on
  Suite 1 and 15 / 15 and 17 / 17 on Suite 2, against about 15–30 % for Fixed and 5–25 % for Random.
- **Primary Suite 1 result (B_q = 1):** NEXUS verified 4 / 24 in each stream, against Fixed 5 / 24 and Random 2–4 / 24. So
  NEXUS − Fixed = −1 and NEXUS − Random = +2 / 0, which is **mixed**. NEXUS made **9 wrong** submissions per stream against Fixed's
  6–7.

**The cause is upstream of the constructor.**
- In 11 of NEXUS's 18 Suite 1 wrong submissions (both streams), the synthesizer retained only **one** candidate, typically the
  passthrough or COUNT(\*) shape. The correct program (`coalesce(x, 0)`, `count(x)`) was not in the candidate set.
- With nothing to disagree with, the frozen NEXUS rule spends no query and submits.
- Fixed spends its static queries regardless. When one happens to contain the deciding case, it falsifies the lone candidate,
  synthesis resumes, and the right program can be found.
- **Active disambiguation can only choose among candidates the synthesizer produces.**

**Strongest arm:** Fixed with two static queries — 8 / 24 per stream with **2 wrong**.

## 1. Successor corrections (verified)

**1. Strict work caps.**
- Counters raise at the exact increment that would pass a cap (`synth12.CappedCounter`).
- **0 of 672 evaluation rows**, and 0 of 224 development rows, exceeded any cap. The maximum full checks was exactly 5,000.
- Phase 11 had 69 / 168 rows over cap.

**2. Exact provenance.** Scalar calls are recorded before inlining and identified by exact id, never by substring. Unit tests cover
F10 vs F1 and scalar provenance. Per-arm participation is given below.

**3. Separation.**
- Suite 1 was frozen in commit 1, before any tuning. It uses six mechanisms that are new to NEXUS: join default, duplicate-key semi
  join, null default, count of a nullable column, twin / tied window ordering, and left lookup join. Half the instances are
  compositions.
- Development used only Phase 11 families.
- Phase 11's W1–W8 development exposure is recorded in the protocol.

**4. Candidate retention.** The search keeps up to 8 distinct consistent programs, or stops 300 pops after the first acceptance, or
at the cap.

## 2. Suite 1 — Fresh_Ambiguous_Compositions_24 (one-use 121000–121023; 336 / 336 rows; 0 missing)

Verified / wrong / submitted per stream (rep0 | rep1):

| Arm | B_q = 1 | B_q = 2 | Query splits (both streams) |
|---|---|---|---|
| First-Match (diagnostic) | 3 / 7 / 10 \| 3 / 7 / 10 | — | — |
| Fixed | 5 / 6 / 11 \| 5 / 7 / 12 | **8 / 2 / 10 \| 8 / 2 / 10** | 7 / 28; 7 / 48 |
| Random | 2 / 8 / 10 \| 4 / 6 / 10 | 1 / 8 / 9 \| 3 / 6 / 9 | 6 / 28; 7 / 49 |
| **NEXUS** | 4 / 9 / 13 \| 4 / 9 / 13 | 4 / 9 / 13 \| 4 / 9 / 13 | **8 / 8; 9 / 9** |

**Pre-registered contrasts:**

| Contrast | B_q = 1 (rep0, rep1) | B_q = 2 (rep0, rep1) |
|---|---|---|
| NEXUS − Fixed | −1, −1 | −4, −4 |
| NEXUS − Random | +2, 0 | +3, +1 |

- **Verdict: mixed.** Positive needed ≥ +2 against both comparators in both streams.
- **Safety:** NEXUS's wrong count is higher than both comparators'.

**By mechanism** (rep0, B_q = 1, of 4):

| Mechanism | NEXUS | Fixed (B_q = 2) |
|---|---|---|
| M1 join default | 1 | 0 |
| M2 duplicate-key semi | 2 | 3 |
| M3 null default | 0 | 2 |
| M4 count column | 0 | 1 |
| M5 window twin | 0 | 0 |
| M6 lookup left | 1 | 2 |

- No consistent candidate at all was found for most composed instances (M1c, M5c, M4c, M2c, M6c), in every arm. That is a search-reach
  limit, not a disambiguation one.

**Causes of NEXUS's wrong submissions** (18 rows, both streams, B_q = 1):

| Cause | Rows |
|---|---|
| Single candidate, no query | 11 |
| Several candidates agreeing on every probe, no query | 4 |
| A survivor after queries that was still wrong (the right program was absent) | 3 |

**Retention plus abstention alone** (Fixed vs First-Match):

| Comparison | Verified | Wrong |
|---|---|---|
| Fixed B_q = 1 vs First-Match | +2 | 6–7 vs 7 |
| Fixed B_q = 2 vs First-Match | +5 | 2 vs 7 |

So static queries plus retention, falsification, resume and abstention cut wrong submissions sharply, and raised completions.

**Provenance** (verified submissions, both streams):

| Arm | Scalar learned | Relational learned |
|---|---|---|
| NEXUS | F6 × 1 | rep1-F10 × 1 (filter-eq) |
| Fixed B_q = 2 | F3 × 2, F6 × 1, rep1-F4 × 1 | the upsert (rep0-F4, rep1-F6) × 1 each; rep1-F10 × 1 |

Function ids are per-stream library names.

## 3. Suite 2 — Phase11_Regression_Audit_24 (diagnostic re-run of the consumed Phase 11 targets; 336 / 336 rows)

Verified / wrong / submitted per stream (rep0 | rep1):

| Arm | B_q = 1 | B_q = 2 | Query splits |
|---|---|---|---|
| First-Match | 7 / 3 / 10 \| 7 / 3 / 10 | — | — |
| Fixed | 5 / 1 / 6 \| 5 / 1 / 6 | 5 / 1 / 6 \| 5 / 2 / 7 | 6 / 24; 8 / 44 |
| Random | 4 / 0 / 4 \| 5 / 3 / 8 | same as B_q = 1 | 3 / 24; 3 / 46 |
| NEXUS | 6 / 3 / 9 \| 7 / 5 / 12 | 6 / 3 / 9 \| 8 / 4 / 12 | 15 / 15; 17 / 17 |

- **NEXUS − Fixed:** +1 / +2 (B_q = 1), +1 / +3 (B_q = 2).
- **NEXUS − Random:** +2 / +2 and +2 / +3.
- **T113018** is still **wrong** under First-Match, Fixed (B_q = 1) and NEXUS in both streams. Fixed at B_q = 2 abstained in both
  streams; Random abstained in rep0 and was wrong in rep1. The correct "latest row" program never entered the candidate set.
- **Caps:** 0 rows over cap (Phase 11: 69).
- **Provenance** (NEXUS verified, both streams): scalar F2 × 10, F5 × 4, F7 × 5; relational upsert × 4 (rep0-F4 × 2, rep1-F6 × 2).

## 4. Work and cost

- **Every row:** full checks ≤ 5,000, relational pops ≤ 1,000, micro-evaluations ≤ 150,000, constructed ASTs ≤ 400,000.
- **Mean full checks per row:** about 1,900–3,000.
- **Probe evaluations** (Suite 1, both streams):

| Arm | Probe evaluations |
|---|---|
| NEXUS B_q = 1 | 3,939 |
| NEXUS B_q = 2 | 5,221 |
| Random | 1,363–1,527 |
| Fixed | 270–483 |

- Shared candidate collection: one run per (task, stream) inside 70 % of the caps, charged in full to every arm.
- Wall per 48-row (task, stream) group set: about 26–57 s per arm-config.

## 5. What this establishes and what it does not

**Established:**
- **Inner-loop caps:** they are now strict (0 overruns).
- **Provenance:** exact, with scalar participation visible.
- **Constructor:** a generic distinguishing-input constructor, using only the candidates' own executions and a fixed mutation menu,
  finds hypothesis-splitting inputs whenever the candidates disagree. Every NEXUS query split and falsified.
- **Retention + falsification + abstention:** these reduce wrong submissions relative to first-match acceptance. Fixed B_q = 2 gave 2
  wrong vs First-Match's 7.

**Not established:**
- **No completion or safety gain on fresh mechanisms:** NEXUS did not beat Fixed on Suite 1.
- **The limiting factor is candidate-set completeness.** The synthesizer often retains near-duplicate variants of one shape
  (refinement keeps only 6 passing realisations per class) and misses the correct alternative.
- **The no-query rule:** the frozen NEXUS rule spends queries only when the candidates disagree, which is exactly wrong when the set
  is incomplete.
- **Agreement is not proof:** agreement of the found candidates under bounded search is an empirical check, and it failed in 15 of
  NEXUS's 18 Suite 1 wrong rows.

## 6. One next architectural question

Should the reference queries be used to test the current **leading hypothesis** against inputs designed to expose classes of
alternatives the synthesizer did not generate, instead of only arbitrating between generated candidates? Two parts:
- **Candidate diversity:** make the candidate set more diverse by retaining across distinct relational / scalar shapes, not
  realisations of one class.
- **Query rule:** let NEXUS query even with one candidate, using an input that maximises the structural edge cases its program
  touches (NULLs in the columns it reads, unmatched keys in its joins, duplicates in its partition keys).
- **Test:** a pre-registered comparison of that variant against Fixed B_q = 2, the strongest arm here.

## 7. Budget, ledger, protection, tests

- **Budget:** **about 215 of 1,500 s** (s1 2.1, s2 28.3, s3 178.4, s4 about 7 at the time of writing). The new grant only; no older
  surplus used.
- **Ledger:** `python scripts/agi12_ledger.py verify` passes, including the frozen Phase 11 and 10C–10G verifiers. The hash chain is
  intact.
- **Protection:** 0 violations; 2,993 frozen Phase 1–11 files unchanged; checkers v1–v5 match their pins; `main` is `d7ac8c5`.
- **Tests:** `tests/test_agi12.py` (9), `tests/test_agi11.py` (9) and `tests/test_checker_kernel.py` pass.
