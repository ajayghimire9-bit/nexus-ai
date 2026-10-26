# Wave 33 (NOT LOCKED): Milestone A (held-out mechanisms) and Milestone B (an evolved learning procedure)

**Fixed:** Checker v3 (pin commit 1642721, sha256 `3c68230e…`; the owner's brief says `7df65196…`), the sandboxed
solver, the OS retired-instruction meter, representations and G_P. final_sealed and main are untouched.

## Milestone A: protocol (committed before the outcomes of dev 763–765 and val_frag 7116–7120)

**Diagnosis** (Wave 31 v3, val_v3, held_out cores). Checker work is identical across arms (≈ 328 M per task). The
solver's proposal is ≈ 150 M per task (31%). Experienced-v3 *loses* on held-out cores (205 M, +37%), because its
whole-program macro search fails before the full primitive search. No learned knowledge ever touched the primitive
search, so nothing transferred to mechanisms that were not seen.

**Mechanism** (`src/nexus/wave33_prior.py`): learned, *mechanism-independent* knowledge about the tools.
* **Lazy best-first proposal.** Children are queued by accumulated transition cost and executed only when popped,
  with exact observational dedup.
* **Transition prior** from certified source programs: p = λ·p_op(bigram) + (1 − λ)·p_sig(signature bigram) /
  |class|. Signatures are type signatures inferred by running each tool on type-stratified observed values, so ops
  never seen in source still inherit mass.
* **Tool knowledge:**
  * a learned type table, used for goal-directed pruning: children predicted to error, or unable to reach the target
    output type in the remaining depth, are never executed;
  * learned redundant bigrams (a no-op after a given op).

  Only *observed* input types are pruned; unknown types stay admissible. If the pruned search finds nothing, it falls
  back to the complete uniform search, and that is billed.
* **Correctness never depends on the prior.** Checker v3 certifies over the full declared scope.

**Development** (disclosed): seeds 761–762 were used in-process to build and tune it, with α = 1.0 and λ = 0.8
chosen there. Held-out proposal work per task was 111 M (learned + knowledge), against 146 M (eager BFS), 153 M
(uniform lazy) and 188 M (permuted placebo).

**Configs** (matched exhaustive strength over G_P at depth 4; no proofs or macros, so only the proposal differs):
* Fresh-v3 (eager BFS first-fit);
* Fresh-lazy (the same engine, uniform prior);
* **Experienced-frag** (learned prior + tool knowledge);
* **Placebo-frag** (the same prior and knowledge with tool identities permuted: size- and shape-matched).

**Learning cost:**
* Source tasks are solved as Fresh-v3, and the evaluator returns the certified candidates and views.
* The child's fitting instructions are the **marginal learning cost**. They are charged *entirely* to that fold's
  held_out tasks in the primary readout (the conservative choice).
* The full source-solve cost is also reported, as Definition A.

**Predeclared success criterion** (val_frag 7116–7120, one-use, run once; held_out category):
* Experienced-frag total `evaluator_work` + the marginal fitting cost must be < min(Fresh-v3, Fresh-lazy) and
  < Placebo-frag, pooled, and lower than each in ≥ 4/5 seeds;
* with all tasks exhaustive_UNIQUE, 0 wrong, 0 detector flags;
* solve counts are reported, and must be ≥ both.

### Milestone A: development iterations (dev 761–765, disclosed) and FREEZE

All three runs: 280/280 exhaustive_UNIQUE, correct, 0 wrong, 0 flags in every config.

| Run | Change | Fit per fold | Held-out (Exp + all fit) / min(Fresh) | Seeds < 1 | vs Placebo |
| --- | --- | --- | --- | --- | --- |
| dev | as committed | 116 M | 0.9985 | 2/5 | 0.920 |
| dev2 | single-pass knowledge (images reused); per_type 2 | 102 M | 0.9916 | 3/5 | 0.913 |
| dev3 | `wave33_prior` imported at child start-up, the same for every arm | 78 M | **0.978** | **5/5** | **0.900** (5/5) |

* **Why dev3 is fair:** module loading had been billed inside the fit job (and to the first best-first task); it is
  code loading, not learning.
* **Ablation:** the redundancy knowledge saves ≈ 5 M per held-out task, so it was kept.
* **Without fitting cost:** Experienced-frag is −6.7% vs Fresh-v3 on held-out (−5.8% over all categories).
* **FROZEN at this commit** (code and α = 1.0, λ = 0.8). Next is val_frag 7116–7120, claimed whole and run once,
  with the criterion unchanged.

### Milestone A: results on val_frag 7116–7120 (one-use, claimed whole, run once; replay of 7118 identical)

Work is G retired instructions; every config is exhaustive_UNIQUE, correct, 0 wrong, 0 flags.

| Category (n) | Fresh-v3 | Fresh-lazy | **Experienced-frag** | Placebo-frag |
| --- | --- | --- | --- | --- |
| familiar_exact (80) | 36.42 | 36.84 | **34.69** | 39.97 |
| compositional (130) | 64.58 | 65.26 | **60.45** | 70.70 |
| **held_out (70)** | 33.57 | 34.01 | **31.20** | 37.17 |
| all (280) | 134.57 | 136.11 | **126.34** | 147.83 |

* **Marginal learning cost:** 1.59 G for all 20 folds. It is charged entirely to the held_out tasks.
* **Held-out, net of all marginal learning cost:**
  * (Experienced-frag + fit) / min(Fresh-v3, Fresh-lazy) = **0.9765**, with 5/5 seeds < 1 (0.953 … 0.996);
  * vs Placebo-frag = **0.882**, with 5/5 seeds (0.838 … 0.962).
* **Solver work alone, on held-out tasks:** 7.99 G vs 10.37 G for Fresh-v3, which is −23%.
* **Solve counts:** equal, 70/70 for every config. The gain is cost, not coverage.

**Predeclared criterion: PASS.**

**What this establishes.** Knowledge learned from source mechanisms — a transition prior over ops and inferred type
signatures, a type table for goal-directed pruning, and redundant bigrams — makes certified solving of **held-out
mechanisms** cheaper than both a fresh solver and a size- and shape-matched placebo. This holds net of the marginal
learning cost, at matched exhaustive_UNIQUE strength.

**What it does not establish:**
* Under Definition A (counting the 271.6 G of source-task solving), learning is not repaid.
* The gain is 2.3% of total work, because the checker (identical across arms) dominates.
* One task family and one grammar were tested.
* The held-out mechanisms reuse ops and types seen in source; they are new compositions, not new primitives.

## Milestone B: protocol (LOCKED selection criterion; committed before evolution starts)

* **Editable object:** a **compositional learner program** in a closed, typed DSL (`src/nexus/wave33_metalearner.py`),
  interpreted inside the sandboxed solver and never executed as Python. Evolution writes and composes:
  * the proposal plan: macro and/or learned-prior stages, guarded by Boolean expressions over observed stream
    statistics (repeat rate, macro and prior hit rates, counts, library size);
  * abstraction-extraction triggers (Boolean expressions);
  * skeleton heuristics;
  * credit and admission: arithmetic scoring expressions over per-macro support, credited hits, age and length;
  * the probe policy;
  * proof citation (lemma generation), also a Boolean expression.

  The complete fallback search is always appended, so no program can lose completeness.
* **Fixed:** Checker v3, the sandbox, the OS meter, G_P, the matched depth-4 scope and the detectors.
* **LOCKED selection criterion** (the only one; no human selection amendments):
  * **Stream score:** learner `evaluator_work` (including every metered update) / the GEN0_OFF learner's work on the
    same stream.
  * **Fitness:** the mean stream score over 9 fitness streams (wave33 dev 791–793 × {2 rep, 3 rep, mixed 2→3}; two
    seeded domains per seed; increment-3 family).
  * **Admission:** wrong = 0, all 5 detectors 0, and a matching replay when replayed (one child per generation).
  * **Archive:** seeded with GEN0_ON, GEN0_OFF and SEED_PRIOR. Then 8 generations × 6 children, each mutated from a
    2-way-tournament archive parent.
  * **Selection:** the top 5 by fitness are re-scored on wave33 valsel 796–800 (15 streams). **The winner is the
    lowest mean valsel score.**
* **Test** (one-use wave33 test 7301–7305, run once):
  * **Data:** the **unseen family F2** (IR-routed mechanisms that appear in no earlier family), at 2 and 3
    repetitions, from an empty library.
  * **Arms:** the evolved learner, Gen 0 learning ON (GEN0_V3C), Gen 0 learning OFF, and the frozen a0c2 gate.
  * **Predeclared success:** the evolved learner's pooled work (both cells) < each of the three, and lower than
    each in ≥ 4/5 seeds, with 0 wrong and 0 flags.
  * **Replay:** 7303 at 3 reps.

### Milestone B: results (zero human selection amendments)

**Evolution** (`artifacts/wave33B_state.json`). 51 learner programs: all admitted, all detectors 0, every replay that
ran matched, and D4 held.

| Archive seed | Fitness mean |
| --- | --- |
| GEN0_ON | 1.031 |
| GEN0_OFF | 1.000 |
| SEED_PRIOR | 0.966 |
| best evolved | 0.958 |

**Locked selection** on valsel 796–800: the top 5 scored 0.9356–0.9391. **Winner: b8c3** (valsel 0.9356). The
program the evolution composed:
* **plan:** never propose with macros; always propose with the learned fragment prior;
* **extraction:** refit the prior every 4 certified tasks; still rebuild the macro library while the repeat rate is
  ≤ 0.4, which is dead work the evolution did not remove;
* **proofs:** cite Checker v3's proved axioms only after more than 10 certified tasks;
* **probe:** 1 mutation, 150 tries.

So the procedure differs from every archive seed, and no human chose it. But it is mostly a recombination of an
existing component (Milestone A's prior, learned online) with a learned *when-to-cite-proofs* trigger. It is not a
qualitatively new learning algorithm.

**Test** (unseen family F2, one-use 7301–7305, run once, from an empty library):
* **Correctness:** every arm 250/250 correct, 0 wrong, 0 detector flags.
* **Checks:** the replay (7303 at 3 reps) matched, and D4 held.

| Cell | Evolved | Gen 0 ON | Gen 0 OFF | frozen a0c2 |
| --- | --- | --- | --- | --- |
| F2 / 2 rep (100) | **40.97** | 42.27 | 42.30 | 41.62 |
| F2 / 3 rep (150) | **62.41** | 64.47 | 66.87 | 63.66 |

| Evolved vs | Pooled | Seeds where Evolved is cheaper |
| --- | --- | --- |
| Gen 0 ON | **0.9685** | 4/5 |
| Gen 0 OFF | **0.9470** | 5/5 |
| frozen a0c2 | **0.9820** | **3/5** (per seed: 0.975, 1.000, 0.969, 1.021, 0.947) |

**Predeclared criterion: FAIL.** Pooled, the evolved learner is cheaper than all three arms. It is cheaper than the
frozen gate in only 3/5 seeds, where ≥ 4/5 was required.

**Reading:**
* An autonomous, zero-amendment search over *compositional learner programs* produced a learner that transfers to
  an unseen task family. It is pooled-cheaper than learning ON (−3.2%), learning OFF (−5.3%) and the hand-selected
  gate (−1.8%).
* Its edge over the gate is not consistent across seeds.
* The evolved program mainly composes existing parts (online fragment prior + a proof-citation trigger), so
  "invented a better learning algorithm" remains **unproved**.
