# Wave 27 — robust memory, abstraction and certification architecture (locked before 4011–4015, 5011–5015, 6011–6015)

Branch `codex/wave27-robust-architecture` (from Wave 26 Phase 6, `da7d9b4`). Owner request 2026-10-26: upgrade the
core architecture in general rather than patch a single gate; then run a clean confirmation on the three places
Wave 26 failed on cost or transfer (Phase 4 F reuse, Phase 5 revisit lags, Phase 6 Experienced vs Placebo).

Code:
* `src/nexus/wave27_core.py`: the engine.
* `src/nexus/wave27_eval.py`: the Wave 26 task generators and loops, driven by the new solver.
* `scripts/wave27_confirm.py`: the driver.
* `tests/test_wave27_core.py`: 5 tests.

Only the solver and the library class differ from Wave 26. The task generators, world builders, scoring
functions and gates are reused unchanged.

## Architecture

### 1. Epistemic promotion and drift-demotion ladder

**States.** CANDIDATE → PROBATIONARY → CONSOLIDATED, and CONSOLIDATED → DEMOTED.

* **PROBATIONARY** schemas transfer across tasks and worlds, but stay under the Wave 26 union synthesis scan:
  the library, ΔB, ΔC and ΔM tiers must all agree.
* **Promotion to CONSOLIDATED** requires all of:
  * certified support on ≥ 2 distinct tasks;
  * 0 counterexamples;
  * positive net benefit = (support − 1) × discovery cost − class-verification cost − 1,000 work units ×
    expanded-AST size (4 nodes). Discovery cost is the fully loaded invention cost: the inventing task's
    work plus its class verification.
* **Core tier.** Consolidated schemas form a CORE tier consulted only after the base tier fails. Base-only
  tools come first, so the Occam priority is unchanged and a macro cannot pre-empt a base explanation.
  When the core tier gives a UNIQUE answer that survives its audit, that answer is certified there and the
  synthesis scan is skipped.
* **Audit (drift detector).** Every core-tier and every library-tier answer is audited with one charged
  oracle call on a reordering of the query.
  * If the certified hypotheses' representatives mispredict, the tier is re-certified with the audit pair.
  * A **counterexample** is declared only when the certified answer changes or loses UNIQUE status.
* **Demotion.** A single counterexample demotes a consolidated schema for good. It stays usable as a
  probationary schema under the union scan, but never returns to the core. A counterexample against a
  probationary schema blocks its consolidation. The task then falls through to the full ladder.

### 2. Cross-task MDL admission filter

A schema used by a certified ΔM answer is only a CANDIDATE: it does not transfer. It is retained
(PROBATIONARY) only if both conditions hold:

* **Evidence**, either:
  * it passes an active boundary-falsification probe (2 charged oracle calls on reorderings of the query and
    of a public input, which some certified chain using the schema must predict); or
  * it is certified on ≥ 2 distinct tasks.
* **Compression:** its summed MDL gain (pointer-coded outputs minus 4 bits per expanded-AST node, minus the
  schema's own description) is positive.

A coincidental one-off fit on a noise world fails the probe, because the oracle follows the real teacher.

### 3. Contract-signature index across all repair tiers

**Postconditions.** Every mechanism with a verified sub-multiset or permutation class carries postconditions
that are closed under any sub-multiset map:
* |out| ≤ k for head/tail k and S[k];
* every item satisfies p, for F[p] and comp-pred p;
* the output is distinct on a path, for first_occ.

**Why pruning is sound.** If every tool in a tier has a verified class, every later step of any chain
preserves these postconditions. So a tool whose postcondition is violated by some public output cannot occur
in any fitting chain, and is pruned before enumeration.

**Where it applies:**
* the base, core, library, ΔB (extended grammar), ΔC and ΔM tiers;
* inside the synthesis scan, on both candidate instantiations and partner mechanisms;
* when every public output is a sub-multiset of its input, projecting schemas are excluded from the core
  tier, using the Wave 26 contract-index argument.

**Where it does not apply (vault firewall).** Tiers containing a tool without a proved class are not
pruned. This covers Phase 5's opaque tools, which have empirical contracts only.

All index checks are charged on the single meter (`index_work_units`).

## Dev history (reusable dev seeds: Phase 4 721–725, Phase 5 streams 731–732, Phase 6 orderings 741–742)

**Run 1**
* **Phase 4:** F later mean 23.7k vs first 18.6k (Wave 26 locked code: about 330k vs 64k).
  * Streams with later encounters cheaper: F 5/10, S 5/10, Sort 6/10.
  * 1 false certificate, on a library-tier answer, the same "non-minimal teacher" mode as Wave 26.
* **Phase 5:** revisit ratios 0.53 / 0.65 / 1.10; interference 6.6%.
* **Phase 6:** Placebo's library stayed empty, so Placebo = Fresh. Experienced was cheaper in 1/2 orderings.

**Fixes before run 2**
* Credit support from any certified hypothesis of the winning tier, not just the first.
* Exclude projecting schemas from the core tier when provenance holds. One consolidated `all/proj` schema had
  disabled the index for the whole core tier.
* Audit library-tier answers too.

**Run 2**
* **Phase 4:** 0 false certificates; streams cheaper F 4/10, S 5/10, Sort 6/10.
* **Phase 6:** Experienced cheaper in 2/2 orderings.

**Fixes before run 3**
* Discovery cost = fully loaded invention cost (it had excluded class verification, so int-list schemas could
  never consolidate).
* An audit counterexample now requires the certified answer to change. Run 2 flagged a counterexample whenever
  the class *representatives* mispredicted, which demoted correct schemas.

**Run 3 (locked code)**

Phase 4:
* Router: ΔB 30/30, ΔC 30/30 (24 solved), ΔM 30/30.
* Deletion streams: 120/120 solved, 0 false certificates; 31 core-tier answers, 25 consolidations,
  1 demotion.

| Primitive | Mean work, first encounter | Mean work, later encounters | Streams with later encounters cheaper |
| --- | --- | --- | --- |
| F | 18.6k | 16.6k | 5/10 |
| S | 14.4k | 11.8k | 7/10 |
| Sort | 2.3k | 1.7k | 9/10 |

Phase 5:
* Revisit ratios: lag 5 0.544, lag 10 0.419, lag 20 1.055.
* Lag 20 is dominated by one world with no hidden mechanism (rebinding/recombination tasks, 2.6M → 2.8M), where
  there is no schema to remember.
* Interference 0.7%; drift-broken opaque contracts retired 5/5; 0 false certificates; 125/128 solved.

Phase 6:

| Ordering | Experienced | Fresh | Placebo |
| --- | --- | --- | --- |
| 741 | 1.228M | 1.536M | 1.536M |
| 742 | 79.2k | 84.1k | 84.0k |

* Experienced's slope is flatter (it starts near its floor), so the slope gate is expected to fail.
* 0 false certificates.

## Confirmation protocol (single shot, fresh one-use ranges, checkpointed per unit, then fresh-process replay with `PYTHONHASHSEED=271828`)

**Phase 4 — seeds 4011–4015.** Wave 26 Phase 4 generators.
* Gate (unchanged from Wave 26):
  * router ≥ 80% correct per fault kind;
  * per primitive: first encounters routed ΔM ≥ 80%, solved ≥ 80%, and later encounters cheaper than the
    first in ≥ 80% of streams;
  * 0 false certificates.
* Reported against Wave 26's 4001–4005: F/S/Sort mean work, first vs later.

**Phase 5 — streams 5011–5015.** Wave 26 Phase 5 generators: 18 base worlds, 36 visits, drift.
* Gate (unchanged):
  * revisit cost ratio < 1 for every lag in {5, 10, 20};
  * interference ≤ 0.10;
  * every drift-broken opaque contract retired, with 0 false certificates.
* Also reported: core consolidations, demotions and audit counterexamples.

**Phase 6 — orderings 6011–6015.** Wave 26 Phase 6 source worlds and arms.
* Evaluation is on 16 held-out synthetic target worlds per ordering (field-name seeds 700000 + 100 ×
  seed + j, disjoint from the source worlds), each arm learning online.
* Fresh is evaluated per ordering, because its target worlds differ.
* Gate (unchanged): Experienced cost < Fresh and < Placebo in 5/5; Experienced slope < Fresh and < Placebo in
  5/5; 0 false certificates.

**Standing gates.**
* G_soundness: 0 false certificates.
* G_replay: an identical digest for every unit.
* G_tycho: every row's itemised meter equals its total.

**Secondary, post-lock only: `wave27_paired_ablation`.** Run only after the three primary confirmations are
complete and recorded. Owner-authorised registry overrides, verifying the vault before any claim; aggregates
only.
* The locked engine runs once on Sealed Group A (3001–3010, full; Wave 26 Phase 4 sealed design).
* It also runs on Group B + external ARC: 2 tasks per seed, orderings 6001–6005, Fresh evaluated once with
  seed 0 (the Wave 26 Phase 6 sealed design).
* This is a side-by-side architectural comparison with Wave 26's recorded numbers. It is a declared second
  pass on those splits, not an unseen confirmation.

**Expected outcomes (declared before confirmation)**
* Phase 4: router PASS; F reuse likely below the 80%-of-streams bar (about 5/10 on dev), so the primitives gate
  is expected to FAIL.
* Phase 5: lags 5 and 10 below 1; lag 20 uncertain.
* Phase 6: cost gate plausible; slope gate expected to FAIL.

**Budget.** Owner grant of 28,800 s (2026-10-26), with ≤ 900 s per call. Before lock, 27,218 s remained
(Wave 27 dev used about 2,440 s).

Locked code sha256:
* `wave27_core.py` `7692ab66…5155`
* `wave27_eval.py` `77e688aa…0c72`
* `wave27_confirm.py` `36a5a59f…72b4`

## Primary confirmation results (locked `e7daf13`; fresh seeds; replays in fresh processes)

**Runs.**
* Phase 4: 181 s (one call).
* Phase 5: 703 s + resume call.
* Phase 6: 613 s (one call).

**Replays: 15 / 15 units identical.**
* Phase 4: 5 / 5. Phase 5: 5 / 5. Phase 6: 5 / 5.
* Disclosed incident: two Phase 6 replay calls ran concurrently and the second write erased the first
  call's results (6011–6013) from the artifact. Those results were restored from
  `runs/experimental/wave27/replay_p6a.log`, and their recorded digests were checked against the artifact.

**Artifacts (sha256)**

| Artifact | sha256 |
| --- | --- |
| `artifacts/wave27_phase4_confirmation.json` | `4f245068…21fd` |
| `artifacts/wave27_phase5_confirmation.json` | `53d9af1f…f773` |
| `artifacts/wave27_phase6_confirmation.json` | `68e3b3c3…e5e2` |

### Phase 4 (4011–4015) — **FAIL** (primitives gate)

**Router.** ΔB 30/30, ΔC 30/30 (27 solved), ΔM 30/30.

**Deletion streams.** 120/120 solved, 0 false certificates. 34 core-tier answers, 27 consolidations,
1 demotion, 83 audits passed and 1 counterexample.

| Primitive | Mean work, first → later (W27) | Streams with later cheaper (W27) | Mean work, first → later (W26, 4001–4005) |
| --- | --- | --- | --- |
| F | 34.2k → 17.8k | 6/10 | ≈ 64k → 330k |
| S | 17.9k → 25.7k | 6/10 | 67k → 48k |
| Sort | 3.9k → 1.6k | 9/10 | 170k → 40k |

* F reuse is now cheaper than invention on average, a reversal of Wave 26.
* Absolute costs fell 2–20×.
* The per-stream 80% bar is still missed for F and S.

### Phase 5 (5011–5015) — **FAIL** (interference gate)

| Lag | Revisit ratio, W27 | Worlds cheaper on revisit | Revisit ratio, W26 |
| --- | --- | --- | --- |
| 5 | **0.663** | 18 / 40 | 1.098 |
| 10 | **0.707** | 14 / 30 | 1.016 |
| 20 | **0.907** | 10 / 20 | 0.985 |

* **Revisit gate: PASS** (ratio < 1 at all three lags; it failed in Wave 26).
* Backward interference **14.6% > 10%: FAIL** (Wave 26: 7.3%).
  * Two revisits account for about two-thirds of the excess: a no-hidden-mechanism ΔB world (+1.16M) and
    a pred world (+0.89M).
  * The extended-binding tier certifies over every retained schema, so a larger library makes rebinding
    dearer.
* Retirement 13/13 drift-broken opaque contracts: PASS.
* 0 false certificates; 313/316 solved.
* 19 consolidations, 1 demotion.

### Phase 6 (6011–6015, held-out synthetic target worlds) — **FAIL** (cost 4/5, slope 2/5)

| Ordering | Experienced | Fresh | Placebo | Experienced cheapest |
| --- | --- | --- | --- | --- |
| 6011 | 714k | 1,326k | 1,325k | yes |
| 6012 | 305k | 2,026k | 2,026k | yes |
| 6013 | 1,181k | 4,174k | 4,174k | yes |
| 6014 | 750k | 577k | 575k | **no** |
| 6015 | 704k | 1,273k | 1,272k | yes |

* **The Placebo problem is fixed.** Placebo retained 0 schemas in every ordering, against 1–2 coincidental
  schemas in Wave 26. Its cost equals Fresh's to within 0.1%.
* Experienced retained 3 schemas, all consolidated. It was 1.8–6.6× cheaper than both controls in 4/5
  orderings.
* Slope wins: 2/5. Experienced starts near its floor, so its learning slope is flat.
* 0 false certificates; 14–16 of 16 solved per arm (all arms equal).
