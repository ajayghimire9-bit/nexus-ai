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
