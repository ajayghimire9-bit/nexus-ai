# NEXUS Phase 10C (revised) — pre-registered protocol (NOT LOCKED)

Committed **before** any Stage 2 training outcome and before either evaluation draw is opened. Branch
`codex/nexus-data-engineering`; start revision `34c1109`; `main` = `d7ac8c5` (untouched).

## Budget

The grant is recorded in `artifacts/agi10c_grant.json`. The owner's revised instruction replaced the original Phase 10C
instruction:

- **Grant:** +1,600 s instead of +1,500 s; one phase, one grant.
- **Hard cap:** 1,800 charged seconds, unchanged.
- **Carried charges:** the 286 s charged under `a10c-` before the revision count against the cap; nothing is reset.
- **Allocation file:** `artifacts/agi10c_allocation.json`.
- **Stage ceilings:** s1 200, s2 750, s3 300, s4 400, s5 150.
- **Transfers:** none. The revised instruction names none.

Stage 1 closed at 193.5 / 200 s. The X2 fix re-check therefore ran under Stage 2 as a pre-evaluation check.

## Stage 1 results already obtained (development data)

**Forensic audit** of the 13 Phase 10B held-out targets unsolved in every arm (`artifacts/agi10c_audit.json`):

- **Abstentions and language gaps:** 0 undecided-requirement abstentions; 0 out-of-language targets.
- **Primary cause:** 7 search-depth exhaustion (witness depth ≥ 4); 5 monolithic macro; 1 other.
- **Monolithic macros overall:** in 10 of the 13, bound library paths made stage-local progress but never passed all
  checks.
- **Work budget:** all 13 exhausted it.
- **Ranker zeroing:** 0 under a strict measure, which is weak because operator tokens are always known.

**X2 training verifier slip** (Phase 10B rep1, task 22, P6.X2 seed 88021) and the same defect on dev target 91940 (H5):

- **What went wrong:** a decision point was resolved although its options had the same end-to-end effect on the
  candidate (`['excluded', 'excluded']`). The boundary was shadowed, or the probe row never reached the output. So the
  requirement was never tested on the candidate.
- **X2 consequence:** the documented effect was mapped to the first matching option, `le`, where the truth is `lt`.
- **Fix:** `src/nexus/de_phase10c/fixes10c.py`. A submission is refused while such a decision point exists. It applies
  in every Phase 10C arm and during training.
- **Verification:** both cases now abstain (`artifacts/agi10c_dev/diag_*_fixed.json`).
- **Memory pollution in Phase 10B rep1:** none.

| Memory component | Entries from the wrong X2 repair |
|---|---|
| Skill sources | 0 |
| Ranker pairs | 0 |
| Trust records | 0 |
| P* hypotheses | 0 |
| Library support | 0 |
| P* boundary-witness log (feeds no learner) | 1 |

**Log reconciliation** (`artifacts/agi10c_reconcile.json`, from the raw logs):

- **Phase 10 main lineage:** 26 candidates and 16 promoted. **7** of the 16 (not 9 as reported) have partial-program
  support; none rely on partials alone.
- **Phase 10B:** 5 promoted in rep0 and 3 in rep1, of which 3 and 2 have partial support. Each repetition has 1
  multi-step method. Valley-crossing: 0 in rep0, 1 in rep1.
- **"197 → 85" runs:** from **2** P6 screen projects (205 → 85, 189 → 85; mean 197 → 85), not 4. The other 14 screen
  projects: the library cost +5 runs typically (X1 +20), with 0 completion changes.

**Numeric random streams** (`src/nexus/de_phase10c/rng10c.py`):

- Every Phase 10C seed comes from integer tuples (repetition, step, task).
- Tests show that renaming a learner or clone leaves ranker samples, train / validation splits and dream / admission
  streams byte-identical (`tests/test_agi10c.py`).
- The Phase 10 / 10B name-seeded calls remain in their frozen files and are not used by Phase 10C.

## Stage 2 — matched 2×2 on deliberately withheld compositions

**Fault mechanisms.** The world6 mechanisms are window, dup_id, latest, tombstone, parse, fanout, normalize, watermark,
checkpoint, replay, require, pit and ratio.

**Training families.** Training, dreams and macro / ranker admission use only these families:

| Family | Stages | Mechanisms seen together |
|---|---|---|
| P1–P7 | one stage each | that paradigm's own mechanisms |
| X1 | P3 → P2 | parse with latest / tombstone |
| X2 | P7 → P6 | pit / ratio with require / normalize |

These families allow exactly 14 co-occurring mechanism pairs (`manifest10c.TRAIN_MECH_PAIRS`).

**Withheld composition families.** All six are absent from training, dreams and admission:

| Family | Stages |
|---|---|
| H1 | P2 → P1 |
| H2 | P3 → P7 |
| H3 | P5 → P6 |
| H4 | P1 → P4 |
| H5 | P1 → P3 → P6 |
| H6 | P5 → P4 → P7 |

- **Withheld-pair guarantee:** each family has a stage pair whose cross pairs are all absent from training, and every
  stage carries at least one fault. So every built target contains at least one deliberately withheld pair (F_i, F_j),
  and each of F_i and F_j is trained separately.
- **Logged per row:** the realised withheld pairs.
- **Leakage check:** `manifest10c.leakage()` checks all 2,000 training / dream / admission specs of both streams; it
  finds 0 violations.

**Held fixed in every arm:**

- **Trust:** the frozen Phase 10B rep0 final trust state, never updated.
- **Procedure:** F0.
- **Learner hyperparameters:** M0; no improver round in Stage 2.
- **Bridge machinery:** search10c — zero-gain bridges, slots (2, 5, 8), K = 3, M = 5, with an order score from the arm's
  guide.
- **Shared fixes:** fixes10b and fixes10c.
- **Search budget:** 1,500 executions and a 4 s wall cap per search, identical in training, admission and every arm.
- **Method queue:** none in any arm.

**The four arms:**

| Arm | Guidance | Library |
|---|---|---|
| A1 | fixed | L0 |
| A2_r | learned G_L0 | L0 |
| A3_r | fixed (bound macros first, capped at 8) | L0 ∪ L*_r |
| A4_r | learned G_L* | L0 ∪ L*_r |

- G_L0 is trained on primitive step pairs.
- G_L* is trained on the same traces rewritten over L0 ∪ L*.
- Macros are atomic children at every node, with stage-local residual-symptom preconditions.
- Macro admission requires modular sub-problem progress on a leave-one-paradigm-out project, plus no lost completion
  and no added wrong submission.
- Tokens carry no paradigm, family, column-name or absolute stage-index feature.

**Two training streams × two separate draws.**

- **Streams:** rep0 and rep1, numeric-seeded, each capped at 175 s; checkpoints N = 15 / 30 / 60. N3 is the number of
  tasks reached within the cap, disclosed.
- **Draw A** (96000–96015) evaluates stream rep0; **Draw B** (96050–96065) evaluates stream rep1.
- **Each draw:** 6 ordinary repairs (P1 sqlite, P2 duckdb, P5 sqlite, P7 duckdb, X1, X2; held-out-name repositories) and
  10 withheld (H1–H4 twice each, H5 and H6 once each). All use documented requirements.
- **A1** runs on both draws.
- **Learning curve:** A4_r at N15 and N30 on the 10 withheld targets; N0 = A1 and N3 = A4_r.
- **Errors:** training errors (wake wrong submissions) and evaluation errors are reported separately.

**Decision rules (per replication = stream r on its draw):**

- **L\* replicated positive:** in both replications, on the withheld targets, A3 − A1 ≥ +2 **and** A4 − A2 ≥ +2, with 0
  evaluation wrong in A3 / A4.
- **L\* replicated null:** in both replications, |A3 − A1| ≤ 1 and |A4 − A2| ≤ 1.
- **Otherwise:** mixed / inconclusive.
- **G_learned:** the same rules with A2 − A1 and A4 − A3.
- **Joint requirement:** withheld targets solved by A4 but by none of A1–A3, counted per draw.
- **Ordinary non-regression:** A4 loses at most 1 ordinary target versus A1 per draw.
- **Sign-flip p-values:** reported as descriptions only. With 10 withheld targets per draw no single replication is
  decisive.
- **No retro-adoption, and no rerun of written rows.**

## Stage 3 — external development audit (≤ 300 s)

- **Task pack:** 12–16 tasks constructed from public real-world SQL / dbt / DataFrame patterns, such as the dbt
  jaffle_shop schema, Debezium envelopes, QUALIFY / MERGE, dialect casts and multi-table joins with dirty keys. They are
  written offline from public knowledge; nothing is downloaded. The tasks are not evaluation data and train nothing.
- **Procedure:** each task goes through NEXUS's real ingestion (`ir6.lift` in the task's dialect), the arena's
  single-table project model and, where it lifts, repair search.
- **Classification:** every failure goes into exactly one class:
  1. ingestion / parser / dialect;
  2. specification / grounding;
  3. primitive / expressiveness;
  4. search horizon / ranking;
  5. verifier.
- **Code timing:** the code is committed before the audit runs.

## Stage 4 — shared-stream improver test (≤ 400 s; only after Stage 2 is scored)

1. **Clone round.** From the rep0 N30 checkpoint, run M0 and M′ on identical numeric streams. M′ is one field from
   `lineage10c.SPACE`, drawn by `rng(4, 0, 0)`. Each clone runs the same wake tasks, sleeps, dreams, admission projects
   and splits. A same-M identity check runs first: two clones with identical M and different names must give
   byte-identical trajectories. M′ is adopted iff it verifies strictly more of a common validation set built for both
   clones, with ≥ 1 verified and no more wrong submissions.
2. **Downstream confirmation.** Fresh learners with M_selected and with the rejected alternative are trained on a common
   separate stream. They are evaluated with the A4 configuration on **Draw C** (96080–96091; 12 targets, 4 ordinary +
   8 withheld; unopened).
3. **Discovery-cost accounting.** The clone-round seconds are charged to M_selected. The report gives the verified
   difference on Draw C and the discovery seconds per extra completion. If M′ is not adopted, the same downstream run
   tests whether the rejection was correct.
4. **Code timing:** the code is committed before the run.

## Deliverables

- **Commit 1 (this one):** the reconciliation, the fix, the RNG test, the withheld-composition manifest and draws, the
  code and this protocol.
- **Commit 2:** `docs/NEXUS_PHASE10C_AUDIT_AND_COMPOSITIONAL_REPORT.md` and the capability register (NOT LOCKED), with
  exact counts only and no capability percentages, pushed to origin and github.
