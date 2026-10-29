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
