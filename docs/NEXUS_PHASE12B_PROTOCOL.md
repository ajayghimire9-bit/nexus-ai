# NEXUS Phase 12B — pre-registered protocol (NOT LOCKED)

Committed **before** any Stage 2 diagnostic run and before `Fresh_Phase12B_24` opens.

## Revision, machine and budget

| Item | Value |
|---|---|
| Branch | `codex/nexus-data-engineering`, start `c8466f1`; `main` `d7ac8c5` untouched |
| Machine | Apple M4, CPython 3.13.5 |
| Runtime constraints | no external LLM API, no pretrained weights |

- **Grant:** `artifacts/agi12b_grant.json`, a **new 800 s** grant and hard cap. The Phase 12 remainder (1,284.8 s) is recorded and not
  consumed.
- **Ceilings:** s1 150, s2 180, s3 350, s4 120. No transfers.
- **Metering:** every execution runs through `scripts/agi12b_exec.py` (prefix `a12b-`).
- **Ledger:** `scripts/agi12b_ledger.py verify` runs the frozen Phase 12, 11 and 10C–10G verifiers plus a `phase12b` section.
- **Protection:** Phase 1–12 frozen (`artifacts/agi12b_protect_before.json`, 0 violations).

## The two toggleable changes (src/nexus/de_phase12b; everything else is Phase 12 code copied verbatim)

**Change A, `reopen`** (`synth12b`; default False reproduces Phase 12 exactly, unit-tested on a development task).

| Search step | Phase 12 | With `reopen` |
|---|---|---|
| Projection | an output matched by an input column was locked as a passthrough | the passthrough is still tried **first**; the pool is grown to band 5 (dedicated allowance of 6,000 micro-evaluations, still globally capped); up to 4 structurally diverse alternatives from that column's class that also fit are kept (one per top-level operator first) |
| Retention | a class at its 48-member cap dropped further members | a class at its cap still keeps up to 16 members of a **new** operator shape |
| Aggregation | `COUNT(*)` closed an output | `COUNT(*)` is still **first**; up to 4 diverse alternative aggregates that also fit are kept (e.g. `COUNT(col)`) |

- **Group MIN / MAX vs rank_window:** checked. No exclusion exists in the Phase 12 search; both come from different relational nodes
  and compete for candidate retention. Disclosed; nothing changed. T113018 is examined in Stage 2.
- **Unit tests:**
  - a null replacement is retained only with `reopen`, and the passthrough stays first;
  - `COUNT(col)` is retained only with `reopen`.

**Change B, `challenge`** (`disamb12b`; default False reproduces Phase 12).
- When query budget remains and the survivors are a **singleton or unanimous**, NEXUS issues a **shared-belief challenge query**.
- The input comes from the **existing** generic mutation generator (NULL / duplicate / copy / fresh / boundary / cross / drop, on the
  columns the candidates read): the draw with the most such mutations among 40.
- If any draw makes the candidates disagree, it becomes an ordinary splitting query.
- A contradiction falsifies the candidates. When every candidate is falsified, the example joins the observations and synthesis
  restarts, with `reopen` as configured.
- Unit test: a singleton gets no query without the flag and a challenge query with it.

## Arms (B_q = 2 primary)

All arms share the frozen Phase 11 Stage A library (rep0 / rep1), the candidate retention, the abstention rule, and caps of 5,000 full
checks, 1,000 pops, 150,000 micro-evaluations, 400,000 constructed ASTs and a 6 s wall.

| Arm | Selector | B_q | reopen (A) | challenge (B) |
|---|---|---|---|---|
| F2_base | fixed | 2 | F | — |
| N2_base | nexus | 2 | F | F |
| N2_challenge | nexus | 2 | F | T |
| F2_reopen | fixed | 2 | T | — |
| N2_both | nexus | 2 | T | T |
| R2_reopen | random | 2 | T | — |
| F1_reopen (diagnostic) | fixed | 1 | T | — |
| N1_both (diagnostic) | nexus | 1 | T | T |

- **Collections:** two shared collections per (task, stream), reopen False and True, each inside 70 % of every cap. Every row is
  charged its collection plus its own work.

## Suites

- **Stage 2 diagnostics** (opened suites; owner-requested; 5 attribution arms: F2_base, N2_base, N2_challenge, F2_reopen, N2_both):
  - **Phase12_Diagnostic_24:** all 24 Phase 12 Suite 1 tasks, tracking the 11 single-candidate wrong tasks and Q121014.
  - **Phase11_Diagnostic:** the Phase 11 tasks that were wrong in Phase 11 or 12: T113003, T113006, T113014, T113018, T113022.
- **Stage 3 primary, `Fresh_Phase12B_24`:** frozen in this commit (`manifest12b.fresh`, one-use 124000–124023, generator
  `tasks12b`). All 8 arms. Six mechanisms used in neither Phase 12's suite nor its development:

| Mechanism | Deciding case hidden from visible data |
|---|---|
| N1 SUM of unit quantities | quantities other than 1 |
| N2 per-parent SUM vs MAX | parents with several children |
| N4 UNION ALL vs upsert | overlapping keys |
| N6 dedup needed | repeated keys |
| N7 group-key twin | a twin column that stops matching |
| N8 invisible status filter | rows with another status |

- Instances 2–3 are compositions: an upsert source, a filter or a join.

## Pre-registered decision rules (Fresh_Phase12B_24, B_q = 2, per stream)

For each contrast:

| Verdict | Rule |
|---|---|
| Positive | ≥ +2 verified in **both** streams, with wrong ≤ the comparator's |
| Null | \|d\| ≤ 1 in both |
| Negative | ≤ −2 in both |
| Mixed | anything else |

- **Change B alone:** N2_challenge − N2_base and N2_challenge − F2_base.
- **Change A alone:** F2_reopen − F2_base.
- **Combined:** **N2_both − F2_base (primary)**, N2_both − F2_reopen and N2_both − R2_reopen.
- **Diagnostic:** N1_both − F1_reopen.

**Also reported:**
- queries on disagreeing vs singleton / unanimous sets;
- shared-belief falsifications (every candidate contradicted, so synthesis restarts);
- post-falsification recoveries and the learned functions reused in them;
- 0-overrun cap compliance;
- full checks, probe evaluations and wall.

Two streams sharing targets are not independent replications. No retro-adoption, no rerun of a written row, no reuse of the one-use
range.

## Stage 2 diagnostic record and pre-opening resource amendment (commit 2; Fresh_Phase12B_24 not yet opened)

**Stage 2 diagnostic run** (owner-requested; opened suites; `a12b-s2-*`): it used the whole s2 ceiling (180.0 / 180 s) and is
**incomplete**.
- **Phase 12 suite:** chunks c0 and c5 hit their per-job time limit twice. 180 of 240 rows were written. Six tasks have no rows:
  Q121006, Q121011, Q121012, Q121017, Q121018, Q121023.
- **Phase 11 subset:** 47 of 50 rows; T113022 rep1 is missing 3 arms.
- No rerun; the s2 ceiling is spent. 0 rows over any cap.

**Phase 12's 11 single-candidate wrong (task, stream) pairs.** Q121011 (2 pairs) has no rows, so 9 pairs were evaluated:

| Arm | Verified | Pairs resolved |
|---|---|---|
| N2_base | 0 / 9 | — |
| N2_challenge (B alone) | 2 / 9 | Q121002 rep1, Q121005 rep1 |
| F2_reopen (A alone, Fixed selector) | 4 / 9 | Q121008 ×2, Q121014 ×2 (F2_base also verifies these) |
| N2_both (A + B) | 7 / 9 | Q121002 ×2, Q121005, Q121008 ×2, Q121014 ×2 |

- **Q121014:** verified by F2_base, F2_reopen and N2_both in both streams; still wrong under N2_base and N2_challenge.
- **Q121020:** unresolved.
- **T113018:** not resolved by any arm (N2_both: abstain rep0, wrong rep1).
- **Totals, Phase12_Diagnostic** (rows present; per stream rep0 | rep1):

| Arm | Verified | Wrong |
|---|---|---|
| F2_base | 7 \| 7 | 1 \| 1 |
| N2_base | 4 \| 4 | 7 \| 6 |
| N2_challenge | 3 \| 5 | 7 \| 3 |
| F2_reopen | 7 \| 6 | 0 \| 0 |
| N2_both | 6 \| 4 | 4 \| 4 |

**No code change to search, disambiguation, caps or arms follows from these diagnostics.**

**Resource amendment** (written before Fresh_Phase12B_24 opens; based only on Stage 2 timings):
- **The problem:** the Stage 2 cost (about 1 s per row; slow task-streams up to about 25 s) puts the full 384-row fresh grid near or
  over the 350 s s3 ceiling.
- **One job per task:** `run fresh i 24`, one task per job, each capped at **14 s** (24 × 14 = 336 s ≤ 350), so a slow task cannot
  starve later ones.
- **Arm order within a task:** the primary pair F2_base and N2_both comes first. Results do not depend on order: every arm has its own
  budget, clock and seeds.
- **Missing rows:** they count as not verified and not wrong (equivalent to abstaining). Every contrast is **also** reported on the
  tasks where both arms have a row (`paired_n`, `paired_diff`). The verdict uses the all-task numbers. If any primary-pair row is
  missing, the verdict is reported both ways.
- The freeze is refreshed (`artifacts/agi12b_freeze.json`) to hash the amended runner.
