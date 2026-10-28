# NEXUS ocean track: three-level state learning, meta-learning and self-evolution (oc) (NOT LOCKED)

This document has two parts:

* §0, the pre-registration. It was committed before any ocean outcome; only one charged smoke run on 12 training
  episodes was made before it.
* Results, appended in later commits.

## 0. Pre-registration

* **Start.** `f45da4e` on `codex/nexus-data-engineering`.
  * Protected: 912 files, `main`, `final_sealed`, Checkers v1–v5, and all f45da4e artifacts.
* **Budget.** 8,441 s carried, plus **GRANT-NEXUS-OCEAN-META-14400S** (explicit in the owner's message; recorded once in
  `artifacts/oc_grant.json`) = **22,841 s**.
  * CPU only.
  * Every run goes through `scripts/oc_exec.py`, at most 900 s per call, charged to the ledger as `oc-*`.
  * The track cap is 20,000 s.
* **Rule.** Three outcomes: PROMOTION CANDIDATE / REJECTED FOR THIS SETTING / INCONCLUSIVE.
  * Every meta-level claim is evaluated on **≥ 300 independent held-out micro-episodes** before any full project.
  * Task memory (hypotheses, examples, synthesised code, membership-query cache) is **wiped at the start of every
    episode**. Only the persistent learning procedure or policy carries over.
  * The evaluator, the oracle, the episode generator and the budget meters are outside every editable surface.

### 0.1 The micro-project ocean (`src/nexus/oc_ocean.py`)

* **Episode.** A random per-key lifecycle machine:
  * 2–4 modes, 3–5 kinds plus one extra kind;
  * 1–2 registers;
  * updates from primitives up to size 5;
  * emits that read pre-update registers or the event value.
* **Regime.** `base` | `new_kind`.
* **Data.** 20 training keys and 100 held-out keys.
* **Oracle.** Counted.
* **Declared grey-box contract.** Per kind: reads the value field? which labels may it emit? This is author-provided
  metadata, analogous to a schema or pipeline contract, and is disclosed. It never reveals modes, registers or updates.
* **Second domain, `protocol`.** Cyclic session protocols, with their own vocabulary and generator statistics; used only
  in Part 3.
* **Seeds** (`src/nexus/oc_seeds.py`):
  * `ep_train` 20000–20599: meta-training;
  * `ep_val` 20600–20799: evolution fitness;
  * `ep_held` 21000–21399: held-out, ≥ 300 used;
  * `ep_xfer` 21500–21899: second domain;
  * `edev` 13001–13048: full projects, energy ones only for Part 2;
  * `pdev`, and the one-use `val`, `val_b` and `test`.
* **Correctness** = exact outputs on the 100-key held-out stream.
* **Silent** = the learner certifies (empirical coverage agreement) but the held-out stream is wrong.
* Certification is **empirical agreement within the probe scope**, not a proof.

### 0.2 Part 1 — task learner (`src/nexus/oc_learner.py`)

* **Arms,** all on the f45da4e full hypothesis space `H_FULL`:
  * (i) coverage, which is f45da4e;
  * (ii) + grey-box contract filter;
  * (iii) + version-space querying with a 25 % certification sample;
  * (iv) both.
* **Data:** 300 held-out episodes.
* **PROMOTION CANDIDATE iff** total membership queries are ≥ 25 % lower than (i), with silent errors ≤ (i)'s and exact
  ≥ (i)'s − 3.

### 0.3 Part 2 — meta-learned hypothesis-space growth

* Every episode starts at `H0 = {1 register, depth 3, no merging, 3 modes}`. On failure a policy picks an extension:
  `add_register` / `add_control_mode` / `expand_update_depth` / `merge_registers` / `add_timer_or_window`. The last is
  unsupported, so choosing it wastes a step.
* **Meta-training:** 300 `ep_train` episodes with uniformly random exploration, logging (signature, action, reward).
  Reward = the episode certified within 2 more steps, minus 0.02 × steps.
* **Arms,** on 300 `ep_held` episodes, max 6 steps:
  * `Meta_Learned_Growth_Rule` (value table on signatures);
  * `Hand_Ordered_Rule` (mode → depth → register → merge → …; this is the f45da4e defect-fixing order);
  * `Random_Growth_Order`;
  * `Shuffled_Episode_Placebo` (the same table trained on signatures shuffled across records).
* **Full energy build projects:** the energy (`seed % 4 == 3`) `edev` projects. The build-time `E.meter` lifecycle is
  learned from ticks 1–8 with each policy, plus the declared contract, and scored exact on ticks 9–16.
* **Measures:** certified / exact / silent, steps, queries, CPU, and learning curves (cumulative exact vs queries).
* **REJECTED unless** Meta beats Hand on held-out energy builds (exact count, then queries) **and** on held-out
  micro-episode learning curves (more exact at ≤ queries, or equal exact with ≥ 10 % fewer queries), with silent ≤ Hand.

### 0.4 Part 3 — distinguishing experiments as a transferable meta-skill

* **Continuation classes** for counterexample search:
  * `loop_then_probe`: reach a mode, repeat a self-loop, probe;
  * `suspend_resume`: leave a mode and return;
  * `repeat_twice`;
  * `reverse_two`;
  * `gap_repeat`: σ x σ;
  * `boundary_flush`: a long run then an emitting kind.
* **Meta-learned choice:** class weights fitted on `lifecycle` training episodes (counterexamples found per query). Task
  memory is reset; no machine or program is kept.
* **Arms** on 300 held-out `lifecycle` episodes and 300 `protocol` episodes:
  * meta-learned class choice;
  * generic L* counterexample search (random words);
  * memoryless info-gain (disagreement among version-space candidates);
  * random continuation classes.
* **Measure:** queries until the hypothesis is exact on the held-out stream (measured offline, after each round).
* **REJECTED unless** meta reduces queries-to-correct vs generic search on the held-out `protocol` domain.

### 0.5 Part 4 — self-evolution over the audited learning surface + research-ledger value predictor

* **Editable surface** (`SURFACE` in `oc_evolve`): the computations that do state learning:
  * (a) continuation-class weights;
  * (b) the partition-revision rule after contradictory evidence (all suffixes vs the distinguishing suffix only);
  * (c) update-proposal order (Occam vs frequency-learned);
  * (d) query-budget allocation (coverage sample fraction, counterexamples per round).
* The checker, evaluator, evidence records and meters are outside it.
* **Fitness:** the learning curve (area of exact-vs-queries) on `ep_val` episodes, with memory reset per episode. Equal
  evolution budget for each arm.
* **Ledger predictor:** parse the repository's wave reports. Positive outcome vs NEGATIVE / REJECTED / FAILED become
  labels, and the mechanism keywords become operator categories, giving a smoothed `P(gain | operator)`.
  * **Retrospective check, hindsight only:** with the ledger frozen before priority A, does it rank verification /
    coverage edits above the t7 wrapper categories?
* **Arms:**
  * `Ledger_Conditioned_Learner_Edits`;
  * `Trace_Only_Learner_Edits` (operator chosen from the run's own failure statistics);
  * `Blind_Random_Mutations`;
  * `Current_Strong_Learner` (no evolution).
* **Evaluation** on 300 `ep_held` learning curves, with 100 % of evolution cost charged.
* **REJECTED unless** ledger-conditioning beats both trace-only and the current learner.

### 0.6 Part 5 — assembly, validation, sealed confirmation with an unseen class X5

* **NEXUS_Confirmed** = f45da4e NEXUS_Tournament_Winner plus only the Part 1–4 promotion candidates that have an
  end-to-end role.
* **X5, declared now** (never executed on dev or val before sealing, except a crash-only generator check on a smoke seed
  that runs no NEXUS arm): **undeclared event-kind vocabulary migration.**
  * From tick 9, two lifecycle event kinds are emitted under new names (`<KIND>_V2`), and the old names stop.
  * The semantics are unchanged and the producer declares nothing.
  * X3 and X4 move to the known pool.
* **Validation (`oc/val`, 8 projects, 2 per domain, D1/D2):** 8/8 independently correct (energy included), 0 silent,
  8/8 completed and crash-identical. One disclosed revision is allowed on `val_b`, otherwise the test stays closed.
* **Sealed test (`oc/test`, 16 projects, 4 per domain;** faults X5, X3, X5, X4 by `(seed // 4) % 4`, so X5 on 8):
  * arms: NEXUS_Confirmed, NEXUS_Tournament_Winner (f45da4e), NEXUS_U5, Fixed_Policy and Conventional, paired;
  * **success** = NEXUS_Confirmed 16/16 independently correct, 0 silent, 16/16 completed and crash-identical.
  * The X5 result is reported separately as the **only** fault-class-generalisation evidence.

### 0.7 Resource plan

| part | planned wall s |
|---|---|
| Part 1 | ≈ 1,500 |
| Part 2 | ≈ 4,000 |
| Part 3 | ≈ 2,500 |
| Part 4 | ≈ 4,000 |
| val + test | ≈ 4,500 |

The cap is 20,000 s.

## 0.8 Results

(appended)
