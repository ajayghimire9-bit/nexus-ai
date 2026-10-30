# NEXUS Phase 12B — reopenable projection / aggregation commitments and challenging singleton or unanimous candidate sets (NOT LOCKED)

## Revisions and scope

| Item | Revision |
|---|---|
| Start | `c8466f1` |
| Commit 1: Fresh_Phase12B_24 frozen, Change A / B implemented, 7 unit tests, protocol, before any diagnostic | `f243a76` |
| Commit 2: Stage 2 diagnostics plus a pre-opening resource amendment, before the fresh suite opened | `7a3aa62` |
| `main` | `d7ac8c5`, untouched |

- **Machine:** Apple M4, CPython 3.13.5; no external LLM API, no pretrained weights.
- **Protocol:** `docs/NEXUS_PHASE12B_PROTOCOL.md`, including the amendment.
- **Raw data:** `artifacts/agi12b_eval/` (`{p12,p11,fresh}_c*.jsonl` and `*_result.json`) and `artifacts/agi12b_freeze.json`.

**Question.** Phase 12 found that NEXUS's wrong submissions came from candidate sets that were incomplete. A passthrough or
`COUNT(*)` locked a column, and NEXUS never queried a singleton or unanimous set. Phase 12B tests two changes:
- **Change A:** reopen those commitments.
- **Change B:** challenge singleton or unanimous sets with a query.

Can these, separately or together, beat the strongest Phase 12 arm (Fixed, B_q = 2) on fresh mechanisms?

## Answer

**No. On the fresh suite, neither change, nor both together, beat Fixed static evidence, and the NEXUS arms were clearly less safe.**

| Contrast (B_q = 2, per stream) | Verified diff rep0 / rep1 | Wrong (arm vs comparator) | Verdict |
|---|---|---|---|
| N2_challenge − N2_base (B alone) | 0 / 0 | 15 vs 16; 11 vs 13 | **null** |
| N2_challenge − F2_base | −3 / −3 | 15 vs 6; 11 vs 5 | **negative** |
| F2_reopen − F2_base (A alone) | +1 / +1 | 8 vs 6; 6 vs 5 | **null** |
| **N2_both − F2_base (primary)** | **0 / −1** | **12 vs 6; 11 vs 5** | **null** (and less safe) |
| N2_both − F2_reopen | −1 / −2 | 12 vs 8; 11 vs 6 | mixed |
| N2_both − R2_reopen | +2 / +2 | 12 vs 11; 11 vs 11 | mixed: rep0 wrong is above the comparator's |
| N1_both − F1_reopen (diagnostic, B_q = 1) | +1 / 0 | 10 vs 8; 11 vs 6 | null |

**On the opened Phase 12 suite (diagnostic), the two changes interact.**
- N2_both verified 7 of the 9 evaluated pairs that Phase 12 left as single-candidate wrong submissions, against 0 for N2_base and 2
  for B alone.
- The fresh suite does not replicate that as a gain over Fixed.

**Why the challenge query does not help: the query inputs, not the candidates, are now the bottleneck.**
- **Challenge queries:** NEXUS issued 110 across N2_both and N2_challenge, both streams. Only **17 (15 %)** contradicted anything,
  and every one of those 17 contradicted **all** candidates (a shared-belief falsification).
- **Fixed static evidence:** 25 of its 58 queries (43 %) falsified at least one candidate. By the generator's construction, those
  batches contain the deciding case about half the time.
- **Why the generator misses:** NEXUS's generic generator resamples observed rows and mutates them (NULL / duplicate / copy / fresh /
  boundary / cross / drop). It rarely produces what these mechanisms hide: quantities other than 1, parents with several children,
  overlapping upsert keys, repeated keys, a twin column that breaks.
- **Result:** the challenge mostly confirmed a wrong belief. Of N2_both's 23 wrong submissions, **15** came after queries that
  falsified nothing. The other 8 came after a restart that still ended wrong.

## 1. What was changed (src/nexus/de_phase12b; everything else is Phase 12 code)

**Change A, `reopen`** (`synth12b`).

| Search step | With `reopen` |
|---|---|
| Projection | the passthrough is still tried **first**; up to 4 structurally diverse alternatives from the same observational class that also fit are kept (one per top-level operator first) |
| Aggregation | `COUNT(*)` is still **first**; diverse alternative aggregates that also fit are kept |
| Class retention | a class at its member cap still keeps up to 16 members of a **new** operator shape |

- **Default flags:** `reopen=False` reproduces Phase 12's candidates exactly (unit test).
- **Measured effect** (46 fresh task-streams with rows, 12 of them with no candidate in either setting): with `reopen`, 30 reached
  the 8-candidate retention limit. Without it, 23 had exactly one candidate.
- **Group MIN / MAX vs rank_window:** checked. No such exclusion exists in the Phase 12 search; both come from separate relational
  nodes. Disclosed, unchanged.

**Change B, `challenge`** (`disamb12b`).
- With query budget left and a singleton or unanimous survivor set, NEXUS queries an input from the **existing** mutation generator:
  the most mutations on the columns the candidates read, out of 40 admissible draws.
- If a draw splits the candidates, it becomes an ordinary splitting query.
- If every candidate is contradicted, the example joins the observations and synthesis restarts.
- Neither change uses a mechanism-specific detector.

## 2. Stage 2 — diagnostics on opened suites (owner-requested; not one-use evaluations)

**Coverage: incomplete.** The s2 ceiling (180 / 180 s) was spent with two chunk timeouts and one resume.

| Suite | Rows written | Missing |
|---|---|---|
| Phase12_Diagnostic_24 | 180 / 240 | 6 tasks (Q121006, Q121011, Q121012, Q121017, Q121018, Q121023) |
| Phase11_Diagnostic | 47 / 50 | T113022 rep1, 3 arms |

No rows were rerun.

**Phase 12 Suite 1** (rows present; verified / wrong per stream, rep0 | rep1):

| Arm | Verified | Wrong |
|---|---|---|
| F2_base | 7 \| 7 | 1 \| 1 |
| N2_base | 4 \| 4 | 7 \| 6 |
| N2_challenge | 3 \| 5 | 7 \| 3 |
| F2_reopen | 7 \| 6 | 0 \| 0 |
| N2_both | 6 \| 4 | 4 \| 4 |

**Phase 12's 11 single-candidate wrong (task, stream) pairs.** Q121011 ×2 was not reached; of the 9 evaluated:

| Arm | Resolved | Which |
|---|---|---|
| A alone (F2_reopen) | 4 | Q121008 ×2, Q121014 ×2; F2_base also verifies all four |
| B alone (N2_challenge) | 2 | Q121002 rep1, Q121005 rep1 |
| **A + B (N2_both)** | **7** | Q121002 ×2, Q121005, Q121008 ×2, Q121014 ×2 |

- Q121020 stays unresolved.
- **Q121014** is resolved by A + B in both streams. Under B alone it stays wrong.
- **T113018** is not resolved by any arm (N2_both: abstain in rep0, wrong in rep1). The correct "latest row" program is still not
  generated.
- **Phase 11 subset** (T113003 / 006 / 014 / 018 / 022): every arm verified 0–1 per stream. N2_challenge and N2_both cut N2_base's
  wrong count (rep0: 4 → 0 and 1).

## 3. Stage 3 — Fresh_Phase12B_24 (one-use 124000–124023; frozen in commit 1)

- **Coverage:** **368 / 384 rows.** The 14 s per-task jobs for tasks t13, t17 and t23 timed out in stream rep1, so 16 rows are missing:
  - Z124013 rep1: N1_both;
  - Z124017 rep1: 7 arms (everything but F2_base);
  - Z124023 rep1: all 8 arms.
- **Primary pair on paired tasks** (rep1, 22 tasks): N2_both − F2_base = −1, wrong 11 vs 4. The verdict is the same either way.
- **0 rows over any cap.**

Verified / wrong / submitted / abstain per stream (rep0 | rep1):

| Arm | rep0 | rep1 |
|---|---|---|
| F2_base | 5 / 6 / 11 / 13 | 5 / 5 / 10 / 13 |
| N2_base | 2 / 16 / 18 / 6 | 2 / 13 / 15 / 7 |
| N2_challenge | 2 / 15 / 17 / 7 | 2 / 11 / 13 / 9 |
| F2_reopen | **6** / 8 / 14 / 10 | **6** / 6 / 12 / 10 |
| N2_both | 5 / 12 / 17 / 7 | 4 / 11 / 15 / 7 |
| R2_reopen | 3 / 11 / 14 / 10 | 2 / 11 / 13 / 9 |
| F1_reopen | 4 / 8 / 12 / 12 | 4 / 6 / 10 / 12 |
| N1_both | 5 / 10 / 15 / 9 | 4 / 11 / 15 / 6 |

**By mechanism** (rep0, verified of 4):

| Mechanism | F2_base | F2_reopen | N2_both |
|---|---|---|---|
| N1 SUM of unit quantities | 1 | 2 | 2 |
| N2 per-parent SUM vs MAX | 1 | 1 | 0 |
| N4 UNION ALL vs upsert | 0 | 0 | 0 |
| N6 dedup needed | 0 | 0 | 0 |
| N7 group twin | 2 | 2 | 2 |
| N8 hidden filter | 1 | 1 | 1 |

N4 and N6 were 0 / 8 in every arm.

**Gains and losses, N2_both vs F2_base:**
- Gains: Z124000 (N1, both streams) and Z124011 (N8, rep0).
- Losses: Z124001 (N2) and Z124005 (N8), both streams.

**Queries** (both streams):

| Arm | Queries on disagreeing sets | Queries on singleton / unanimous sets | Challenge queries | Shared-belief falsifications | Recovered after restart |
|---|---|---|---|---|---|
| N2_both | 7 | 59 | 59 | 12 | 1 |
| N2_challenge | 13 | 51 | 51 | 8 | 0 |
| N2_base | 13 | 0 | 0 | 2 | 0 |

- Fixed and Random query unconditionally, so their "unanimous" counts are not decisions.
- **Recovery after falsification is rare:**
  - **N2_both:** 1 verified recovery after 12 restarts. That submission used no learned scalar or relational function.
  - **Fixed:** in F2_base / F2_reopen rep1, the recoveries reused the learned relational filter function rep1-F10.

**Work** (both streams):

| Arm | Probe evaluations | Mean full checks per row |
|---|---|---|
| N2_both | about 55,000 | about 2,500 |
| Fixed | about 630 | about 2,250 |

- The maximum full-check count was exactly 5,000. No counter passed its cap.

## 4. What this establishes and what it does not

**Established:**
- **Change A:** reopening passthrough / `COUNT(*)` commitments and shape-diverse retention make the candidate sets much larger and
  more varied. The flags are toggleable, and the defaults reproduce Phase 12. On the opened Phase 12 suite, A + B resolved 7 of 9
  evaluated former single-candidate failures.
- **Change B, as implemented:** challenging a singleton or unanimous set with a generic mutation of the observed rows rarely exposes
  the hidden case. Only 15 % of challenge queries contradicted anything. Stacking more candidates does not help if the evidence never
  touches the case that tells them apart.
- **Safety:** all NEXUS arms submitted many more wrong answers than Fixed (11–16 vs 5–6 per stream). The bounded-agreement submit rule
  is not a safety mechanism.
- **Caps and seeds:** strict caps held (0 over-cap rows), and the one-use range was claimed once.

**Not established:**
- No completion or safety gain on fresh mechanisms, from either change or both.
- The Phase 12 suite diagnostic gain did not transfer. It was measured on an already-opened suite with incomplete coverage.
- N4 (upsert vs UNION ALL) and N6 (dedup needed) are beyond the current search and evidence in every arm.
- The two streams share targets, so they are not independent replications. Stage 2 coverage was incomplete (6 Phase 12 tasks not
  reached).

## 5. One next experiment

**Make the queried input able to reach values the observed rows never contain.**
- Today the generator resamples observed rows. Instead, derive what a challenge input changes from the **leading program's own
  structure**: multiplicities, so that a group or join key repeats and an aggregate sees several rows; key overlap between the
  sources of a union; and values that break a column equivalence the program relies on.
- **Comparison:** pre-register that generator change (Change B′) against F2_base at B_q = 2 on a fresh suite, with
  `reopen` held on.
- **Safety gate:** submitting requires that the challenge query has falsified at least once or that the query budget is spent;
  otherwise abstain. This targets the wrong-submission gap, which is the clearest failure here.

## 6. Budget, ledger, protection, tests

**Budget:** **about 340 of 800 s** (new grant only; Phase 12's 1,284.8 s remainder not consumed).

| Stage | Used / ceiling |
|---|---|
| s1 | 5 / 150 s |
| s2 | 180 / 180 s (ceiling reached; diagnostics incomplete) |
| s3 | 146 / 350 s |
| s4 | about 10 / 120 s |

- **Ledger:** `python scripts/agi12b_ledger.py verify` passes, including the frozen Phase 12, Phase 11 and 10C–10G verifiers. The
  hash chain is intact.
- **Protection:** `artifacts/agi12b_protect_after.json` shows 0 violations, frozen Phase 1–12 files unchanged, checkers v1–v5 matching
  their pins, and `main` at `d7ac8c5`.
- **Tests:** `tests/test_agi12b.py` (7), `tests/test_agi12.py` (9) and `tests/test_checker_kernel.py` pass (20 total).
