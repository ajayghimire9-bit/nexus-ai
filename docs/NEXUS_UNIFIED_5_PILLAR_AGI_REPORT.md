# NEXUS unified 5-pillar track (u5) (NOT LOCKED)

This file is the pre-registration (§0), written and committed before any u5 dev outcome. Results are appended in later
sections, in separate commits. Nothing here claims AGI: the pillars are bounded program-synthesis mechanisms, measured on
author-generated tasks and projects.

* **Start.** `017e074` on `codex/nexus-data-engineering`, worked in the worktree `claude/s456-work`.
  * The OOP Phase 1 outcome is NEGATIVE; that record is unchanged.
  * `d8fa061`, the commit the owner text names, is an ancestor of `017e074`. R2 and Phase 1 are kept and built on.
  * `main`, `final_sealed`, Checkers v1–v5 (`622a29a`) and the 912 protected Stage 1–6 / R1 files are not touched.
* **Budget.** The owner text ("GRANT-NEXUS-UNIFIED-AGI-36000S", 3,162 s + 36,000 s = 39,162 s) restates the allocation
  already recorded as GRANT-NEXUS-DE-OOP-36000S.
  * The owner ruled that this allocation covers R2 ("go ahead with Phase 1, use 34,139 s").
  * It is therefore **not** added again (`artifacts/u5_grant.json`), because agents must not infer an increase.
  * Carried balance at the start of u5: **28,032 s**.
  * `scripts/u5_budget.py` debits every `w41*`, `de-*`, `de2-*`, `r1-*`, `r2-*`, `oop-*` and `u5-*` ledger row.
  * Every u5 execution, including smoke checks, runs through `scripts/u5_exec.py`, which refuses to start when the
    remaining budget is below its cap. Each call is capped at 900 s, and its wall time is charged.
* **The two R1 baseline defects the owner text lists were already fixed in R2:**
  * Localiser selection by end-to-end repair rate, mean fault rank and CPU: `docs/NEXUS_SELF_REPAIR_R2_REPORT.md` §0.4.
  * Quarantine row-identity reconciliation by keys and digests (48/48 swaps flagged, against R1's 8/48): R2 report §2.
  * u5 does not redo them. The u5 testbed below is new and does not use the R2 operator.

## 0. Pre-registration

### 0.1 What is reused (named before adding)

| need | reused | new in u5 |
|---|---|---|
| primitives, OE collapse, deductive decomposition, decision lists | `oop_synthesizer` (Phase 1; unchanged) | `u5_construct` cost-ordered construction policies, which build the bank the unchanged Phase 1 `Solver` decomposes over |
| abstraction | `oop_synthesizer.anti_unify` semantics (`("fn", …)` nodes, `def_source`) | `u5_library` candidate extraction, MDL and utility admission |
| measured-saving admission principle | `s6_library` (procedure admission by measured saving) | the same principle applied to code abstractions |
| seeds, one-use claims | `seed_registry` | `u5_seeds` (registered at import) |
| ledger | `wave31_evaluator.ledger_append` | `scripts/u5_exec.py` wrapper |
| sealing | `oop_seal_test` / `r2_seal_test` pattern | `scripts/u5_seal_test.py` |

There is no new memory, RL or evolution framework outside these modules. `evolvable_learner.py` and `meta_improver.py`
are the two files the owner text names.

### 0.2 Testbed (author-written; disclosed)

* **Synthesis tasks** (`u5_world`): 21 formula and validity families, 7 per domain (Logistics, Financial Clearing, IoT
  telemetry). Target programs have 4–21 nodes.
  * Field names are drawn from synonym lists per instance, and distractor fields are added.
  * Each task gives 30 training examples labelled by the oracle (the author's reference program) and 120 held-out
    inputs.
  * "Correct" means the program matches the oracle on **all** held-out inputs.
* **Lifecycle tasks** (`u5_stateful`): one per domain, each a per-key machine with control modes and data registers.
  * `L.barrier`: release only after payment AND packing, in either order.
  * `C.clearing`: two-phase NEW / AMEND / PREPARE / COMMIT / ABORT / CANCEL; COMMIT settles the last *accepted* amount.
  * `I.session`: count and sum accumulators.
  * A training stream has 40 keys; the held-out stream has 200 keys.
  * The learner sees events, oracle outputs and its own counted membership queries. It never sees modes, register
    names or transition tables.
* **End-to-end projects** (`u5_platform`): 16 ticks; a record stream (formula + validity) and a lifecycle stream.
  * Build uses ticks 1–8. Operation covers ticks 9–16, with faults from tick 9.
  * dev / val faults: D1 (declared unit change) or D2 (never-seen members).
  * test faults: X3 (new lifecycle event kinds) on even seeds, X4 (undeclared nesting of a formula field) on odd seeds.
  * One crash is injected per project.
* **Disclosure.** While implementing, I ran the X3/X4 generators on the two smoke-only seeds 8090/8091 (never evidence).
  * Two lifecycle-learner priors were fixed after an X3 smoke failure:
    * the same output column uses the same source;
    * same-symbol, same-label transitions share updates.
  * X3/X4 are therefore known to the developer, as in R2. Only the test seeds and their data are withheld.
  * No dev or val run uses X3/X4.
* **Oracle access is a disclosed assumption.** The spec oracle is a black box that learners may query on streams they
  construct, and on counted production samples after an alarm. All queries are counted and reported under Cost.

### 0.3 Splits (`src/nexus/u5_seeds.py`)

| range | seeds | use |
|---|---|---|
| `tsrc` | 10000–10009 | learning material: policies, libraries, curricula, meta-training (L + C families only; IoT is unseen) |
| `tadm` | 10600–10604 | library admission validation (0–1); meta-validation (2) |
| `tdev` | 10800–10804 | pillar selection |
| `theld` | 11000–11004 | held-out report for Pillars 3–5; never selects anything |
| `psmoke` | 8090–8091 | smoke checks only |
| `pdev` | 8001–8012 | end-to-end development (D1/D2) |
| `val` | 8021–8026 | one-use end-to-end gate (D1/D2; each domain twice) |
| `val_b` | 8027–8032 | one-use; only after ONE disclosed revision triggered by a val failure |
| `test` | 8041–8052 | one-use sealed confirmation; X3 even / X4 odd; 4 projects per domain |

### 0.4 Pillar dev experiments and promotion rules (runner = the rule; frozen now)

| pillar | runner | arms | data | promotion rule |
|---|---|---|---|---|
| 1 | `u5_p1.py` | StateSplit / FlatDict / Stateless | 3 lifecycle families × tdev 0–4 (15 tasks) | StateSplit exact on ≥ 12/15 **and** mean key accuracy ≥ FlatDict + 0.10. Expressiveness gate: FlatDict exact on ≤ 1/15 |
| 2 | `u5_p2.py` | baseline / count / exec | train: L+C × tsrc 0–4 (baseline wake, own solutions only); eval: 21 families × tdev 0–1 (42 tasks), 4 s per task | most generalising solves (hybrid engine); ≤ 1 solve = tie, broken by ≥ 10 % CPU; else the simpler policy |
| 3 | `u5_p3.py` | none / mdl / utility | candidates from own src solutions; utility on ADM (L+C × tadm 0–1); eval DEV (select) + HELD (report) | most DEV solves; tie broken by charged CPU (search + discovery + admission); not eligible if DEV wrong-generalisations exceed none's by > 1 |
| 4 | `u5_p4.py` | none / random / fixed / boundary | 240 CPU s of practice each; identical update, re-admission and zero-forgetting acceptance | boundary promoted iff DEV solves ≥ every other arm's + 2, or a tie within 1 with ≥ 10 % less CPU than all others |
| 5 | `u5_p5.py` | M0 / Scalar_Tuning / Random_Modification / M_evolved | same L0, same B = 120 s, unseen IoT families, seeds 0–2; meta-evolution on L+C only | M_evolved promoted iff its mean DEV solves exceed every other arm's and L0's |

* **Charging.** Every CPU second of scoring, discovery, admission, practice and meta-evolution is charged to the arm that
  uses it.
* **The chain.** Each pillar starts from the configuration promoted by the pillars before it.
* **Ablations.** A pillar that is not promoted is left out of NEXUS_U5, and its ablation arm is dropped.

### 0.5 End-to-end arms and the 7 measures

* **Arms:** `scripts/u5_run.py` docstring (NEXUS_U5, one single-pillar ablation per promoted pillar, NEXUS_NoLearning,
  Fixed_Policy, Conventional).
* **Fixed_Policy is a strong, informed baseline.**
  * It is written from the documented spec: field names, the formula, the validity rules and the documented lifecycle.
  * It handles the known fault classes (declared unit changes, unseen members).
  * Every other alarm is escalated, as a counted human repair.

| measure | definition (per project; aggregated over projects) |
|---|---|
| Correctness / 0 silent errors | **primary:** independently correct = final tick 9–16 tables equal the reference, project completed, no human repair. Silent error = the arm claims healthy but the data are wrong |
| Completion | built and operated (not ABSTAIN, not CRASHED) |
| Reliability | the crash-recovered outputs and state are identical to a clean re-run from the same checkpoint |
| Cost | build CPU + operations CPU; oracle labels and queries (build labels, membership queries, spot checks, incident samples) |
| Human dependence | escalations (human repairs) |
| Learning benefit | NEXUS_U5 vs NEXUS_NoLearning: Δ independently correct, Δ build+ops CPU |
| Generalization | results by domain (IoT was unseen by every learned component) and by withheld class (X3 / X4) |

### 0.6 Gates and sealed protocol

1. Run the dev experiments for Pillars 1–5, then end-to-end dev on `pdev`. Dev may change code and hyperparameters, and
   every change is logged here.
2. **Freeze.** `artifacts/u5_freeze.json` records sha256 of every u5 source file and every promoted artifact, plus the
   gate. Commit and push it before val.
3. **Val gate (u5/val, one use).** NEXUS_U5 must be independently correct on ≥ 5/6, with 0 silent errors, 6/6 completed
   and 6/6 crash-identical.
   * On a fail: one disclosed revision, diagnosed on dev only, then the same gate on `val_b`.
   * A second fail means no sealed test and a negative verdict.
4. **Seal.** `scripts/u5_seal_test.py` writes the 12 test projects to `$NEXUS_SEALED_VAULT_DIR/u5_test/` and commits only
   the sha256 manifest. The runner reads only manifest-verified blobs with `NEXUS_SEALED_HARNESS_TOKEN`. Parts run in
   order, once each; a crash stops the run, and no traceback is printed.
5. **Sealed success criterion (predeclared):**
   * NEXUS_U5 independently correct on ≥ 10/12;
   * 0 silent errors;
   * 12/12 completed and crash-identical;
   * strictly more independently correct projects than Fixed_Policy.
   * Pillar ablations at test are descriptive (n = 12). A pillar "shows at test" if its ablation arm has fewer
     independently correct projects, or ≥ 20 % more build+ops CPU at equal correctness.

### 0.7 Resource plan

| stage | planned wall s |
|---|---|
| Pillars 1–5 dev | ≈ 7,500 |
| e2e dev | ≈ 2,000 |
| val (+ val_b if needed) | ≈ 1,000 |
| sealed test | ≈ 3,500 |

* Hard stop for the whole u5 track: **22,000 s**, leaving at least 5,700 s of the carried balance unused.
* A stage that would exceed its cap is stopped and saved as partial. Grids are never silently shrunk.

### 0.8 What would NOT follow from a positive result

* It would not show unrestricted program invention or AGI.
* It would not show learning-to-learn beyond the measured Pillar 5 comparison on author-generated task families.
* It would not show transfer to real data systems: the testbed is synthetic.

## 0.9 Dev log

(appended as dev runs happen)
