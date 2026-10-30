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

## MI-3 — acceptance reliability and discovery-efficiency diagnostic (2026-10-29; report `docs/NEXUS_MI3_ACCEPTANCE_AND_DISCOVERY_DIAGNOSTIC.md`)

Every MI-3 component is **diagnostic / experimental**. None is integrated into a NEXUS runtime arm.

| component | source | call site | activation | evidence | limits |
|---|---|---|---|---|---|
| interface-closure acceptance check (`new_check`, `interface_cex`) | `src/nexus/mi3_accept.py` | `full_space3`, the acceptance step of every MI-3 evaluation | MI-3 experiments only | one-use audit: 0/120 incorrect accepted (old check 30/120, all dropped-kind), 119/120 correct (old 119/120); 26801 regression test | needs a declared event-kind interface (`Episode3.interface`); a missing kind is rejected, not learned; constructed audit distribution, not a production error rate |
| `full_space3` learner stage | `src/nexus/mi3_accept.py` | `mi3_search.eval_one` (Stages 2–4) | MI-3 experiments only | 0 silent errors in 576 calibration + 520 winner evaluations | **not integrated**; the x7 runtime still uses `ba_accept` |
| staged evaluation (screen 6, TAU 0.75, 10 % rejection audit) | `src/nexus/mi3_search.py`, `artifacts/mi3_schedule.json` | `scripts/mi3_discover.py` (E-S, R-S) | MI-3 discovery only | calibration 36.6 % CPU saving, top quartile kept; in discovery only about +25 % candidates for random search and none for evolution; no downstream gain | the audit can only afford cheap rejected candidates |
| 8 discovery winners | `artifacts/mi3_disc/*.json`, `artifacts/mi3_freeze.json` | `scripts/mi3_eval.py` only | **inactive** | 4–7/30 fresh unfamiliar (A0 3, MI-1 7, MI-2 A4 12, A6 19, A5 25), 0 silent | not promoted; Milestone B not run |
| job runner + budget guard | `scripts/mi3_jobs.py`, `scripts/mi3_budget.py` | every MI-3 stage | MI-3 tooling | PID and exit-code tracking, finite timeouts, ceilings enforced | `mi_exec` exits 0 even when its child fails; the status line must be read |

Correction to the MI-2 known gap above, preserved as written: the accepted `acc + 3` update at 26801 was correct. The silent error
came from a declared event kind (ADD) that was absent from training and therefore never probed. MI-3 §0.3 has the details.

## Multi-world autonomous-learning campaign (2026-10-29; report `docs/NEXUS_MULTI_WORLD_AGI_CAMPAIGN_REPORT.md`)

* **Built:** new versioned modules only (`src/nexus/campaign/`).
  * Six worlds: A data, B temporal, C spatial (held out), D planning, E causal (held out), F programs.
  * 24 families × 4 levels, a shared typed substrate and enumerator, learner state (R, L, π, M), and an 11-step agent loop
    with entropy queries, confirmation queries and a chance-fit commitment bound.
  * Not integrated into any runtime.
* **Commits:** protocol `62204b3`, source results `324010a`, meta clones `0c32d0a`, evaluation and report: this commit.
* **Results:**
  * The held-out C + E target was **not met**: Full − Placebo −1.0 pp, Full − Init −2.1 pp, Full − Scratch +4.2 pp (Scratch
    is the weakest arm), 0 of 3 repetitions positive, 0 silent errors by Full on C and E.
  * Within-world reuse is real but narrow: a sum-of-squares macro family learned from F3 solves withheld-family F4
    compositions.
  * There was no meta-improvement: 0 of 26 edits were adopted, so M* = M0.
* **Capability status:** autonomous library and representation construction is **demonstrated in a minimal form** (MDL
  anti-unification over verified solutions). Cross-world transfer, a learned experiment policy, and recursive improver
  gains are **not demonstrated**.
* **Budget:** 3,478 of the 4,500 s campaign cap; the carried balance is 7,216 s.
* **Errata to the `86953d3` summary** (see the campaign report §2):
  * F.F4.L4.36012 was solved by Full and Fixed in r0 and r2, so a level-4 task *was* solved.
  * Full lineages had a baseline admission solve in 15 of 52 rounds.
  * B / D is 12 distinct tasks per arm, all unsolved (240 arm–task evaluations), not 64.

## Multi-world campaign Phase 2 (2026-10-29; report `docs/NEXUS_MULTI_WORLD_PHASE2_REPORT.md`)

* **Built:** new modules `src/nexus/campaign2/`:
  * the expressivity / reachability audit, with lazy lambda pools replacing the excluding lambda cap;
  * the provisional experience archive P against validated R / L;
  * graded admission and a locked acceptance barrier;
  * draft-origin tags and pure-synthesis F tasks;
  * full-rollout M evaluation;
  * untouched C5 / C6 / E5 / E6;
  * fcntl-locked one-use claims.
* **Commits:** errata `b07e86b`, protocol `b21b171`, source `da7dbed`, meta `63fa3c7`, results: this commit.
* **Results:**
  * Every R / L proposal of the P cohorts was provisional and refused, so **0 validated items came from incomplete
    experience**.
  * All evaluation arms solve 2 of 32 (identical solver states): withheld, fresh-seed C / E and untouched-mechanism transfer
    are all **0.0** against Init, Placebo and Scratch.
  * B / D: 0 of 4. Untouched: 0 of 16.
  * 0 of 3 full-rollout meta-edits were adopted, so M* = M0 and the improver panel is 0 of 12 for all improvers.
* **Capability status:**
  * not demonstrated: learning from incomplete experience, the improver gain, and unseen-mechanism transfer;
  * demonstrated: the expressivity audit and the full-rollout meta-evaluation harness as working infrastructure.
* **Budget:** 2,598 of the 3,200 s Phase 2 cap; the carried balance is 4,618 s.

## Phase 3: real-pipeline DE world + Spark 4 ANSI (2026-10-29; report `docs/NEXUS_PHASE3_REAL_PIPELINE_AND_SPARK_REPORT.md`)

* **Built:**
  * the `src/nexus/campaign3/` real-pipeline project world on SQLite and Spark 4.0.1 ANSI, with an independent
    hidden-batch evaluator;
  * a DE learner on the shared experience, admission and M interfaces: generic repair operators, an evidence → operator
    policy, admitted skills, a failure archive, differential SQLite investigation;
  * untouched C7, C8, E7 and E8;
  * the B / D expressibility, reachability and discoverability audit;
  * JDK 17 and PySpark, installed unattended.
* **Commits:** freeze `9209c0c`, then the Stage 2, Stage 3 and results commits.
* **Results:**
  * **Operating cycle demonstrated** on dev projects: investigate → attempt → learn → repair → verify → reuse, including
    reuse on Spark.
  * Unseen DE projects: every arm completes 6 of 12. Full uses 10–58 % fewer runtime executions than Memory-Reset and
    Baseline at matched completion, but not fewer than Fixed-M0.
  * Worlds: 0 of 16 for every arm, including untouched C7 / C8 / E7 / E8 at 0 of 8.
  * Failure memory: no demonstrated value. Meta-edits: 0 of 3 adopted, so M* = M0.
  * 1 silent DE error in every arm (the G6 holdout).
* **Capability status:**
  * demonstrated: the real-runtime repair cycle and a skill-reuse **cost** effect;
  * not demonstrated: a completion gain, transfer to untouched mechanisms, value of incomplete experience, and an improver
    gain.
* **Budget:** 2,505 of 3,200 s; carried 2,113 s.

## Phase 4: DE / PySpark scaling, de_accept_v2, multi-fault failure learning (2026-10-29; report `docs/NEXUS_PHASE4_SPARK_AND_DE_SCALING_REPORT.md`)

* **Built:** `src/nexus/de_phase4/`:
  * real `.sql` / `.py` adapter (sqlglot / ast lifting, patches + PATCH.diff, the evaluator runs the submitted file);
  * `de_accept_v2`: K-fold held-back split, invariant and relabelling probes, ambiguity closure with learned preferences or
    abstention;
  * 8-mechanism multi-fault world (F7 / F8 untouched);
  * failure archive with verified partial repairs and refuted-submission preferences;
  * Spark start-up 2–3.5 s (was 33 s) and 17.9 ms per script;
  * DE-only lineage with a 35-edit improver space.
* **Commits:** protocol `2701de8`, then the freezes `a9ed328` / `499d6e5` and the results commit.
* **Results (24 unseen projects, 17 arms):**
  * **0 silent errors in every arm**: target met, at the cost of about 10 / 24 ambiguity abstentions.
  * Full − Memory-Reset **+5.6 pp** (CI −4.2, 15.3); Spark half +11.1 pp; untouched F7 / F8 **+16.7 pp** (CI 8.3, 25.0).
  * Full − Solved-Only **+5.6 pp** (CI 2.8, 8.3): small failure-memory signal.
  * Cost saving 6 % vs Memory-Reset and 2 % vs Baseline (target 20 %: not met).
  * Improver: 1 / 0 / 1 edits adopted, one degenerate (`cross_engine = off`); M* ≤ M0 on the panel.
  * Spark: Init 6 / 12 (Phase 3: 1 / 6).
* **Capability status:**
  * demonstrated: real-file repair on SQLite and Spark with zero accepted wrong repairs; Spark scale;
  * suggestive: value of incomplete experience; untouched-mechanism gain;
  * not demonstrated: ≥ 10 pp completion, ≥ 20 % cost, improver gain.
* **Budget:** 1,419 of the 1,800 s Phase 4 cap; carried 694 s.

## Phase 5: learning to investigate and transferring the procedure (2026-10-29; report `docs/NEXUS_PHASE5_INVESTIGATION_PROCEDURE_REPORT.md`)

* **Human engineering:**
  * requirement decision points whose business answer reverses per project;
  * structured requirement documents (a structured-contract diagnostic; no language model);
  * a 1-row stakeholder clarification;
  * a typed investigation-policy language, its interpreter and actions;
  * the fixed policy F0;
  * the corrected admission rule (equal-zero and same-completed-set loopholes closed);
  * a Phase 5 closure extension.
* **Model contribution:** none (no LLM used; cost gap documented).
* **Learned memory:**
  * claim-trust weights, counterexamples and action outcomes, with provenance and scope;
  * Phase 4 repair memory.
  * Failure-derived records changed later trust decisions (`agi5_demonstration.json`).
* **Learned procedures:** composed automatically from a minimal seed in 3 / 3 lineages
  (search → [read_all, resolve] → ask → submit), stored with interface, applicability, provenance and utility, and
  rebound to new schemas.
* **Demonstrated transfer** (72 one-use targets):
  * Fresh F0 45 / 72 with 0 wrong repairs and 14 / 14 justified abstentions.
  * Memory + F0 48 / 72 (+4.2 pp, Holm p 0.15) **but 4 / 6 / 1 accepted wrong repairs** (over-confident learned trust on
    undecided conflicts), and 21–31 % cheaper on the same completed projects.
  * Learned procedure vs F0: −2.3 pp (no gain).
  * Removing stored procedures: −11 pp.
  * Placebo: no usable procedure.
* **Not demonstrated:** a learned procedure beating the strong fixed policy; a safe experience gain; external validity;
  improvement of the improver.
* **Budget:** 476 of the 600 s Phase 5 cap; carried 218 s.

## Phase 6: nine-paradigm multi-language arena, calibrated trust, invented skills, evolvable improver (2026-10-29; report `docs/NEXUS_PHASE6_NINE_PARADIGM_HYBRID_REPORT.md`)

* **Human engineering:**
  * the multi-language substrate (sqlglot Hive / Postgres / Snowflake, PySpark, dbt Jinja + schema.yml, read-only Scala;
    SQLite / DuckDB / Spark);
  * the nine-paradigm, three-tier arena with cross-engine hybrids;
  * `de_accept_v3`;
  * the calibrated-trust rules;
  * the primitives of the skill-invention, procedure and improver machinery.
* **Model contribution:** none.
* **Learned:**
  * invented skills (role abstraction + anti-unification): one admitted, the CDC tombstone method, in 3 lineages;
  * calibrated trust records (2–6 per lineage);
  * automatically composed procedures, all converging on a one-document shortcut;
  * 1 adopted improver edit.
* **Demonstrated transfer** (72 one-use targets):
  * none beyond the base system: Fresh F0 35 / 72, Learned memory + F0 35 / 72, Full 33 / 72;
  * 29 accepted wrong repairs across arms, all point-in-time (an undecided requirement already implemented by the legacy
    pipeline; one-document shortcut);
  * every attribution contrast 0;
  * improver panel: no difference.
* **Not demonstrated:** completion / cost / safety gains, value of failure memory, of the skill library or of the
  procedure, learning to learn.
* **Budget:** 3,282 of the 3,600 s Phase 6 cap; the grant has 718 s left, plus the untouched 218 s pot.

## Phase 7: learning from incomplete programs, method consolidation, transfer (2026-10-29; report `docs/NEXUS_PHASE7_DEEP_HORIZON_CONSOLIDATION_REPORT.md`; erratum `docs/NEXUS_PHASE6_ERRATUM.md`)

* **Human infrastructure** (shared by every arm):
  * dedup-on-`id` parameterisation (fixes an unrepairable mechanism);
  * de_accept_v7 gate repair (the false `corruption` rejection of grouped aggregates);
  * bounded archive search (neutral / worse retention, progressive widening, operator interleaving, SQLite gate screen);
  * requirement-coverage barrier;
  * legacy-contradiction projects;
  * the strong fixed investigation strategy.

  Base completion of the fresh fixed endpoint: 51 / 72, vs 35 / 72 in Phase 6 (different draws).
* **Automatic abstraction:** six distinct admitted methods, all recombinations of authored operators:
  * four single-operator specialisations;
  * two multi-operator compositions (dedup-latest → drop-tombstone; normalise → require-nonempty, the latter supported
    by a partial program of an unsolved project).
* **Learned procedures and decisions:** `check_coverage → ask(first)` (both Full repetitions, confirmed on untouched
  projects, used on every later source batch); delayed-utility archive policy.
* **Verified transfer:** none.
  * Primary: Full vs fresh −4.9 pp; Full vs trained fixed learner −4.9 pp.
  * Learned decisions: −2.8 pp. Skill library: −2.1 pp, although exercised (bound in 11–42 rows).
  * Tier 3: 0 / −6.2 pp.
  * 7 wrong rows, all on one P5 project (a documented-but-unimplemented requirement the barrier does not block on).
* **Untested hypotheses:**
  * the improver (M fixed; comparator implemented and unit-tested; panel unopened);
  * failure memory (no Solved-Only cohort);
  * learning-to-learn;
  * external cross-domain transfer.
* **Budget:** ~2,047 of the 2,600 s cap; the pool has ~1,089 s left.

## Phase 8: learning to learn through future transfer (2026-10-29; report `docs/NEXUS_PHASE8_FUTURE_LEARNING_AND_TRANSFER_REPORT.md`)

* **Human infrastructure** (shared by every arm):
  * coverage v8, semantic obligations: absent implementations block; consistent-cut rule; misleading comparisons rejected
    on dev cases;
  * bounded method queue with a shared total work budget;
  * future-learning round machinery: behaviour-signature screen, paired clone rollouts, F0 downstream evaluation,
    confirmation;
  * the F0 prior for both cohorts.
* **Automatic abstraction:** one method admitted (FixedLearner_r0: `dedup_latest → exclude 'D'`, a work saving). Of 66
  candidates, 15 had partial-program support; none was admitted.
* **Learned procedures:** none adopted. Four Full rounds: 3 downstream ties, 1 uninformative (clone ran out of time).
  One exercised edit changed the evidence acquired (0 vs 36 documents read; 1 vs 5 trust records) without changing
  downstream decisions.
* **Verified transfer** (72 fresh targets, 648 rows, **0 accepted wrong repairs**):
  * fresh 51, trained fixed learner 53 / 53, Full 51 / 51;
  * A2 − A0 0.0 pp, A2 − A1 −2.8 pp, A3 − A1 −2.8 pp, A1 − A0 +2.8 pp;
  * the only gains are two P5 targets solved through calibrated trust acquired by the fixed procedure.

  This is learning from experience, not learning to learn.
* **Untested:** meta-learning (no adopted procedure); the improver (S3 = 0 s); failure memory; cross-domain transfer (no
  shared executable interface with the `campaign/worlds` TaskView).
* **Budget:** ~1,562 of the 2,100 s cap; pool remaining ≈ 1,027 s.

## Phase 9: measurable future value; capability roadmap (2026-10-29; report `docs/NEXUS_PHASE9_LEARNING_VALUE_AND_CAPABILITY_ROADMAP.md`)

* **Human infrastructure** (evaluation only):
  * evidence-stratified blocks (6 strata) and balanced 9-family cycles;
  * the future-learning comparator, with per-task exposure, C_acquire / C_future / C_discovery accounting and proxy
    sensitivity;
  * the predeclared selection rule.
* **Autonomous changes:** none (Stages 2–3 not run).
* **Verified benefits:** none.
* **Sensitivity audit** (development):
  * equivalent and irrelevant-memory controls pass;
  * useful-vs-removed and useful-vs-corrupted trust **fail**: 5 / 9 tasks reach no repair candidate; the single question
    rescues single-conflict tasks; corrupted trust fails safe;
  * cheaper-equivalent and method channels not run (the first audit timed out with no incremental saving).
* **Untested hypotheses:**
  * learning to learn;
  * autonomous procedure improvement;
  * method causal utility;
  * the improver M;
  * failure memory;
  * cross-domain transfer;
  * external SQL repair (BIRD-Critic not yet checked);
  * local-model assistance.
* **Budget:** ~168 of the 900 s authorised (no new grant); the one-use `agi9de/confirm` is unopened.

## Phase 9B: rebuilt sensitivity gate (2026-10-29; report section in `docs/NEXUS_PHASE9_LEARNING_VALUE_AND_CAPABILITY_ROADMAP.md`)

* **Human infrastructure** (evaluation):
  * structure-only gate-set screen with a fresh memory (reachable, multi-conflict K ≥ 2);
  * stepwise-saved controls;
  * disclosed composite extension of the skill screen.
* **Autonomous changes:** none (paired comparison not run).
* **Measured** (development):
  * calibrated trust from experience is necessary for every multi-conflict completion of the trained memory: 4 / 6 vs
    0 / 6 with trust removed or corrupted (0 wrong);
  * the comparator ignores equivalent and irrelevant memory and detects redundant acquisition cost;
  * the learned method library (6 canonical methods) cuts work 56 % on P6 (4 / 4) but changes **no** completion in
    24 screen projects.
* **Gate:** 5 / 6, not passed. The one-use confirmation set is unopened; an owner decision on the skill control is needed.
* **Untested:** autonomous procedure improvement and its repeatability across parents; completion-enabling methods; the
  improver M; cross-domain transfer.
* **Budget:** ~149 of 950 s; the pool keeps ≥ 262.586 s reserve plus ~801 s unspent under the cap.

## Phase 10: unified Phase 9B completion + wake–sleep self-evolution (2026-10-29; report `docs/NEXUS_PHASE10_UNIFIED_WAKE_SLEEP_SELF_EVOLUTION_REPORT.md`)

* **Human infrastructure:**
  * coverage v10 legacy-baseline conflict rule;
  * wake–sleep machinery (P\* store, MDL + LOPO promotion, contract-guarded dreams, pairwise ranker with 70 / 30
    guided / fallback children, π\* replay rounds, M\* round);
  * a roles memo (output-identical);
  * the 48-target manifest with repository / family splits;
  * the substrate check (23 / 23 decided truths execute; multi-table / Polars / CDC envelopes / MERGE / QUALIFY /
    external repositories not implemented).
* **Autonomous changes:**
  * 16 promoted methods (9 with partial-program support);
  * a learned ranker (held-out pair accuracy 0.83–0.97);
  * calibrated trust.
  * **No adopted π\* or M\*** (the M\* rejection traced to a completeness-check discrepancy, disclosed).
* **Verified benefits** (48 unseen targets, 576 rows):
  * trust from experience: C1 − B3 **+12.5 pp (p = 0.032)**, multi-conflict 0 / 7 → 6 / 7;
  * learned ranker: +2.1 pp (n.s.), 2–3 of 15 candidate-starved searches rescued;
  * invented library: 0; count prior: 0; P\*: 0; Tier 3: no gain; curve flat after N25.
* **Accepted wrong repairs:** 1 / 576, from a coverage-application defect in shared infrastructure (diagnosed; fix
  proposed).
* **Gate 1:** 5 / 6 (control 6 fails twice); `agi9de/confirm` unopened.
* **Untested:** an improved procedure or improver; completion-enabling methods; cross-domain transfer; multi-table
  repositories.
* **Budget:** ~1,773 of 3,500 s; ~2,291 s remain, including the reserve.

## Phase 10B: bridge expansion, valley-crossing macros, confirmation (2026-10-29; report `docs/NEXUS_PHASE10B_BRIDGE_EXPANSION_AND_CONFIRMATION_REPORT.md`)

* **Human infrastructure** (all arms):
  * ROUND primitive `round_uncast` (closes the audited expressiveness gap);
  * idempotent coverage application (0 / 618 wrong);
  * fixed M\* validation gate;
  * ranker-guided bridge expansion (40 / 30 / 30 by expansion count);
  * valley-crossing detection and promotion priority.
* **Autonomous changes:**
  * the first adopted M\* edit (rep0: MDL threshold 10);
  * 8 promoted methods, 1 valley-crossing;
  * learned rankers;
  * calibrated trust.
* **Verified benefit** (48 fresh targets, 2 repetitions): Full − fresh **+12.5 pp in both** (p ≈ 0.03), from:
  * calibrated trust: +8.3 pp;
  * learned ranking: +6.2 pp.
* **No benefit:**
  * learned macros (0);
  * bridge expansion (0);
  * Tier 3 (7 / 20 everywhere);
  * the 18-project one-use confirmation set (11 / 18 for every arm).
* **Gate 6:** passed under the combined definition. The library-only check shows the pass came from learned ranking (no
  macros 3 / 3; macros + fixed guide 0 / 3).
* **Untested:** unfamiliar-composition transfer; a matched bridge-for-all 2 × 2; multi-table / MERGE / CDC.
* **Budget:** ~1,560 of 1,800 s.

## Phase 10C (revised): audit, withheld compositions, external audit, shared-stream M* (2026-10-30; report `docs/NEXUS_PHASE10C_AUDIT_AND_COMPOSITIONAL_REPORT.md`)

* **Human infrastructure** (all arms; not NEXUS learning):
  * `fixes10c` — no submission while a resolved decision point has indistinguishable end-to-end effects. Closes the
    Phase 10B X2 training slip and the dev H5 case.
  * Numeric (rep, step, task) random streams.
  * search10c — macros as atomic children at every node, with stage-local residual-symptom preconditions.
  * Residual-symptom ranker tokens and trace rewriting over L0 ∪ L\*.
  * One bridge machinery for fixed and learned guidance.
* **Corrections to earlier reports:**
  * Phase 10: 7 (not 9) of 16 promoted methods have partial support.
  * "197 → 85 runs" covers 2 P6 projects, not 4.
* **Demonstrated:**
  * Shared-stream determinism: renamed clones give identical trajectories and memories.
  * Errors: 0 training wrong in 120 tasks; 0 Stage 2 evaluation wrong in 154 rows.
  * A 16-task external failure taxonomy: 0 of 16 ingested as written; first failures 10 loader / dialect, 2 multi-table,
    4 expressiveness.
  * 1 external repair, behind an adapter.
* **Not demonstrated:**
  * Macro transfer to withheld compositions. A3 − A1 and A4 − A2 = 0 on both draws, but the libraries were nearly empty
    (rep0: 0, rep1: 1): leave-one-paradigm-out admission cannot validate mechanism-specific macros.
  * A learned-guidance gain beyond +1 (+0 / +1 withheld).
  * Synergy (0 targets needed both).
  * A useful M\* edit: `dream_ratio` 0.6 tied 6 vs 6, not adopted; the downstream check was inconclusive (3 vs 2 on 7
    common Draw C targets; rows incomplete).
* **Open:**
  * A predicate-placement verifier gap: 1 wrong Draw C submission (96088; a filter moved before dedup-latest).
  * Draw B / Draw C rows left unrun at the stage ceilings.
  * L\* transfer with a mechanism-matched admission rule.
* **Budget:** 1,426 of 1,800 s; protection 0 violations; `main` untouched.

## Phase 10D: out-of-sandbox multi-table DAGs (2026-10-30; report `docs/NEXUS_PHASE10D_OUT_OF_SANDBOX_DAG_REPORT.md`)

* **Human infrastructure built** (`src/nexus/de_phase10d/`):
  * a 3-node stg_ → int_ → fct_ DAG IR;
  * Debezium CDC envelopes, QUALIFY latest-per-key, pre-aggregated / typed / as-of joins, MERGE INTO with soft-delete
    detection;
  * DuckDB, SQLite, Polars 2.1 and PySpark 4.0.1 lowerings;
  * Snowflake / Postgres / Hive / dbt / Scala legacy lifters;
  * 3–5-table, 60–120-column workspaces;
  * 13 fault mechanisms and generic column-parameterised L0 operators.
* **Gate 0:** passed 100 % (twice).
* **Shared verifier amendments,** before any target: minimal-change dedup ordering, Occam pruning, two visible batches,
  about 2× rows.
* **Demonstrated** (48 one-use targets, 2 repetitions):
  * learned search guidance adds **+4 held-out multi-node completions in both repetitions** (14 → 18 of 24; from 3-fault
    compositions C5 and C6), with no ordinary regression;
  * learning curve 14 → 17/18 → 18 → 18, with search work 9,891 → about 5,700 executions;
  * **0 wrong repairs** in 528 evaluation rows and 240 v2 training tasks;
  * mechanism-matched admission promoted 4 / 6 macros (the Phase 10C admission flaw is fixed).
* **Not demonstrated:**
  * net completions from learned macros on wide schemas (A4 − A2 = 0; A3 − A1 = 0);
  * guidance × macro synergy (0);
  * a DAG-localisation gain (0 / −1).
* **Open:** the `replay` mechanism is unsolved by every arm (9 targets). Training v1 had 3 wrong training submissions,
  superseded before evaluation and disclosed.
* **Budget:** 936 of 2,400 s; protection 0 violations; `main` untouched.

## Phase 10E: replay macros on wide DAGs, the 96088 gap, external ingestion (2026-10-30; report `docs/NEXUS_PHASE10E_REPLAY_MACROS_AND_EXTERNAL_INGESTION_REPORT.md`) — NOT LOCKED

* **Corrected:** the Phase 10C account of 96088 (a filter before dedup) was wrong. The cause was a missing window-start
  predicate.
  * New guard (`de_phase10e.fixes10e`): 0 false accepts on 96088; 0 false abstains on 342 Phase 10C truths.
  * The shadow-sequence witness is implemented and unit-tested in both substrates.
* **Diagnosed:** Phase 10D verified 0 replay repairs because of reachability, not verification. Truth was visible-ok and
  hidden-ok 25 / 25, but sat at fixed-order position 294–961 with a median of 29 role twins.
* **Human infrastructure (shared by every arm):**
  * `ckey` / `arrival` schema roles;
  * a two-step `add_partition → set_dedup` dedup;
  * `deterministic_dedup` and `latest_state_witness` acceptance rules;
  * admission with 30 draws plus no-bind retries;
  * a general external loader with a multi-table binder (`extload10e`).
* **Demonstrated** (fresh one-use draw, 48 targets, 336 rows, **0 wrong**):
  * learned guidance +21 held-out replay compositions in **both** repetitions (A1 0 → A2 21 of 24);
  * in rep1, the admitted replay macro L5 (`add_partition → set_dedup`) added **+3 completions beyond learned guidance**
    (A4 24 versus A2 21). These are the three hardest 3-fault compositions (R5 102036 / 102038, R8 102045), each solved only
    with L5 as an atomic step. A3 − A1 = +18;
  * A4_rep1 held-out search work was 2,618 executions, against 5,653 for A2_rep1;
  * replay repairs were verified in training (6 / 7 and 5 / 7 S_replay).
* **Not demonstrated:** replication of the L\* gain. In rep0 the replay macro candidate lost its `ckey` key role through a
  dream-witness tie and was rejected, so L\* was untestable there by the pre-registered precondition.
* **External audit:** 16 / 16 ingested natively (Phase 10C: 0); 10 expressible; 4 reached; 3 verified, of which **1** is a
  genuine repair (T09); 1 wrong (T16, a visible-sample gap). The 6 inexpressible tasks need CASE, MIN, COUNT(col), MERGE, JSON
  paths, or joins of aggregated inputs. Development measurement (the loader was developed on these 16 texts).
* **Open:**
  * 1 rep1 training wrong (a partition on orders that the visible batches cannot distinguish);
  * the dream-witness key / order tie;
  * T16's visible-sample gap.
* **Budget:** 928 of 1,400 s (surplus remaining 910 s); protection 0 violations; `main` untouched.

## Phase 10F: subgroup abstraction, decoupled evaluation, frozen-guidance and atomic-dedup controls (2026-10-30; report `docs/NEXUS_PHASE10F_SUBGROUP_ABSTRACTION_AND_DECOUPLED_EVAL_REPORT.md`) — NOT LOCKED

* **Abstraction (`de_phase10f.abstract10f`):** Abs_subgroup (role-consistent subgroups alongside the whole-group candidate) admitted
  the `(ckey, arrival)` replay macro in **both** streams, at step 90 (rep0) and step 100 (rep1), with the dream teacher unchanged.
  * Abs_current (whole-group intersection) never admitted a valid one.
  * Neither rule had one at step 50 (support threshold 3), so the pre-registered verdict is **subgroup insufficient**.
* **Shortcut removed (`world10f`):** 0 of 340 evaluation rows order the replay dedup by quantity (Phase 10E: 16 / 24).
* **Fresh one-use draw:** 340 of 576 rows; 22 complete held-out targets; **0 wrong**.
  * A2 = A4 = Bl = 22 / 22 in both streams, so learned guidance saturates the held-out set.
  * A4 − A2 = 0 and A4 − Bl = 0 (atomic dedup is as good, and cheaper).
  * A3 − A1 = A3 − Bf = +17 (the macro helps only under fixed guidance).
  * A4 − A4f (frozen G_L\*): 0 / +18, mixed.
* **Phase 10E training wrong closed:** new `justified_dedup` rule (5 wrong accepted paths → 0). A residual dirty-partition gap
  remains: 1 rep1 training wrong (104529), mechanism unconfirmed.
* **Tracked ledger:** `docs/NEXUS_COMPUTE_LEDGER.json` (verifiable with `scripts/agi10f_ledger.py verify`).
* **Budget:** ≈ 700 of 950 s; the 300 s buffer was not drawn. Protection 0 violations; `main` untouched.

## Phase 10G: learning what evidence to obtain next (2026-10-30; report `docs/NEXUS_PHASE10G_EVIDENCE_ACQUISITION_REPORT.md`) — NOT LOCKED

* **10F closure:**
  * the step-50 `ckey` support was 1 verified project per stream (< k_min 3);
  * rep1 A4 with only L10 removed 22 / 22 (via L6), with only L6 removed 22 / 22 (via L10), so 10F's A4f drop needed both removed;
  * the Abs_current solver scores 21 / 22 (rep0) and 22 / 22 (rep1).
* **104529 closed:** confirmed distractor-collision dedup; new `dag10g.necessary_dedup` (a non-documented dedup must be visibly
  necessary). Training wrong **0 / 240**.
* **Evidence acquisition** (shared atomic-guided solver; designed seq / time / grain ties; 5 typed channels; ambiguity guard
  abstains):
  * fresh one-use draw, **768 / 768 rows, 0 wrong**;
  * B_ev = 1 withheld compositions: learned `pi_ev` (E3) **24 / 24** in both streams, fixed operator-type rule (E2) 18, random
    11 / 9, none 4;
  * E3 − E2 = +6 in both streams (pre-registered *learned beats fixed*), with a 100 % disambiguation hit rate against 74 %.
* **Limit:** the gain is entirely the designed CDC-time mechanism (dedup ties needing the late-arrival channel). At B_ev = 2, E2
  equals E3; a relation-aware fixed rule would match it; E3's exploration cost was about 1,875 executions per stream.
* **Budget:** 685 of 1,300 s; ledger verified; protection 0 violations; `main` untouched.

## Phase 11: autonomous program acquisition and reusable relational abstraction (2026-10-30; report `docs/NEXUS_PHASE11_ATOMIC_RELATIONAL_ENGINE_REPORT.md`) — NOT LOCKED

* **New core (`src/nexus/de_phase11`):** typed relational core with published semantics, a native DuckDB compiler (conformance
  60 / 60; SQLite 58 / 60), a synthesizer with recoverable observational fingerprints and refinement, and typed anti-unification
  abstraction (k_min 3).
* **Learned from NEXUS's own solved source programs:** 12 + 11 functions; distinct mechanisms are coalescing, JSON extract-and-cast,
  predicate-shaped filters and a **pure next-state upsert** `union(anti_join(p0, p1, k, k), p1)` (both streams).
* **Suite 1** (24 fresh withheld compositions, library frozen, 168 / 168 rows):
  * F1 (fixed search + library) 8 / 24 against F0 5 / 24 in both streams, 0 losses; all 3 gains call the learned upsert.
  * F1 has 5 wrong against F0's 4, so the pre-registered verdict is **mixed**.
  * L1 − L0 = +1 / +1 (null); the guides (13–14 records) gave nothing.
* **Not done:** Suite 3 NOT READY (BIRD-Critic references by email only); Stage B reached 40–42 of 80 tasks; Polars / PySpark
  adapters not implemented; deep compositions (W1–W3, W5, W7) 0 / 3 in every arm.
* **Budget:** 1,161.6 of 1,800 s (new grant only); ledger verified; protection 0 violations; `main` untouched.
