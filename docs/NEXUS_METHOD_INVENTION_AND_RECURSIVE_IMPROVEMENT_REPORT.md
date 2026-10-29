# NEXUS MI-2 — Method Invention and One Step of Recursive Improvement

Status: NOT LOCKED (exploration workflow; validation and confirmation one-use). Branch `codex/nexus-data-engineering`,
starting revision `8b5582d` (verified HEAD; github and origin both at `8b5582d` after the origin push that had failed with
HTTP 403 succeeded on retry at the start of this round).

Claim under test, as two separately evaluated milestones:

* **Milestone A**: a NEXUS-generated learning procedure improves learning on untouched task families.
* **Milestone B**: using that procedure inside the improver produces better subsequent improvements than keeping the original
  improver, under equal compute.

A positive A does not establish B.

## 0. Pre-registration (committed before any discovery run)

### 0.1 State, protection, budget

* Audit at `8b5582d`:
  * working tree clean, no active workers;
  * 912 protected files, 157 ba, 74 oc and 390 frozen sc files unchanged;
  * pinned checkers v1–v5 unchanged (`tests/test_checker_kernel.py`);
  * frozen X7 and MI-1 code and results untouched; `main` and `final_sealed` untouched.
* Budget: the existing carried balance only, with no new grant. 29,244 s were verified at `8b5582d`; after the development
  diagnosis 28,996 s remain. CPU only, ≤ 900 s per call (`scripts/mi_exec.py`, run ids `mi-2-*`).
* Allocation (s):

  | stage | allocation |
  |---|---|
  | development / diagnosis / pool cache | 1,000 |
  | discovery (7 lineages × 1,200 CPU s) | 8,400 |
  | selection | 900 |
  | validation | 3,200 |
  | confirmation | 4,500 |
  | Milestone B | 6,500 |
  | ablation / analysis | 800 |
  | reserve | ≥ 3,000 |
* Previous results stay as reported:
  * **MI-1** failed its validation gate (19/60 vs 10/60; needed +10, got +9). Its procedure stays experimental and its
    confirmation stays closed. MI-1's unused `mi/test` range is not used by MI-2.
  * The evidence-derived constant primitive (`dconsts`) was **human supplied**; NEXUS generated only its composition with other
    operations.
  * **X7** expression mapping is supported, but its full-system result remains 15/16 with one silent error (13495, A stream).
    That defect is separate from this experiment and not addressed here.

### 0.2 Development diagnosis: why SUBH was unsolved, and headroom (`artifacts/mi2_dev/diag.jsonl`, mi2/diag only)

Setup: 18 dev episodes (MUL, ADDC and SUBH × 6) on which the shared fast path does not accept, each with a 20 s CPU cap:

| procedure | MUL | ADDC | SUBH | mean CPU s |
|---|---|---|---|---|
| baseline (GRAMMAR5) | 0/6 | 0/6 | 0/6 | 1.6 |
| witness_end (GRAMMAR5 + the episode's true updates appended) | 6/6 | 6/6 | 6/6 | 0.07 |
| witness_front (true updates first) | 6/6 | 6/6 | 6/6 | 0.06 |
| witness_min (identity + true updates only) | 6/6 | 6/6 | 6/6 | 0.05 |
| MI-1 procedure | 1/6 | 3/6 | 0/6 | 4.1 |
| MI-1 direct control | 5/6 | 5/6 | 2/6 | 6.1 |

Diagnosis:

* **SUBH failure = missing expressiveness.** `acc − x/2` is absent from every tested procedure's space: GRAMMAR5 has no division
  and no 2; MI-1's procedure divides only by 0 and 1; the direct control truncates its 3,000-expression space before it.
* **Not hypothesis ordering.** Appended witnesses solve as fast as front-placed ones.
* **Not assignment-search exhaustion.** Witness solves take ≤ 0.3 s. The direct control's SUBH time-outs come from its
  3,000-expression space.
* **Not insufficient evidence.** The minimal witness space solves every episode with the same oracle budget.
* **Headroom:** 18/18 (100 %) of failing dev episodes are solvable by the unchanged engine given the right space.

Witness domains are refused by the discovery machinery and are never shown to candidates.

Runtime calibration:

* 14 of 16 non-witness successful solves needed ≤ 1.3 s CPU; two direct-control solves in 3,000-expression spaces took 7.7 s
  and 11.3 s.
* **Discovery and selection cap: 3 s CPU per episode.** This keeps compact informative candidates scoreable and charges huge
  spaces their cost.
* **Validation and confirmation cap: 15 s CPU per episode, identical for every arm** (primary endpoint). An "exact within 3 s"
  curve is derived from the same rows (a run under 3 s is identical under either cap).
* Caps count process CPU (ITIMER_PROF), not wall time.

### 0.3 Editable component, language, attribution

* **Editable:** the register-hypothesis procedure (an LPL program, `src/nexus/mi_lpl.py`, frozen with MI-1), run inside the
  unchanged learner (`src/nexus/mi2_learner.py`: same fast path, assignment engine, control learning, coverage, bounded
  acceptance).
* **Outside the editable surface:** checker kernels, episode generator (`mi_ocean`), oracle, held-out evaluator, acceptance
  check, meters.
* **Human supplied (Claude):** the LPL statements and interpreter, including the `dconsts` constant miners; the generic random
  generator, mutation and crossover; the seed (a verified transcription of GRAMMAR5); the fitness, schedule and selection rules;
  A5; and the B call site `mi2_lpl.mutate_lib`.
* **No external model** proposes candidates. Once a discovery search starts, no human or Claude edit to any candidate.

### 0.4 Milestone A arms

| arm | procedure | discovery |
|---|---|---|
| A0 | original strongest learner (GRAMMAR5 inside the x7 learner) | none |
| A1 | MI-1's frozen generated procedure (`artifacts/mi_dev/select_evolve.json`) | (MI-1, sunk) |
| A2 | new evolution-guided discovery (`evolve`), lineages L1–L3 | 1,200 CPU s each |
| A3 | random structural search, same language / primitives / evidence access, lineages L1–L3 | 1,200 CPU s each |
| A4 | parameter tuning, **restricted space**: closure of {acc, x, 0..k} under {+, −} with size bound ∈ {3, 5, 7}, k ∈ {1, 2, 3, 5, 10}, register-search seconds ∈ {4, 60} (30 configs); no new operator, no evidence access | ≤ 1,200 CPU s (finite grid, may stop early) |
| A5 | human-written evidence-aware procedure (`mi2_learner.A5_PROG`, frozen now) | none |
| A6 | generic direct synthesis: bottom-up, smallest-first, all four operators over {acc, x, 0..10, mined constants}, conditionals, signature dedupe, cap 3,000 (`mi2_learner.a6_domain`) | none |

A5 in detail:

* terms {acc, x}; constants 0, 1, 2 plus every `dconsts` miner;
* one layer of all four operators (variable-bearing results only);
* one further additive (+ / −) layer over a variable;
* deduplicated, smallest first (333 expressions on a typical context).

A5 disclosure: the literal 2 was chosen after the diagnosis above. Its author (Claude) knows the withheld family definitions.
By its generic additive layer A5 also contains SCL's `acc·c + x` (c = 2, or a mined c), but not AVG or MAX.

Discovery (dev only, `scripts/mi2_discover.py`):

* **Pools:** fast-path failures from fresh dev seeds, family balanced. Discovery pool: MUL / ADDC / SUBH × 20 = 60 episodes
  (`mi2/disc`). Selection pool: × 10 = 30 (`mi2/sel`).
* **Fitness (lexicographic, frozen):** (exact episodes; mean fraction of register searches solved; −CPU).
  * The second term is learner-side partial credit, recorded separately; its relation to exactness is reported.
  * Per-family exact counts are recorded; no per-family minimum is imposed.
* **CPU matching:** every lineage gets the same evaluation-CPU budget (1,200 s), failed and degenerate candidates included.
  Candidate counts are reported, not matched. The downstream task budget (cap, oracle, acceptance) is identical for all arms.
* **Selection within a lineage:** the top 3 by fitness re-scored on the selection pool.
* **Arm representative:** the lineage winner with the best selection score. The other lineage winners are evaluated as
  replication evidence (A2_L*, A3_L*).

### 0.5 Milestone A validation, confirmation, decision rules (`scripts/mi2_score.py`)

* **Validation** (`mi2/val`, one-use; 110 fresh episodes: K 20, MUL / ADDC / SUBH × 30; all arms).
  * Primary comparisons: A2 vs each of the six decisive controls A0, A1, A3, A4, A5, A6, on the 90 dev-unfamiliar episodes,
    exact within the 15 s cap.
  * Gate (all required, no revision):
    * **G1** exact(A2) − exact(c) ≥ 6 for every c (practical threshold ≈ 6.7 pp);
    * **G2** exact one-sided sign test on discordant episodes p ≤ 0.05/6 for every c (Bonferroni over six comparisons);
    * **G3** silent(A2) ≤ silent(A0) (no increase in wrong accepted outputs);
    * **G4** K exact(A2) ≥ K exact(A0) − 1.
* **Confirmation** (only if the gate passes; `mi2/test`, one-use; 210 fresh episodes: K 30, MUL / ADDC / SUBH × 20,
  **withheld** SCL / AVG / MAX × 40).
  * Same comparisons on the 120 withheld-family episodes, G1 threshold ≥ 8, G2 as above.
  * G3 on all 210 episodes; G4 K ≥ A0 − 2.
  * A pass writes `artifacts/mi2_accepted.json`.
* **Exposure audit:**
  * SCL / AVG / MAX were fixed in MI-1's pre-registration (`8ea5746`) and no learner, discovery or selection run has ever
    executed on them.
  * Their definitions are known to the experimenter who wrote the language and A5.
  * Dev-family test episodes are fresh instances of discovery-exposed families.
* **Fully loaded cost** reported per arm: fast path + full space + checking + amortised discovery CPU, failed candidates
  included.
* **If validation fails:** Milestone A is reported negative or inconclusive and the confirmation stays closed.

### 0.6 Milestone B (pre-registered now, before any Milestone A outcome)

* **Call-site audit.**
  * The existing improver (`mi_discover` / `mi2_discover`: propose → evaluate → select) **never invokes a learned procedure**.
    Candidates are only scored, and proposals come from fixed generic operators. That is the architectural gap.
  * Connection implemented and tested (`src/nexus/mi2_lpl.py`, `mutate_lib`). The improver's mutation call site can insert
    1–4-statement blocks copied from a library of accepted machine-generated procedures (probability 0.3).
  * With an empty library it is exactly the original operator (tested for identical outputs under identical RNG states).
* **Branches from an identical checkpoint:**
  * **B0** = original improver (evolve, empty library).
  * **B1** = the same improver with `mutate_lib` and library = the procedure accepted by Milestone A's confirmation
    (`artifacts/mi2_accepted.json`, written only by the scorer).
  * Both start from an identical archive (seed + the same 2 random programs; shared RNG streams per pair), with the same
    language, task access, evaluator, acceptance checks and 1,200 CPU s per lineage.
* **Next discovery problem:** the families no Milestone-A procedure was discovered or selected on (SCL / AVG / MAX).
  * Pools from `mi2/bdev` (fast-path failures; 45 discovery, 30 selection).
  * Opened only after Milestone A's confirmation passes (enforced in code).
* **Paired seeds** L1 and L2. Each branch's descendant is frozen by the same selection rule, then evaluated once on
  `mi2/btest`: 140 fresh episodes (K 20, SCL / AVG / MAX × 30, MUL / ADDC / SUBH × 10), untouched by A.
  * Arms: B0_L1, B0_L2, B1_L1, B1_L2, BA (the accepted procedure unchanged), A0.
  * Exposure label: SCL / AVG / MAX are discovery-exposed in B; btest uses fresh instances.
* **Positive B iff all of:**
  * for both pairs, exact(B1) − exact(B0) ≥ 5 on the 90 SCL / AVG / MAX episodes;
  * pooled paired sign test p ≤ 0.05;
  * the better B1 descendant beats BA by ≥ 5 (an actual further improvement, not a redeployed solver);
  * silent(B1) ≤ silent(B0);
  * K retention ≥ A0 − 1.
* **Also reported:** improvement yield per CPU (candidates exceeding the lineage's starting best) and discovery cost and
  amortisation.
* **Precondition:** B runs only if A passes confirmation and the remaining budget covers B's allocation. Otherwise the precise
  reason is reported.
