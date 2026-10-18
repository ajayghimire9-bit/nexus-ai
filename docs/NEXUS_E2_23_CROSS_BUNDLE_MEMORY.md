# NEXUS Evolution-2.23 — Cross-bundle calibrated strategy memory

Development source-only screen. Not a scientific result, not
learning-to-learn, and not AGI. E2.17 remains inconclusive. H17 is
untouched. Scores are `decide()` + `FakeStepModel` **proxies**. The
E2.22 task list is a frozen observed development set, not confirmation.

## Calibration (frozen before eval)

Leave-one-bundle-out on E2.8 `bundle{0,1}_train` only. Query 0→1 and
1→0. Predeclared accept rule: p95 of those nearest-neighbor distances.
No E2.22 shifted first-free numbers entered the threshold.

| Quantity | Within-source (E2.22) | Cross-bundle LOBO |
|---|---:|---:|
| Gate | 0.491 | **1.505** |
| Kernel / median NN | 2.549 pairwise | 0.366 LOBO NN |
| LOBO recall | 0.665 | **0.949** |
| False accept far +4σ | — | **0.000** |
| False accept zero | — | 0.500 |
| False accept coord-shuffle | — | 0.847 |
| LOBO queries | — | 1024 |

Far stays outside the gate (NN 5.11 / 8.45). Zero is accepted on
Pendulum (1.385) and refused on Acrobot (4.42). Coordinate-shuffled
queries are usually accepted: same-family z-score geometry is a weak
unrelated-state detector.

An open cross-bundle gate uses **hard nearest-neighbor** scores.
Source evidence: p95 ≫ median, so a median kernel gives mass ≈ 0 at
accepted neighbors and the gate cannot change `choose()`.

## Protocol

Base `cfc753a0`. Six proposals, two anchors, four free slots. Seed 7.
60 matched lookups. Wall 0.188 s. CPU 0.188 s. 0 env steps.

Methods: reset, persist, E2.22 fixed gate, cross-bundle + persist
fallback, cross-bundle + current-task-only fallback, ungated.

## Results

| Method | Dev FF | Shift FF | Collision | Dev retrieve |
|---|---:|---:|---:|---:|
| persist | **0.000** | 0.063 | 0.110 | — |
| reset | 0.915 | 0.617 | 0.110 | — |
| fixed gate (E2.22) | **0.000** | **0.000** | 0.110 | 0 |
| cross-bundle + persist fallback | 0.155 | **0.000** | 0.110 | 4 |
| cross-bundle + reset fallback | 0.311 | 0.617 | 0.110 | 4 |
| ungated | **0.000** | **0.000** | 0.110 | 4 |

Causal obs-only (frozen memory): stored retrieve at 1.216, zero
retrieve at 0, far fallback at 9.059. The gate now accepts the
familiar Acrobot neighbor that E2.22 refused.

`pend_store_2` first-free regret under hard cross-bundle retrieve is
0.310 (`977fff8a…`); persist stays 0 (`fde871fd…`). `acro_store_1`
ties persist at 0.

**Development success: false.** Cross-bundle calibration raised
source recall and made familiar retrieval happen. It did **not** beat
persist or ungated on first-free. Gating adds no selection value over
ungated (both shift 0; ungated familiar 0, gated familiar 0.155).

## Fallback audit

- Retrieval + persist fallback: retrieve fires on familiar; inner
  weights still help only when the gate is closed. When the gate is
  open, hard NN can override persist and lose.
- Retrieval + current-task-only fallback: worse (dev 0.311). Memory
  does not replace persist weights.
- No retrieval (persist / reset): persist remains the familiar winner.

## Research answer

**No.** Calibrated observation-aware memory does not improve
cross-bundle strategy selection beyond unconditional persistence or
ungated retrieval.

The obstacle is **planner-quality prediction**, not the old 0.491
cutoff. Source neighbors are now accepted and still point
`choose()` at a worse catalogue arm than persist. Similarity
estimation is also weak (84.7% shuffled false accept). Limited
source diversity is secondary: two bundles are enough to open the
gate and enough to demonstrate harm.

Do not widen the gate again. The smallest next change is a
consistency check on retrieved planner scores (retrieve only when
neighbor-arm scores agree), still source-only. A real-control
experiment is not justified until the proxy first-free no longer
loses to persist.

No collection. No E2.17 reuse. No n=10. H17 blocked.
