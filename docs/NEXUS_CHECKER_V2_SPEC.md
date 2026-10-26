# NEXUS Checker v2: specification (written before implementation, owner-authorised 2026-10-26)

**Separation from v1.** v2 is a separately versioned checker, `src/nexus/checker_kernel_v2.py`. The pinned v1
kernel (`src/nexus/checker_kernel.py`, sha256 `5082402f…121e`) is not modified or replaced. v1 evidence is never
re-labelled by v2. All arms in one comparison use the same checker version.

**Independence.** v2 uses the Python standard library only and imports nothing from NEXUS. It has its own
interpreter, its own postcondition table and its own enumeration. Agreement between the prover's and the checker's
interpreters is never treated as evidence of correctness. The validation (§6) uses hand-derived cases, bounded
exhaustive property checks and adversarial evidence.

## 1. Types (JSON values only; tuples are not accepted)

| Type | Representation | Bounds |
| --- | --- | --- |
| Int | JSON integer (bool excluded) | \|v\| ≤ 10^6 |
| Bool, Str | JSON | Str length ≤ 32 |
| Record | object, string keys → scalar | ≤ 8 fields |
| List / Sequence | array | length ≤ 64 |
| Grid | array of equal-length arrays of Int colours 0–9 | 1 × 1 … 12 × 12 |
| ObjectSet (middle IR) | `{"objects": [{"color": c, "cells": [[r, c], …]}, …]}` | cells sorted; objects sorted by (min cell, colour); ≤ 144 cells |
| RelationGraph (middle IR) | `{"nodes": [n, …], "edges": [[a, b], …]}` | sorted, nodes ≤ 144, edges ≤ 2,048 |
| Counter (middle IR) | `{"counts": [[key, n], …]}` | sorted by key; ≤ 64 keys |

A value outside these bounds, at any intermediate step, is an execution **error**.

## 2. Operations

* **v1 list language, re-implemented:** F, S, Sort, comp (all cond / transform variants), proj, map_add / mul / mod,
  prefix_sum, running_max, diff, rotate, run_heads, group_count, and repeat (n ≤ 4).
* **Grids:**
  * `grid_coord {a, b, c, d}`: `out[i][j] = g[(a·i + b) mod H][(c·j + d) mod W]`, with integer params, |p| ≤ 12.
  * `grid_connect {moves: [[dr, dc], …], passable, seed, fill}`: cells of colour `passable` reachable from any
    `seed`-coloured cell by repeated moves (≤ 16 offsets, \|d\| ≤ 3) are recoloured `fill`; everything else is
    unchanged.
  * `grid_cellwise {table: [[c1, c2, c3], …], dr, dc}`: `out[i][j] = table(g[i][j], g[(i + dr) mod H][(j + dc) mod W])`.
    A missing table entry is an error, and a duplicate key in the table makes the spec invalid.
* **Middle-IR adapters** (typed composition `decode(g(encode(x)))`):
  * `enc_objects {conn: 4|8, background}`: Grid → ObjectSet (same-colour components);
  * `dec_objects {background}`: ObjectSet → Grid. The height and width come from the max cell + 1, unless
    `shape: [H, W]` is given;
  * `ir_objects_filter_size {min, max}`, `ir_objects_recolor {color}`, `ir_objects_keep_color {color}`:
    ObjectSet → ObjectSet;
  * `enc_counter {path}`: List → Counter; `dec_counter`: Counter → List of `[key, n]` pairs;
    `ir_counter_top {k}`: Counter → Counter (highest counts, ties broken by key);
  * `enc_graph {moves, passable}`: Grid → RelationGraph over passable cells (node = r·W + c, edges by moves);
  * `ir_graph_reach {seeds}`: RelationGraph → List of reachable node ids, sorted.
* **Unsupported:** any other op, or a known op with malformed parameters. **Unsupported means ABSTAIN**: a
  certificate is never weakened to fit a new representation.

## 3. Program and execution bounds

* Programs are chains of ≤ 4 ops (`max_depth` ≤ 4).
* Every op charges deterministic steps (cells, items or edges visited). One program application has at most
  100,000 steps; exceeding that is an error.
* One check may enumerate at most 3,000,000 chains and 2 × 10^8 steps in total. Exceeding either gives
  `ABSTAIN(budget_exhausted)`.
* **No wall-clock timeouts.** Verdicts are deterministic functions of the evidence.

## 4. Error semantics

An application that raises, violates a type or a bound, or exceeds its step bound yields the token `ERROR`.

* A program **fits** only if it produces exactly the expected output on every public pair. `ERROR` never matches.
* On the query, `ERROR` is a distinct answer, so a fitting program that errors on the query creates ambiguity.
* If every fitting program errors on the query, the result is `ABSTAIN(query_error)`.

## 5. Evidence and certificates

**Evidence** has `checker_version: 2`. Missing or other versions give ABSTAIN. The remaining fields are as in v1:
`public`, `query`, `claimed_answer`, `candidate`, `scope {kind, tools, max_depth}`, `lemmas`, `trace`.

**Lemmas.** The kinds are len_le, all, distinct and sorted, and they are defined **only for list ops**. The
preservation rules are v1's, re-derived independently. A lemma on a grid or IR op gives `ABSTAIN(bad_lemma)`.

**Labels:**
* `exhaustive_UNIQUE`: every chain of length ≤ `max_depth` over the declared tools that fits all public pairs
  gives the claimed answer. This holds relative to exactly the declared tools, depth, the representation set
  (the types above) and these execution semantics.
* `proposal_relative_UNIQUE`: the same, over a proposal scope. Reported as AGREEMENT_AMONG_PROPOSALS, never as
  exhaustive.
* `AMBIGUOUS`: `k` distinct query answers among fitting programs. `k` is exact for an exhaustive scope and
  "at least k" otherwise. The verdict returns **two concrete witness programs**, as tool-index chains, with
  their answers.
* `ABSTAIN(reason)`: malformed, unsupported, `candidate_fails`, `bad_lemma`, `budget_exhausted`, `query_error`,
  or `claimed_not_unique`.

**Invariance.** The verdict is invariant to the order of scope tools and of public pairs. This is tested.

## 6. Validation plan

* **Hand-derived cases:** small grids whose outputs are worked out by hand, for coord, knight connectivity,
  cellwise Z2 × Z2, and the adapters.
* **Bounded exhaustive property checks:**
  * all 2 × 2 binary grids × all coord params: identity params give identity; composition closure;
  * connectivity: king moves on an all-passable grid fill every cell; monotonicity in the move set;
  * `dec_objects(enc_objects(g)) == g` for all 3 × 3 binary grids;
  * group-table laws.
* **Adversarial evidence:**
  * a tampered answer;
  * a mis-cited lemma, and a lemma on a grid op;
  * an unknown op;
  * oversize and non-rectangular grids;
  * two observation-consistent programs that disagree on the query (must give AMBIGUOUS with both witnesses);
  * an all-ERROR query;
  * a wrong `checker_version`;
  * tool and pair permutations.
* **Regression only (not evidence of correctness):** v2's list semantics are compared with the frozen v1 on random
  cases.

**Freeze.** The v2 sha256 is pinned in `src/nexus/checker_kernel_v2.sha256` and verified by the independent runner
from a git object before any experiment.
