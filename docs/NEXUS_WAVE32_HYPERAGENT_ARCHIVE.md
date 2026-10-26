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
