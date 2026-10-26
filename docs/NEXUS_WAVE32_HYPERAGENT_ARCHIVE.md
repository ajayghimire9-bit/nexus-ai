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
