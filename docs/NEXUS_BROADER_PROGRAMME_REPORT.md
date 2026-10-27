# NEXUS broader programme (Wave 38, NOT LOCKED)

* **Branch:** `codex/nexus-broader-programme`, from 80f9cc2.
* **Owner grant:** +28,800 s (recorded in the ledger); 35,940 s available at the start; per call ≤ 900 s.
* **Untouched:** main, final_sealed, and Checkers v1 / v2 / v3.

## Architecture (what was built)

* **Wave 38 language** (`w38_lang.py`, prover side) and **Checker v4** (`checker_kernel_v4.py`, an independent
  implementation, pinned `c07e21ec…` at 51c12f9). Tools carry **lambda ASTs** with:
  * a variable, record fields, constants, arithmetic, comparisons, booleans, **if / else**, string functions and
    `bef` / `aft` parsing;
  * higher-order map / filter / sortby / groupby / countby / best;
  * **fold / scan** (bounded loops with accumulators);
  * **representation tools:** segments (split / words / chars / join), indices (enum), relations (pairs, tjoin),
    missing values (fill), a grid ↔ object-record encoder / decoder (objs / paint / recolor_if), and graph
    relations / dependency order (reach / topo / indeg / outdeg).

  Chains are ≤ 4 long. The **declared scope** (`w38_scope.py`) is a deterministic function of the public data and a
  fixed config, identical for all arms.
* **Evidence classes:**
  * `exhaustive_UNIQUE` / `AMBIGUOUS(k)` / `ABSTAIN`: Checker v4, scope-relative;
  * `TEST_VERIFIED_PATCH`: repairs, judged by a held-out test oracle in a separate sandboxed process;
  * `VALIDATED_PLAN`: planning, via an independent simulator;
  * `CALIBRATED_PREDICTION`: the noisy worlds (N1 track).
* **Domains:**
  1. strings and parsing;
  2. tables and records (joins, group-by counts, missing values);
  3. grids and objects;
  4. graphs.

  Domains 1–4 have 35 mechanisms in total (18 source and 17 withheld), and 4–5 of each per domain.
  5. **Planning:** internal logistics-lite (capacity, fuel, a dynamics-shift variant) plus **external blocksworld**
     from planning.domains (13 files; SHA-256 in `artifacts/external/planning_domains/SHA256SUMS`).
  6. **Python repairs** (6 bug families needing conditionals, state updates and loops).

  The **external PROSE** Transformation.Text sample (40 tasks, SHA-256 in `artifacts/external/prose/`) is tracked
  in a **separate external ledger**.

## Stage 1: timing, memory and semantics pilot (development data; `artifacts/w38_stage1.json`)

| Domain | Tasks | Result | Wrong | Mean wall / instructions | Notes |
| --- | --- | --- | --- | --- | --- |
| strings | 10 | 10 exhaustive_UNIQUE | 0 | 0.28 s / 5.9 G | scopes of 230–270 tools |
| tables | 10 | 10 exhaustive_UNIQUE | 0 | 1.22 s / 24.6 G | |
| grids | 8 | 8 exhaustive_UNIQUE (3 probes) | 0 | 3.62 s / 73.9 G | the slowest domain |
| graphs | 10 | 10 exhaustive_UNIQUE (1 probe) | 0 | 0.46 s / 9.4 G | |
| PROSE (external) | 10 | 7 ABSTAIN (no in-scope program), 2 UNIQUE, 1 skipped (format) | **1 UNIQUE wrong on held-out examples** (wrong_teacher_outside_scope) | — | scope-relative certificates can be wrong w.r.t. external truth: external tasks are scored by held-out pass rate |
| planning | 4 external blocksworld + 6 internal | 10 VALIDATED_PLAN | — | ≤ 535 expansions | easy at this size |
| repairs | 12 | 12 TEST_VERIFIED_PATCH | — | 1–58 candidate evaluations | easy at this size |

**MPS vs CPU** (MLP 256-256-64, one Adam step):

| Batch | CPU | MPS |
| --- | --- | --- |
| 16 | 0.20 ms | 0.42 ms |
| 128 | 0.24 ms | 0.43 ms |
| 1024 | 0.68 ms | 0.44 ms |
| 4096 | 1.73 ms | 1.48 ms |

**Rule:** MPS is used only for training batches ≥ 1024. Peak RSS was 473 MiB, and the pilot took 53 s of wall time.

**Semantics exposed and fixed before Stage 2:**
* structural fields produced by tools (size, color, r, key, count, node, deg) were missing from the lambda pools;
* `up(fst x)` was missing.

The program domains were widened from 19 to 35 mechanisms (scans, conditionals, counts, sorting, degree folds), and
every teacher is verified to be inside the declared scope.

## Stage 2–4 budget plan (derived from Stage 1 throughput: ≈ 1.4 s per Fresh solve, grids ≈ 3.6 s)

| Stage | Cap |
| --- | --- |
| Stage 2 (development, per experiment, ≤ 200 tasks × arms) | ≤ 6,000 s |
| Stage 3 (frozen confirmation; exact counts locked in the freeze commit before any seed is drawn) | ≤ 12,000 s |
| Stage 4 (long continual streams) | ≤ 5,000 s |
| Reserve | ≥ 10,000 s |

## Stage 2: capability development (development data only)

**Engineering fixes made during Stage 2** (all arms affected equally, all disclosed):
* **Lazy cost rows.** The eager (T + 1) × T prior matrix cost more than it saved.
* **Proposal budget 2 M executions,** so that Fresh solves what the others solve and solve counts are comparable.
  Budget abstentions still count as failures.
* **Folds run as separate calls.** A first run hit the 890 s cap after 2 folds; its ledger row was appended
  manually, marked KILLED_AT_CAP.
* **Regime memory** (experiment 6) after the surprise gate proved inert, with its signature keyed on input type only
  (an input + output signature made tiny contexts that were never refit).
* **Probe seeds** depend on the stream only (identical genomes had scored ±6% apart).

### Experiments 1 / 2 / 3 / 7: leave-one-domain-out (dev seeds 841, 842; 140 targets each × 6 arms; learning fit charged)

| Slice | Fresh | Fixed (d) | Learned | **Repr** | Placebo | Neural (exp 7) |
| --- | --- | --- | --- | --- | --- | --- |
| E3: withheld domain + mechanism (64) | 1.000 (64/64) | 0.768 (**60/64**) | 0.942 | **0.877 (64/64)** | 0.961 | 0.981 |
| E1: encoder / representation tasks (136) | 1.000 | 0.831 | 0.910 | **0.854** | 0.931 | 0.978 |
| all targets (140) | 1.000 | 0.791 (136/140) | 0.917 | **0.860 (140/140)** | 0.940 | 0.978 |

* **Repr vs Placebo:** 0.912 on E3 and 0.915 overall, in 2/2 seeds.
* **E2:** every withheld-mechanism solution was a composition absent from all source solutions; 13 of 64 used
  fold / scan / if.
* **Wrong answers:** 0 everywhere.
* **Source-task solving** (definition A, an extra curriculum): ≈ 900–1,500 G per fold.

### Experiment 4: meta-learning (dev)

The selected genome is α 0.5, λ 0.5, refit 2, with a meta-selection cost of 995 G.

| Domain | vs Fresh | vs 80f9cc2 |
| --- | --- | --- |
| tables | 0.975 (Fresh 17/18) | 0.985 |
| grids | 0.978 | 1.011 |

### Experiment 5: evolution (dev, 2 lineages per method, budget 6)

* **Best result:** 0.9895 vs the starting learner; most lineages returned the starting genome.
* **Measurement:** the noise flaw above was fixed.

### Experiment 6: continual (dev)

Long program stream: strings → graphs → strings (return) → tables.

| Learner | Total | Returning phase | New domain |
| --- | --- | --- | --- |
| Fresh | 520.9 | 83.2 | 274.5 |
| no gate | 673.1 | 68.1 | **437.2** (negative transfer) |
| surprise gate | 693.5 (never fired) | 68.2 | 437.3 |
| **regime memory** | **504.5** | **68.1** | **274.8** |

World track, long streams (2,000 steps):

| Agent | Return | Brier | Delay, new / returning goal | Compute |
| --- | --- | --- | --- | --- |
| N1 | **387.8** | **0.046** | 12–16 | 20.7 G |
| fixed-model | 274.8 | 0.159 | 70–90 | 0.14 G |

N1 shows no retention benefit for returning goals.

### Planning and repairs (dev)

* **Planning:** online heuristic weights gave **identical** expansions. Each domain has a single goal predicate, so
  per-predicate weights only rescale the heuristic; the learner design is degenerate.
* **Repairs:** the online mutation prior gave no gain (182 vs 168 evaluations, 23/24 verified in both arms).

## Stage 3 FREEZE (this commit; before any confirmation seed is drawn)

Frozen: all code at this commit, the learned-knowledge definitions, the genome, the regime-memory rule, the evolution
rules, and the thresholds below. Confirmation ranges are one-use and run once.

| Experiment | Confirmation (one-use seeds) | Arms | Predeclared verdict rule |
| --- | --- | --- | --- |
| 1 Representation | LODO `confirm_lodo` 7801–7805: 4 folds × (2 src + 2 tgt reps), budget 2 M; slice = encoder tasks | Fresh, Fixed (d), Learned, **Repr**, Placebo, Neural | **PROVED** if Repr total work (fit charged) < Fresh and < Placebo, pooled and in ≥ 4/5 seeds, with solves ≥ Fresh and 0 wrong. **PARTIAL** if it beats only one. Otherwise **NEGATIVE**. |
| 2 Mechanism discovery | the same runs; slice = withheld-mechanism tasks | the same | **PROVED** if Repr / Learned solves ≥ Fresh, every solution is a novel composition (vs all source solutions), and work < Fresh and < Placebo in ≥ 4/5 seeds. **PARTIAL** if novel solutions are found but the cost bar fails. |
| 3 Cross-domain transfer | the same runs; slice = withheld domain AND mechanism | the same; primary = Repr (pre-designated) | **PROVED** if Repr < Fresh and < Placebo (≥ 4/5 seeds, pooled), solves ≥ every control, 0 wrong. The Fixed DSL is compared at matched solves: if Fixed solves fewer it is not quality-preserving; if it solves equally and is cheaper, the verdict is at most **PARTIAL**. |
| 7 Closed-loop neural ranker | the same runs | Neural (training + inference charged, CPU per the Stage 1 rule) | **PROVED** if Neural < Fresh, < Placebo and < Learned in ≥ 4/5 seeds. |
| 4 Empty-library meta-learning | `confirm_online` 7806–7810: tables streams (an unfamiliar domain for the meta-selection), empty library | Fresh, Baseline-80f9cc2, Meta-learned (the dev-selected genome) | **PROVED** if Meta < Fresh and < Baseline in ≥ 4/5 seeds, with the meta-selection cost (995 G) also reported. |
| 5 Self-evolution | the evolution itself: 5 lineages × {dgm_branching, incumbent, random}, budget 6, on dev fitness streams; each lineage winner then on `confirm_evo` 7811–7815 untouched streams | every winner, Start-80f9cc2, Fresh | **PROVED** if ≥ 4/5 lineages of a method beat Start on the untouched streams (pooled, with 0 wrong), *and* that method beats random and incumbent. Search cost is included, with break-even reported both ways. |
| 6 Continual / forgetting | `confirm_cont` 7816–7820: 4-phase streams (strings → graphs → strings return → tables); long world streams | Fresh, Learner-no-gate, **Learner-regime-memory**; N1 vs fixed / reactive / model-free | **PROVED** if regime memory < Fresh and < no-gate in total work in ≥ 4/5 seeds, with return-phase work < Fresh and new-domain work ≤ 1.02 × Fresh. World track reported separately. |
| Planning / repairs | `confirm_plan_repair` (fresh instances: 12 external blocks 8–11 + 8 internal logistics; 24 repairs) | Fresh vs Online-learned | Report. A learner design that is degenerate on dev is reported as such. |

## Stage 3: frozen confirmation (one-use seeds, run once after cd02435)

### Experiments 1 / 2 / 3 / 7: LODO, `confirm_lodo` 7801–7805

* **Scale:** 20 fold runs; **2,100 target attempts** (350 targets × 6 arms) plus 560 source tasks.
* **Integrity:** **0 wrong, 0 detector flags** in every arm; D4 held for every seed.
* **Work:** G retired instructions, with learning fit charged.
* **Source-task solving** (definition A, an extra curriculum): 21,024 G. **Marginal fitting:** 207 G.

| Slice | Fresh | Fixed (d) | Learned | **Repr** | Placebo | Neural (exp 7) |
| --- | --- | --- | --- | --- | --- | --- |
| E3 withheld domain + mechanism (160) | 9,500.7 (159) | 7,443.5 (**149**) | 9,148.7 (159) | **8,571.7 (159)** | 9,361.9 (159) | 9,481.6 (159) |
| E1 encoder / representation tasks (340) | 16,149.0 (339) | 13,640.7 (339) | 15,253.4 | **14,058.8 (339)** | 15,623.3 | 15,948.1 |
| all targets (350) | 17,235.8 (349) | 13,845.8 (339) | 16,347.5 | **15,075.6 (349)** | 16,790.5 | 17,003.2 |

**Per-seed comparisons (5 seeds):**

| Comparison | E1 | E3 |
| --- | --- | --- |
| Repr < Fresh | 5/5 | 5/5 |
| Repr < Placebo | 5/5 | 5/5 |
| Learned < Placebo | 5/5 | 5/5 |
| Neural < Fresh | 5/5 | 3/5 |
| Neural < Placebo | 0/5 | 1/5 |
| Neural < Learned | 0/5 | 0/5 |
| Repr < Fixed | 0/5 | 0/5 (but Fixed loses 10 solves) |

**E2 novelty:** 159/159 withheld-mechanism solutions are compositions absent from every source solution, and 36 use
fold / scan / if. Fresh finds the same novel solutions.

### Experiment 4: `confirm_online` 7806–7810 (tables, an empty library)

| Arm | Solved | Work vs Fresh |
| --- | --- | --- |
| Meta-learned | **45/45** | **+14% to +42%** in every seed |
| Fresh | 39/45 | — |
| 80f9cc2 baseline | 39/45 | ≈ Fresh |

### Experiment 5: self-evolution

* **Lineages:** 15 (5 × {dgm_branching, incumbent, random}).
* **Search cost:** ≈ 22.3 T instructions.
* **Development fitness:** winners are 0.9896–1.0023 of the start.
* **Untouched `confirm_evo` 7811–7815:** every winner is within ±0.5% of Start-80f9cc2, and Start itself costs *more*
  than Fresh in 4/5 seeds (182.9 vs 190.3 … 206.0 vs 218.6). No method beats random.

### Experiment 6: `confirm_cont` 7816–7820 (strings → graphs → strings return → tables)

| Learner | Total | Return phase | New-domain phase | Solved |
| --- | --- | --- | --- | --- |
| Fresh | 2,710.0 | 411.8 | 1,499.6 | 192/200 |
| no gate | 3,217.1 | 336.5 | 2,075.2 | **199/200** |
| **regime memory** | **2,612.1** | **336.4** | **1,499.4** | 192/200 |

* **Regime memory:** below Fresh 5/5, below no-gate 5/5, return-phase work below Fresh 5/5 (≈ 0.82×), new-domain
  work ≤ 1.02 × Fresh 5/5.
* **World, long streams (5 one-use seeds, 2,000 steps):**

| Agent | Return | Brier | Delay, return / new goal | Compute |
| --- | --- | --- | --- | --- |
| N1 | **391.4** | **0.039** | **15.4 / 19.6** | 20.7 G |
| fixed-model | 267.8 | 0.178 | 94.1 / 132.9 | 0.14 G |
| reactive | 89.0 | 0.042 | — | — |
| model-free | 55.2 | 0.050 | — | — |

### Planning and repairs: `confirm_plan_repair`

* **Planning:** 20/20 VALIDATED_PLAN in both arms, with **identical** expansions (21,820). The learner is
  degenerate, because each domain has a single goal predicate.
* **Repairs:** 23/24 TEST_VERIFIED_PATCH in both arms (one public-fit-only patch in each). The online prior uses
  181 vs 221 candidate evaluations (−18%), and instructions 6.9 vs 7.0 G (−1.4%).

## Stage 4: long-duration continual study (run once, fresh instances; development-grade, single runs)

**6-phase program stream** (53 tasks: strings → graphs → tables → strings return → graphs return → grids; empty library):

| Learner | Total | strings | graphs | tables (new) | strings (return) | graphs (return) | grids (new) | Solved |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fresh | 2,009.4 | 83.2 | 159.4 | 275.7 | 73.9 | 117.2 | 1,300.0 | 51/53 |
| regime memory | 2,005.4 | 82.3 | 165.1 | 275.7 | **61.9** | 120.8 | 1,299.5 | 51/53 |
| no gate | **1,963.0** | 82.3 | 173.2 | 427.6 | 61.9 | 109.2 | **1,108.8** | **53/53** |

**Reading:**
* Regime memory retains a returning regime (−16% on the strings return) and prevents negative transfer (tables =
  Fresh).
* It also **blocks the positive transfer** the ungated learner gets on grids (−15%).
* Over this longer stream the ungated learner is cheapest overall, and it solves 2 more tasks.

**World stream** (10,000 steps; noise 0.15, slip 0.1, hazard 1/200):

| Agent | Return | Brier | Delay, return / new goal | Instructions |
| --- | --- | --- | --- | --- |
| N1 | **1,995** | **0.044** | **15.0 / 18.3** | 110 G |
| fixed-model | 1,201 | 0.177 | 130 / 142 | 0.7 G |
| reactive | 337 | 0.033 | 647 / 438 | 0.2 G |

**External PROSE ledger** (34 tasks, run once; separate from internal confirmations): Fresh and Repr are
**identical**. Each gives 5 exhaustive_UNIQUE (in-scope); 4 pass every held-out example, and 1 UNIQUE is wrong on
held-out examples (scope-relative). Work is 101.7 vs 101.5 G. Internal experience gives no external gain; the
language covers only ≈ 15% of these tasks.

## Capability & Domain Proof Matrix

Work ratios are against the strongest **quality-preserving** control. Discovery cost under definition A means the
source tasks are an extra curriculum; under mandatory work they are part of the workload, and only marginal fitting
counts.

| Capability / Experiment | Domains tested (internal + external) | Held-out solve / return | Total work vs strongest control (excl. & incl. discovery cost) | Independent-run repeatability | Certificate / verification class | Final verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 Representation discovery | strings, tables, grids, graphs (LODO) + PROSE | 339/340 (= Fresh); PROSE 4/34 (no gain) | excl.: 0.871 vs Fresh, 0.900 vs Placebo, **1.031 vs the designed Fixed DSL (equal solves)**. Incl. definition A: not repaid (≈ 3.6k tasks to break even); mandatory work: +207 G of fitting, repaid | 5/5 seeds | exhaustive_UNIQUE (Checker v4), 0 wrong | **PARTIAL**: beats Fresh and Placebo, not the hand-designed fixed DSL; "representation" means selecting among declared encoders, not inventing new ones |
| 2 Mechanism discovery | the same 4 domains (withheld mechanisms) | 159/160 (= Fresh) | 0.902 vs Fresh, 0.916 vs Placebo | 5/5 | exhaustive_UNIQUE, 0 wrong | **PARTIAL**: 159/159 solutions are novel compositions (36 use fold / scan / if) found by bounded search, and Fresh finds the same. Experience makes discovery cheaper; it does not enable it |
| 3 Cross-domain transfer (withheld domain AND mechanism) | 4 domains, LODO (train 3, test the 4th) | 159/160 (= Fresh; Fixed DSL 149/160) | **0.902 vs Fresh, 0.916 vs Placebo** (Fixed DSL cheaper but loses 10 solves). Incl. definition A: break-even ≈ 3,600 tasks; mandatory work: repaid immediately | **5/5 seeds × 4 folds** | exhaustive_UNIQUE, 0 wrong, 0 flags | **PROVED** (under the frozen rule, within the declared finite scope, 4 internal program domains, −10%) |
| 4 Empty-library meta-learning | tables (unfamiliar to the meta-selection) | **45/45 vs 39/45** (Fresh, 80f9cc2) | **+14% to +42% work** vs Fresh / 80f9cc2; meta-selection cost 995 G | 5/5 seeds, more solves | exhaustive_UNIQUE, 0 wrong | **NEGATIVE** under the frozen work rule (a quality gain at a cost loss) |
| 5 Repeatable self-evolution (5 lineages × 3 methods) | strings + graphs | = Fresh on solves | winners ≈ start (±0.5%); the start costs more than Fresh in 4/5 seeds; search 22.3 T, **never repaid** | 15 lineages; no method beats random | exhaustive_UNIQUE, 0 wrong | **NEGATIVE** |
| 6 Continual adaptation / forgetting | program streams (4- and 6-phase) + SwitchGrid world | programs: 192/200 (= Fresh); world: return 391 vs 268 | program 4-phase: **0.964 vs Fresh, 0.812 vs no gate (5/5)**; 6-phase long stream: 1.002 vs Fresh, 1.022 vs no gate; world N1 +46% return at ≈ 150× compute | 5/5 (4-phase); single run (6-phase); world 10/10 + 5/5 + 1 long | exhaustive_UNIQUE (programs); CALIBRATED_PREDICTION (world: Brier 0.039–0.044 vs 0.18) | **PARTIAL**: regime memory removes negative transfer and retains returns, but blocks positive transfer over longer streams. N1 change detection is strongly positive in the world track |
| 7 Closed-loop neural ranker | 4 domains (LODO) | 349/350 (= Fresh) | 0.987 vs Fresh, **1.013 vs Placebo, 1.040 vs count prior** (training and inference charged; CPU per the Stage 1 measurement) | loses to Placebo in 5/5 (E1) | exhaustive_UNIQUE, 0 wrong | **NEGATIVE** |
| Planning (domain 5) | blocksworld (external, 8–11 blocks) + logistics (internal) | 20/20 VALIDATED_PLAN | 1.000 (identical search) | — | VALIDATED_PLAN (independent simulator) | **NEGATIVE** (the learned heuristic is degenerate in single-goal-predicate domains) |
| Python repairs (domain 6) | 6 bug families, 24 tasks | 23/24 TEST_VERIFIED_PATCH (both arms) | 0.986 instructions, 0.82 candidate evaluations | single confirm | TEST_VERIFIED_PATCH (held-out oracle, separate sandbox) | **INCONCLUSIVE** (a small effect; not predeclared as a claim) |

## Decisive milestone

**"Experience from several domains helps NEXUS learn genuinely unfamiliar mechanisms in another domain, with less
total work, while preserving answer quality, and this repeats across independent runs."**

* **Supported within this setting.** Experiment 3 meets its frozen rule. Trained on 3 program domains and tested on a
  withheld 4th domain's withheld mechanisms:
  * the representation prior cuts total work by **9.8% vs Fresh and 8.4% vs a size-matched permuted history**;
  * it makes **0 wrong answers** under exhaustive Checker v4 certificates at an identical declared scope;
  * it solves as many as the strongest quality-preserving control;
  * this holds in **5/5 independent seeds × 4 held-out folds**.
* **It does *not* establish:**
  * cost advantage over a hand-designed fixed prior (cheaper, but it loses 10 solves);
  * any gain when the source tasks are an extra curriculum (≈ 3,600-task break-even);
  * any gain on the external PROSE benchmark;
  * gains for meta-learning, neural ranking or autonomous evolution, all of which were negative;
  * generalisation beyond one finite language and checker.
