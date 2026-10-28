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

### 0.7a Amendment (committed before any Part 1 / 2 outcome)

* **Cost.** `H_FULL` costs about 5.2 s per episode, which would put Part 1 near 6,000 s.
* **Change.** Part 1's four arms therefore run on the same learner using the **hand-ordered growth rule from H0**
  (about 1.9 s per episode). Arm (i) is identical to Part 2's `Hand_Ordered_Rule` and is reused.
* **Unchanged:** the Part 1 criterion and everything else.

## 0.8 Results

### Ledger incident (disclosed)

* An over-broad `pkill` also killed 10 `oc_exec` wrappers, so their wall time was not recorded.
* I charged each of them manually: 150 s, from file birth to the last write plus 30 s, marked `KILLED_CHARGED_MANUALLY`
  (1,500 s total).
* Their completed episodes were kept, and the runs resumed with a resumable runner, at most 4 concurrent.

### Part 1 — task learner (300 held-out micro-episodes; hand growth from H0)

| arm | certified | exact | silent | membership queries | CPU |
|---|---|---|---|---|---|
| coverage (f45da4e acceptance) | 249 | 217 | **32** | 254,152 | 677 s |
| + grey-box contract | 249 | 217 | 32 | 254,460 | 604 s |
| + version space (25 % cert. sample) | 248 | 185 | 63 | **88,011** | 778 s |
| both | 248 | 185 | 63 | 88,041 | 698 s |

* **Outcome: REJECTED FOR THIS SETTING.**
  * Version space cuts queries by 65 % but doubles silent errors and loses 32 exact.
  * The grey-box contract only cuts CPU (−11 %); queries are unchanged.
* **Main finding: coverage certification is silently wrong on 32/300 random machines (10.7 %).** The f45da4e acceptance
  rule is empirical, and its silent-error rate on a broad ocean of mechanisms is far from 0.

### Part 2 — meta-learned hypothesis-space growth

* **Data:** 300 held-out episodes; 725 meta-training records from 300 exploration episodes; 12 full energy build projects.

| arm | certified | exact | silent | queries | exact within 500 / 1k / 2k / 4k queries | steps | energy builds exact / silent |
|---|---|---|---|---|---|---|---|
| Hand_Ordered_Rule | 249 | 217 | 32 | 254 k | 88 / 154 / 198 / 215 | 850 | **0/12** / 1 |
| **Meta_Learned_Growth_Rule** | 276 | **235** | 41 | 276 k | **100 / 168 / 213 / 233** | **403** | **9/12** / 2 |
| Random_Growth_Order | 242 | 213 | 29 | 255 k | 96 / 156 / 197 / 211 | 700 | 7/12 / 2 |
| Shuffled_Episode_Placebo | 272 | 237 | 35 | 283 k | 97 / 165 / 211 / 233 | 625 | 0/12 / 2 |
| f45da4e full space (energy only) | – | – | – | – | – | – | 7/12 / 2 |

* **Outcome: REJECTED FOR THIS SETTING,** by the pre-registered silent ≤ Hand condition (41 vs 32 on micro; 2 vs 1 on
  energy).
* **What it does show:**
  * The meta-learned rule **fixes the energy build-time weakness** (9/12 vs 0/12 for the hand order and 7/12 for f45da4e).
  * It wins the learning curve at every budget, with half the growth steps.
* **Caveats:**
  * On micro-episodes the shuffled placebo matches it (237 vs 235), so that part of the gain comes from action-level
    priors, not from reading the failure signature.
  * On energy builds the placebo gets 0/12, so the signature mapping matters there.
* **Common cause of the silent errors:** each arm's silent rate per certification is 13–15 %. Certification reliability,
  not growth, is the bottleneck.

### Part 4 — ledger predictor retrospective check

* 620 reports were parsed; only 34 (36 including post-priority-A reports) have an unambiguous verdict line.
* With the ledger frozen before priority A, the predictor's `P(gain | category)` ranks **verification lowest** (0.39) and
  transport/alignment **highest** (0.73).
* **The retrospective check FAILS:** the ledger is too sparse and keyword-confounded to point toward what actually
  worked. The prospective comparison still runs as registered.

### Part 3 — distinguishing experiments as a meta-skill (300 held-out protocol episodes; 150 held-out lifecycle episodes)

* **Meta-training:** the class weights learned on 100 source episodes are weak. Counterexamples found per query:
  loop_then_probe 0.030, suspend_resume 0.029, gap_repeat 0.027, repeat_twice 0.023, others 0.019.

| domain | selector | correct | mean queries-to-correct | median | total queries | CPU |
|---|---|---|---|---|---|---|
| protocol (unseen domain) | meta-learned class choice | 124 | 122.0 | 113.5 | 47,138 | 961 s |
| protocol | generic L* random words | 131 | 122.3 | 121 | 47,244 | 1,075 s |
| protocol | memoryless info-gain | **142** | 124.3 | 117.5 | 46,901 | 1,179 s |
| protocol | random classes | 127 | 122.0 | 121 | 47,381 | 985 s |
| lifecycle | meta / generic / info-gain / random | 115 / 117 / 115 / 113 | 109.4 / 110.7 / 109.5 / 109.3 | 107 / 108 / 107 / 107 | ≈ 21.5 k each | 116–167 s |

* **Outcome: REJECTED FOR THIS SETTING.** There is no reduction in queries-to-correct vs generic search on the held-out
  domain, and meta is correct on fewer episodes.
* Queries are dominated by the initial continuation-splitting phase. The choice of continuation class changes little.

### Part 4 — self-evolution over the audited state-learning surface

* **Audit.** u5's `evolvable_learner` exposed only construction costs and an affinity AST. The oc surface (`oc_evolve`)
  exposes four state-learning computations:
  * continuation-class weights;
  * the partition-revision rule;
  * the update-proposal order;
  * the query budget and rounds.
* **Evolution:** 10 proposals per arm, fitness on 20 `ep_val` episodes. Evolution CPU: ledger 91 s, trace 81 s,
  random 166 s.
* Ledger-conditioned and trace-only both accepted the same single edit (random-word weight 1.0 → 0.25), so their surfaces
  are **identical**. Blind random accepted random-word weight 4.0.

| arm (300 held-out episodes; task memory reset) | learning-curve score | correct | queries | CPU |
|---|---|---|---|---|
| Ledger_Conditioned_Learner_Edits (= Trace_Only, identical surface) | 0.331 | 214 | 44,321 | 347 s |
| Blind_Random_Mutations | 0.331 | 215 | 44,368 | 406 s |
| Current_Strong_Learner | 0.323 | 210 | 44,319 | 341 s |

* **Outcome: REJECTED FOR THIS SETTING.** Ledger conditioning beats neither trace-only nor random.
* All evolved surfaces gain about 2 % over the current learner, which is within noise.
* The ledger retrospective check also failed (see above).

### Summary of the meta-level results (all ≥ 300 held-out episodes)

* No meta-level mechanism met its kill criterion.
* The most promising is **Part 2's meta-learned growth rule**: energy builds 9/12 vs 0/12, and a better learning curve
  at every budget. It is rejected only because its higher certification rate came with more silent errors.
* The common blocker is **certification reliability**: empirical coverage agreement is silently wrong on about 11–15 %
  of certifications on random mechanisms.
* **NEXUS_Confirmed** is therefore the f45da4e priority-A stack, unchanged.

## 1. Validation (one-use oc/val 13121–13128, frozen `5432e8d`) — gate FAILED

| arm | independently correct | silent | completed | crash-identical |
|---|---|---|---|---|
| NEXUS_Confirmed (f45da4e stack) | 7/8 | **1** (13127 energy) | 8/8 | 8/8 |
| NEXUS_U5 | 6/8 | 1 | 7/8 | 7/7 |
| Fixed_Policy | 8/8 | 0 | 8/8 | 8/8 |

* The gate required 8/8 and 0 silent. **FAILED.** The failure is preserved, and the sealed test stays closed unless
  `val_b` passes.

### 1.1 Revision 1 (the one disclosed revision; diagnosed on dev only)

* **Change: extended certification** (`src/nexus/oc_cert.py`). After coverage agreement, up to 150 random long-word
  probes (length 6–16, fresh values) are run, and the machine is relearned on any counterexample.
* **Rationale:** Parts 1 and 2 showed that coverage certification is silently wrong on about 11–15 % of mechanisms.
* **Dev evidence** (8 paired energy dev projects, `rev1_*.json`): independently correct 5/8 vs 4/8, silent 1 vs 2,
  abstentions 2 vs 2.
* **Cost:** about 150 extra membership queries per lifecycle learn.
* 13127 (validation) was **not** inspected.
