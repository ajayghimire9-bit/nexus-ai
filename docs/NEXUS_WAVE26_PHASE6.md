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

## Confirmation result (orderings 6001–6005; Sealed Group B 3011–3020 + external ARC 3021–3030, reduced subset)

* **Post-lock infrastructure change (disclosed).** The first launch was refused by the old loader on this
  branch. Before any seed was claimed, the 5-physical-file loader fix (`f7baac7`, cherry-picked as `086b683`)
  was applied. That fix touches `sealed_vault_loader.py` and its tests only; the science code is unchanged.
* **Runs.** Three checkpointed confirmation calls (742.9 s, 658.2 s, 346.2 s). Three fresh-process replay
  calls with `PYTHONHASHSEED=271828` (744.3 s, 759.1 s, 449.6 s): **5 / 5 ordering digests identical**.
* **Artifact.** `artifacts/wave26_phase6_confirmation.json`, sha256
  `564a44050621c9bb792f2c5752fcfbb41da2c205f42586298917dc8ee02e829e` (aggregates only).

| Ordering | Experienced | Fresh | Placebo | Experienced cheapest | Slopes E / F / P |
| --- | --- | --- | --- | --- | --- |
| 6001 | 16,815,190 | 47,565,596 | **11,897,710** | no | −30.1k / −82.1k / −21.2k |
| 6002 | 16,815,190 | 47,565,596 | 28,381,000 | yes | −30.1k / −82.1k / −51.3k |
| 6003 | 16,815,190 | 47,565,596 | 47,626,361 | yes | −30.1k / −82.1k / −82.1k |
| 6004 | 16,815,190 | 47,565,596 | **11,708,180** | no | −30.1k / −82.1k / −20.9k |
| 6005 | 16,815,190 | 47,565,596 | 49,188,837 | yes | −30.1k / −82.1k / −84.2k |

Every arm solved 10 / 40 sealed tasks in every ordering, with 0 false certificates and 0 errors. Source work:
Experienced 7.5–9.5M vs Placebo 7.5–9.9M (compute-matched).

| Gate | Result |
| --- | --- |
| Experienced cost < Fresh and < Placebo in 5 / 5 orderings | **FAIL** (3 / 5) |
| Experienced slope < Fresh and < Placebo in 5 / 5 orderings | **FAIL** (0 / 5) |
| 0 false certificates | **PASS** |
| G_replay (all 5 orderings) | **PASS** |

**Phase 6 overall: FAIL.**

**Reading.**
* Source experience lowers the cost of unseen sealed tasks about 65% relative to Fresh in every ordering.
* It does **not** beat a compute-matched Placebo reliably. In 2 of 5 orderings, the 1–2 schemas Placebo
  admitted from noise worlds (which fit by coincidence) were cheaper on the sealed tasks than Experienced's
  3 valid ones.
* The ordering of source worlds made no difference: Experienced reached the same 3-schema library every time.
* Fresh's cost falls fastest along the stream, because it starts highest.
* So what is shown is benefit from **library contents** (structure in the grammar that happens to fit), not a
  better learning procedure. Learning-to-learn is not established.
