# Wave 32 (bounded, NOT LOCKED): empty-library procedure evolution with a stepping-stone archive

* **Branch:** `codex/wave32-hyperagent-archive`, from Wave 31 increment 3 (ed21c20).
* **Authorisation:** owner brief of 2026-10-26, within the remaining session grant.
* **Locking:** this protocol is committed before any evolution or test outcome.
* **Corrections to the brief:** the checker pin is `6ba0a268…`, not `b1d6c5d1…`. The 5-detector suite was first
  built and run in fa1c6fe.

## What may change and what may not

* **Editable (a typed, bounded genome; `wave32_archive.GENES`):**
  * search ordering (`order`: canonical / reverse / macros_last / short_first);
  * lemma policy (`lemmas`: none / all v2-verifiable);
  * proposal policy (`macro_first`, `macro_depth` 1|2);
  * active-probe policy (`probe_mut` 1–3, `probe_tries` 50 / 150 / 300);
  * anti-unification heuristics (`max_holes` 0|1, `min_support` 1–3, `cap` 10 / 40 / 200);
  * online library-update policy (`online` on / off).

  The genome is not arbitrary code. Unknown genes, or values outside the table, are rejected (tested).
* **Frozen:**
  * Checker v2 (`6ba0a268…`);
  * the sandboxed child and the evaluator;
  * the external `evaluator_work` meter (OS-counted retired instructions + evaluator kernel instructions + 5·10⁷
    per oracle query);
  * the certificate definition (exhaustive_UNIQUE over exactly G_P at depth 3, forced by the runner);
  * the splits and the detectors.
  * main and final_sealed are untouched.

## Episodes (the learning procedure under test)

* **Setup:** each episode is an online task stream that starts from an **empty library**.
* **Learning step:** after each task that the evaluator's checker labels exhaustive_UNIQUE (label only, never
  correctness), the child adds the certified candidate and rebuilds its library with the genome's heuristics.
  Every rebuild is metered.
* **What this isolates:** improvement in the *procedure*, separate from stored macros, because nothing is carried
  between episodes.

## Evolution

* **Data:** evolution domains are records, strings and graphs (increment-2 2-op cores; teacher depth 3). Fitness
  uses wave32 dev seeds 771–773; selection uses 774–775. The test domain is **grids**, never used before the test.
* **Fitness** (lexicographic, external meter only): wrong = 0 first, then max correct, then min `evaluator_work`
  (target work + learning rebuilds).
* **Archive:** Gen 0 = the current Wave 31 solver policy (`GEN0`). Each generation adds λ = 6 novel children,
  each mutated from a tournament-picked *archive* member, which keeps stepping stones and not only the elite.
  Lineage (parent id) is recorded, with ≤ 10 generations.
* **Admission:** a child enters the archive only if all 5 detectors are 0 and wrong = 0. One child per
  generation also gets a fresh-process replay (`PYTHONHASHSEED=1`), which must match. D4 integrity is checked
  around every generation, and a violation stops the run.
* **Champion:** the top 3 archive members by fitness are re-evaluated on selection seeds 774–775. The best is
  **Gen k**.

## Test (wave32 test 7201–7205, one use, claimed whole)

* **Data:** the held-out domain is grids, with streams of target_stream(seed, grids, n_per=3), starting from an
  empty library.
* **Arms:**
  * Gen 0;
  * Gen k;
  * Gen 0 with online learning off;
  * Gen k with online learning off. This ablation separates gains from search, probe and lemma policy from gains
    from the learning procedure itself.
* **Readouts:**
  * T1: 0 wrong and 0 detector flags in every arm.
  * T2: Gen k vs Gen 0 `evaluator_work` (total, and child-only), per seed and pooled, with correct and
    exhaustive counts and oracle calls.
  * T3: the online-learning contribution: (Gen k − Gen k without online) vs (Gen 0 − Gen 0 without online).
  * T4: a replay of one test seed for Gen k.
* **Expected ceiling, stated in advance:** under Checker v2 the kernel is about 98% of evaluator_work at depth 4
  (increment 3). The editable scope can therefore change only a few percent of total work at depth 3, and any
  improvement is bounded accordingly.

# Results (NOT LOCKED)

## Evolution (dev 771–773)

* **Scale:** Gen 0 + 10 generations × 6 children = 61 genomes (`artifacts/wave32_archive.json`, with full lineage).
* **Admission:** all 61 admitted. Every detector was 0 for every genome, all 11 replays matched, and D4 integrity
  held in every generation.
* **Fitness:** every genome was 126/126 correct with 0 wrong, so fitness was decided by work alone.
* **Best:** g1c2, found in generation 1, at 37.41 G vs Gen 0's 40.28 G (−7.1%). Its single mutation is
  `online: True → False`.
* **Archive pattern:** every genome near the top has online learning off, or learning made inert. Later
  generations found no further gain beyond noise.

## Selection (dev 774–775)

| Genome | Work | Note |
| --- | --- | --- |
| g1c2 | 24.38 G | champion |
| g4c2 | 24.38 G | online off |
| g6c1 | 24.38 G | online off |
| Gen 0 | 26.10 G | |

Champion: g1c2 = Gen 0 with online learning off.

## Test (held-out grids, wave32 test 7201–7205, claimed whole, run once; 120 tasks per arm, from an empty library)

| Arm | Correct / exhaustive / wrong | evaluator_work | Child (incl. learning) | Kernel | Detectors |
| --- | --- | --- | --- | --- | --- |
| Gen 0 | 120 / 120 / 0 | 59.20 G | 10.61 G | 48.54 G | all 0 |
| **Gen k (g1c2)** | 120 / 120 / 0 | **55.33 G (−6.5%)** | 6.75 G (−36%) | 48.53 G | all 0 |
| Gen 0, online off | 120 / 120 / 0 | 55.32 G | 6.74 G | 48.53 G | all 0 |
| Gen k, online off (= Gen k) | 120 / 120 / 0 | 55.32 G | 6.74 G | 48.53 G | all 0 |

* **Per seed:** Gen k / Gen 0 ranges over 0.922–0.941, with Gen k cheaper in 5/5 seeds. The replay (7203, Gen k)
  matched, and D4 held.
* **T1:** PASS.
* **T2:** Gen k is 6.5% cheaper than Gen 0, consistent over 5/5 seeds.
* **T3, the decisive readout:** the entire gain is the removal of online learning.
  * Gen 0 with online learning off equals Gen k to within 0.02%, which is the meter's noise floor (two identical
    genomes differ by 0.017%).
  * Online learning changed coverage on 0 of 120 tasks, and cost +7% (0.82 G of rebuilds + 3.1 G of macro-search
    overhead).
* **T4:** PASS.

## Reading

* **No learning-procedure improvement was found.** Within this bounded genome, the procedure evolution's best
  move was to *stop learning*. Under Checker v2 at depth 3:
  * the kernel is 82% of the work, and it is identical for every procedure;
  * the base grammar is already cheap to search;
  * learned macros only add search and rebuild cost.

  The archive, lineage and detectors worked as intended, and the loop optimised the external meter honestly. That
  includes finding the "do less" solution rather than gaming the meter.
* **This is a negative result about this regime, not about learning-to-learn in general.** It agrees with Wave 31
  increments 2 and 3: experience can only pay where proposal or verification cost is something experience can
  reduce.
* **What would change the picture:**
  * a sound class-enumerating Checker v3, about 19× cheaper verification (projected). The solver share would then
    rise, and proposal savings would matter;
  * verifiable algebraic pruning proofs (would cover 8.4% of the scope);
  * deeper or larger scopes.

  All of these need owner decisions, and v3 needs a RULE 2 authorisation.

---

# Targeted Wave 32 check under Checker v3 (protocol; committed before its outcomes)

* **Trigger.** The predeclared gate in the Wave 31 v3 matrix was met: on val_v3, Experienced-v3 was below Fresh-v3
  target-only in 5/5 seeds, with a pooled saving of −6.2%. That makes learned macro proposal a concrete policy lever.
* **Genome (`GENES_V3`):** as before, with v2 lemmas fixed to none (they are inert under v3) and an editable proof
  policy (`proofs`: none / all). Frozen: Checker v3 (pinned 1642721), matched G_P at depth 4, the sandbox, the meter
  and the detectors.
* **Gen 0:** `GEN0_V3`, the Wave 31 solver with no proofs and online learning ON.
* **Evolution:** Gen 0 + 4 generations × 4 children, from tournament-picked archive parents. Episodes are depth-4
  streams on records, strings and graphs, starting from an **empty library**, with fitness on dev 771–773. All 5
  detectors, D4 integrity and one replay run per generation.
* **Selection:** top 3 on dev 774–775.
* **Test:** one-use `wave32 test_v3` 7206–7210, on held-out grids (n_per = 3, an empty library).
* **Arms:** Gen k, Gen 0 learning ON, Gen 0 learning OFF, and Gen k learning OFF. Readouts are per seed and pooled;
  a replay of 7208 for Gen k must match.

## Results of the targeted v3 check (NOT LOCKED)

* **Evolution:** 17 genomes (`artifacts/wave32_v3_archive.json`). All were admitted, all detectors were 0, 5/5
  replays matched, D4 held, and every genome was 120/120 correct.
* **Selection (774–775):** the champion is **v4c3**, which is Gen 0 with `online: False`, `proofs: all` and
  `min_support: 2`.

**Test (held-out grids, one-use 7206–7210, 120 tasks per arm, from an empty library):**

| Arm | Correct / wrong | evaluator_work | Child | Checker |
| --- | --- | --- | --- | --- |
| **Gen 0, learning ON** | 120 / 0 | **86.11 G** | 18.81 G (incl. 0.89 G of rebuilds) | 67.05 G |
| Gen 0, learning OFF | 120 / 0 | 91.35 G | 24.05 G | 67.06 G |
| Gen k (v4c3) | 120 / 0 | 90.46 G | 24.08 G | 66.13 G |
| Gen k, learning OFF (= Gen k) | 120 / 0 | 90.44 G | 24.08 G | 66.11 G |

* **Per seed:**
  * Gen 0 ON / Gen 0 OFF = 0.928–0.950, so learning pays in 5/5 seeds;
  * Gen k / Gen 0 ON = 1.043–1.068, so Gen k is worse in 5/5;
  * Gen k / Gen 0 OFF = 0.989–0.991.
* **Checks:** the replay (7208, Gen k) matched, D4 held, and all detectors were 0.

## Reading

* **Under Checker v3, the online learning procedure pays on a held-out domain at matched exhaustive strength.**
  Gen 0 with learning ON is 5.8% cheaper than with it OFF, with rebuild costs included, 0 wrong, and an empty
  library at the start. This is the first verified net-positive *learning-procedure* effect in Waves 30–32. It is
  a within-stream effect: no source learning is charged, because there is none.
* **The procedure evolution did not find it, and selected against it.** On the evolution domains (records,
  strings, graphs) online learning did not pay, so the archive converged on learning OFF. That choice
  transferred badly: Gen k is 5.1% worse than Gen 0 ON on grids. Its only real gain is the generic proofs (−1%).
* **Disclosed confound:** the test streams use n_per = 3 repetitions per mechanism and the evolution streams use
  n_per = 2. More repetition gives a learned library more reuse, so part of the sign flip may come from this
  design asymmetry rather than from domain shift.
* **Implication:** fitness must be measured on streams that resemble the deployment regime (repetition rate,
  domain), or the evolution will optimise away learning. A next check would rerun selection with matched n_per
  and a multi-domain fitness. It needs an owner decision and fresh one-use seeds.

---

# Reclassification (owner, 2026-10-26)

The held-out grids results on `wave32 test_v3` 7206–7210 (Gen 0 ON 86.11 G, Gen 0 OFF 91.35 G, Gen k 90.46 G) have
been inspected and now inform the experimental design. From here on they are **development evidence**, recorded in
`seed_registry.RECLASSIFIED_AS_DEV`, and are never reported as untouched confirmation.

**Corrections to the owner's brief:**
* There is no commit 8a6f202. This continues from 0917de1.
* The Checker v3 pin is `3c68230e…`, not `7df65196…`.
* Gen k was 90.46 G, not 90.1 G.

# Repetition × domain factorial: protocol (NOT LOCKED; committed before its outcomes)

* **Fixed:** Checker v3 (pin 1642721, `3c68230e…`), the OS retired-instruction meter, representations and the
  library mechanics.
* **Streams:** every stream starts from an empty library, and every learning decision and rebuild runs in the
  sandboxed solver and is billed.
* **Cells:**
  * Domain ∈ {Source = records + strings + graphs (mixed stream), Target = grids};
  * Repetition ∈ {2, 3} per mechanism (depth-4, 3-op cores).
* **Editable scope (`GENES_V3B`):** the v3 genome plus regime-adaptive controls:
  * `warmup`: minimum certified tasks before any rebuild;
  * `gate_repeat`: minimum observed within-stream repeat rate of certified cores before macros are admitted or
    rebuilt;
  * `rebuild_on`: rebuild on every certified task, or only when a new core appears;
  * `macro_hit_min`: switch macro proposal off when its observed hit rate falls below this, after ≥ 5 attempts.
* **Policies:**
  * always-ON = `GEN0_V3B`;
  * always-OFF = the same with `online: False`;
  * Gen k(2) and Gen k(3): each is Gen 0 + 5 generations × 5 children, evolved on **Source** streams at that
    repetition count (fitness dev 771–773; top 3 re-selected on 774–775). The evolution never sees the Target
    domain. Every generation runs all detectors, D4 integrity and one replay.
* **Development table:** dev2 781–785, all 4 cells × 4 policies. This also gives the cross-evaluation of the 2-rep-
  and 3-rep-evolved policies.
* **Confirmation:** after the table, the design is frozen (committed), and `confirm_rep` 7211–7215 (one-use, unseen)
  is run **once**, with the same cells and policies.
* **Confirmation readouts:**
  * per cell: correct, wrong, detector counts and `evaluator_work`;
  * the ON/OFF ratio per cell, and its decomposition into domain and repetition effects;
  * evolved vs always-ON and vs always-OFF per cell, with the matched-repetition Gen k as primary and the other as
    the cross check;
  * a replay of 7213 (Target, 3 reps, Gen k(3)).
* **Prior inspection:** the inspected 7206–7210 grid results are development evidence only.

## Factorial development results (dev2 781–785) and FROZEN design

**Evolution** (`artifacts/wave32_factorial_state.json`). Both evolutions ran on Source streams; all genomes were
admitted, detectors were 0, replays matched and D4 held.

| Champion | Selected genome | Settings |
| --- | --- | --- |
| Gen k(2) | `r2g2c1` | **online OFF**, proofs all, probe_tries 50, cap 40 |
| Gen k(3) | `r3g4c0` | **online ON with gate_repeat 0.3**, order short_first, proofs all |

**Development table** (all 0 wrong and 0 detector flags; G instructions; n = tasks per cell):

| Cell (n) | always-ON | always-OFF | Gen k(2) | Gen k(3) | ON / OFF |
| --- | --- | --- | --- | --- | --- |
| Source / 2 rep (200) | 65.42 | 64.52 | 63.24 | **63.01** | 1.014 |
| Source / 3 rep (300) | 98.74 | 98.60 | 96.77 | **95.98** | 1.001 |
| Target / 2 rep (80) | 60.74 | 60.17 | **59.55** | 60.20 | 1.009 |
| Target / 3 rep (120) | 86.95 | 92.56 | 91.67 | **86.62** | **0.939** |

**Decomposition** of ln(ON / OFF):
* repetition main effect −0.042;
* domain main effect −0.034;
* **domain × repetition interaction −0.060**.

Learning pays only in the Target × 3-rep cell. A repetition count alone does not explain the earlier sign flip,
but repetition is the knob that evolution can see: the evolution at 3 reps on Source alone found a gated-ON
policy (Gen k(3)). That policy is the best, or within 1.1% of the best, in every cell.

**FROZEN** at this commit: policies always-ON, always-OFF, Gen k(2) and Gen k(3) (the genomes in the state
artifact); cells, streams and readouts as in the protocol. Next is `confirm_rep` 7211–7215, run once.

## Confirmation (confirm_rep 7211–7215, one-use, run once after freezing)

`artifacts/wave32_factorial_confirm.json`. Every cell and policy: 100% correct, **0 wrong, 0 detector flags**.
The replay (7213, Target / 3 rep, Gen k(3)) matched, and D4 held.

| Cell (n) | always-ON | always-OFF | Gen k(2) | Gen k(3) | ON / OFF (seeds ON < OFF) |
| --- | --- | --- | --- | --- | --- |
| Source / 2 rep (200) | 66.66 | 65.26 | **63.99** | 64.76 | 1.021 (1/5) |
| Source / 3 rep (300) | 98.55 | 99.11 | 97.23 | **96.16** | 0.994 (4/5) |
| Target / 2 rep (80) | 57.75 | 57.92 | 57.34 | **57.03** | 0.997 (3/5) |
| Target / 3 rep (120) | 85.68 | 89.21 | 88.34 | **85.01** | **0.960 (5/5)** |

**Evolved policy matched to the cell's repetition count**, primary readout:

| Cell | Policy | vs ON | vs OFF |
| --- | --- | --- | --- |
| Source / 2 | Gen k(2) | 0.960 (5/5 seeds) | 0.980 (5/5) |
| Source / 3 | Gen k(3) | 0.976 (5/5) | 0.970 (5/5) |
| Target / 2 | Gen k(2) | 0.993 (3/5) | 0.990 (5/5) |
| Target / 3 | Gen k(3) | 0.992 (4/5) | **0.953 (5/5)** |

* **Cross-evaluation:** Gen k(3) in the 2-rep cells is 0.972 / 0.988 vs ON. Gen k(2) in the 3-rep cells is
  0.987 / **1.031** vs ON: learning OFF costs 3% in Target / 3 rep.
* **Decomposition** of ln(ON / OFF) on confirmation: repetition −0.032, domain −0.029, interaction −0.011.

## Reading

* **The mismatch is resolved.**
  * Learning ON pays where mechanisms repeat (3 reps), and more so on the Target domain. At 2 reps it is neutral
    or slightly harmful.
  * The earlier "evolution turned learning off" came from evolving at 2 reps.
  * Evolved at 3 reps, on Source domains only, the evolution keeps learning ON behind a repeat-rate gate (0.3).
    That policy is never worse than the better fixed policy by more than 1.2%, in any cell.
* **The matched evolved policy beats both fixed policies, pooled, in all 4 confirmation cells.** In 3 of the 4 it
  does so in ≥ 4/5 seeds against each.
* **This is development-level evidence of a procedure that adapts to the regime, not learning-to-learn in general.**
  * The gains are 1–5%.
  * The policy space is a small typed genome.
  * Only one checker, one task family and one repetition design were tested.
  * The 2-rep vs 3-rep champion is still chosen by matching the known repetition count. A single policy that
    detects the regime online (Gen k(3)'s gate is a partial step) was best in 3/4 cells, but not in Source / 2 rep.

---

# Single regime-detecting policy: protocol (owner go-ahead; NOT LOCKED; committed before its outcomes)

* **Goal.** One policy, with no knowledge of the stream's repetition count, that is at least as good as the better
  fixed policy in every regime.
* **Fixed:** Checker v3 (pin 1642721), the OS meter, representations and the library mechanics. Every stream
  starts from an empty library, and all learning decisions run in the sandboxed solver and are billed.
* **Genome `GENES_V3C`:** `GENES_V3B` plus:
  * a finer `gate_repeat` (0 … 0.4);
  * `rebuild_hit_min`: stop rebuilding once the observed macro-proposal hit rate is below it, after ≥ 5 attempts.
    This is an online low-reuse detector.
* **Evolution:**
  * **Fitness:** Source streams at both 2 and 3 repetitions (dev 771–773), scored as the mean over (seed, rep) of
    work / always-OFF work on that same stream. That normalises each regime equally, with no regime label given to
    the policy. The worst-case ratio is reported alongside.
  * **Archive:** seeded with Gen 0 (always-ON) and the earlier Gen k(2) and Gen k(3), lifted with
    `rebuild_hit_min = 0`, which is behaviourally identical. Then 8 generations × 6 children, with detectors, D4
    integrity and one replay per generation.
  * **Selection:** the top 3, re-selected on 774–775 (both reps). The champion is **Gen k(adapt)**.
* **Development check:** dev2 781–785, 4 cells × {always-ON, always-OFF, Gen k(2), Gen k(3), Gen k(adapt)}.
* **Confirmation:** after the design is frozen, run **once** on fresh one-use `confirm_adapt` 7216–7220, with the
  same cells and policies, plus a replay (7218, Target / 3 rep, Gen k(adapt)).
* **Predeclared success criterion** for Gen k(adapt) on confirmation:
  * pooled work ≤ min(always-ON, always-OFF) in ≥ 3 of 4 cells; and
  * ≤ 1.01 × min(always-ON, always-OFF) in every cell;
  * with 0 wrong and 0 detector flags.
* **Secondary readout:** Gen k(adapt) vs the regime-matched reference policy (Gen k(2) in 2-rep cells, Gen k(3) in
  3-rep cells). Those reference policies are told the regime; Gen k(adapt) is not.

## Regime-detecting policy: development results and protocol amendment (before any confirmation draw)

* **Evolution:** 51 genomes, all admitted, detectors 0, replays matched, D4 held.
  * The champion of the Source-only selection was **a6c5**: online ON, gate_repeat 0.3, warmup 3, rebuild only on a
    new core, no proofs.
  * Its fitness mean ratio was 0.969, with a worst stream of 1.020. On selection the mean was 0.977, worst 1.005.
* **dev2 check of a6c5:** it **fails** the predeclared criterion, while staying 100% correct with 0 wrong.

| Cell | a6c5 / min(ON, OFF) | Seeds where it is ≤ min |
| --- | --- | --- |
| Source / 2 rep | 0.980 | 4/5 |
| Source / 3 rep | 0.956 | 5/5 |
| Target / 2 rep | 1.015 | 0/5 |
| Target / 3 rep | 1.019 | 1/5 |

* **Diagnosis:** its evolution and selection saw Source streams only. The warm-up and new-core-only rebuild delay
  learning on the shorter Target streams.
* **Amendment** (development data only; the confirmation seeds are still untouched):
  * re-select among the top 8 archive members on dev 774–775 across **all 4 cells**, each stream scored as work /
    always-OFF;
  * rule: worst ratio ≤ 1.01, then the minimum mean (falling back to the minimum worst ratio);
  * then the dev2 check again, then the freeze, then confirm_adapt, run once.
* **Disclosed:** Target-domain dev streams now inform the policy choice. The confirmation domain is still grids, on
  unseen seeds.
* **Amendment 1, result (disclosed):** the selection normalised each stream by always-OFF only and picked a0c1,
  which is the earlier Gen k(2) with learning OFF (mean 0.985, worst 0.991). That score was misaligned with the
  success criterion, which uses min(ON, OFF): a learning-OFF policy cannot detect regimes, and on dev2 Target / 3 rep
  it was 5.4% worse than ON.
* **Amendment 2** (development only, before any confirmation draw): the same re-selection, but with each stream
  normalised by **min(always-ON, always-OFF) on that stream**. Rule: worst ratio ≤ 1.01, then the minimum mean
  (falling back to the minimum worst ratio).
* **Amendment 2, result:** no candidate met worst ≤ 1.01 on 774–775. The fallback (minimum worst ratio) picked
  **a4c2** (online ON, gate 0.4, max_holes 0, proofs all; mean 0.995, worst 1.012). On dev2 it **fails** the
  criterion:

| Cell | a4c2 / min(ON, OFF) |
| --- | --- |
| Source / 2 rep | 1.000 |
| Source / 3 rep | 0.976 |
| Target / 2 rep | 1.004 |
| Target / 3 rep | **1.019** |

* **Amendment 3 = FREEZE** (development only, before any confirmation draw):
  * **Primary policy:** **a0c2 = the earlier Gen k(3)**, lifted with rebuild_hit_min = 0. It is the only evaluated
    single policy that satisfies the success criterion on dev2, in both dev tables:

| Cell | First table | Second table |
| --- | --- | --- |
| Source / 2 rep | 0.977 | 0.977 |
| Source / 3 rep | 0.973 | 0.973 |
| Target / 2 rep | 1.0005 | 1.0007 |
| Target / 3 rep | 0.996 | 0.996 |

  * **Regime knowledge:** it is never told the regime; its repeat-rate gate (0.3) reads the stream.
  * **Secondary arms** (reported, not the claim): a4c2 and a6c5. Gen k(2), learning OFF, is the reference.
  * **Unchanged:** the confirmation criterion and readouts. The confirmation is `confirm_adapt` 7216–7220, run
    once.
* **Disclosed:** the 51-genome mixed-regime evolution found no single policy better than Gen k(3). Three selection
  amendments were made on development data. Choosing the primary by its dev2 result means dev2 is not independent
  evidence for it; only the confirmation is.
