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
