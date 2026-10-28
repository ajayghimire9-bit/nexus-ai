# NEXUS mi — Structural Learning-Method Invention (register-hypothesis procedures)

Status: NOT LOCKED (exploration workflow; validation and confirmation one-use). Branch `codex/nexus-data-engineering`, starting
revision `bf53905` (X7 at its reporting endpoint; owner choice 2026-10-28: finish X7, then invent from the current HEAD).

## 0. Pre-registration (committed before any discovery run)

### 0.1 Scope, budget, protection

* Target this round: **learning-method invention (Target 2)** — NEXUS generates the procedure by which its lifecycle learner
  constructs register-update hypotheses. **Target 1 (solution-method invention with reusable helpers) is not run this round**
  (owner direction: prioritise learning-method invention; budget). Per-task learned machines are "new programs for a particular
  task" only.
* Budget: grant `GRANT-NEXUS-METHOD-INVENTION-18000S` recorded once (`artifacts/mi_grant.json`; owner answer: add 18,000 s to the
  balance): 32,975 s available at bf53905; profiling used 603 s. CPU only; ≤ 900 s per call (`scripts/mi_exec.py`, rows `mi-*`).
* Protection: 912 protected files, 157 ba, 74 oc, 390 frozen sc files and all x7 artifacts unchanged (manifests re-verified at
  every stage). The checker kernels, the episode generator (`mi_ocean`), the oracle, the evaluator (held-out exactness), the
  acceptance check (ba_accept) and the meters are outside the editable surface.

### 0.2 Profile and headroom (development data, `artifacts/mi_dev/profile.jsonl`, 80 episodes)

Strongest existing learner = the x7 lifecycle learner (learned ba growth policy from H0, reset-aware register search, full-space
fallback, bounded acceptance). Exact on held-out: K 20/20, MUL 11/20, ADDC 1/20, SUBH 0/20; 0 silent. Control learning and
acceptance cost ≈ 0 s; the register search dominates (3–10 s / episode) and its outcomes on unfamiliar families are almost all
**unsat** (the update is outside the hard-wired space: closure of {acc, x, 0, 1} under {+, −}, size ≤ 5). The consequential
component = the register-hypothesis procedure (`t7_repair.GRAMMAR5` + its use in `_search_register`). Headroom: 48 of 60
unfamiliar dev episodes unsolved.

### 0.3 The editable component and the invention mechanism

* Editable: the procedure that constructs the ordered register-update hypothesis space from primitives and from the problem's
  evidence (observed values). Representation: LPL programs (`src/nexus/mi_lpl.py`) with pools, terminals, literals 0–10,
  evidence-derived constants (small observed integers, near-integer ratios / differences), `combine` (+ − × ÷), general
  conditionals `(r if p < q else s)`, union / dedupe / sort / take / filter, bounded `repeat`, feature-conditioned branches,
  helper definitions and calls. This changes the computation of the hypothesis space, not a parameter of it.
* Fixed (identical for every arm): the established fast path (growth learner) run first, then a full-space stage in which only
  the hypothesis procedure differs (`src/nexus/mi_learner.py`, `LearnerMI`); the assignment engine (reset-aware backtracking),
  control learning, coverage and bounded acceptance.
* Supplied by Claude (disclosed): LPL statements, interpreter, generic random generator, generic mutation (insert / delete /
  replace / perturb / wrap in repeat / wrap in feature test / extract helper) and crossover operators, the seed = a transcription
  of the existing procedure (`SEED_BASELINE`, verified identical to GRAMMAR5 in order and content), the fitness rule. No external
  model proposes candidates (not model-assisted). Once discovery starts, no human or Claude edit to any candidate; the winner is
  chosen by the rule in `scripts/mi_discover.py`.

### 0.4 Arms (equal discovery budgets)

| arm | how its procedure is obtained | discovery budget |
|---|---|---|
| baseline | the existing hard-wired procedure (strongest existing learner) | none |
| invented | `evolve`: tournament mutation / crossover with lineage from the seed + random programs | 24 candidate evaluations |
| random_struct | random structural search: random LPL programs and the seed with random edits, no selection-driven iteration | 24 |
| params | parameter tuning only: closure size bound {3, 5, 7, 9} × register-search seconds {2, 4, 8, 60} (no new operator) | 24 |
| direct | equal-budget direct synthesis: the full primitive closure (acc, x, 0–10, + − × ÷, conditionals of pairs; capped 3,000) per task; no reused invented procedure | none |

Discovery pool: 12 dev episodes (MUL / ADDC / SUBH × 4) from `mi/disc` that the shared fast path does not accept; fitness =
exact count − 0.001 × CPU s, 8 s cap per episode. Selection: each search arm's top 3 by discovery fitness re-evaluated on a
separate selection pool (12 failing `mi/sel` episodes, 20 s cap); winner = best selection fitness. Winners frozen
(`artifacts/mi_freeze.json`).

### 0.5 Validation, confirmation, decision rules

* Validation (`mi/val`, one-use, 80 fresh episodes: K / MUL / ADDC / SUBH × 20; arms baseline, invented): **gate** invented exact
  on dev-unfamiliar ≥ baseline + 10, on K ≥ baseline − 1, silent ≤ baseline + 1. No revision: a failed gate is the result.
* Confirmation (`mi/test`, one-use, 300 fresh episodes: K 60; MUL / ADDC / SUBH 30 each; **withheld** SCL `acc·c + x`, AVG
  `(acc + x)/2`, MAX `x if acc < x else acc` 50 each — generator fixed now, never run by any learner before this; arms baseline,
  invented, random_struct, params, direct). Per-episode full-space cap 15 s for every arm; task memory reset per episode.
* Rules: **R1** invented vs each other arm on withheld — supported iff invented-only > other-only with exact one-sided sign test
  p ≤ 0.05; **R2** the same on dev-unfamiliar fresh; **R3** K: invented ≥ baseline − 2. Learning curves: exact within query budgets
  (500 … 8,000) and CPU budgets (2 … 40 s); fully loaded cost = fast path + full space + amortised discovery CPU.
* Substantiveness: complete winner source and lineage; behavioural diff (hypothesis-space contents vs GRAMMAR5); component
  ablations on the selection pool (each generated statement removed in turn).
* Novelty levels to be reported separately: new program for a task / reusable method new to NEXUS / materially different from the
  compared algorithms / research-novel (needs a prior-art review — not claimed).
* Budget estimate: discovery ≤ 7,000 s, selection ≤ 800 s, validation ≤ 2,000 s, confirmation ≤ 14,000 s; reserve ≥ 8,000 s.

### 0.6 Disclosed revision before any winner was selected (development data only)

Discovery run 1 (`artifacts/mi_dev/run1/`): the seed solved 0 / 12 discovery episodes (25 s); every other candidate also scored 0,
and the CPU tie-break then favoured degenerate procedures (hypothesis spaces of 1–4 expressions, 0.04 s), so `evolve` collapsed
(24 / 24 evaluations at 0). Stopped after 1 random_struct evaluation (interrupted call charged, 60 s upper bound). Revision (generic,
applied identically to all three search arms, which restart from zero as run 2): fitness = exact episodes + 0.5 × mean fraction of
register searches explained by the procedure's space (learner-side evidence, no evaluator information) − 0.0001 × CPU s. Nothing
else changed.

## 1. Results (validation gate NOT passed; the confirmation on withheld families stays closed)

| stage | outcome |
|---|---|
| Discovery run 1 | collapsed (fitness flaw; all candidates 0 / 12) — preserved, negative |
| Discovery run 2 (24 evaluations per arm, 12-episode pool) | best: evolve 3 / 12, random_struct 2 / 12, params 1 / 12, seed 0 / 12; 0 silent everywhere |
| Selection (12-episode pool) | evolve #17 2 / 12, random_struct #18 2 / 12, params (size ≤ 9, 4 s) 2 / 12 |
| **Validation** (80 fresh dev episodes, one-use) | invented dev-unfamiliar **19 / 60** vs baseline **10 / 60** (9 : 0 discordant, p = 0.002; ADDC 12 vs 3, MUL 7 vs 7, SUBH 0 vs 0); K 19 / 20 both; 0 silent both — **gate (≥ baseline + 10) NOT passed by one episode** |
| Confirmation (300 episodes incl. withheld SCL / AVG / MAX) | **not run** (pre-registered: no revision; the confirmation needs a passing gate) |

Verdicts (tested setting): learning-method improvement on unfamiliar dev mechanisms — **inconclusive** (real paired gain on fresh
dev episodes, below the pre-registered margin); generalisation to withheld mechanism families — **not tested**; superiority over
parameter tuning and random structural search — **not established** (equal on the selection pool; those arms were not in the
validation by design); learning-algorithm invention — **not shown**.

## 2. The invented procedure (complete executable program, `artifacts/mi_dev/select_evolve.json` → `winner.prog`)

Lineage: #17 = crossover(#12[:13], #15[10:]); #12 and #15 are mutation chains from the seed (#0) and the early random programs
(#1, #2) under tournament selection; every edit is recorded in `artifacts/mi_dev/disc_evolve.json`. No human or Claude edit.

```
def h0:
  if n_trans >= 10:
    combine P2 P0 P1 /          # guarded division terms
  else:
    dconsts P3 int_diffs        # constants = near-integer differences between observed register values
  union P2 P2 P3
def h0b:                         # inherited from a parent, never called
  combine P3 P0 P0 -
  union P1 P2 P3
main:
  terms P0 [acc, x]; lits P1 [0, 1]; union P0 P0 P1
  combine P2 P0 P0 +; call h0
  combine P3 P2 P0 +; union P3 P3 P4; combine P4 P0 P2 +; combine P5 P0 P2 -; union P4 P4 P5; union P3 P3 P4
  union P0 P0 P2; union P0 P0 P3
  combine P4 P0 P2 +; combine P5 P0 P2 /; union P4 P4 P5; union P3 P3 P4; union P0 P0 P2; union P0 P0 P3
  dedupe P0 P0; sort P0 P0 size; ret P0
```

Behavioural difference from the existing procedure: the hypothesis space is data-dependent (constants mined from the problem's
own observations when the problem has < 10 transitions), drops the size-3 `−` layer of the seed, closes `+` a second round (sizes
up to 9) and adds division terms; 102 expressions on an empty context vs 53. Component ablation (dev pools disc + sel, 24 episodes,
after the freeze; `artifacts/mi_dev/ablation.json`): frozen 5 (all ADDC); seed 0; without `call h0` 3; h0 = evidence constants only
6; h0 = division only 0; without main-level division 5 (−30 % CPU). The contributing generated components are the evidence-derived
difference constants and the deeper `+` closure; the generated division terms contribute nothing.

Attribution: supplied by Claude — LPL language, interpreter, primitives (incl. the `dconsts` evidence miners), generic operators,
seed transcription, fitness and selection rule, the fast path and assignment engine (reused); synthesised by the discovery search —
the program above (which primitives to compose, the feature-conditioned branch, the helper, the closure structure); no external
model. Novelty level: a new procedure for NEXUS's own learner, i.e. "a reusable method new to NEXUS" at most — and only on
unfamiliar dev mechanisms of one kind (additive constants); not shown materially different in effect from parameter tuning or random
structural edits; not research-novel (mining constants from data is a known program-synthesis heuristic; no prior-art review done).

## 3. Cost

mi ledger rows 3,731 s (profile 603, discovery run 1 ≈ 86, run 2 1,271, selection 700, validation 546, ablation 307, other ≈ 220);
remaining 29,244 s. Validation CPU: invented 434 s vs baseline 351 s (+24 %) for +9 exact episodes; queries 56,118 vs 50,561.

## 4. Next experiment (recommendation)

The bottleneck is the discovery signal, not the language: 12-episode pools give fitness differences of one or two episodes, so
selection cannot separate evolve from random edits or parameter tuning. Next: a larger, cheaper discovery pool (≥ 60 episodes with a
2 s cap), candidates that must generalise across all three dev families to score (per-family minimum), and the params and
random_struct winners included in the one-use validation, with the same frozen withheld confirmation design.
