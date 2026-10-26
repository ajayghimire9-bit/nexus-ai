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
