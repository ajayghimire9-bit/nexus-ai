# NEXUS 7-trial tournament and confirmation (t7) (NOT LOCKED)

This document has three parts:

* §0, the pre-registration. It was committed before any trial outcome.
* Per-trial result sections, appended in separate commits.
* The confirmation sections.

## 0. Pre-registration

* **Start.** `a53d680` on `codex/nexus-data-engineering` (worktree `claude/s456-work`).
  * The u5 confirmation is NEGATIVE and its record is unchanged.
  * `d8fa061`, which the owner text names, is an ancestor of `a53d680`.
  * `main`, `final_sealed`, Checkers v1–v5 (`622a29a`) and the 912 protected files are not touched.
* **Budget.** "GRANT-NEXUS-MASTER-TOURNAMENT-36000S" restates the same 3,162 s + 36,000 s allocation already recorded twice.
  * It is **not** added again (`artifacts/t7_grant.json`).
  * Carried balance: 18,584 s. The t7 track cap is **14,000 s**.
  * Every execution runs through `scripts/t7_exec.py`, with at most 900 s per call, charged to the ledger as `t7-*`.
* **GPU.** No GPU is used. AGENTS.md requires explicit approval *and* a working enforcement backend, this host refuses
  GPU execution, and `mlx` is not installed.
  * Every "GPU" mechanism below runs as numpy-vectorised CPU code.
  * Trial 7's hyper-network is a numpy MLP.
* **Baseline fixes requested by the text, both already in place.**
  * B1 (causal trace shrinking, provenance, typed CEGIS holes) was promoted in R2 using the corrected selection rule
    (R2 report §0.4).
  * `grow_obs` (`src/nexus/r1_checks.py:46`) is active in every R1, R2 and OOP run, and unchanged.
* **Fourth domain.** Energy billing (`src/nexus/t7_world.py`): 7 formula families plus the lifecycle family `E.meter`.
  It was never used by u5, and is registered at runtime without editing `u5_world.py`.
* **Seeds.** `src/nexus/t7_seeds.py`. All ranges are fresh.
  * One-use ranges: `dval` (Trial 1 state arm), `val`, `val_b` and `test`.

### 0.1 Rule

* Each trial is a falsifiable hypothesis, run against its equal-compute controls on src and dev.
* **KEEP** only if the mechanism beats every control and clears the kill criterion below. Otherwise it is **REJECTED**:
  it stays out of the confirmation stack, and the negative result is reported.
* A trial that cannot be run as specified is reported as REJECTED with the reason. It is not reported as a success.

### 0.2 Trials (design and kill criteria)

| # | mechanism (module) | controls | data | KEEP iff (otherwise REJECT) |
|---|---|---|---|---|
| 1L | knockoff-gated library admission (`t7_knockoff`) | current admission (u5 separate-task utility), MDL | candidates from NEXUS's own solutions on u5 + t7 src (≥ 1 use); twins = same skeleton, type-matched random operators; W = utility(real) − utility(twin) on t7 dev tasks; knockoff+ threshold q = 0.20 | ≥ 20 candidates; realised false-admission rate ≤ 0.20 (false = an admitted item that does not improve held-out search); total admission work ≤ current admission's; admitted library smaller than MDL's and not larger than current admission's |
| 1S | knockoff-gated state monitors (`t7_monitors`) | the frozen OOP monitors | about 200 derived per-tick stream quantities from the de5 operations log and lake (lags, per-key lag, cardinality ratios, …); twins = the same quantity with permuted tick alignment; admitted on de5 dev projects (t7/ddev) by knockoff+ at q = 0.20 | on 4 fresh one-use de5 projects (t7/dval) with the frozen NEXUS_Synth operator: 0 silent errors, ≤ 1 false alarm per project, and the admitted set has ≥ 20 candidates behind it |
| 2 | check-concept invention over vectorised mutant worlds, steered by a blind-spot critic (`t7_oracle`) | (b) equal-cost fixed generic suite (Deequ-style); (c) unguided concept proposals; (d) no new checks | u5/t7 platform outputs; mutant classes W1 (partition birth dropped), 7953 (count-preserving accepted↔quarantined swap), X1 (aborted-transaction rows applied), X2 (segment gap), unit_shift, clock_skew, id_collision; leave-one-class-out | invented concepts catch held-out classes strictly better than both (b) and (c), with 0 false rejections on clean runs. Reported first: with 7953 held out, is row-identity reconciliation invented, and does it catch 7953? |
| 3 | joint failure-constraint tool invention + phantom-state retrodiction (`t7_jointtool`) | (b) deeper direct search, equal compute; (c) library learning from successes; (d) random abstractions | undo-editing streams + nested transaction / rollback streams; bounded infeasibility = exhaustive register search UNSAT (not a timeout), minimised by delta debugging; evaluated on withheld compositions and families | beats (b), (c) and (d) on withheld solve rate at equal compute, and the invented operation is used by a withheld family (not memorisation) |
| 4 | Gromov–Wasserstein skill transport + 4-D column spectrum (`t7_transport`) | Fresh, Useful_Reuse (wave-31 style), Name_Matching, Strong heuristic map, HDC_Map, Random_Map | old→new schema pairs (renames, widening, unit ×100, epoch-ms) and cross-domain pairs; alignment and probe costs charged | GW (or GW + ΔM) beats both Fresh and the strong heuristic map on held-out correctness, or matches them with lower total CPU |
| 5 | symbolic experiment translation (`t7_experiments`) | (b) information gain (max disagreement); (c) fresh experiment synthesis; (d) size-matched irrelevant procedure library | learn on L, C and I; delete all solution programs; target = energy domain; hypotheses = programs consistent with 3 examples | fewer oracle queries than (b) and (c) at no more total CPU (translation, applicability and failed attempts charged), and the gain is not confined to rename-only tasks |
| 6 | joint learner + memory-translator evolution with autopsy-compiled cuts (`t7_memory`) | (a) unchanged learner; (b) evolved learner + memory reset; (c) evolved learner + full replay | independent sequences of unfamiliar families; evolution, migration, replay and verification all charged; machine-checked preservation contract | (d) learns better than (a), does not freeze adaptation, and costs less than (c) at equal or better solves |
| 7 | 64 KB neurosymbolic genome bottleneck (`t7_genome`) | MAML-style start, hand-written defaults, random genome, shuffled-experience genome, full inheritance | 5 lineages × 3 generations; genome ≤ 64 KB; the library is wiped every generation | evolved genome regrows faster (CPU to target solve rate on the unseen energy domain) than BOTH the MAML start and the defaults in ≥ 3 of 5 lineages |

### 0.3 Assembly, freeze and confirmation

* **NEXUS_Tournament_Winner** = the frozen u5 NEXUS stack plus every KEPT mechanism that has an end-to-end role.
* **Freeze:** `artifacts/t7_freeze.json`.
* **Val gate (t7/val, 8 projects across all 4 domains, D1/D2):** independently correct ≥ 7/8, 0 silent errors, 8/8
  completed and crash-identical. One disclosed revision is allowed, with a `val_b` rerun.
* **Sealed test (t7/test, 16 projects; X3 even / X4 odd; 4 per domain, including energy).** Arms:
  * NEXUS_Tournament_Winner;
  * NEXUS_U5 (the u5 frozen configuration);
  * one ablation per KEPT mechanism;
  * Fixed_Policy;
  * Conventional.
* **Success criterion:** winner ≥ 14/16 independently correct, 0 silent errors, 16/16 completed and crash-identical, and
  strictly more independently correct than Fixed_Policy.
* **Disclosure.** X3 and X4 were already used in the u5 sealed test, so they are **not unseen classes to the developer**.
  Only the t7 test seeds and the energy-domain test pipelines are new.

### 0.4 What would not follow

* No AGI claim.
* No transfer claim beyond these synthetic generators.
* No GPU-efficiency claim, because none was measured.

## 0.4a Owner addendum (2026-10-28) — rules now in force

* The addendum supersedes conflicting parts of §0.
* **Three outcomes** replace KEEP/REJECT:
  * **PROMOTION CANDIDATE:** the method passes its pre-registered dev comparison. This is provisional.
  * **REJECTED FOR THIS SETTING:** a valid experiment shows the method fails its criterion.
  * **INCONCLUSIVE:** the experiment lacked headroom, power, implementation fidelity, budget or evaluator validity.
* A failed method does not disprove the capability goal.
* **Execution priority:**
  * **A.** Strengthen u5 repair acceptance and monitoring on reproduced dev failures.
  * **B.** A minimal decisive Trial 3.
  * **C.** Trial 5.
  * **D.** Trial 6, once headroom exists.
  * Trials 1, 4 and 7 run only as bounded pilots.
* A capability / integration register is kept in `docs/NEXUS_CAPABILITY_INTEGRATION_REGISTER.md`.
* **Confirmation uses fresh seeds.** X3/X4 are now *known* classes, so new X3/X4 seeds test **unseen instances of known
  fault classes**, not fault-class generalisation.
* **Reconciliation at the addendum.**
  * HEAD `f554aee` matches both remotes.
  * Budget: 14,537 s remaining (t7 had used 4,047 s).
  * GRANT-NEXUS-MASTER-TOURNAMENT-36000S is not credited again.
  * The R1/R2 baseline fixes (B1 promotion, `grow_obs`) already exist and were not re-implemented.

## 0.5 Trial log (results under the three-outcome rule; raw data in `artifacts/t7_dev/`)

| trial | what ran | numbers vs controls | outcome |
|---|---|---|---|
| 1 library: **matched negative-control admission** (not a formal Model-X knockoff: null hypotheses and exchangeability were not established, so **no FDR guarantee is claimed**) | 13 candidates from 197 of NEXUS's own solutions; one operator-swapped or parameter-permuted twin each; utility on 21 dev tasks | no threshold was reachable, so 0 admitted; current utility admission 0; MDL 5; work 649 s vs current 345 s CPU | **INCONCLUSIVE** (13 < 20 candidates: underpowered). Measured: the twin protocol costs 1.9× current admission |
| 1 state: matched negative-control monitors | 226 derived per-tick quantities over 6 de5 dev projects (the frozen OOP operator) | W split 74 positive / 48 negative / 104 zero; 0 admitted; the clock-skew-related `telemetry.lag_max.delta` ranks high but is not separable from its twins | **INCONCLUSIVE** (6 projects, too few incident ticks). The 4 one-use `dval` seeds were **not** spent. Monitor admission is not an operational silent-error result |
| 2 check selection over mutant outputs | 7 mutant classes on correct u5 outputs; typed check grammar; leave-one-class-out over W1, 7953, X1, X2, unit_shift; oracle budget 60 labels per run | mean held-out kill: critic 0.24, equal-cost generic 0.54, unguided 0.80, none 0; 0 false rejections **observed** on fresh clean runs | **REJECTED FOR THIS SETTING** (the critic keeps only checks that kill training classes). Caveats: the mutants edit outputs of the same reference implementation that the oracle uses, so they were **not validated against an independent engine**; row-identity comparison (`q_identity`) was **supplied** in the grammar, so choosing it is selection, not invention; with 7953 held out it was not selected |
| 3 joint failure-constraint tool (v1) | U and T: single-register space UNSAT by complete search (625 / 3,125 nodes), ddmin to 1 / 2 histories; joint search → stack of snapshots | withheld C: 3/3 streams (direct search at equal compute 0/3; it also failed at 60 s in smoke); withheld S (new symbols): 0/3 | **REJECTED FOR THIS SETTING** (v1 restricted the tool to the exact op combinations seen in U and T, and S needs `add` without `push`). Rerun as v2 under priority B |
| 4 transport | 46 old→new pairs: renames, widening, unit ×100, epoch-ms, cross-domain | all arms 46/46 correct (fresh fallback); total CPU: Fresh 87.2, Heuristic 57.5, Name 65.1, HDC 81.6, Random 75.5, GW 77.0, GW+ΔM 44.5 s; GW transported 8/46 vs Heuristic 21/46 | **GW alignment: REJECTED FOR THIS SETTING** (no better than a random map). The saving comes from **ΔM** (the old program reused as a library function in resynthesis, alignment-free). **ΔM: INCONCLUSIVE**, because it was not compared with Heuristic+ΔM or with ΔM alone under a pre-registered rule |
| 5 experiment translation (v1) | learn the experiment-type order on L, C, I; target energy; hypotheses from the construction bank | mean queries: translation 0.46, info-gain 0.40, fresh 0.46, irrelevant 0.43; identified 14/13/10/10 of 35; source learning 73 s | **INCONCLUSIVE** (3-example hypothesis sets were almost trivial, so there was no headroom). Rerun under priority C |
| 7 genome pilot | 5 lineages × 3 generations; hyper-network 12,213 parameters (float16) plus a symbolic prior; serialised **22.7 KB** (zlib) | regrowth CPU to target on energy: evolved = defaults = random within about 0.1 s in every lineage; MAML start and full inheritance marginally faster; 0/5 wins | **INCONCLUSIVE** (a 21-operator cost table gives the genome almost no leverage, and the energy stream had little headroom). The size limit does **not** imply that only "how to learn" survives. Shared decoder code (op list, descriptor, `decode`) is fixed infrastructure that is not counted |
| 6 memory translator (v1) | running at the addendum (old design: irreversible cuts) | — | recorded when complete; the addendum requires cuts to be used for **ordering** unless soundness is checked in a declared scope |

### 0.6 Work after the owner addendum (dev only; raw data in `artifacts/t7_dev/`)

#### Priority A: stronger repair acceptance

* **Data.** The known u5 failure *mechanisms* were reproduced on **fresh** dev data: t7/pdev projects with X3/X4, which
  are known classes, plus targeted lifecycle tasks. The u5 sealed seeds were not reused.
* **Components** (`t7_repair`, `t7_platform`):
  * transition × continuation probes from register-diverse prefixes;
  * column-level register search with merging (it fixed a fragmentation in which one register was fitted per emitting
    transition);
  * a size-5 update grammar, needed for `acc + x + x`;
  * early-pruning variable order;
  * condition-crossing status probes;
  * heightened post-repair monitoring.
* **Targeted lifecycle results** (X3 kinds present, 16 training keys, 5 dev seeds per family, held-out 200 keys):

  | family | u5 learner: exact / key acc | covered: exact / key acc |
  |---|---|---|
  | L.barrier | 5 / 1.000 | 5 / 1.000 |
  | C.clearing (PARTIAL then COMMIT) | 2 / 0.788 | **5 / 1.000** |
  | I.session (SUSPEND / RESUME) | 1 / 0.391 | **4 / 0.982** |
  | E.meter (ESTIMATE = acc + 2x) | 0 / 0.000 | 0 / 0.754 |
  | **total** | 8/20, 0.545, 5,771 queries, 110 s | **14/20, 0.934**, 14,511 queries, 266 s |

* **8 dev projects** (paired; the same learner in both arms):
  * NEXUS_Strong: independently correct 6/8, silent errors 1, escalations 0, abstentions 1.
  * NEXUS_U5: 4/8, 2, 1, 1.
  * Both remaining failures are energy projects: 12403 is silent (`E.meter`), and 12407 abstains because the lifecycle
    is unsolved at build.
* **Outcome:** PROMOTION CANDIDATE (provisional), by the rule set before the run: fewer silent errors, not fewer
  independently correct.
* **Costs:** 2.4× lifecycle-learning CPU and 2.5× membership queries.
* **Dev debugging during priority A, all disclosed:**
  * a 12-key harness bug (field discovery needs more than 12 keys);
  * the register-search blow-up;
  * the column-merge key collision.

#### Trial 3 v2 (priority B) — REJECTED FOR THIS SETTING

* **Correction from v1:** the tool now allows every primitive update with its stack actions, and controls have the same
  grammar and CPU.
* **Bounded infeasibility,** established by complete search:
  * U: 625 nodes, reduced by ddmin to 1 of 30 histories;
  * T: 3,125 nodes, reduced to 2 of 30 histories.
* **Synthesised:**
  * representation = per-key `x` plus a stack of snapshots;
  * state updates = per-symbol `(g, stack action)`;
  * reusable operations = push / pop_restore / pop_discard;
  * task-specific callers = the per-symbol assignments, for example
    `T: BEGIN=(keep, push), SET=(set, none), COMMIT=(keep, pop_discard), ROLLBACK=(keep, pop_restore), READ=(keep, none)`.
* **Withheld results:** S (new symbols) and C (composition): tool 6/6 fresh held-out streams, direct search 6/6, direct
  plus retrodiction 6/6, library from successes 0/6, random representation 0/6.
* **Cost:** search 0.006 s for the tool (plus 0.1 s invention) against 1.4 s for direct search. That is a cost benefit
  only; the criterion is solves.
* **Retrodiction** is used only as a filter on candidate explanations. Other mechanisms (the queue was tried) were
  ruled out by data, not assumed away.

#### Trial 5 (priority C)

* **v1 and v2 had a fidelity bug:** the hypothesis bank stopped early on a placeholder target, which left at most one
  hypothesis (v2 output kept in `t5v2_early_stop_bug.json`). Both are **INCONCLUSIVE**.
* **v2b** (fixed; 1 labelled example; only the ordered experiment-type list survives to the target; no solutions):

  | method | mean queries | identified (of 35) |
  |---|---|---|
  | translation | **1.00** | 13 |
  | info-gain | 1.29 | 13 |
  | fresh | 0.91 | 10 |
  | irrelevant | 1.57 | 10 |

* Every method spends about 71 s of CPU on the target; translation also spends 85 s on source learning.
* **Outcome: REJECTED FOR THIS SETTING.** Translation used 22 % fewer queries than info-gain at equal success, but
  fresh synthesis used fewer queries (with fewer identified), and the fully loaded CPU is higher.

#### Trial 6 v1 (old design, irreversible cuts) — REJECTED FOR THIS SETTING

* Solved on tasks 9–24 of 3 sequences:

  | arm | solved | CPU |
  |---|---|---|
  | unchanged | 38 | 99.2 s |
  | reset | 30 | 108.8 s |
  | full replay | 38 | 110.7 s |
  | joint translator | 38 | 93.8 s |

* The contract passed 3/3.
* Memory preservation clearly matters (reset −8 solves), and the translator is 15 % cheaper than replay.
* There was **no learning gain** over the unchanged learner.
* **v2** (cuts used for ordering only, with regime-aware evidence) is **deferred**: no headroom setting fit the remaining
  budget fairly.

#### Freeze

`artifacts/t7_freeze.json` lists 32 files with their gates. Spot-check randomness is now seeded per project, so
schedules are paired across arms.

## 1. Validation (one-use t7/val 12421–12428, frozen `99f504b`) — gate PASSED

| arm (paired; 8 D1/D2 projects; 2 per domain incl. energy) | independently correct | silent errors | completed | crash-identical | human repairs | build+ops CPU |
|---|---|---|---|---|---|---|
| **NEXUS_Tournament_Winner** | **8/8** | 0 | 8/8 | 8/8 | 0 | 205.1 s |
| NEXUS_U5 | 7/8 (12427 energy: build ABSTAIN) | 0 | 7/8 | 7/7 | 0 | 178.1 s |
| Fixed_Policy | 8/8 | 0 | 8/8 | 8/8 | 0 | 0 |
| Conventional | 4/8 | 4 | 8/8 | 8/8 | 0 | 0 |

* Gate (frozen): ≥ 7/8, 0 silent, 8/8, 8/8. **PASSED**, so no revision was used.
* Raw data: `artifacts/t7_val/`.

## 2. Sealed confirmation (one-shot t7/test 12441–12456, frozen `99f504b`, manifest `2cdd1f4`) — criterion NOT MET (one build abstention)

**Claim scope.** X3 and X4 are KNOWN fault classes (known since the u5 sealed test). These are **unseen instances of
known classes**, across 4 domains including energy (new in t7). The arms are paired: same projects, same crash ticks, and
the same initial spot-check schedule.

### 2.1 Final sealed 7-measure scorecard (16 projects)

| arm | independently correct | data correct | silent | completed | crash-identical | human repairs | build CPU s | ops CPU s | oracle labels | membership queries |
|---|---|---|---|---|---|---|---|---|---|---|
| NEXUS_Tournament_Winner | 14/16 | 15/16 | 0 | 15/16 | 15/16 | 1 | 417.0 | 382.4 | 14157 | 11544 |
| NEXUS_U5 | 9/16 | 12/16 | 4 | 16/16 | 16/16 | 3 | 281.5 | 373.3 | 14018 | 6877 |
| Fixed_Policy | 0/16 | 8/16 | 8 | 16/16 | 16/16 | 14 | 0.0 | 0.1 | 4661 | 0 |
| Conventional | 0/16 | 0/16 | 16 | 16/16 | 16/16 | 0 | 0.0 | 0.0 | 0 | 0 |

| measure | NEXUS_Tournament_Winner | paired NEXUS_U5 | reading |
|---|---|---|---|
| Correctness / 0 silent | **14/16 independently correct, 0 silent** | 9/16, 4 silent | +5 projects and −4 silent errors on identical workloads |
| Completion | 15/16 (12447 energy: build ABSTAIN, lifecycle unsolved) | 16/16 | the sealed criterion requires 16/16, so it is **not met** |
| Reliability | 15/15 operated projects crash-identical | 16/16 | |
| Cost | build 417 s + ops 382 s CPU; 14.2 k oracle labels; 11.5 k membership queries | 282 + 373 s; 14.0 k labels; 6.9 k MQ | +22 % CPU and +68 % MQ, fully loaded |
| Human dependence | 1 escalation (12451) | 3 | Fixed_Policy: 14 escalations, 8 silent |
| Learning benefit | no learned component differs between the two NEXUS arms | – | the gain is from repair acceptance, not from learning |
| Generalization | X3 8/8, X4 6/8; logistics, clearing and iot 4/4 each; energy 2/4 | X3 4/8, X4 5/8; energy 1/4 | energy remains the weak domain |

* **Pre-registered criterion:**
  * ≥ 14/16: met (14);
  * 0 silent: met;
  * 16/16 completed and crash-identical: **not met** (15/16);
  * more than Fixed_Policy (0): met.
* **Verdict: NOT MET.** It is not reported as a pass.
* The paired comparison is descriptive (n = 16). It is the first sealed evidence that the priority-A acceptance
  components cut silent errors (4 → 0) on unseen instances of known classes.
* **Non-independent projects,** from committed outputs only:
  * **12447 (energy X4, E.standing):** the `E.meter` lifecycle was unsolved at build, so the build abstained. NEXUS_U5
    built a class there and needed a human repair.
  * **12451 (energy X4):** both arms needed 1 escalation.

### 2.2 The 7-trial verdict table (development outcomes under the addendum's rule)

| trial | best numbers vs controls | outcome |
|---|---|---|
| 1 library (matched negative controls; **no FDR claim**) | 13 candidates; 0 admitted; work 649 vs 345 s | INCONCLUSIVE (underpowered) |
| 1 state monitors (matched negative controls) | 226 quantities; 0 admitted (W +74 / −48) | INCONCLUSIVE (6 projects); validation seeds unspent |
| 2 check selection | held-out kill 0.24 vs generic 0.54 vs unguided 0.80 | REJECTED FOR THIS SETTING (mutants not validated against an independent engine) |
| 3 joint tool invention v2 | withheld 6/6 vs direct 6/6 (tool 13× cheaper) | REJECTED FOR THIS SETTING (no solve advantage) |
| 4 GW transport | GW 77.0 s ≈ Random 75.5 s > Heuristic 57.5 s; ΔM 44.5 s | GW REJECTED FOR THIS SETTING; ΔM INCONCLUSIVE |
| 5 experiment translation v2b | 1.00 vs 1.29 (info-gain) vs 0.91 (fresh) queries; CPU higher | REJECTED FOR THIS SETTING (v1/v2 INCONCLUSIVE: fidelity bug) |
| 6 memory translator v1 | 38 = 38 (unchanged) solves; 93.8 vs 110.7 s (replay) | REJECTED FOR THIS SETTING; v2 deferred |
| 7 64 KB genome (22.7 KB) | 0/5 lineage wins; no measurable effect | INCONCLUSIVE |
| **A repair acceptance** | dev: 6/8 vs 4/8, silent 1 vs 2; **sealed: 14/16 vs 9/16, silent 0 vs 4** | PROMOTION CANDIDATE; sealed criterion not met (completion 15/16) |

### 2.3 Verbatim code NEXUS wrote (sealed project 12454, IoT X3)

* It was relearned with transition × continuation coverage at tick 9, after the new SUSPEND/RESUME symbols raised
  `?unknown`.
* It was correct for ticks 9–16. Paired NEXUS_U5 had 3 silent lifecycle errors on this project.
* Excerpt of the class:

```python
class StateMachine_a9d5b9d7:
    """Invented by continuation splitting: 3 control modes (mode_0 = start), 2 data register(s).
    witness: histories ['CONNECT'] vs [] differ after continuation ['CONNECT']
    witness: histories ['CONNECT', 'SUSPEND'] vs ['CONNECT'] differ after continuation ['RESUME']
    witness reg_0: in mode_1 histories ['CONNECT'] / ['CONNECT', 'CONNECT', 'DISCONNECT', 'CONNECT', 'DISCONNECT', 'CONNECT', 'CONNECT', 'READ', 'CONNECT', 'READ', 'CONNECT', 'READ'] emit 0 / 1 after ['DISCONNECT']
    witness reg_1: in mode_1 histories ['CONNECT'] / ['CONNECT', 'CONNECT', 'DISCONNECT', 'CONNECT', 'DISCONNECT', 'CONNECT', 'CONNECT', 'READ', 'CONNECT', 'READ', 'CONNECT', 'READ'] emit 0 / 55.8 after ['DISCONNECT']
    """

    def __init__(self):
        self.mode = {}
        self.reg_0 = {}
        self.reg_1 = {}

    def ingest(self, rec):
        k, s = rec.get('ref'), rec.get('event')
        m = self.mode.get(k, 0)
        r0 = self.reg_0.get(k, 0)
        r1 = self.reg_1.get(k, 0)
        x1 = rec.get('amount')
        x1 = x1 if isinstance(x1, (int, float)) and not isinstance(x1, bool) else 0
        if m == 0:
            if s == 'CONNECT':
                out = []
                self.mode[k] = 1
                return out
            elif s == 'DISCONNECT':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'READ':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'RESUME':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'SUSPEND':
                out = [('q:invalid', None, None)]
                return out
        elif m == 1:
            if s == 'CONNECT':
                out = [('session', r0, r1)]
                self.reg_0[k] = 0
                self.reg_1[k] = 0
                return out
            elif s == 'DISCONNECT':
                out = [('session', r0, r1)]
                self.reg_0[k] = 0
                self.reg_1[k] = 0
                self.mode[k] = 0
                return out
            elif s == 'READ':
                out = []
                self.reg_0[k] = (r0 + 1)
                self.reg_1[k] = (r1 + x1)
                return out
            elif s == 'RESUME':
                out = [('q:invalid', None, None)]
                return out
            elif s == 'SUSPEND':
                out = []
                self.mode[k] = 2
                return out
        elif m == 2:
            if s == 'CONNECT':
                out = [('session', r0, r1)]
                self.reg_0[k] = 0
                self.reg_1[k] = 0
                self.mode[k] = 1
                return out
            elif s == 'DISCONNECT':
                out = [('session', r0, r1)]
                self.reg_0[k] = 0
                self.reg_1[k] = 0
                self.mode[k] = 0
                return out
            elif s == 'READ':
                out = []
                return out
            elif s == 'RESUME':
                out = []
                self.mode[k] = 1
                return out
            elif s == 'SUSPEND':
                out = [('q:invalid', None, None)]
                return out
        return [('?unknown', None, None)]   # a symbol never seen: the operator's monitor raises an alarm
```

* The other invented artifacts are committed:
  * the Trial 3 stack representation and callers: `artifacts/t7_dev/t3v2.json`;
  * the Trial 2 selected check sets per fold: `t2.json`;
  * the Trial 6 memory-translator output and contract checks: `t6.json`;
  * the experiment-type order of Trial 5: `t5v2b.json`.

### 2.4 Resources

* t7 total: about 10,140 s wall (ledger `t7-*`), including the 900 s-capped Trial 6 rerun and every failed or debug run.
* Carried balance now 8,441 s. The t7 cap (14,000 s) was respected.
* No GPU was used. Oracle labels and membership queries are in the scorecard. Source learning is reported per trial.

### 2.5 Status after confirmation, and next step

* **Status (see the register):**
  * The priority-A components stay **provisionally integrated**. The sealed criterion was not met, so they are **not**
    independently confirmed, although the paired sealed evidence favours them.
  * Everything else stays experimental or inactive, as tabled.
* **Unproved:**
  * fault-class generalisation (no withheld class was tested);
  * reliable energy-domain lifecycle learning;
  * every learning-to-learn mechanism in Trials 1, 4, 5, 6 and 7.
* **Next experiment:** make `E.meter`-style lifecycles learnable at build in full projects. The build stream there still
  defeats the covered learner (1 dev abstain, 1 sealed abstain). Then re-confirm on fresh seeds with a genuinely
  withheld fault class, under a new pre-registration.
