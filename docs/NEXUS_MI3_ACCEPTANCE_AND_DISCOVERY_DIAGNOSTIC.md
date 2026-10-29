# NEXUS MI-3: acceptance reliability and discovery efficiency diagnostic

Status: **NOT LOCKED**. This is a diagnostic. It is not an AGI test and does not confirm self-evolution.

* MI-2 remains negative: its validation is not rerun and its withheld families (SCL, AVG, MAX) stay closed.
* Milestone B stays closed.
* CPU only. No external-model candidates and no new compute grant.

Long-term claim, untested here: *"A NEXUS-generated learning procedure improves learning on untouched task families; using
that procedure also produces better subsequent improvements than keeping the original improver, under equal compute budgets."*

MI-3 asks two narrower questions:

* Can the shared acceptance check be made reliable?
* Does staged evaluation make discovery cheap enough to search?

## 0. Pre-registration

Sections 0.1–0.5 are committed before the one-use acceptance audit. Section 0.6 lists the items fixed later, and the rule
that fixes each one; every one is committed before the measurement it governs.

### 0.1 State, protection, budget

* **Start:** `332161d` on `codex/nexus-data-engineering` (github and origin both at `332161d`; working tree clean).
* **Processes:** none running. The five obsolete MI-2 waiting shells were stopped by task ID beforehand.
* **Protection snapshot:** `scripts/mi3_protect.py` → `artifacts/mi3_protected_hashes_before.json`. Zero differences:
  * the 912 protected files, 157 sc-ba, 74 ba-oc and 390 x7-sc files;
  * the MI-1, MI-2 and X7 freezes;
  * checkers v1–v5 against their pins;
  * `main` at `d7ac8c5`, and no `final_sealed` claim;
  * 856 frozen MI-1, MI-2 and X7 code and artifact files hashed for the after-check.
* **Budget:** MI-3 may charge at most **8,000 s** (ledger `wall_s` of `mi-3-*` rows, via `scripts/mi_exec.py`) of the carried
  14,206 s.

  | stage | ceiling (s) |
  |---|---|
  | s1: audit of state, development diagnosis, implementation, unit checks | 800 |
  | audit: independent acceptance audit | 1,200 |
  | cal: screening calibration | 1,000 |
  | disc: discovery, 4 arms × 2 seeds × 400 s | 3,200 |
  | win: fresh winner evaluation | 1,400 |
  | rep: reporting, protection checks, contingency | 400 |

  * `artifacts/mi3_allocation.json` records the ceilings. `scripts/mi3_budget.py` and `scripts/mi3_jobs.py` refuse any launch
    whose cap, added to the caps still running, would exceed the stage ceiling or the MI-3 total.
  * A transfer between stages is appended to the allocation and committed before the receiving stage's outcomes are seen.
  * The reporting reserve is never used to force a result.
* **Processes:** every multi-job stage runs through `scripts/mi3_jobs.py`.
  * Each child is tracked by PID and exit code; no stage waits on a log marker.
  * Status is written atomically; the overall wall timeout is finite.
  * Only the runner's own children are terminated, by PID.

### 0.2 Seed allocations (`src/nexus/mi3_seeds.py`)

All ranges sit above every registered range (highest stop 28400) and every spent seed (highest 27099). Disjointness is
checked at import.

| allocation | seeds | use |
|---|---|---|
| `mi3/dev` | 28400–28799 | development diagnosis and repair design (reusable) |
| `mi3/accept_audit` | 28800–29099 | **one-use** acceptance audit; claimed whole on first use |
| `mi3/screen_calibration` | 29100–29399 | Stage 2 calibration (development) |
| `mi3/discovery` | 29400–29699 | Stage 3 discovery pools (development) |
| `mi3/selection` | 29700–29899 | Stage 3 within-run selection (development) |
| `mi3/winner_eval` | 29900–29999 | **one-use** fresh winner evaluation; claimed whole on first use |

Learners never see evaluator-only ground truth. The reference machine and the held-out stream are read only by the
evaluator, and by the audit's candidate constructor and witness recorder, never by an acceptance check.

### 0.3 Stage 1: the 26801 mechanism (development diagnosis, already measured)

`scripts/mi3_diag.py 26801 ADDC` (run `mi-3-diag-26801-1`):

* **Reference machine:** 2 modes, 1 register; declared kinds RELEASE, ADD, FLUSH, CLOSE, VOID.
* **The constant was right.** The accepted update `acc + 3` on (0, RELEASE) is the reference update.
* **What actually happened:**
  * The 120-event training stream never contained the declared kind **ADD** (RELEASE 108, VOID 6, CLOSE 4, FLUSH 2).
  * The learner's alphabet, and so every probe of the old check, lacked ADD. The old check's own scope states "only kinds
    observed at build time".
  * On the held-out stream, ADD occurs 31 times. The reference answers `q:invalid` and the accepted machine emits
    `?unknown`: 31 of 641 rows differ.
* **Mechanism:** the hypothesis is not total over the declared input interface, and the check certifies only the observed
  sub-alphabet. It is not a wrong constant, a delayed effect or a register error.
* **Why A0 had no silent error:** A0 cannot express `acc + 3`, so its register search failed before acceptance was reached.

**Repair (`src/nexus/mi3_accept.py`, new module).** A new interface-closure tier runs before the unchanged old tiers
(`coverage_cex`, then `ba_accept.bounded_cex`).

* The episode's declared event-kind interface (`Episode3.interface`) is a schema of kinds only, with no outputs or behaviour.
* Every declared kind the hypothesis never observed is probed through the counted oracle, from these starting points:
  * the empty word;
  * every hypothesis mode's access path;
  * every register-loading prefix.
* A differing probe is an `interface_gap` counterexample. The learner cannot extend its alphabet, so an interface gap means
  rejection (no answer).
* The repair is not a syntactic ban: no expression, constant or family is special-cased.
* 26801 is kept only as an exposed regression test (`tests/test_mi3.py`).
* Every MI-3 arm uses `mi3_accept.full_space3`. ba_accept, t7_repair, mi_learner, mi2_learner, checkers v1–v5 and the evaluator
  are unchanged.

**Development check of the design (`mi3/dev`, 24 episodes, `artifacts/mi3_dev/audit/summary.json`).**

| candidates | old check accepted | new check accepted |
|---|---|---|
| correct (20) | 20 | 20 |
| wrong constant (18) | 0 | 0 |
| delayed effect (18) | 0 | 0 |
| nonzero register (20) | 0 | 0 |
| dropped kind (24) | **23** | 0 |

* All 80 witnesses verified.
* Check CPU: old 1.67 s, new 1.04 s, because the new tier rejects missing-kind candidates early.

### 0.4 Stage 1 audit (frozen: `scripts/mi3_audit.py` with `mi3_accept.py` at this commit)

**Construction.** Episodes are processed in seed order per family (K, MUL, ADDC, SUBH). One constructor is used for dev and the
audit.

* **Base candidate:** the x7 learner learns from the full training stream, using the privileged witness domain and no acceptance
  loop. If exact, it is **C** (correct). If not exact, it is **NAT**, reported but outside the 240.
* **Perturbations of a correct base:**
  * **CONST:** a wrong constant (c → c+d).
  * **DELAY:** an update moved to the next transition.
  * **REG:** a register initialised nonzero (1, 2 or 5).
* **KIND:** a newly generated instance of the 26801 mechanism. One declared kind that occurs on the held-out stream is removed
  from training, outputs are recomputed by the reference, and the learner relearns.

**Order of operations.** The old and new checks run first. They receive only the learner object (training data, oracle,
hypothesis, candidate) and the interface. Only then does the evaluator classify the candidate. For an incorrect candidate it
stores a witness in a separate file: the held-out key prefix where candidate and reference differ, re-verified by direct
simulation.

**Quotas.** Filled in seed order by evaluator class only; check outcomes never affect inclusion.

* 120 correct: C × 30 for each of K, MUL, ADDC, SUBH.
* 120 incorrect: CONST, DELAY, REG and KIND × 30 each, split 8/8/7/7 over K/MUL/ADDC/SUBH.

The audit runs seed indices 0–59 per family, one metered job per family, each capped at 280 s. Rows beyond the quotas are
reported but do not count.

**Hard gate (all required; no revision).**

* The new check accepts 0/120 incorrect.
* The new check accepts ≥ 114/120 correct.
* The new check accepts ≥ (old check's correct acceptances − 2) on the same 120.
* All 240 are present with verified witnesses, within the 1,200 s ceiling.

**Stop rule.** If the gate fails, MI-3 halts before discovery and reports. The checker is not revised against this one-use set.

This audit is an intentionally constructed distribution. Zero failures here would not establish a universal or production
error rate.

### 0.5 Stages 2–4 (frozen rules)

**Common.**

* Every evaluation is `mi3_search.eval_one`: a fresh `Episode3` and a fresh learner per episode (task memory reset),
  `full_space3` with the arm's procedure, the Stage 1 check, and the unchanged evaluator.
* There is no fast path in MI-3. It is identical for every arm, and removing it makes known-task retention depend on each
  arm's own procedure.
* **Per-episode CPU cap: 1.0 s.** Rule: the smallest of {1.0, 1.5, 2.0, 3.0} s that covers ≥ 90 % of the 416 exact solves in
  the MI-2 development discovery records. 1.0 s covers 94.7 % (`artifacts/mi3_dev/capcal.json`, run `mi-3-cal-capcal-1`).
* **Fitness (MI-2, frozen):** [exact, mean partial, −CPU].

**Stage 2 calibration (`scripts/mi3_cal.py`; development data `mi3/screen_calibration`).**

* **Candidate pool:** a fixed list of 24:
  * the seed (LPL transcription) and the hard-wired A0;
  * MI-1 #17; MI-2 A2, A3 and A4; A5; A6;
  * 8 random LPL programs;
  * 3 human-written domain specialists (MUL, ADDC, SUBH; calibration only);
  * 2 syntactic duplicates (A5 and the seed, each plus a no-op);
  * 3 known poor procedures.
* **Episodes:** 24, which is seed indices 0–7 for each of MUL, ADDC and SUBH. The screen is indices 0–1 of each family
  (6 episodes).
* Every candidate is fully evaluated.
* **Staged schedule.**
  * **Survive rule:** screen exact ≥ 1, or screen mean partial ≥ TAU.
  * Survivors are evaluated on the other 18 episodes.
  * **Rejection audit:** 10 % of cumulative screening CPU is reserved. Whenever audit_spent + 3 × (the candidate's screen CPU)
    ≤ 0.10 × screen_spent, one uniformly drawn, not yet audited rejected candidate is fully evaluated.
  * Zero initial solves is never a permanent rejection.
  * The schedule is simulated from the same per-episode measurements, with candidates in a seeded order.
* **TAU menu:** {0.75, 0.5, 0.25}. The largest saving among the TAUs that pass the gate is chosen.
* **Calibration gate (all required).**
  * CPU saving of at least 20 %.
  * Every top-quartile candidate survives or is recovered by the audit. Top quartile is by full fitness, with ties at the
    boundary all included.
  * At least 3 distinct full exact counts, and fewer than 80 % of candidates at 0.
  * Zero silent errors.
* **If it fails:** stop and report; no discovery.
* **If it passes:** `artifacts/mi3_schedule.json` is frozen and committed before discovery.
* Passing establishes development feasibility only, not that screening generalises.

**Stage 3 discovery (`scripts/mi3_discover.py`).**

* **Arms:** E-F, E-S, R-F, R-S, each with lineages L1 and L2. Each run is one metered job at 400 charged s.
* **Pools:** discovery uses 24 episodes (`mi3/discovery` indices 0–7 × 3 families); selection uses 12 (`mi3/selection`
  indices 0–3 × 3).
* **Same for every arm:**
  * DSL and primitives (`mi_lpl`);
  * the generic operators (`mutate`, `crossover`, `random_program`), with no new block operators and no A5 macro;
  * the Stage 1 check;
  * the cap;
  * the matched start: k = 0 is the seed.
* **Evolution (E):** k = 1 and 2 are random programs. For k ≥ 3, a tournament over the top 8 by rank, followed by 1–3
  mutations, or crossover with p 0.3.
* **Random search (R):** a random program (p 0.5), or the seed with 1–6 random edits. No selection and no ancestry from
  evaluated candidates.
* **Pairing:** the proposal RNG `mi3-{E|R}-L{lin}-{k}` is shared by the F and S arm of the same family and lineage.
* **Evaluation regime:** F arms evaluate all 24 episodes; S arms use the frozen schedule.
* **Deadline:**
  * A stage launches only if elapsed + n_episodes × 1.25 s + SEL_RESERVE ≤ 385 s, where SEL_RESERVE = 3 × 12 × 1.25 s is
    kept for selection.
  * All generation, signatures, evaluation and bookkeeping count toward the run's time.
* **Winner selection:**
  * The top 3 fully evaluated candidates are re-scored on the selection pool.
  * Winner = best (selection exact, selection partial, discovery rank, −id).
  * Fallbacks: the top fully evaluated candidate, else candidate 0.
  * One winner per run (8 in total); no manual edit or curation.
* **Telemetry per candidate:**
  * ancestry and edits;
  * hypothesis-space signature on 3 fixed probe contexts, with a duplicate flag;
  * degenerate flag;
  * stage reached;
  * screen and full fitness, per-episode rows and CPU;
  * a best-so-far curve against elapsed time.

**Stage 4 fresh winner evaluation (`scripts/mi3_eval.py`; one-use `mi3/winner_eval`).**

* **Arms (13):** the 8 winners, plus A0, MI-1 #17, MI-2 A4, A5 and A6.
* **N:** the largest of {40, 28, 16} with 13 × (N × (1.0 s + overhead) + 5 s) ≤ 1,400 s. Overhead is the largest per-episode
  non-learner CPU in Stage 2, plus 0.1 s.
* N and the cap are committed in `artifacts/mi3_eval_plan.json` before `winner_eval` is claimed. If no N fits, it is never
  opened.
* Episodes are split evenly over K, MUL, ADDC and SUBH (indices 0..N/4−1).
* **Metrics:**
  * exact by family;
  * silent (incorrect accepted), abstentions, timeouts and interface gaps;
  * CPU and queries;
  * coverage at matched per-episode budgets 0.1, 0.25, 0.5 and 1.0 s;
  * discovery cost, separately and amortised over 40, 1,000 and 10,000 episodes. Run winners are charged their ledger
    discovery seconds; MI-1 390 s; MI-2 A4 1,311 s; human references 0.
  * K retention relative to A0.

### 0.6 Analysis and claim limits (predeclared)

**Contrasts.** Four, all on the MUL, ADDC and SUBH winner_eval episodes, paired by lineage:

* E-S vs E-F
* R-S vs R-F
* E-S vs R-S
* E-F vs R-F

**Statistics.**

* **Primary:** per-seed differences, their mean, and a 95 % bootstrap interval (2,000 episode resamples).
* **Exploratory:** a one-sided sign test on discordant episodes pooled over both pairs, with Holm correction over the 4.
* N = 2 discovery seeds per arm. Seed disagreements are flagged, and no single best lineage stands for an arm.

**A larger follow-up is justified only if all four hold, for the S arm against its F arm in both seed pairs:**

1. Better downstream unfamiliar solves (difference ≥ 1 in both pairs), or equal (|difference| ≤ 1) at lower total cost.
2. Zero additional silent errors.
3. K retention no worse than the F arm minus 1.
4. Mechanistic evidence beyond volume: the winner's extra solves use learned updates that lie outside the seed procedure's
   hypothesis space on those episodes.

**References.** A0, MI-1, MI-2 A4, A5 and A6 stay in every table. Nothing is promoted, Milestone B is not run, and the withheld
families are not touched.

**Endpoint guidance (predeclared).**

* **(a) Scale up** only if the follow-up criteria hold.
* **(b) Pivot to a different search or synthesis mechanism** if the follow-up criteria fail and the best winner stays below
  half of A6's unfamiliar solves.
* **(c) Halt the current LPL evolution line** if, in addition, evolution beats random search in neither regime and no winner
  beats MI-2 A4.

The final assessment states which of these the evidence supports.

---

## 1. Results (NOT LOCKED)

All runs were metered by `scripts/mi_exec.py` and launched by `scripts/mi3_jobs.py`. Every job exited 0 and nothing was rerun.

| commit | content |
|---|---|
| `c85f082` | protocol and implementation |
| `0f9f80b` | audit |
| `0eccc28` | calibration and schedule |
| `9abb09d` | discovery, freeze and plan |
| this commit | winner evaluation and report |

### 1.1 Stage 1: acceptance repair and audit (`artifacts/mi3_accept_audit/summary.json`)

The one-use `mi3/accept_audit` set was claimed once (run `mi-3-audit-claim-1`). It ran in 4 family jobs at 274 s charged
(ceiling 1,200).

* **Construction:** 1,092 candidates from 240 episodes:

  | class | count |
  |---|---|
  | C (correct) | 204 |
  | CONST | 186 |
  | DELAY | 189 |
  | REG | 204 |
  | KIND | 232 |
  | natural errors | 17 |
  | perturbations still correct | 7 |
  | no machine | 27 |
  | not applicable | 26 |

  Quotas were filled in seed order: 120 correct and 120 incorrect.

* **Gate: PASSED.**

  | the 240 audit candidates | old check (MI-2) | new check (MI-3) |
  |---|---|---|
  | correct accepted (of 120) | 119 | **119** |
  | incorrect accepted (of 120) | **30** | **0** |
  | … wrong constant (30) | 0 | 0 |
  | … delayed effect (30) | 0 | 0 |
  | … nonzero register (30) | 0 | 0 |
  | … dropped declared kind (26801 mechanism, 30) | **30** | 0 |
  | check CPU (s, all 240) | 6.57 | 5.78 |
  | oracle queries (all 240) | 99,956 | 86,384 |

* **Witnesses:** 120 of 120 present, each re-verified by direct simulation.
* **The one correct candidate both checks reject:** 28827 ADDC. It is correct on the held-out stream, but the bounded tier finds
  a probe on which it differs from the reference. This is a conservative rejection the two checks share.
* **Natural errors:** among the 17 natural (unperturbed) errors, the old check accepted one, 28806 ADDC. There the declared kind
  SETTLE never occurs in training: a spontaneous instance of the 26801 mechanism. The new check rejected it. Both checks
  rejected the other 16.
* **Reading:** this is a constructed distribution, and zero false accepts here is not a production error rate. Within it:
  * The old check's only measured blind spot is the unobserved declared kind, and it accepted every such case.
  * The perturbation types the old check already caught are easy: its coverage tier rejects them at once. The audit does not
    test subtler errors that agree with every probe.

### 1.2 Stage 2: screening calibration (`artifacts/mi3_cal/calibration.json`)

24 candidates × 24 episodes. Charged 174 s (ceiling 1,000). Zero silent errors in 576 evaluations.

| TAU | survivors | screen CPU | survivor CPU | audit CPU | staged CPU | full CPU | saving | top quartile lost | gate |
|---|---|---|---|---|---|---|---|---|---|
| **0.75** (chosen) | 7 | 49.1 | 59.3 | 0.3 | 108.8 | 171.5 | **36.6 %** | none | pass |
| 0.5 | 7 | 49.1 | 59.3 | 0.3 | 108.8 | 171.5 | 36.6 % | none | pass |
| 0.25 | 12 | 49.1 | 102.9 | 0.6 | 152.7 | 171.5 | 11.0 % | none | fail (saving below 20 %) |

* **Rank agreement** (Spearman, screen fitness vs full fitness): 0.947; on exact counts alone, 0.812.
* **Full exact counts** (of 24) ranged over {0, 1, 2, 3, 6, 9, 10, 13, 17}.
* **Top quartile:** A5 17, dup_A5 17, A6 13, MI-2 A4 10, spec_ADDC 10, spec_SUBH 9. All passed the screen directly.
* **Useful candidates:** 16 with at least one exact solve. They have 13 distinct hypothesis spaces and 10 distinct solved-episode
  sets. The A5 duplicate was behaviourally identical to A5, and the seed duplicate to the seed.
* **Useful candidates discarded at TAU 0.75 and not recovered:** 8. They hold 20 full-pool solves: MUL 15, ADDC 5, SUBH 0.
  * MI-1 #17 (6 exact: ADDC 4, MUL 2) had 0 screen solves.
  * The others were MI-2 A2 (3), seed (2), A0 (2), seed duplicate (2), poor_params3 (2), MI-2 A3 (1) and random_0 (1).
* **Weakness of the rejection audit:** it recovered only cheap candidates. Its affordability rule (3 × screen CPU within
  10 % of cumulative screening CPU) never admits an expensive rejected procedure.
* The gate establishes development feasibility only.

### 1.3 Stage 3: discovery (`artifacts/mi3_disc/*.json`, `artifacts/mi3_attribution.json`)

Charged 2,775 s of the 3,200 s ceiling: 332–363 s per run, all COMPLETE. The deadline rule, with its worst-case stage and
selection reserves, stopped candidate generation at 310–336 s elapsed. The runs charged 332–363 s, so 9–17 % of each 400 s allowance went unused.

| run | candidates | fully evaluated | screen-rejected | audited | duplicates | degenerate | distinct spaces | best discovery exact (of 24), when | winner (selection exact of 12) |
|---|---|---|---|---|---|---|---|---|---|
| E-F L1 | 40 | 40 | — | — | 18 | 7 | 22 | 7 @ 251 s | #34 (3) |
| E-F L2 | 38 | 38 | — | — | 20 | 7 | 18 | 7 @ 165 s | #24 (3) |
| E-S L1 | 38 | 35 | 0 | 9 | 28 | 7 | 10 | 4 @ 64 s | #34 (1) |
| E-S L2 | 44 | 39 | 0 | 9 | 26 | 8 | 18 | 4 @ 71 s | #33 (1) |
| R-F L1 | 74 | 74 | — | — | 44 | 27 | 30 | 7 @ 34 s | #14 (2) |
| R-F L2 | 86 | 86 | — | — | 52 | 36 | 34 | 6 @ 142 s | #33 (3) |
| R-S L1 | 95 | 77 | 12 | 40 | 56 | 31 | 39 | 7 @ 34 s | #14 (2) |
| R-S L2 | 99 | 88 | 6 | 48 | 59 | 38 | 40 | 6 @ 142 s | #33 (3) |

**Why screening did not pay in discovery** (calibration predicted 36.6 %):

* Seed-derived candidates almost always pass the screen. E-S screened out no candidate at all: 9 were rejected and then all 9
  were audited, and 3–5 survivors ran out of time.
* What random search rejects is mostly degenerate programs, which already cost about 0.1 s.
* Staged random search therefore evaluated only about 25 % more candidates (95 vs 74, 99 vs 86). Staged evolution evaluated
  about the same number (38 vs 40, 44 vs 38).
* Pairing: R-S and R-F share proposal streams, so R-S reached the same best candidate at the same time and selected the
  **byte-identical winner** in both lineages.
* E-S converged on duplicates (28 of 38 in L1) and plateaued at 4, below E-F's 7. Fitness from candidates that failed the screen
  ranks them below every fully evaluated candidate, which narrowed the tournament.

### 1.4 Stage 4: fresh winner evaluation (`artifacts/mi3_winner_eval/result.json`)

The plan (`artifacts/mi3_eval_plan.json`, committed before the claim) was N = 40, 10 per family, with a cap of 1.0 s and a
worst-case bound of 640.6 s. The one-use `mi3/winner_eval` set was claimed once by A0, and all 13 arms ran once on the same 40
fresh episodes: 520 of 520 rows, charged 216 s (ceiling 1,400).

| arm | K | MUL | ADDC | SUBH | **unfamiliar (30)** | silent | abstain | timeouts | eval CPU s | queries | solved ≤ 0.1 / 0.25 / 0.5 / 1 s | discovery s | cost/episode at 40 / 1,000 / 10,000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E-F L1 | 9 | 3 | 4 | 0 | **7** | 0 | 24 | 12 | 20.1 | 15,185 | 0 / 11 / 15 / 16 | 336 | 8.90 / 0.84 / 0.54 |
| E-F L2 | 8 | 3 | 4 | 0 | **7** | 0 | 25 | 15 | 23.8 | 15,285 | 0 / 11 / 15 / 15 | 338 | 9.03 / 0.93 / 0.63 |
| E-S L1 | 9 | 2 | 2 | 0 | **4** | 0 | 27 | 13 | 24.6 | 13,425 | 0 / 0 / 10 / 13 | 361 | 9.64 / 0.98 / 0.65 |
| E-S L2 | 9 | 3 | 2 | 0 | **5** | 0 | 26 | 12 | 21.5 | 13,779 | 0 / 10 / 12 / 14 | 363 | 9.61 / 0.90 / 0.57 |
| R-F L1 | 9 | 2 | 4 | 0 | **6** | 0 | 25 | 2 | 4.8 | 13,736 | 13 / 15 / 15 / 15 | 336 | 8.53 / 0.46 / 0.15 |
| R-F L2 | 8 | 6 | 0 | 0 | **6** | 0 | 26 | 11 | 16.2 | 15,127 | 9 / 13 / 14 / 14 | 332 | 8.71 / 0.74 / 0.44 |
| R-S L1 | 9 | 2 | 4 | 0 | **6** | 0 | 25 | 2 | 4.8 | 13,736 | 13 / 15 / 15 / 15 | 356 | 9.02 / 0.48 / 0.16 |
| R-S L2 | 8 | 6 | 0 | 0 | **6** | 0 | 26 | 11 | 16.2 | 15,127 | 7 / 13 / 14 / 14 | 353 | 9.22 / 0.76 / 0.44 |
| A0 original learner | 9 | 3 | 0 | 0 | **3** | 0 | 28 | 5 | 8.9 | 13,164 | 12 / 12 / 12 / 12 | 0 | 0.22 |
| MI-1 #17 | 9 | 3 | 4 | 0 | **7** | 0 | 24 | 11 | 18.0 | 15,261 | 0 / 14 / 16 / 16 | 390 | 10.20 / 0.84 / 0.49 |
| MI-2 A4 (params) | 9 | 3 | 9 | 0 | **12** | 0 | 19 | 9 | 14.1 | 17,870 | 17 / 20 / 21 / 21 | 1,311 | 33.13 / 1.66 / 0.48 |
| A5 human reference | 8 | 9 | 7 | 9 | **25** | 0 | 7 | 6 | 10.9 | 26,199 | 21 / 30 / 32 / 33 | 0 (human) | 0.27 |
| A6 generic synthesis | 8 | 4 | 8 | 7 | **19** | 0 | 13 | 13 | 22.4 | 21,119 | 0 / 12 / 23 / 27 | 0 | 0.56 |

**Notes on the table:**

* Exact solves are counted out of 10 per family; "unfamiliar" is MUL + ADDC + SUBH.
* "Abstain" counts episodes with no accepted answer, including timeouts.
* Cost per episode is evaluation CPU per episode plus discovery cost divided by the horizon, in seconds.
* No arm made a silent error or hit an interface gap on these 40 episodes.
* **K retention:** every arm is within one solve of A0's 9: E-F L2, R-F L2, R-S L2, A5 and A6 have 8; the rest have 9.
* **SUBH:** no discovered procedure solved any SUBH episode. A5 solved 9 of 10 and A6 7.

**Predeclared contrasts** (unfamiliar episodes, paired by lineage; difference = primary − control):

| contrast | L1 | L2 | mean | 95 % bootstrap | seeds agree | pooled discordant | p (one-sided) | Holm |
|---|---|---|---|---|---|---|---|---|
| E-S vs E-F | 4 − 7 = −3 | 5 − 7 = −2 | −2.5 | [−5.5, 0.0] | yes | 0 : 5 | 1.0 | 1.0 |
| R-S vs R-F | 6 − 6 = 0 | 6 − 6 = 0 | 0.0 | [0, 0] | yes (identical winners) | 0 : 0 | 1.0 | 1.0 |
| E-S vs R-S | 4 − 6 = −2 | 5 − 6 = −1 | −1.5 | [−5.0, 2.0] | yes | 4 : 7 | 0.89 | 1.0 |
| E-F vs R-F | 7 − 6 = +1 | 7 − 6 = +1 | +1.0 | [−3.0, 5.0] | yes | 7 : 5 | 0.39 | 1.0 |

* There were 0 additional silent errors in every pair.
* The staged arms cost slightly more in total than their full-evaluation partners (+20 to +30 s), because they ran longer
  before the selection reserve took effect.
* N = 2 discovery seeds per arm: none of these contrasts supports an inference about the arms.

### 1.5 Generated procedures: attribution (full source and ancestry trees in §2)

All 8 winners came from the automatic searches, with no human or Claude edit. The language, primitives, operators and seed are
human-written. There are 6 distinct programs, because R-S equals R-F in each lineage.

| winner | origin | hypothesis space (probe context 3) vs seed (53) | behavioural difference |
|---|---|---|---|
| E-F L1 #34 | 6-node lineage: mutations, helper extraction, crossover | 140 (+87, −0) | duplicated +/− closure rounds reach `acc ± small constants`: ADDC 4 |
| E-F L2 #24 | 12-node lineage, mostly crossovers | 283 (+230, −0) | repeated closure rounds, the same mechanism as MI-2 A2 |
| E-S L1 #34 | 14-node lineage | 101 (+52, −4) | closure duplication plus a conditional `*` branch |
| E-S L2 #33 | 14-node lineage | 114 (+61, −0) | closure duplication |
| R-F / R-S L1 #14 | seed + 3 random edits | 27 (+18, −44) | evidence constants (`dconsts small_obs`) replace the literals 0 and 1: ADDC 4, at 0.12 s per episode |
| R-F / R-S L2 #33 | seed + 3 random edits | 148 (+105, −10) | a `*` layer under a conditional on `n_trans`: MUL 6 |

* Each winner has 4–7 fresh unfamiliar solves that use a learned update outside the seed's space (a syntactic comparison of
  update source): E-F L1 7 of 7, E-F L2 4 of 7, E-S 4 of 4 and 4 of 5, R 4 of 6 in both lineages.
* That is expected for any procedure that beats the seed. None of the mechanisms is new: each is a duplicated closure, evidence
  constants already in the language, or a multiply layer.
* None reaches `acc − x/2`, so SUBH stays at 0.
* No invention is claimed.

### 1.6 Assessment against the predeclared limits

**Larger follow-up criteria: NOT met.**

* Criterion 1 fails: E-S was worse than E-F in both seeds, and R-S equalled R-F with identical winners.
* Criterion 4 (mechanism beyond volume) therefore does not arise.
* Staged screening as frozen does not make this discovery cheaper or better.

**The two questions:**

* **Acceptance reliability: answered positively within scope.** The 26801 failure was an observation gap in the check, not a
  constant error. A general interface-closure tier removes it (audit 0/120 false accepts) at no measured cost to correct
  acceptance (119 vs 119), and the evaluations afterwards made 0 silent errors.
* **Discovery efficiency: negative.**
  * Calibration promised a 36.6 % saving, but that came from a pool dominated by cheap or poor procedures.
  * In real discovery, survivors dominate the cost, so screening bought about 25 % more candidates for random search and none
    for evolution, with no downstream gain.
  * The 10 % rejection audit cannot recover expensive candidates.

**Against the references:**

* The best winners (7 of 30) equal MI-1 #17 (7). They trail MI-2 A4 (12), A6 (19) and the human A5 (25).
* At workload horizons up to 10,000 episodes, their amortised cost is above A5's and A6's.

**Endpoint (predeclared guidance in §0.6):**

* **(a) Scale up:** not justified.
* **(b) Pivot to a fundamentally different search or synthesis mechanism:** **supported.**
  * The best winner (7) is below half of A6 (19 / 2 = 9.5).
  * The gap is in what the search can construct: no winner contains the SUBH half-term `acc − x/2`.
  * It is not in how many candidates are evaluated: random search evaluated about twice as many candidates as evolution and
    reached the same 6–7.
* **(c) Halt the current LPL evolution line:** its literal condition is not met.
  * Evolution beat random search by +1 in both full-evaluation seed pairs, but descriptively only, with a CI of [−3, 5].
  * No winner beat MI-2 A4.
  * Investing further in mutation and crossover over this LPL, at this budget, is not supported by any result in MI-1, MI-2
    or MI-3.

### 1.7 Budget, protection, integration, remotes

**Charged MI-3 total: 3,512 s of the 8,000 s cap**, at the score and attribution step, before this report's protection and test
runs. The carried balance is 10,694 s. No new grant and no stage transfer.

| stage | used (s) | ceiling (s) |
|---|---|---|
| s1 | 61 | 800 |
| audit | 274 | 1,200 |
| cal | 174 | 1,000 |
| disc | 2,775 | 3,200 |
| win | 216 | 1,400 |
| rep | 12 | 400 |

* **Metering caveat:** `mi_exec` charges its child's wall time. The runner's own startup (about 2 s per job, 45 jobs) is not
  charged.
* **Bookkeeping events:**
  * `mi-3-win-score-1` crashed on ledger rows that have no `run` key, a scoring-path bug. It was fixed in `scripts/mi3_eval.py`
    after the evaluation, so the frozen hash of that file differs; the run path is unchanged.
  * `mi-3-rep-protect-1` reports FAILED only because of 49 new MI-3 log files in the shared `artifacts/mi_logs` directory,
    which the frozen-file glob includes.
* **Protection (`artifacts/mi3_protected_hashes_after.json`), all unchanged:**
  * the 912 protected files, 157 sc-ba, 74 ba-oc and 390 x7-sc files;
  * the MI-1, MI-2 and X7 freezes;
  * checkers v1–v5 against their pins;
  * `main` at `d7ac8c5`, with 0 `final_sealed` claims;
  * the 856 previously frozen MI-1, MI-2 and X7 files: 0 changed, 0 removed.
* **Tests:** `tests/test_mi3.py`, `test_mi2.py` and `test_checker_kernel.py`: 18 passed.
* **Integration:** none. See the MI-3 section of `docs/NEXUS_CAPABILITY_INTEGRATION_REGISTER.md`.
  * `mi3_accept` is used only by MI-3 evaluations. The x7 runtime still uses `ba_accept`.
  * The schedule and the winners are inactive. Milestone B stays closed, and the MI-2 withheld families were not touched.
* **Remotes:** each commit is pushed to github and origin, `codex/nexus-data-engineering`.

### 1.8 Recommended next experiment

Change the generator, not the evaluator. Test one fundamentally different construction mechanism against the same frozen
references, Stage 1 check and cap:

* **Mechanism:** example-guided synthesis of register updates, deriving the candidate update directly from the observed
  register traces (enumerate small terms that fit the traces, CEGIS-style), instead of mutating procedures that build spaces.
* **Primary endpoint:** SUBH solves, which no search has produced in MI-1, MI-2 or MI-3.
* **Fixed beforehand:** a pre-registered budget equal to A6's evaluation cost.
* **Learner-side follow-up for the Stage 1 finding:** when the interface tier finds a missing declared kind, acquire oracle
  traces for it and relearn, instead of abstaining.

## 2. Appendix: the 8 frozen winners (generated by `scripts/mi3_attrib.py` from the frozen artifacts)

R-S L1 and R-S L2 are byte-identical to R-F L1 and R-F L2, the same proposal from the shared random stream.
Ancestry trees list each candidate with its operator, edits and fitness [exact, partial]; full = 24-episode pool, screen = 6.

### E-F_L1: candidate #34 (best selection score of the top-3)

Space 140 expressions on probe context 3 (seed 53): +87 / −0. Fresh unfamiliar solves 7.

```
def h0:
  union P2 P3 P4
def h0b:
main:
  terms P0 ['acc', 'x']
  lits P1 [0, 1]
  union P0 P0 P1
  combine P2 P0 P0 +
  combine P0 P0 P1 +
  union P2 P2 P3
  combine P4 P2 P0 -
  union P3 P3 P4
  combine P4 P0 P2 +
  dedupe P1 P1
  combine P5 P0 P2 -
  union P4 P4 P5
  call h0
  union P0 P0 P2
  union P0 P0 P3
  dedupe P1 P1
  combine P5 P0 P2 +
  union P4 P4 P5
  call h0
  union P0 P0 P2
  union P0 P0 P3
  dedupe P0 P0
  sort P0 P0 size
  ret P0
```

Ancestry:

- #34 mutate ['replace@0', 'delete@0', 'perturb@0'] | full [7, 0.3488] screen [2, 0.4393]
  - #24 mutate ['perturb@16'] | full [4, 0.2715] screen [2, 0.4358]
    - #20 crossover a[:15] + b[9:] | full [4, 0.2715] screen [2, 0.4358]
      - #15 mutate ['replace@4', 'extract_helper h0'] | full [4, 0.2645] screen [2, 0.4358]
        - #10 mutate ['insert@10', 'delete@6'] | full [2, 0.195] screen [2, 0.4358]
          - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
      - #15 mutate ['replace@4', 'extract_helper h0'] | full [4, 0.2645] screen [2, 0.4358]
        - #10 mutate ['insert@10', 'delete@6'] | full [2, 0.195] screen [2, 0.4358]
          - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]

### E-F_L2: candidate #24 (best selection score of the top-3)

Space 283 expressions on probe context 3 (seed 53): +230 / −0. Fresh unfamiliar solves 7.

```
main:
  terms P0 ['acc', 'x']
  lits P1 [0, 1]
  union P0 P0 P1
  combine P2 P0 P0 +
  combine P3 P0 P0 -
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  combine P4 P0 P2 +
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  union P0 P0 P2
  union P0 P0 P3
  dedupe P0 P0
  sort P0 P0 size
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  combine P4 P0 P2 +
  combine P5 P0 P2 -
  union P4 P4 P5
  union P3 P3 P4
  union P0 P0 P2
  union P0 P0 P3
  dedupe P0 P0
  ret P0
```

Ancestry:

- #24 crossover a[:18] + b[11:] | full [7, 0.3483] screen [2, 0.4375]
  - #23 crossover a[:14] + b[12:] | full [4, 0.2715] screen [2, 0.4358]
    - #22 mutate ['perturb@22'] | full [4, 0.2715] screen [2, 0.4358]
      - #20 crossover a[:20] + b[14:] | full [4, 0.2715] screen [2, 0.4358]
        - #15 crossover a[:10] + b[5:] | full [4, 0.2715] screen [2, 0.4358]
          - #10 crossover a[:16] + b[3:] | full [2, 0.195] screen [2, 0.4358]
            - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
            - #5 crossover a[:0] + b[15:] | full [0, 0.0243] screen [0, 0.0]
              - #1 random_program | full [0, 0.0243] screen [0, 0.0]
              - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
          - #10 crossover a[:16] + b[3:] | full [2, 0.195] screen [2, 0.4358]
            - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
            - #5 crossover a[:0] + b[15:] | full [0, 0.0243] screen [0, 0.0]
              - #1 random_program | full [0, 0.0243] screen [0, 0.0]
              - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
        - #14 mutate ['delete@1'] | full [2, 0.195] screen [2, 0.4358]
          - #7 mutate ['insert@8', 'wrap_repeat@8'] | full [2, 0.195] screen [2, 0.4358]
            - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
    - #16 mutate ['insert@1'] | full [4, 0.2541] screen [2, 0.4358]
      - #14 mutate ['delete@1'] | full [2, 0.195] screen [2, 0.4358]
        - #7 mutate ['insert@8', 'wrap_repeat@8'] | full [2, 0.195] screen [2, 0.4358]
          - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
  - #15 crossover a[:10] + b[5:] | full [4, 0.2715] screen [2, 0.4358]
    - #10 crossover a[:16] + b[3:] | full [2, 0.195] screen [2, 0.4358]
      - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
      - #5 crossover a[:0] + b[15:] | full [0, 0.0243] screen [0, 0.0]
        - #1 random_program | full [0, 0.0243] screen [0, 0.0]
        - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
    - #10 crossover a[:16] + b[3:] | full [2, 0.195] screen [2, 0.4358]
      - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]
      - #5 crossover a[:0] + b[15:] | full [0, 0.0243] screen [0, 0.0]
        - #1 random_program | full [0, 0.0243] screen [0, 0.0]
        - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [2, 0.4358]

### E-S_L1: candidate #34 (best selection score of the top-3)

Space 101 expressions on probe context 3 (seed 53): +52 / −4. Fresh unfamiliar solves 4.

```
def h0:
  union P3 P3 P4
  union P0 P0 P2
  dedupe P1 P1
  union P0 P0 P3
def h1:
def h0b:
  union P3 P3 P4
  union P0 P0 P2
  dedupe P1 P1
  union P0 P0 P3
def h1b:
  lits P3 [3, 7]
def h4:
  combine P4 P0 P4 *
def h0bb:
  union P3 P3 P4
  dedupe P1 P1
  union P4 P0 P3
def h1bb:
  dedupe P3 P3
  if n_obs_int_frac < 0.5:
    repeat 3:
      if n_trans < 10:
        combine P4 P0 P4 *
        combine P0 P2 P1 *
      else:
        union P3 P5 P4
main:
  terms P0 ['acc', 'x']
  if n_trans < 15:
    call h0
    dedupe P3 P0
  else:
    repeat 3:
      combine P3 P3 P5 +
      repeat 2:
        combine P5 P2 P3 +
        if n_trans < 10:
          union P4 P5 P5
  lits P1 [0, 1]
  union P0 P0 P1
  combine P0 P0 P1 +
  combine P3 P0 P0 -
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  combine P4 P0 P2 +
  combine P5 P0 P2 -
  union P4 P4 P5
  call h0
  dedupe P0 P0
  union P3 P3 P4
  combine P4 P0 P2 +
  combine P5 P0 P2 -
  union P4 P4 P5
  call h0
  dedupe P0 P0
  call h0
  dedupe P0 P0
  sort P0 P0 size
  ret P0
```

Ancestry:

- #34 mutate ['wrap_if@1', 'delete@0', 'wrap_if@1'] | full [4, 0.2812] screen [1, 0.1667]
  - #31 crossover a[:21] + b[19:] | full [4, 0.2812] screen [1, 0.1667]
    - #23 mutate ['insert@1', 'extract_helper h4'] | full [4, 0.2686] screen [1, 0.1667]
      - #21 mutate ['insert@0', 'insert@0', 'insert@1'] | full [4, 0.2686] screen [1, 0.1667]
        - #20 crossover a[:15] + b[9:] | full [4, 0.2686] screen [1, 0.1667]
          - #18 mutate ['replace@0', 'insert@0', 'insert@0'] | full [4, 0.2645] screen [1, 0.1667]
            - #15 mutate ['replace@4', 'wrap_if@0'] | full [4, 0.2645] screen [1, 0.1667]
              - #11 mutate ['extract_helper h1', 'insert@0', 'wrap_repeat@0'] | full [2, 0.195] screen [1, 0.1667]
                - #10 mutate ['insert@2', 'delete@0'] | full [2, 0.195] screen [1, 0.1667]
                  - #7 mutate ['insert@1', 'wrap_repeat@0', 'extract_helper h0'] | full [2, 0.195] screen [1, 0.1667]
                    - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]
          - #18 mutate ['replace@0', 'insert@0', 'insert@0'] | full [4, 0.2645] screen [1, 0.1667]
            - #15 mutate ['replace@4', 'wrap_if@0'] | full [4, 0.2645] screen [1, 0.1667]
              - #11 mutate ['extract_helper h1', 'insert@0', 'wrap_repeat@0'] | full [2, 0.195] screen [1, 0.1667]
                - #10 mutate ['insert@2', 'delete@0'] | full [2, 0.195] screen [1, 0.1667]
                  - #7 mutate ['insert@1', 'wrap_repeat@0', 'extract_helper h0'] | full [2, 0.195] screen [1, 0.1667]
                    - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]
    - #28 mutate ['wrap_repeat@1'] | full [4, 0.2686] screen [1, 0.1667]
      - #24 mutate ['perturb@2'] | full [4, 0.2686] screen [1, 0.1667]
        - #22 mutate ['delete@1', 'replace@1', 'replace@0'] | full [4, 0.2686] screen [1, 0.1667]
          - #21 mutate ['insert@0', 'insert@0', 'insert@1'] | full [4, 0.2686] screen [1, 0.1667]
            - #20 crossover a[:15] + b[9:] | full [4, 0.2686] screen [1, 0.1667]
              - #18 mutate ['replace@0', 'insert@0', 'insert@0'] | full [4, 0.2645] screen [1, 0.1667]
                - #15 mutate ['replace@4', 'wrap_if@0'] | full [4, 0.2645] screen [1, 0.1667]
                  - #11 mutate ['extract_helper h1', 'insert@0', 'wrap_repeat@0'] | full [2, 0.195] screen [1, 0.1667]
                    - #10 mutate ['insert@2', 'delete@0'] | full [2, 0.195] screen [1, 0.1667]
                      - #7 mutate ['insert@1', 'wrap_repeat@0', 'extract_helper h0'] | full [2, 0.195] screen [1, 0.1667]
                        - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]
              - #18 mutate ['replace@0', 'insert@0', 'insert@0'] | full [4, 0.2645] screen [1, 0.1667]
                - #15 mutate ['replace@4', 'wrap_if@0'] | full [4, 0.2645] screen [1, 0.1667]
                  - #11 mutate ['extract_helper h1', 'insert@0', 'wrap_repeat@0'] | full [2, 0.195] screen [1, 0.1667]
                    - #10 mutate ['insert@2', 'delete@0'] | full [2, 0.195] screen [1, 0.1667]
                      - #7 mutate ['insert@1', 'wrap_repeat@0', 'extract_helper h0'] | full [2, 0.195] screen [1, 0.1667]
                        - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]

### E-S_L2: candidate #33 (best selection score of the top-3)

Space 114 expressions on probe context 3 (seed 53): +61 / −0. Fresh unfamiliar solves 5.

```
main:
  terms P0 ['acc', 'x']
  lits P1 [0, 1]
  union P0 P0 P1
  combine P2 P0 P0 +
  combine P3 P0 P0 -
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  combine P4 P0 P2 +
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  combine P4 P0 P2 +
  combine P5 P0 P2 -
  union P4 P4 P5
  union P3 P3 P4
  union P0 P0 P2
  union P0 P0 P3
  dedupe P0 P0
  sort P0 P0 size
  repeat 2:
    dedupe P5 P2
    union P3 P3 P4
    dedupe P0 P2
    combine P4 P0 P2 +
  combine P5 P0 P2 -
  union P4 P4 P5
  union P0 P0 P2
  union P0 P0 P3
  dedupe P0 P0
  sort P0 P0 size
  ret P0
```

Ancestry:

- #33 mutate ['insert@2'] | full [4, 0.2719] screen [1, 0.1667]
  - #24 crossover a[:22] + b[18:] | full [4, 0.2719] screen [1, 0.1667]
    - #22 mutate ['perturb@22'] | full [4, 0.2715] screen [1, 0.1667]
      - #20 crossover a[:20] + b[14:] | full [4, 0.2715] screen [1, 0.1667]
        - #15 crossover a[:10] + b[5:] | full [4, 0.2715] screen [1, 0.1667]
          - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]
          - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]
        - #14 mutate ['delete@1'] | full [2, 0.195] screen [1, 0.1667]
          - #7 mutate ['insert@8', 'wrap_repeat@8'] | full [2, 0.195] screen [1, 0.1667]
            - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]
    - #21 crossover a[:17] + b[8:] | full [4, 0.2645] screen [1, 0.1667]
      - #17 mutate ['delete@5'] | full [2, 0.195] screen [1, 0.1667]
        - #10 crossover a[:16] + b[6:] | full [2, 0.195] screen [1, 0.1667]
          - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]
          - #3 mutate ['wrap_repeat@1', 'replace@1'] | full [0, 0.0243] screen [0, 0.0]
            - #1 random_program | full [0, 0.0243] screen [0, 0.0]
      - #12 mutate ['insert@7', 'delete@12', 'perturb@8'] | full [2, 0.195] screen [1, 0.1667]
        - #7 mutate ['insert@8', 'wrap_repeat@8'] | full [2, 0.195] screen [1, 0.1667]
          - #0 seed (transcribed existing procedure) | full [2, 0.195] screen [1, 0.1667]

### R-F_L1: candidate #14 (best selection score of the top-3)

Space 27 expressions on probe context 3 (seed 53): +18 / −44. Fresh unfamiliar solves 6.

```
def h0:
  combine P5 P0 P2 -
  union P4 P4 P5
def h1:
  combine P1 P2 P3 /
  union P3 P3 P4
main:
  terms P0 ['acc', 'x']
  dconsts P1 small_obs
  union P0 P0 P1
  combine P2 P0 P0 +
  combine P3 P0 P0 -
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  combine P4 P0 P2 +
  call h0
  call h1
  union P0 P0 P2
  union P0 P0 P2
  dedupe P0 P0
  sort P0 P0 size
  ret P0
```

Ancestry:

- #14 seed + random edits (no selection) ['insert@12', 'extract_helper h0', 'replace@1', 'extract_helper h1', 'perturb@13'] | full [7, 0.3458] screen [1, 0.3525]

### R-F_L2: candidate #33 (best selection score of the top-3)

Space 148 expressions on probe context 3 (seed 53): +105 / −10. Fresh unfamiliar solves 6.

```
main:
  terms P0 ['acc', 'x']
  lits P1 [0, 1]
  union P0 P0 P1
  combine P2 P0 P0 +
  combine P3 P0 P0 -
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  filter P3 P1 size_le_5
  if n_trans >= 10:
    combine P4 P0 P2 *
  else:
    repeat 2:
      repeat 2:
        union P3 P5 P3
        dconsts P3 int_ratios
        combine P3 P2 P2 *
  combine P5 P0 P2 -
  union P4 P4 P5
  union P3 P3 P4
  union P0 P0 P2
  union P0 P0 P3
  dedupe P0 P0
  sort P0 P0 size
  ret P0
```

Ancestry:

- #33 seed + random edits (no selection) ['wrap_if@9', 'insert@0', 'insert@9', 'wrap_repeat@0', 'perturb@0'] | full [6, 0.35] screen [6, 0.9445]

### R-S_L1: candidate #14 (best selection score of the top-3)

Space 27 expressions on probe context 3 (seed 53): +18 / −44. Fresh unfamiliar solves 6.

```
def h0:
  combine P5 P0 P2 -
  union P4 P4 P5
def h1:
  combine P1 P2 P3 /
  union P3 P3 P4
main:
  terms P0 ['acc', 'x']
  dconsts P1 small_obs
  union P0 P0 P1
  combine P2 P0 P0 +
  combine P3 P0 P0 -
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  combine P4 P0 P2 +
  call h0
  call h1
  union P0 P0 P2
  union P0 P0 P2
  dedupe P0 P0
  sort P0 P0 size
  ret P0
```

Ancestry:

- #14 seed + random edits (no selection) ['insert@12', 'extract_helper h0', 'replace@1', 'extract_helper h1', 'perturb@13'] | full [7, 0.3458] screen [2, 0.3333]

### R-S_L2: candidate #33 (best selection score of the top-3)

Space 148 expressions on probe context 3 (seed 53): +105 / −10. Fresh unfamiliar solves 6.

```
main:
  terms P0 ['acc', 'x']
  lits P1 [0, 1]
  union P0 P0 P1
  combine P2 P0 P0 +
  combine P3 P0 P0 -
  union P2 P2 P3
  combine P3 P2 P0 +
  combine P4 P2 P0 -
  union P3 P3 P4
  filter P3 P1 size_le_5
  if n_trans >= 10:
    combine P4 P0 P2 *
  else:
    repeat 2:
      repeat 2:
        union P3 P5 P3
        dconsts P3 int_ratios
        combine P3 P2 P2 *
  combine P5 P0 P2 -
  union P4 P4 P5
  union P3 P3 P4
  union P0 P0 P2
  union P0 P0 P3
  dedupe P0 P0
  sort P0 P0 size
  ret P0
```

Ancestry:

- #33 seed + random edits (no selection) ['wrap_if@9', 'insert@0', 'insert@9', 'wrap_repeat@0', 'perturb@0'] | full [6, 0.35] screen [2, 0.3333]
