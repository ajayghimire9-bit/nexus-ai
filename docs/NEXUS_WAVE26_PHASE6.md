# Wave 26 Phase 6 — learning to learn: Experienced vs Fresh vs compute-matched Placebo (locked before 6001–6005)

Branch `codex/wave26-phase6-meta-learning` (from Phase 5). Code: `src/nexus/wave26_phase6.py`, driver
`scripts/phase6_meta.py`.

## Design

* **Units.** 5 independent random orderings (seeds 6001–6005) of the same 10 source worlds. Each source world
  needs one hidden comprehension mechanism; there are 2 tasks per world.
* **Arms.**
  * **Experienced** solves the ordered source worlds with the Phase 4/5 router + synthesizer and carries its
    slot-level library forward.
  * **Fresh** has no source experience.
  * **Placebo** solves noise versions of the same source tasks (public outputs permuted across examples),
    cycled until its source work reaches Experienced's (compute-matched, at most 4 passes).
* **Evaluation.** All arms solve the same sealed evaluation stream and keep learning online.
* **Owner-approved reduced subset (2026-10-26).** The first 2 tasks by index from every sealed seed of
  Group B (3011–3020) and the external ARC 1D/2D grid family (3021–3030): 40 tasks per arm per ordering.
  The subset is outcome-blind. It was reduced because the full splits (about 3,000 task-solves) exceed the
  remaining budget about 4×.
* **Fresh reuse.** Fresh's evaluation does not depend on the ordering, so it is computed once (fixed seed 0)
  and reused for every ordering.
* **Sealed access.** Only through the token-gated loader (5 physical files hash-verified, plus the vault's
  virtual verification). Outputs are aggregates; errors are recorded by exception type only.

## Gates (orderings are the statistical units, n = 5)

* Experienced evaluation cost < Fresh AND < Placebo in 5 / 5 orderings (one-sided sign test p = 1/32).
* Experienced learning slope (least-squares slope of per-task cost over the stream) < Fresh AND < Placebo
  in 5 / 5 orderings.
* 0 false certificates.
* G_replay: an identical fresh-process digest for **every** ordering. If the budget does not allow all 5
  replays, G_replay is reported as INCOMPLETE, never PASS.

## Dev evidence (dev ordering 741, held-out synthetic evaluation worlds)

| Arm | Cost | Slope | Solved |
| --- | --- | --- | --- |
| Experienced | 782,885 | −29,897 | 6 / 8 |
| Fresh | 795,325 | −32,120 | 6 / 8 |
| Placebo | 795,325 | −32,120 | 6 / 8 |

* Experienced was 1.6% cheaper, but Fresh's slope was steeper.
* Placebo admitted nothing from noise worlds, so it equalled Fresh.
* 0 false certificates; 193 s.

**Expected to fail:** the slope gate, and likely the cost gate on unseen sealed mechanisms, given Phase 4
Group A (10% repaired).
