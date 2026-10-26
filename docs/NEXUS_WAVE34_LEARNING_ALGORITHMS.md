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

## Wave 35 results (NOT LOCKED)

**Final evolution** under the locked criterion (`artifacts/wave34_final_state.json`): 84 programs, all admitted, all
detectors 0, every replay that ran matched, and D4 held.

| Program | Score (fitness) |
| --- | --- |
| SEED_PRIOR (seed) | **0.948** |
| best evolved (g5c4) | 0.956 |
| SEED_ON | 1.067 |
| SEED_OFF | 1.043 |
| FIXED_PAYOFF | 1.025 |

**Locked selection** (valsel 809–813): the winner is **g0c2 = the SEED_PRIOR archive seed** (valsel 0.9446, 0/20
losses), ahead of g5c4 (0.9563) and g10c1 (0.9564). It was frozen at 9950e88 before any confirmation seed was drawn.

**Discovery cost:** `search_instr` = **33,960.7 G** (evolution 30,634 G + selection 3,327 G).

**Frozen learner (exact code):**

```json
{"use": {"m": ["false"], "p": ["true"], "x": ["false"]}, "extract": {"m": ["false"], "p": ["true"]},
 "pscore": ["const", 1], "alpha": 1.0, "lam": 0.8, "refit": 4, "score": ["const", 1], "cap": 200, "explore": 0,
 "macro_depth": 2, "max_holes": 1, "min_support": 1, "probe": {"mut": 2, "tries": 300}}
```

That is: learn the fragment prior and the tool knowledge online from certified solutions, refit every 4 certified
tasks, always propose with it, and use no macros and no proofs. **No new mechanism was discovered by evolution**;
this is the Milestone A mechanism, learned online.

### One-shot multi-family confirmation (one-use seeds, run once; the same frozen learner, no family flags)

Every family and arm: **100% solved, 0 wrong, 0 detector flags**. The replay (F3 7503 at 3 reps) matched, and D4 held
for every family. Work is in G retired instructions.

| Family (tasks) | Evolved | Fresh-v3 | Placebo-v3 | Gen 0 ON | Gen 0 OFF | a0c2 | Fixed-payoff | Strongest fixed | vs Fresh | vs Placebo | vs strongest | Pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F2 IR-routed (250) | **103.04** | 110.01 | 115.80 | 106.89 | 109.58 | 105.87 | 108.47 | a0c2 | 0.937 (5/5) | 0.890 (5/5) | **0.973 (4/5)** | **yes** |
| F3 unseen (200) | 75.48 | 75.63 | 80.32 | 75.34 | 76.14 | **73.93** | 77.41 | a0c2 | 0.998 (4/5) | 0.940 (5/5) | **1.021 (0/5)** | no |
| F4 unseen counter outputs (200) | 69.68 | 66.96 | 71.41 | 68.15 | **66.95** | 67.05 | 70.86 | Gen 0 OFF | **1.041 (0/5)** | 0.976 (5/5) | **1.041 (0/5)** | no |
| mixed, non-stationary (980) | **395.22** | 441.54 | 463.23 | 457.24 | 440.54 | 441.39 | 461.59 | Gen 0 OFF | 0.895 (5/5) | 0.853 (5/5) | **0.897 (5/5)** | **yes** |
| **all (1,630)** | **643.4** | 694.1 | 730.8 | 707.6 | 693.2 | 688.2 | 718.3 | (per family) 687.3 | 0.927 | 0.880 | **0.936** | **2 / 4** |

**Including discovery cost:** (643.4 + 33,960.7) / 687.3 = **50.3×** the strongest fixed learners. The saving is
1.10 G per stream, so break-even comes after **≈ 31,000 streams** of this size.

### Reading

* **The bar is not met.** The single frozen learner beats Fresh-v3, Placebo-v3 and the strongest fixed learner in 2
  of 4 families: F2, and the long non-stationary mixed streams, where it is −10.3% vs the best fixed learner in 5/5
  seeds.
* **It fails on both genuinely unseen families.**
  * On F3 it is +2.1% vs the a0c2 gate, in 0/5 seeds.
  * On F4 (counter-valued outputs) it is +4.1% vs no learning, in 0/5 seeds. There the online prior's fitting cost
    and its misdirected ordering outweigh its savings.
* **Pooled over all 1,630 tasks:** 0.936 vs the per-family strongest fixed learner, and 0.880 vs Placebo.
* **Learned knowledge is relevant, not just engineering.** Placebo-v3 loses to the real learner in all 4 families,
  in 20/20 seeds.
* **The self-evolution claim is negative.** Under a locked, zero-amendment criterion, 80 evolved programs did not
  beat the simplest seed; the payoff ledgers and evolved Score / credit formulas never produced a better learner.
  The discovery cost (34 T instructions) is also ~31,000 streams away from being repaid.
* **What would change this:**
  * learners that can *turn learning off per family from measured payoff*. FIXED_PAYOFF tried this by hand and was
    worse, because its ROI estimates rely on a cost model that is noisy early in a stream;
  * richer acquisition (new verified law kinds, which need a new checker version);
  * fitness streams that include counter-valued and string-output families. They were absent from training by
    design, and that is exactly where the learner failed.
