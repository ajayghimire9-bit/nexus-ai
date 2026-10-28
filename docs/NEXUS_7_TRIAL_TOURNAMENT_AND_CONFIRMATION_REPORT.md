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

## 0.5 Trial log

(appended)
