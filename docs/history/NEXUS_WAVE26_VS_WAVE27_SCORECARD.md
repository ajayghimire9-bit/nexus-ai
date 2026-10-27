# Wave 26 vs Wave 27 scorecard (2026-10-26)

**Engines.**
* **Wave 27** = `codex/wave27-robust-architecture`: the locked engine `e7daf13`, recorded in `f23fb07` and later.
* **Wave 26** = the per-phase branches `codex/wave26-phase{4,5,6}-*`.

**Design.** Every Wave 27 primary confirmation used fresh one-use seeds with the Wave 26 generators, scoring
and gates unchanged. Every unit was replayed identically in a fresh process (`PYTHONHASHSEED=271828`).
Details are in `docs/NEXUS_WAVE27_ROBUST_ARCHITECTURE.md`.

## What changed in the architecture

1. **Epistemic ladder.**
   * CANDIDATE → PROBATIONARY → CONSOLIDATED (core) → DEMOTED.
   * Consolidated schemas are certified in a core tier, after the base tier and before the union synthesis
     scan.
   * Every core-tier and library-tier answer is audited with one charged oracle call. A single falsifying
     audit demotes a consolidated schema.
2. **Cross-task MDL and falsification admission.** No schema transfers unless it survives an active
   falsification probe or is certified on ≥ 2 tasks, and it must compress.
3. **Contract-signature index.** Proved postconditions (cardinality bound, membership predicate, distinctness),
   closed under sub-multiset maps, prune tools and synthesis candidates before enumeration in every provable
   tier.

## Primary confirmations (fresh seeds)

| Place Wave 26 failed | Gate | Wave 26 | Wave 27 |
| --- | --- | --- | --- |
| **Phase 4 router** | ≥ 80% routed per kind | PASS (90/90) | PASS (90/90) |
| **Phase 4 F reuse** | later encounters cheaper in ≥ 80% of streams | F 4/10; mean ≈ 64k → 330k | F **6/10**; mean **34.2k → 17.8k** |
| Phase 4 S / Sort reuse | same | S 67k → 48k; Sort 170k → 40k | S 6/10, 17.9k → 25.7k; Sort **9/10**, 3.9k → 1.6k |
| Phase 4 overall | | **FAIL** | **FAIL** |
| **Phase 5 revisit** | ratio < 1 at lags 5, 10, 20 | **FAIL** (1.098 / 1.016 / 0.985) | **PASS** (0.663 / 0.707 / 0.907) |
| Phase 5 interference | ≤ 10% | PASS (7.3%) | **FAIL (14.6%)** |
| Phase 5 drift retirement | all retired, 0 false certificates | PASS (15/15) | PASS (13/13) |
| Phase 5 overall | | **FAIL** | **FAIL** |
| **Phase 6 Experienced vs Placebo/Fresh, cost** | cheapest in 5/5 orderings | 3/5 (Wave 26 ran on sealed B + ARC) | **4/5** (held-out synthetic) |
| Phase 6 slope | steepest in 5/5 | 0/5 | 2/5 |
| Phase 6 Placebo library | — | 1–2 coincidental schemas; cheaper than Experienced in 2/5 | **0 schemas in 5/5**; cost = Fresh ± 0.1% |
| Phase 6 overall | | **FAIL** | **FAIL** |
| G_soundness (false certificates) | 0 | 0 | 0 |
| G_replay | identical | PASS | PASS (15/15 units) |

## Secondary: `wave27_paired_ablation` on the sealed splits (post-lock, owner override; a second pass, not unseen data)

| Split | Measure | Wave 26 | Wave 27 |
| --- | --- | --- | --- |
| Group A (3001–3010, 100 tasks) | solved / repaired | 10 / 10% | 10 / 10% |
| | mean work, first → second encounter | 1.34M → 3.44M | **0.99M → 2.46M** (≈ −28%) |
| | errors / false certificates | 0 / 0 | 0 / 0 |
| | schemas with positive net benefit | 1 | 1 (consolidated) |
| Group B + ARC (2 tasks per seed, orderings 6001–6005) | Experienced cheapest | 3/5 | **5/5** |
| | evaluation cost, Experienced / Fresh / Placebo | 16.8M / 47.6M / 11.7–49.2M | 17.5M / 61.0M / 61.0–62.5M |
| | solved per arm (of 40) | 10 / 10 / 10 | **0 / 2 / 2** |
| | slope wins | 0/5 | 0/5 |
| | false certificates | 0 | 0 |

### Regression on Group B + ARC solved count

Read from per-task aggregates only (RULE 1). In Wave 26, 9–10 Group B tasks were answered correctly through
the probationary-library route. In Wave 27, the library-route audit (one oracle call on a reordering of the
query) falsified 8–10 of those certificates:
* After the audit pair was added, the tiers no longer produced the same UNIQUE answer.
* No hypothesis in the tiers fits the public pairs plus a reordered input.

So the Wave 26 answers were correct on the query without a robust supporting hypothesis, and Wave 27 withdraws
them. This trades coverage for soundness. Both waves have 0 false certificates, so it is not a false
certificate. But the reduced Experienced cost on Group B + ARC partly reflects certificates withdrawn after
cheap audits, not cheaper successful reasoning. **It must not be read as a transfer win.**

## What the evidence now supports

* **Sound, scalable pruning works.** The contract index cut absolute work 2–20× on the synthetic phases and
  about 28% on sealed Group A, with 0 false certificates everywhere.
* **Memory makes revisits cheaper.** The Phase 5 revisit gate passed at every lag, and F reuse became
  cheaper than invention. Both failed in Wave 26.
* **The Placebo problem is fixed.** Noise worlds no longer populate the library (0 / 5, against 1–2
  coincidental schemas per ordering in Wave 26).
* **Experienced beats a compute-matched Placebo and Fresh on held-out synthetic worlds in 4/5 orderings**,
  but not 5/5.

## What it does not support

* **No full gate passes.** Phases 4, 5 and 6 each still fail one locked gate:
  * Phase 4: F and S streams 6/10 against the 8/10 bar.
  * Phase 5: interference 14.6% against 10%.
  * Phase 6: cost 4/5 and slope 2/5 against 5/5.
* **Learning-to-learn remains unestablished.**
  * The slope gate structurally favours an arm that starts expensive.
  * Experienced starts near its floor.
  * The held-out target worlds use the same 5 hidden schemas as the source worlds (in-distribution transfer).
* **No extra coverage on sealed out-of-grammar tasks.** Group A stays at 10%, and Group B + ARC lost its
  coincidentally correct library answers.

## Remaining bottleneck (one next experiment)

Phase 5 interference and the Phase 4 F/S per-stream misses share one cause. The **extended-binding (ΔB) and
core tiers certify over every retained or consolidated schema instantiation**, so a larger library makes
rebinding and core certification dearer. The two worst Phase 5 revisits (a ΔB world +1.16M; a pred world
+0.89M) account for about two-thirds of the interference.

**Next experiment:** index schemas by world-signature applicability. The proved postconditions already
computed per task tell, before enumeration, which schemas could possibly fit. So:
* ΔB would instantiate only schemas whose class signature is compatible with the task;
* the core tier would cap instantiations by a proved order-slot equivalence (comp-pred under a field order ≡
  Sort ∘ comp-pred when Sort is present).

Test on new seeds against the Phase 5 interference gate and the Phase 4 per-stream gate.
EOF
echo ok