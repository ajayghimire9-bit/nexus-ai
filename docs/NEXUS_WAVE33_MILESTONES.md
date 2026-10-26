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
