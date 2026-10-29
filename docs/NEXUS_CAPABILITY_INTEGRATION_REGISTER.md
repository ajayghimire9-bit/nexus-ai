# NEXUS capability / integration register (NOT LOCKED; t7, 2026-10-28)

A failed method does not retire its capability goal. Its component is simply left inactive.

## Status vocabulary

* **experimental:** the component exists but is not used by the confirmation stack.
* **provisionally integrated:** a dev promotion candidate, wired into the confirmation stack and awaiting independent
  confirmation.
* **independently confirmed:** it passed a one-use validation and the sealed test.
* **inactive:** it was tested and left out of the stack.

## Components

### Lifecycle class invention by continuation splitting

* **Module:** `u5_statesplit`.
* **Call site:** `u5_platform.learn_b` (build and `repair_B`), active on every lifecycle stream.
* **Artifact:** the generated `StateMachine_*` class per project, with its witnesses.
* **Evidence:**
  * u5 dev: 15/15 exact, vs 0/15 for the flat dictionary.
  * u5 sealed test: 9/12 for NEXUS_U5, vs 0/12 for the flat-dictionary ablation.
* **Limits:**
  * finite modes plus numeric registers only;
  * the u5 update grammar has size ≤ 3;
  * relearning can miss delayed consequences (see the next component).
* **Status:** independently confirmed (u5 sealed test, as a pillar), in its u5 form.

### Covered relearning

* **Module:** `t7_repair.learn_class_covered` / `Learner2`.
* **Call site:** `NexusArmStrong._learn_b`, active at build and on every lifecycle repair.
* **What it does:**
  * transition × continuation probes from register-diverse prefixes;
  * column-level register search with merging;
  * a size-5 update grammar;
  * early-pruning variable order.
* **Artifact:** none persistent; this is a procedure.
* **Evidence (dev only):**
  * targeted X3 lifecycle tasks: exact 14/20 vs 8/20, key accuracy 0.93 vs 0.54;
  * 8 dev projects: independently correct 6/8 vs 4/8, silent errors 1 vs 2, escalations 0 vs 1.
* **Limits:**
  * 2.4× lifecycle-learning CPU and 2.5× membership queries;
  * energy `E.meter` in full projects still fails (1 silent, 1 abstain on dev);
  * sessions with SUSPEND can time out, which leads to escalation.
* **Rollback:** set `boost = False` and use `PL.learn_b`, which is the u5 behaviour.
* **Sealed t7 evidence (paired, n = 16):** 14/16 vs 9/16 independently correct, silent errors 0 vs 4. The sealed criterion was not met (one build abstain).
* **Status:** provisionally integrated (not independently confirmed).

### Condition-crossing status probes

* **Module:** `t7_repair.crossing_records`.
* **Call site:** `NexusArmStrong._probe` (build) and `_probe_sample` (repair), active whenever ≥ 2 quarantine labels occur.
* **Artifact:** none persistent.
* **Evidence:** included in the 8-project dev comparison above. It was **not separately ablated**.
* **Limits:** its oracle labels are counted. It only crosses fields that look abnormal relative to accepted records.
* **Status:** provisionally integrated.

### Heightened post-repair monitoring

* **Module:** `t7_platform` patch.
* **Call site:** `operate`, active for 2 ticks after a repair (10 records and 6 keys).
* **Evidence:** included in the dev comparison above, and not separately ablated.
* **Limits:** spot checks remain sampling-based.
* **Status:** provisionally integrated.

### Count-based construction costs

* **Module:** `u5_construct` (count policy).
* **Call site:** every value and status synthesis.
* **Artifact:** `artifacts/u5_dev/p2_policy.json`.
* **Evidence:**
  * u5 dev: −40 % CPU at equal solves;
  * u5 sealed test vs NoLearning: +1 project, −16 % CPU.
* **Status:** independently confirmed (small effect).

### Precision-guarded decomposition and type priors

* **Module:** `u5_construct._Bank`, `_Solver`; `u5_platform.synth_status`.
* **Call site:** all synthesis.
* **Evidence:** u5 dev fixes (pdev 8010, 8007).
* **Status:** confirmed as part of the u5 stack.

### Transported-program library function (ΔM)

* **Module:** `t7_transport.as_function`.
* **Call site:** none.
* **Evidence:** Trial 4: −49 % CPU vs Fresh on 46 pairs. It was not compared with Heuristic+ΔM.
* **Status:** experimental (INCONCLUSIVE). Not integrated.

### Rejected or inconclusive mechanisms

| capability | module | outcome | status |
|---|---|---|---|
| Gromov–Wasserstein column alignment | `t7_transport.map_gw` | REJECTED for this setting (no better than a random map) | inactive |
| Matched negative-control library admission | `t7_knockoff` | INCONCLUSIVE (13 candidates) | inactive |
| Matched negative-control state monitors | `t7_monitors` | INCONCLUSIVE (6 dev projects) | inactive |
| Check selection over mutant outputs | `t7_oracle` | REJECTED for this setting (held-out kill 0.24 vs 0.54 / 0.80) | inactive |
| Joint failure-constraint tool invention | `t7_jointtool` | v2 REJECTED for this setting (direct search ties on solves; the tool is about 13× cheaper) | experimental |
| Experiment-procedure translation | `t7_experiments` | v2b REJECTED for this setting (22 % fewer queries than info-gain, but fully loaded CPU higher and fresh synthesis uses fewer queries) | experimental |
| Learner + memory translator | `t7_memory` | v1 REJECTED for this setting (equal solves to unchanged; 15 % cheaper than full replay; contract passed); v2 deferred | experimental |
| 64 KB genome | `t7_genome` | INCONCLUSIVE (no effect; 22.7 KB) | inactive |
| u5 Pillars 3–5 (library, curriculum, meta-improver) | `u5_library` / `u5_curriculum` / `meta_improver` | not promoted (harm / ceiling) | inactive |

## Assembled stack for the t7 confirmation

* **NEXUS_Tournament_Winner** = `t7_platform.NexusArmStrong` + the u5 learner (count costs, hybrid engine, no library),
  entered through `t7_platform.run_project`.
* **The only differences from NEXUS_U5** are the three provisionally integrated components above.

## oc track additions (2026-10-28)

### Extended certification (revision 1)

* **Module:** `oc_cert.learn_class_certified`.
* **Call site:** `oc_platform.NexusArmCertified._learn_b`, at build and on every lifecycle repair.
* **What it does:** after coverage agreement, up to 150 random long-word probes; relearn on any counterexample.
* **Evidence:**
  * dev energy: 5/8 vs 4/8 independently correct, silent 1 vs 2;
  * val_b: 8/8;
  * sealed: 12/15 evaluated, X5 6/7; paired NEXUS_U5: 7/15.
* **Limits:**
  * sealed criterion not met (1 silent, 1 unevaluated);
  * energy is still weak.
* **Rollback:** use `NexusArmStrong`.
* **Status:** provisionally integrated.

### Meta-learned hypothesis-space growth (Part 2)

* **Module:** `oc_learner.TablePolicy` + `learn_episode`.
* **Call site:** none in the confirmation stack.
* **Evidence (300 held-out episodes):**
  * exact 235 vs 217, with a better learning curve at every budget;
  * energy builds 9/12 vs 0/12;
  * but silent 41 vs 32.
* **Status:** experimental (REJECTED for this setting by the silent condition).

### Other oc results

| capability | module | outcome | status |
|---|---|---|---|
| Version-space querying | `oc_learner.vs_cex` | REJECTED (−65 % queries, 2× silent) | experimental |
| Grey-box contract filter | `oc_learner.Learner3._domain` | REJECTED (no query reduction; −11 % CPU) | experimental |
| Experiment-class meta-choice | `oc_experiments` | REJECTED (no query reduction on the held-out domain) | inactive |
| Ledger-conditioned self-evolution | `oc_evolve` | REJECTED (= trace-only; ≈ random; ledger retrospective check failed) | inactive |

## ba track additions (2026-10-28; `docs/NEXUS_BOUNDED_ACCEPTANCE_AND_GROWTH_REPORT.md`)

### Bounded acceptance check
* **Module:** `ba_accept.bounded_cex` (tier 1 exhaustive kind words to horizon h; tier 2 loaded-prefix · kind ·
  shortest-emitting-continuation tests with boundary draws), used by `ba_learn.attempt` and
  `ba_platform.learn_class_bounded`.
* **Call site:** `ba_platform.NexusArmBounded._learn_b`, at build and on every lifecycle repair; replaces oc revision 1's
  open-ended random probing. Unaccepted machines abstain / escalate (oc revision 1 returned the last machine).
* **Label:** `TESTED_WITHIN_STATED_LIMITS` + scope record (alphabet, modes, registers, horizon, tests, value draws, caps).
* **Evidence:** 300 fresh held-out episodes, hand growth: false acceptance among accepted 14.4 % → 0.8 %, solves 214 → 248,
  abstentions unchanged; queries +60 %.
* **Limits:** not a proof; 2 in-scope false acceptances remain; kinds unseen at build are outside the scope.
* **Validation / sealed:** ba/val 8/8 (gate PASSED); sealed 8/16 (criterion NOT MET): X3 + X5 8/8 with 0 silent (every
  relearned machine accepted and correct); X6 0/8 for every arm (no NEXUS false acceptance: all X6 relearns were refused and
  escalated; the X6 human patch of the harness is itself wrong).
* **Rollback:** `NexusArmStrong` / `oc_platform.NexusArmCertified`.
* **Status:** provisionally integrated (sealed criterion not met, so not independently confirmed).

### Learned hypothesis-space growth rule (Part 2 rerun under the bounded check)
* **Module:** `oc_learner.TablePolicy` on `artifacts/ba_dev/records_bounded.jsonl`.
* **Call site:** `ba_platform.learn_class_bounded(growth=...)` (first line; full-space fallback when nothing is accepted).
* **Evidence:** 265 / 300 vs Hand 248, Shuffled 241, Random 213 (sign tests p ≤ 0.0001); false acceptance 1.1 %; energy 12/12.
* **Status:** provisionally integrated (promoted by the pre-registered rule S4; in the sealed stack as the first-line learner
  with the full-space fallback, so its own sealed contribution is not isolated).

### Extended certification (oc revision 1)
* **Status:** inactive in the ba stack (replaced by the bounded acceptance check).

### Self-evolution (oc Part 4) — honest scope
The c84fc76 Part 4 artifacts (weights such as `random_word = 0.25`, `occam` order, budgets, revision flags) demonstrate a
**search over learner configurations**, not NEXUS inventing a new learning algorithm. Status unchanged: inactive.

### Open capability gap found by the ba sealed test
* **Undeclared value-field rename (X6):** detected only by spot checks (7/8, late); not repairable by any arm (the lifecycle
  learner has no field-mapping inference; the harness human patch is also wrong). Status: gap, no component.

## sc track additions (2026-10-28; `docs/NEXUS_SCHEMA_CONTRACT_AND_GROWTH_REPORT.md`)

### Runtime field contract
* **Source:** `src/nexus/sc_contract.py` (`infer`, `ContractRunner`).
* **Call site:** `sc_platform.Program.new_b` (b_kind `contract`) for every lifecycle program deployed by `NexusArmSchema`;
  alarm `B:schema_mismatch` in the sc operator.
* **Activation:** every lifecycle event; a field is checked only on kinds whose accepted machine reads it.
* **Evidence:** dev 10/10 X6-family faults detected at the fault tick, 0 false alarms on LM; val 4/4, confirmation 8/8 at tick 9.
* **Cost:** negligible CPU.  **Limits:** single machine-read fields; structured values only through mappings.
* **Status:** provisionally integrated → passed its one-use validation and confirmation in the sc stack (known classes only).

### Generic field-mapping repair
* **Source:** `src/nexus/sc_mapping.py` (`repair`).  **Call site:** `sc_platform.NexusArmSchema.repair_B` on schema incidents.
* **Evidence:** dev 10/10 (incl. decoy via 1 distinguishing query, nested path, gradual migration); val 4/4; confirmation 8/8.
* **Cost:** ~365–434 charged membership queries per repair (acceptance + mixed tests).  **Limits:** one expected field per
  incident set; ambiguity beyond 24 probes → abstain; relearn path rarely exercised.
* **Status:** confirmed for fresh instances of known schema-change classes (not for unseen classes).

### Corrected simulated human repair (evaluation intervention, not a NEXUS component)
* `sc_platform.HumanRefMachine`: 0 wrong rows on all 48 sc_dev projects; counts as human assistance; privileged.

### Learned growth rule — separate retest (fallback disabled)
* Fresh sc/ep_held3: 278/300 vs Hand 256, Shuffled 248, Random 226 (sign tests p ≤ 1.5e-6); 0 wrong among accepted in every arm.
* **Status:** provisionally integrated; its advantage over hand / shuffled growth is now replicated on two fresh held-out sets
  (ba, sc). In the sc stack it is the first-line learner (full-space fallback present).

### Bounded acceptance check
* Status unchanged (provisionally integrated); in the sc confirmation every accepted relearn / mapping was correct.

### Known limitation
* Some energy builds (dev 13327) abstain in every arm: the full-space learner fails register search.

## x7 — expression adapters, dependency pruning, reset-aware register search (2026-10-28; report `docs/NEXUS_COMPOSITE_SCHEMA_AND_X7_REPORT.md`)

| component | source | call site | activation | evidence (scope) | cost | limits |
|---|---|---|---|---|---|---|
| reset-aware register search | `src/nexus/x7_regsearch.py` (`Learner2X`, `Learner3X`, `learn_class_bounded`) | `NexusArmX7._learn` (build + relearn) | every lifecycle learn in x7 arms | 13327 solved (0.58 s vs abstain); identical class on 13/13 previously solved sc dev builds; unit test | faster or equal | sound only for the u5 register language (acc-free update = reset) |
| dependency analysis + pruning | `src/nexus/x7_contract.py` (`reads`, `prune`, `sensitivity`, `infer`) | `NexusArmX7._payload` | every deployed build | exact rewrite; 13/54 builds unbound a field, 4 dropped a distractor read; no outcome effect measured | < 0.1 s | static analysis of this machine language only |
| expression grammar | `src/nexus/x7_expr.py` | `x7_mapping.repair` | on incident / notice | X7a 4/4, X7b 4/4 (confirmation) | ~7k candidates, 1–3 s | size ≤ 5 bodies, constants {1, 2, 10, 100, 1000}, one target field |
| adapter repair + composite acceptance | `src/nexus/x7_mapping.py` | `NexusArmX7.repair_B` | B:schema_mismatch, B:shape_change, other B alarms | A 15/16 vs FieldOnly 7/16 (8:0 on X7, p = 0.0039) | 297–445 mq per repair | TESTED_WITHIN_STATED_LIMITS; probes decide when the archive is uninformative |
| runtime contract with notices | `src/nexus/x7_contract.py` (`ContractRunnerX`) | `_x7_runner` in the x7 platform | deployed payloads with `x7=True` | 0 silent lifecycle errors in A on val + test | per event | shape notices can cost a benign verification (~360 mq) |
| x7 platform + corrected human | `src/nexus/x7_platform.py` | `scripts/x7_run.py` | x7 splits | helper 0 wrong rows (38 projects) | — | shared A-stream build across x7 arms (caused the shared 13495 failure) |
Full-system confirmation objective NOT met (15/16); expression capability beyond FieldOnly supported; growth-policy comparison inconclusive.

## mi — learning-method invention for the register-hypothesis procedure (2026-10-28; report `docs/NEXUS_EXECUTABLE_METHOD_INVENTION_REPORT.md`)

| component | source | call site | activation | evidence | limits |
|---|---|---|---|---|---|
| LPL procedure language + generic operators | `src/nexus/mi_lpl.py` | `mi_learner.lpl_domain` | mi experiments only | seed = existing procedure (identical) | human-written primitives |
| procedure-driven full-space learner | `src/nexus/mi_learner.py` (`LearnerMI`) | `scripts/mi_eval.py`, `mi_discover.py` | after the shared fast path fails | invented procedure +9 dev-unfamiliar episodes on validation (19 vs 10 of 60) | gate not passed; **not integrated** into any NEXUS runtime arm |
| invented procedure #17 | `artifacts/mi_dev/select_evolve.json` | — | inactive | gain from evidence-derived constants (ablation) | confirmation not run |

## MI-2 — method invention and one step of recursive improvement (2026-10-29; report `docs/NEXUS_METHOD_INVENTION_AND_RECURSIVE_IMPROVEMENT_REPORT.md`)

| component | source | call site | activation | evidence | limits |
|---|---|---|---|---|---|
| CPU-capped procedure-driven learner | `src/nexus/mi2_learner.py` (`full_space`, `LearnerMI2`) | `scripts/mi2_discover.py` `evaluate`, `scripts/mi2_eval.py` | mi2 experiments only, after the shared fast path fails | witness diagnosis 18/18; validation run for 11 arms | **not integrated** into any NEXUS runtime arm |
| A5 human-written evidence-aware procedure | `src/nexus/mi2_learner.py` `A5_PROG` | `mi2_eval.arm_domain` | evaluation reference only | 74/90 fresh dev-unfamiliar (SUBH 28/30), 1 shared silent | human-written; not a NEXUS-generated method; **not integrated** |
| A6 generic direct synthesis | `src/nexus/mi2_learner.py` `a6_domain` | `mi2_eval.arm_domain` | evaluation control only | 59/90 | cap 3,000 expressions |
| generated procedure A2 (evolve L3 #10) | `artifacts/mi2_dev/select_a_evolve_L3.json` | — | **inactive** | 14/90 (vs A0 6, A5 74); gain = duplicated closure round (parameter-equivalent) | validation gate failed; confirmation not run |
| improver library call site (`mutate_lib`) | `src/nexus/mi2_lpl.py` | the mutation call in `mi2_discover.propose` (arm b1 only) | **inactive**: no accepted procedure (`artifacts/mi2_accepted.json` absent) | unit-tested: identical to `mi_lpl.mutate` with an empty library | Milestone B not run |

Known gap: the shared bounded acceptance check accepted a wrong `acc + 3` machine (mi2/val seed 26801) in every arm able to
express it.
