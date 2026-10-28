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
