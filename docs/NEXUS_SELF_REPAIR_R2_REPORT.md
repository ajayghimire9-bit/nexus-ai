# NEXUS self-repair increment R2 (NOT LOCKED)

* **Start.** R2 starts at `d8fa061` on `codex/nexus-data-engineering` (worktree `claude/s456-work`). Both remotes match it,
  and the worktree is clean. No R1 process is running, and Antigravity's checkout is untouched at `18f53b6`. All 912
  protected files are unchanged against `artifacts/r1_protected_hashes_after.json`.
* **R1.** R1's code, artifacts and report are preserved unchanged. R2 lives in separately named `r2_*` modules that import
  R1's.
* **Budget.** `GRANT-R2-14400S` is recorded once, in `artifacts/r2_grant.json`.
  * Cumulative allowance: 32,390 s.
  * The verified balance at `d8fa061` was 3,162 s, so **17,562 s is available**.
  * `scripts/r2_budget.py` debits every `w41*`, `de-*`, `de2-*`, `r1-*` and `r2-*` ledger row.
  * The unit is the ledger's wall seconds. CPU figures are performance measurements and are reported separately.
* **Template.** The R1 template has **16** decisions, verified: the 14 Stage 4 decisions plus `txn_isolation` and
  `gap_handling`.

## 0. Pre-registration (committed before any R2 dev outcome)

### 0.1 Splits (namespace `de4`, `src/nexus/r2_seeds.py`)

| split | seeds | withheld / development classes |
|---|---|---|
| src | 961–966 | library learning only. X1 (even seeds) / X2 (odd seeds) from tick 9: known development material |
| dev | 971–978 | X1 / X2 as in src |
| val | 7961–7964 | X1 / X2 as in src; one-use |
| val_b | 7965–7968 | used once, only after ONE disclosed revision triggered by a val failure; otherwise unopened |
| test | 7971–7978 | one-use sealed; **X3 on even seeds, X4 on odd seeds**, from tick 9 |

R1 artifacts (de3) are not changed and are not reused as fresh evidence.

### 0.2 Withheld classes X3 / X4, and exactly what is withheld

* **X3: an order currency outside the declared fx table.** From tick 9, a few new orders are written in a currency not in
  `fx_to_usd`.
* **X4: a registry-declared discount unit change.** From tick 9, orders schema v4 declares `discount_unit: fraction`, so
  discount values arrive as fractions of 1.

The rules for both are declared in **every** de4 spec:

* "an order record whose currency is not in fx_to_usd is quarantined (reason unknown_currency) and never enters
  silver / gold";
* "a registry version may declare discount_unit = fraction; discount percent = value × 100".

**What is withheld:** only the **realisations**, meaning the X3 / X4 generator output and their combination with that
project's incidents. These run only in the seal script.

**What is not withheld:** the mechanisms and their handlers are **author-written**:

* the template options `fx_unknown = quarantine` and `discount_unit = registry_unit`;
* the spec-derived reconciliation rules;
* the typed holes: decode / silver-stage decisions and "schema version first seen after the build window".

Repairing X3 / X4 is therefore **selection and verification of a known repair option at run time**. It is not autonomous
discovery, and it will not be described as such. The handlers are unit-tested only on hand-written mini logs. The X3 / X4
generators are never run on src, dev or val.

### 0.3 Reconciliation is fixed BEFORE repair methods are compared

The known R1 defect is that count-based accounting missed a quarantine-row difference on test-7953. Its cause is
undetermined.

* **Minimal dev reproducer.** I'll try to reproduce it from the R1 evidence: an interrupted snapshot (tick 11) followed by
  a clock skew (tick 13), forced on de4/dev worlds. The finding is reported whether or not it reproduces. The sealed de3
  world is never regenerated.
* **Event-level reconciliation** (`r2_reconcile`, expected values computed only from the operator archive and the spec;
  nothing from the pipeline's replay logic):
  * one class per consumed offset: accepted / control, quarantined(reason), duplicate, aborted, pending;
  * the first copy of each event identity (topic, msg_id) carries the class and its canonical content hash; later copies
    are duplicates;
  * quarantine rows compared as a multiset of (topic, msg_id, reason);
  * bronze contents compared with the canonical first copy: orders (key, source_version, op, canonical row), telemetry
    (event time, future flag), manifests (converted kg);
  * silver compared row by row, including tombstones, soft deletes and snapshot precedence; late_events,
    `gold_sla` and supplier volume as before.
* **Mutation tests** on real dev pipeline states: count-preserving substitutions, changed payloads, duplicated events,
  missing events and wrong quarantine classification. The report states the tested bounds and makes no zero-error
  guarantee.

### 0.4 Repair-method comparison: selection rule frozen now

* **Matched set.** de4/dev worlds; the correct pipeline with ONE wrong decision; the same incidents; the same corrected
  reconciliation, observations and caps. The caps are 40 shadow tests per turn, 200 per run and 12 full verifications per
  repair.
* **The R1 B1 results are development evidence** for this comparison.
* **Selection rule (frozen now):**
  1. **Primary:** the number of cases that end end-to-end correct within the caps. The arm with strictly more wins.
  2. **On a tie:** the lower total operator CPU over ALL cases, unsuccessful attempts included, wins, but only if it is
     at least 5% lower.
  3. **Otherwise:** the incumbent B0 is kept.
* Fault rank and suspect-set size are **diagnostics only**.
* If B1 fails the rule, that is reported, and there is no tuning until it passes.
* **Comparison C runs only after B is decided, inside the selected localiser.** Its arms:
  * **C0:** the localiser's own candidate order, the fallback;
  * **C1:** a cheap contextual order: candidates whose decision's pipeline stage matches the lineage of the failing table
    come first;
  * **C2:** a **cost / information-gain heuristic**: candidates are ordered by estimated fix probability (normalised
    suspect score) divided by measured verification cost. It is not exact IDS and is not claimed as such.

  C1 or C2 is adopted only if it **strictly** increases end-to-end correct cases, or on a tie lowers total operator CPU,
  **including the scoring overhead**, by at least 10%. Otherwise C0 stays. "No improvement" is a valid outcome.

### 0.5 Baselines

* **Fixed_Policy** is preserved from R1 unchanged in behaviour: src-majority build options, the sequential incident
  runbook, and one typed redeploy. It gets the same monitors, reconciliation, observations and actions.
* No context-dependent regime is added, so no contextual fixed policy is needed. This is stated, not assumed away.
* Conventional_Checked is kept as the reference.
* All baseline development finishes before the freeze.

### 0.6 Two separately scored evaluations

1. **Natural:** build → deploy the arm's own pipeline → recovery. This is the primary end-to-end metric, as in R1.
2. **Forced-failure recovery (matched intervention).** In every test project, each arm's own submitted pipeline is
   deployed with the withheld class's decision forced to its naive option:
   * X3 → `fx_unknown = error`;
   * X4 → `discount_unit = percent_only`;
   * val and dev: X1 → `txn_isolation = read_uncommitted`, X2 → `gap_handling = skip`.

   Every forced deployment is vulnerable by construction. It is scored as affected / detected / repaired /
   end-to-end correct, with separate denominators per class. **Forced changes are never counted as natural build
   failures.**
3. **Secondary comparison (frozen):** on the same forced deployments, the same incidents and NEXUS_Fresh's starting
   pipeline, the selected localiser against the other. This isolates the localiser's contribution.

### 0.7 Library (Stage 6 procedure)

* Relearned on de4/src with the selected localiser.
* Applicability is matched before reuse, and every build still runs the full independent suite.
* Retrieval, checking, failed reuse, maintenance (leave-one-out) and source learning are all charged.
* Ops playbooks may all be rejected again.
* Fresh, Placebo and Experienced use identical code. They differ only in library history.

### 0.8 Gates and decision rules

* **R2 natural PASS:** every NEXUS arm end-to-end correct ≥ 7/8 **and** 0 silent errors for every NEXUS arm.
* **R2 forced-recovery PASS:** for every NEXUS arm and each class (X3, X4), at least 3 of the 4 forced deployments end
  end-to-end correct, with 0 silent errors.
* **Learning claim:** all of the following must hold:
  * Experienced natural end-to-end ≥ Fresh's and ≥ Placebo's (maintained correctness);
  * the Experienced / Fresh fully loaded project-cost ratio has a 95% CI upper bound < 1;
  * the Experienced / Placebo ratio has a CI upper bound < 1.

  Uncertainty and the source-learning break-even are reported. Whether Experienced beats Fixed_Policy on end-to-end and
  on cost is reported separately.
* **Validation gate** (4 projects, X1 / X2):
  * NEXUS_Fresh natural end-to-end ≥ 3/4;
  * 0 silent errors for every NEXUS arm;
  * NEXUS_Fresh forced recovery ≥ 3/4;
  * 0 replay-view violations.

  **At most one disclosed revision, then val_b once. If val_b fails, stop and leave the test unopened.** The test is
  never used for tuning.
* **Failure rules:** a crashed arm fails that project. A cap hit is saved as a CHECKPOINT and resumed, which is not a
  re-run. Post-test fixes are separate commits and are not results.
