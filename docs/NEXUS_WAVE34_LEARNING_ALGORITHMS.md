# Wave 34 (NOT LOCKED): evolving payoff-driven learning algorithms

* **Fixed:** Checker v3 (pin 1642721, `3c68230e…`; the brief says `7df65196…`), the sandbox, the OS meter, G_P, the
  matched depth-4 scope and the detectors. final_sealed and main are untouched.
* **Constraint (stated up front):** frozen Checker v3 accepts only its 4 proved fixpoint axioms, and refuses every
  other lemma. "Online checker-pruning synthesis" is therefore limited to *learning which proved axioms to cite from
  measured payoff*. New pruning-rule kinds would need a new checker version.

## DSL v2 (`src/nexus/wave34_learner.py`)

The learner is an interpreted program, not code. Evolution writes:
* the use-guards for macros, the fragment prior and proof citation;
* the extraction triggers for macros and the prior;
* a symbolic **Score(item)** over support, hits, saved, age, len, survival and fit_rate, used for admission and
  eviction;
* the cap, refit period, exploration rate, macro depth, skeleton heuristics and probe policy.

The guards read **payoff ledgers**: ROI, recent ROI, hit rates and uses per component, plus stream statistics.
* **Units:** deterministic op units inside the child; checker work comes from v3's verdict fields.
* **Counterfactual baseline:** an online plain-search cost model by solution length.
* **Archive seeds:** SEED_ON, SEED_OFF and SEED_PRIOR only. Every payoff rule must be evolved.

## Phase 1: DSL iteration on development data (devA 801–804; allowed to change the DSL)

* **Evolve:** on devA 801–802; select on 803–804.
* **Diagnose:** on devA mixed streams and F2 streams, against Gen 0 ON, Gen 0 OFF and frozen a0c2.
* **Decision:** if the winner only flips switches, or loses on mixed streams, iterate on the DSL. Then lock.

## Dev iteration 1 (devA, disclosed)

* **Run:** 83 programs, all admitted.
* **Automatic winner:** g3c5, which is effectively *prior-always*. It never extracts macros, and its proof guard can
  never fire.
* **Dev diagnosis:** strong on mixed streams (0.891 vs a0c2, 4/4) and F2 (0.963 vs a0c2, 4/4). But it is a
  **trivial recombination**: the payoff primitives were unused, because the only ROI-controlled items were macros,
  which rarely pay here.
* **DSL v2.1 iteration:**
  * the prior itself is placed under evolved learning mechanics: an evolved per-task credit formula `pscore` weights
    which solved tasks shape the prior;
  * an evolved refit trigger (it can read `since_fit` and the prior's ROI);
  * evolvable smoothing and mixture weights.
* **Dev iteration 2 crashed:** a KeyError on the new item features `novel` / `cost` for macro items. It was fixed and
  smoke-tested, and is disclosed.

---

# Wave 35 (owner directive, 6 parts): one frozen learner across several families. LOCKED protocol

This is committed **before** the final evolution starts. There are no human selection amendments after this commit.

**Scope limits (stated up front):**
* Checker v3 (`3c68230e…`; the brief says `7df65196…`), its evidence objects, AMBIGUOUS(k) and ABSTAIN are
  unchanged.
* Frozen v3 accepts only its 4 proved fixpoint axioms. "Checker-verified pruning laws" is therefore limited to
  learning *which* proved axioms to cite from measured payoff. New law kinds need a new checker version.
* Representation discovery is limited to learned sub-program abstractions (macros with holes, op / type-signature
  fragment priors, learned type tables) over the supplied middle IR. No new adapters are invented.
* Noisy real-world environments are deferred.

**Learner space:** DSL v2.1 (`wave34_learner.py`). Every use, extraction, refit, admission and eviction decision is
an evolved expression over **net-ROI ledgers**: estimated savings against the online plain-search cost model, minus
the invested and lookup costs. Item scores are evolved formulas.

**Archive seeds:** SEED_ON, SEED_OFF, SEED_PRIOR and the hand-written **FIXED_PAYOFF** controller.

**LOCKED selection criterion** (the only one):
* **Stream score:** r = learner `evaluator_work` (including every metered update) / min(SEED_ON, SEED_OFF,
  FIXED_PAYOFF) on that stream.
* **Program score:** mean(r) + mean(max(0, r − 1)).
* **Fitness:** wave34 `fit` 805–808 × {2 rep, 3 rep, mixed 2→3→2, F2 × 3}.
* **Admission:** wrong = 0, all detectors 0, and a replay match when replayed.
* **Evolution:** 10 generations × 8 children, parents by a fitness or novelty tournament, mutation and crossover.
* **Selection:** the top 5 by fitness are re-scored on `valsel` 809–813. The winner is the minimum valsel score, and
  it is frozen to `artifacts/wave35_frozen_learner.json` and committed before any confirmation seed is drawn.

**Discovery cost:** every instruction of every final-evolution and selection episode is summed (`search_instr`).

**Confirmation** (one-use, run once; the same frozen learner; no family IDs or flags; no edits between families):

| Family | Content | Seeds |
| --- | --- | --- |
| F3 | unseen: 2-op cores, string outputs | 7501–7505 |
| F4 | unseen: counter-valued outputs | 7506–7510 |
| mixed | non-stationary 2→3→2 repetition, Source + Target, increment-3 family | 7511–7515 |
| F2 | IR-routed, family seen in training, fresh seeds | 7516–7520 |

* F2 has 2- and 3-rep cells; F3 and F4 likewise.
* **Arms:**
  * Evolved;
  * Fresh-v3 (no learning);
  * Placebo-v3 (the evolved learner with its fitted priors permuted and size-matched placebo macros);
  * the fixed learners Gen 0 ON, Gen 0 OFF, frozen a0c2 and FIXED_PAYOFF.
* **Strongest fixed learner** per family = the lowest pooled work among the 4 fixed learners *on the confirmation
  data* (conservative).
* **Per-family pass:** Evolved pooled < Fresh-v3, < Placebo-v3 and < the strongest fixed learner, each in ≥ 4/5
  seeds, with 0 wrong and 0 flags.
* **Including search cost:** the totals with search_instr added, and the break-even number of streams =
  search_instr / mean per-stream saving against the strongest fixed learner.
* **Replay:** F3 seed 7503 at 3 reps.
