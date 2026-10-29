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

## 1. Results: Milestone A NEGATIVE (validation gate failed), confirmation closed, Milestone B not run

| stage | commit | outcome |
|---|---|---|
| pre-registration + implementation + dev diagnosis | `1585ed2` | as §0 |
| discovery + selection (dev) | `68cb401` | evolve weakest of the search arms |
| freeze | `52ea81b` | A2 = evolve L3, A3 = random_struct L3, A4 = params L1 |
| **validation** (mi2/val, one-use, run once) | this commit | **gate failed** (G1, G2, G3 fail; G4 passes) |
| confirmation (mi2/test, withheld SCL / AVG / MAX) | — | **not run**: closed by the failed gate; seeds unclaimed |
| Milestone B | — | **not run**: no procedure passed Milestone A, so no accepted procedure exists for the call site |

### 1.1 Discovery (dev, CPU-matched lineages; `artifacts/mi2_dev/summary_a.json`)

| lineage | candidates | eval CPU s | best on 60-episode pool (MUL / ADDC / SUBH) | improvements over running best | selection winner on 30-episode pool |
|---|---|---|---|---|---|
| evolve L1 | 43 | 1,206 | 1 (1 / 0 / 0) | 1 | #35, 0 |
| evolve L2 | 29 | 1,200 | 2 (1 / 1 / 0) | 4 | #27, 2 |
| evolve L3 | 28 | 1,269 | 4 (1 / 3 / 0) | 1 | #10, 2 → **A2** |
| random_struct L1 | 46 | 1,204 | 6 (6 / 0 / 0) | 1 | #12, 4 |
| random_struct L2 | 70 | 1,250 | 15 (15 / 0 / 0) | 4 | #45, 6 |
| random_struct L3 | 64 | 1,208 | 15 (1 / 14 / 0) | 2 | #12, 8 → **A3** |
| params L1 | 18 | 1,201 | 19 (1 / 18 / 0) | 3 | #13, 7 → **A4** |

* 0 silent rows in any discovery candidate.
* No lineage solved any SUBH episode.
* Partial-credit check: across all 298 candidates the partial-credit term correlates with independent exactness (Spearman
  0.91). Of 3,358 episode evaluations with partial credit > 0, 416 were exact. The signal tracks correctness but is far from
  sufficient for it.

### 1.2 Validation (110 fresh episodes; 15 s CPU cap per episode, identical for all arms; `artifacts/mi2_val/gate.json`)

| arm | K (20) | MUL (30) | ADDC (30) | SUBH (30) | dev-unfamiliar (90) | exact ≤ 3 s (90) | silent | full-space CPU s | total CPU s | queries | discovery CPU s (fully loaded) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 original learner | 20 | 4 | 2 | 0 | 6 | 6 | 0 | 365 | 914 | 62,050 | 0 |
| A1 MI-1 procedure | 20 | 4 | 14 | 0 | 18 | 18 | 1 | 463 | 1,012 | 71,810 | 390 (MI-1 evolve arm; MI-1 selection extra) |
| **A2 evolve (new)** | 20 | 4 | 10 | 0 | **14** | 14 | 1 | 553 | 1,102 | 69,469 | 3,675 + 220 selection |
| A2_L2 | 20 | 4 | 3 | 0 | 7 | 7 | 0 | 462 | 1,011 | 62,975 | (in A2) |
| A2_L1 | 20 | 4 | 2 | 0 | 6 | 6 | 0 | 373 | 923 | 62,050 | (in A2) |
| A3 random structural | 20 | 14 | 2 | 0 | 16 | 16 | 0 | 195 | 744 | 70,558 | 3,662 + 172 |
| A3_L2 | 20 | 22 | 2 | 0 | 24 | 24 | 0 | 390 | 939 | 75,578 | (in A3) |
| A3_L1 | 20 | 10 | 2 | 0 | 12 | 12 | 0 | 608 | 1,157 | 66,975 | (in A3) |
| A4 params (restricted) | 20 | 4 | 27 | 0 | 31 | 30 | 1 | 425 | 974 | 84,539 | 1,201 + 110 |
| **A5 human-written** | 20 | 26 | 20 | 28 | **74** | 67 | 1 | 248 | 798 | 115,493 | 0 machine (human design) |
| A6 generic direct synthesis | 20 | 18 | 21 | 20 | 59 | 52 | 1 | 601 | 1,150 | 102,606 | 0 |

Shared costs: the fast path for every arm (549 s of the totals) and the shared cache, diagnosis and pool building (698 s).

Pre-registered comparisons (A2 vs control on the 90 dev-unfamiliar episodes; Bonferroni α = 0.05/6):

| control | A2 | control | diff | A2-only : control-only | one-sided p |
|---|---|---|---|---|---|
| A0 | 14 | 6 | +8 | 8 : 0 | 0.0039 |
| A1 | 14 | 18 | −4 | 2 : 6 | 0.96 |
| A3 | 14 | 16 | −2 | 8 : 10 | 0.76 |
| A4 | 14 | 31 | −17 | 0 : 17 | 1.0 |
| A5 | 14 | 74 | −60 | 3 : 63 | 1.0 |
| A6 | 14 | 59 | −45 | 1 : 46 | 1.0 |

Gate:

* **G1 fails** (A2 is below five of six controls).
* **G2 fails.**
* **G3 fails:** silent 1 vs 0. All five silent rows across arms are the same ADDC episode (seed 26801): every space containing
  `acc + 3` learns it, the bounded acceptance check passes it, and the held-out stream rejects it. This is an acceptance-check
  gap in the shared engine, not an A2-specific defect.
* **G4 passes** (K 20/20).

**Milestone A: negative.** No revision; the confirmation stays closed; the `mi2/test` seeds are never claimed.

### 1.3 The generated procedure A2 (complete source, ancestry, attribution)

```
def h0:
  terms P0 ['acc', 'x']
  lits P1 [0, 1]
main:
  call h0; union P0 P0 P1
  combine P2 P0 P0 +; combine P3 P0 P0 -; union P2 P2 P3
  combine P3 P2 P0 +; combine P4 P2 P0 -; union P3 P3 P4; combine P4 P0 P2 +; combine P5 P0 P2 -; union P4 P4 P5; union P3 P3 P4
  union P0 P0 P2; union P0 P0 P3; dedupe P0 P0                       # = the seed's closure (GRAMMAR5)
  combine P3 P2 P0 +; combine P4 P2 P0 -; union P3 P3 P4; combine P4 P0 P2 +; combine P5 P0 P2 -; union P4 P4 P5; union P3 P3 P4
  union P0 P0 P2; union P0 P0 P3; dedupe P0 P0                       # the same closure round again, over the enlarged pool
  sort P0 P0 size; ret P0
```

Ancestry (`artifacts/mi2_dev/disc_a_evolve_L3.json`):

* #0 the seed;
* #4 = #0 with `extract_helper h0` (behaviourally identical);
* #10 = crossover(#4[:15], #9[6:]), which splices a second copy of the closure block after the first.

No human or Claude edit; no external model.

Behavioural difference from its parent (the seed / GRAMMAR5):

* 189 expressions vs 53, a superset; only + and − (152 / 33), no new operator.
* It reaches sums such as `acc + 2` and `acc + 3` (as `acc + ((1 + 1) + 1)`), but not `acc + 5`, `acc · x` or `acc − x/2`.

Development ablation (selection pool, `artifacts/mi2_dev/ablation_A2.json`):

| variant | exact / 30 |
|---|---|
| frozen | 2 |
| second closure round removed | 0 (seed behaviour) |
| first segment removed / helper emptied | 0 (empty space) |

The entire gain comes from repeating the closure round. That is equivalent to raising the closure size bound, which is a
parameter change, and the restricted parameter-tuning arm A4 does it better (31 vs 14).

Attribution:

* Humans (Claude) supplied the language, all primitives and the seed.
* The search generated only the duplication: a helper extraction plus a crossover splice.
* Novelty level: **none beyond "a new program for this task distribution"**. Not a new learning method; not materially
  different from parameter tuning; not research-novel. The unused-helper-free structure does not change this assessment.

### 1.4 Why discovery does not yet improve the learner (diagnosis)

1. **The language and engine are not the bottleneck.** A human-written procedure in the same language with the same miners
   (A5) solves 74/90 fresh dev-unfamiliar episodes, including SUBH 28/30, and does it with the least full-space CPU (248 s).
   Generic enumeration (A6) solves 59/90. The witness diagnosis (§0.2) gives 100 % on failing dev episodes.
2. **The search is compute-starved at this budget.**
   * One candidate costs 20–100 CPU s on the 60-episode pool, so each 1,200 s lineage evaluated only 18–70 candidates.
   * A5-quality procedures need about 30 coordinated statements (literal choice, miners, four-operator layer, additive layer).
     The generic statement distribution almost never assembles them in so few draws.
3. **Evolution was weaker than random structural search under CPU matching.**
   * Evolve's archive is dominated by expensive seed descendants (the seed costs 56 s per evaluation), so it evaluates fewer
     candidates (28–43) than random search (46–70), whose random programs are cheap.
   * Tournament selection then refines seed variants (closure repetition) instead of exploring new operators.
4. **Discovery winners specialise.** The best random and parameter lineages solve one family (MUL-only or ADDC-only), and
   selection on 30 episodes cannot reward breadth.
5. **The shared acceptance check accepts one wrong machine** (seed 26801) for every arm able to express `acc + 3`. That is a
   separate correctness gap that any future gate on silent errors will keep hitting.

### 1.5 Milestone B: not run (precise reason)

* **Precondition unmet:** Milestone A did not pass validation, so there is no accepted machine-generated procedure.
  `artifacts/mi2_accepted.json` does not exist, the B pools (`mi2/bdev`, SCL / AVG / MAX) were never opened (code-enforced),
  and `mi2/btest` is unclaimed.
* **Architectural finding stands.** The original improver never invokes a learned procedure. The connection
  (`mi2_lpl.mutate_lib`, library insertion at the mutation call site) is implemented and unit-tested (identical to the original
  operator with an empty library). It is **inactive**.
* Using A5 (human-written) or any failed candidate as the library would test a different claim, so it was not done.

### 1.6 Budget, protection, remotes

* MI-2 ledger rows (`mi-2-*`): 15,038 s.

  | stage | s | allocation |
  |---|---|---|
  | diagnosis | 248 | |
  | pool cache | 450 | |
  | discovery | 8,546 | 8,400 |
  | selection | 503 | |
  | validation | 5,237 | 3,200; the overrun came from the reserve and is disclosed |
  | ablation | 54 | |
* Remaining carried balance: **14,206 s**. No new grant was used.
* Protected manifests unchanged: 912 / 157 / 74 / 390. Checkers v1–v5 pinned. `main` and `final_sealed` untouched. MI-1 and X7
  files untouched (MI-2 uses separately versioned files).

### 1.7 Next experiment (recommendation)

Make discovery cheap enough to search, before asking whether it can improve itself. Two options:

* **Racing evaluation.** Score each candidate on 6 episodes first and spend the full pool only on candidates that solve ≥ 1.
  This should give about 10× more candidates per CPU s.
* **Compositional search operators** that can insert whole layered blocks. These would still be generic, not copied from A5.

Both variants should be tested against the same random-structural and parameter controls, with A5 kept as the frozen human
reference. Separately, the bounded acceptance check needs a held-out-style probe for constant-offset updates (seed 26801)
before any silent-error gate can be met by an arm that can express constants.
