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

### 0.9 Development log (de4 src / dev only; before the freeze)

1. **Reproducer.** Interrupted snapshot at tick 11 plus clock skew at tick 13, forced on 8 de4/dev worlds, run with the
   correct pipeline, the R1 operator and the R1 reconciliation. On **de4-dev-977**, R1's reconciliation passed while the
   evaluator scored the data wrong: the same silent pattern as R1's test-7953.
   * **Mechanism:** event `t00034`'s first delivery (tick 12) has a valid event time. The clock-skew incident rewrote
     **only its retry duplicate** (tick 13), and the incident's truth update relabelled the whole event as a future event.
   * **Conclusion:** under the declared identity rule, the first delivery is the event, so the pipeline was right and
     the **reference** was wrong.
   * **Fix (environment side, disclosed):** de4 telemetry truth takes each event's time and future flag from its first
     delivered copy (`r2_env._first_copy_truth`).
   * Whether this is also what happened on R1's test-7953 stays **undetermined**, since the sealed world is not
     regenerated. R1 scores are not rescored.
2. **Event-level reconciliation (`r2_reconcile`).** The test results are in `artifacts/r2_dev_results/reconcile_mutations.json`.
   * **Setting:** 4 dev worlds × {no incidents, the reproducer setting}, each producing 1 clean state plus 6 mutation
     kinds (M1–M6).
   * **Clean states:** both reconcilers accept 8/8.
   * **Mutations:** R2 flags **48/48**. R1's count-based reconciler flags **8/48**: only the duplicate promoted to
     accepted (M3). It misses M1 count-preserving substitution, M2 changed payload, M4 missing event, M5 wrong quarantine
     reason and M6 superseded-payload change.
   * **Bounds:** these 6 mutation kinds on these 8 states. No claim beyond that.
   * **Defects found and fixed on dev:**
     * after a failed run, published outputs legitimately lag the ledger (non-transactional protocols commit consumption
       per topic), so output comparisons are deferred while ledger, bronze and coverage checks still apply;
     * decoding now uses every **published** registry record, after a crash on de4-dev-974 where a consumed record's
       registry version lay beyond the committed `_schemas` offset.
   * **First-run bug:** `forced=[]` meant "use the schedule", so the "no incidents" baseline of the first test run had
     unrepaired incidents (`reconcile_mutations_first_run_baseline_bug.json`).
3. **Localisation fix, applied to both localisers before the comparison.** It was found on de4-dev-971. When a relaxed
   incident composition exists, localisation uses the evidence observed **after** it, in its shadow. That is the
   counterexample with the incident removed. R1 discarded shadow evidence for monitors already failing in the real
   environment, so a crash-time artefact (stale accounting typed to `dedup`) hid a genuine `lateness` defect.
4. **Comparison B under the frozen rule** (de4-dev-972 X1 and 975 X2; 22 single-fault mutants each = 44 matched cases;
   identical reconciliation, observations and caps):

   | arm | **end-to-end correct** | total operator CPU, all cases | silent | top-1 (diag.) | mean suspect set (diag.) | full verifications |
   |---|---|---|---|---|---|---|
   | B0 | 33/44 | 328.2 s | 0 | 6/35 | 18.0 | 1,372 |
   | **B1** | **42/44** | **87.4 s** | 0 | 27/35 | 3.0 | 165 |

   **B1 is adopted** (primary: 42 > 33).
5. **Comparison C** (inside B1, same 44 cases):

   | arm | end-to-end correct | total operator CPU incl. scoring |
   |---|---|---|
   | C0 | 42 | 87.4 s |
   | C1 | 42 | 96.9 s |
   | C2 | 42 | 98.7 s |

   **No improvement, so C0 is kept.** C1 and C2 ran four processes in parallel, against two for C0. CPU is measured per
   process, but contention is possible.
6. **Library** (de4/src; B1 / C0):
   * 11 build procedures admitted;
   * `commit_protocol`, `gold_maintenance` and `lateness` retired because the src evidence disagrees;
   * **every ops playbook rejected** (each saving was ≤ its retrieval and applicability cost);
   * source learning cost 464.9 s.
7. **Baseline development (Fixed_Policy) before the freeze.**
   * **What went wrong on dev:** with this src sample, the src-majority `lateness` option is `processing_time` (4 of 6).
     It is indistinguishable from `watermark` on visible data. Fixed_Policy therefore abstained twice when the lateness
     probe caught it, and when the probe did not, it deployed the wrong option and its single typed redeploy took the
     first alternative in template order (`none`).
   * **What was strengthened, still a fixed policy with no search:**
     * the library records the option frequencies of the accepted src builds (`option_counts`);
     * the build gets ONE fixed fallback: the failing check's implicated decisions move to their second most frequent
       src option, then there is one more full-suite check;
     * the typed redeploy uses the most frequent src option other than the current one.
   * **Preserved from R1:** the precondition checks, the incident runbook and the typed redeploy itself.
   * **Result on de4-dev-973 / 974 / 976 / 977:** natural 4/4 and forced 4/4.
8. **Incident scheduling.** de4 projects get 2 seen incidents each, while R1's non-test projects got 3. This is noted here
   because the protocol did not state it.
9. **Regression on de4-dev-971 / 978, final code, all arms.**
   * Natural and forced recovery: correct for Fixed_Policy and every NEXUS arm on both worlds. Conventional fails both.
   * Builds: no arm's build was independently correct on either world, because the X class hits held-out ticks 9–12
     (declared UNKNOWN at build time).

### 0.10 FREEZE (committed before `de4/val` or `de4/test` is opened)

`artifacts/r2_freeze.json` records the frozen choices, gates, caps and budgets, and the sha256 of every frozen file: code,
library, evaluator, baseline policies and split registry.

| frozen item | value |
|---|---|
| localiser | B1 |
| ordering | C0 |
| secondary localiser | B0 |
| forced naive options | X1 `txn_isolation=read_uncommitted`, X2 `gap_handling=skip`, X3 `fx_unknown=error`, X4 `discount_unit=percent_only` |
| budget caps | val ≤ 2,000 s, val_b ≤ 2,000 s, test ≤ 4,500 s |

The gates are those of §0.8.

## 1. Validation (`de4/val` 7961–7964, run once at `8a92efc`): PASSED on the first attempt

| arm | natural | forced recovery |
|---|---|---|
| NEXUS_Fresh | 4/4 | 4/4 (X1 2/2, X2 2/2) |
| every NEXUS arm | 0 silent errors | 0 silent errors |
| Fixed_Policy | 4/4 | 4/4 |
| Conventional_Checked | 0/4 (3 silent errors) | — |

* There were 0 replay-view violations.
* Secondary comparison, on the same forced deployments: B1 4/4 at 7.8 s of operator CPU, B0 2/4 at 76.1 s.
* No revision was made, and val_b is unopened.

## 2. Sealed confirmation (`de4/test`): INCOMPLETE because of a harness crash

**What ran:** the one-shot test started at `861b3c7` (frozen `8a92efc`).

* The first call scored 7971–7973.
* The second call scored 7974 and 7975, then **the runner crashed on de4-test-7976** with `KeyError: 'JPY'`, raised in
  harness code rather than in a pipeline subprocess.
* My resume loop retried after the crash, so it **re-executed 7976 twice more** before I stopped it. A crash should
  have stopped the loop.
* 7977 and 7978 never ran. Nothing has been re-run since, and no code was changed in order to finish the split.
* The crashed calls' 581 s is ledgered as an **estimate** from file timestamps.

**Crash cause: undetermined.** The vault is not inspected; one attempted directory listing was blocked by the
permission system and not retried.

* Post-test, on dev worlds with the X3 hook enabled (974, 976, 978 and 972), the crash did **not** reproduce.
* The candidate mechanism is an X3 order whose create record arrives late (tick ≥ 9) while an earlier update of the same
  order falls in the visible window. The build-time Stage 4 silver derivation, which is not de4-aware, would then index
  the fx table with JPY. That pattern occurred in 0 of 14 dev and src worlds, so the mechanism is **unconfirmed**.

**Scorecard on the 5 scored projects** (`artifacts/r2_test_scorecard_partial.txt`; X4 = 7971, 7973, 7975; X3 = 7972, 7974).
It is reported as partial, not as an 8-project result.

| measure | Conventional_Checked | Fixed_Policy | NEXUS_Fresh | NEXUS_Placebo | NEXUS_Experienced |
|---|---|---|---|---|---|
| **Natural end-to-end correct** | 0/5 | 2/5 | 3/5 | 3/5 | 3/5 |
| silent errors (natural) | 2 | 1 | 1 | 1 | 1 |
| ops data correct | 0/5 | 2/5 | 3/5 | 3/5 | 3/5 |
| open escalation at end | 0 | 2 | 1 | 1 | 1 |
| exactly-once crash trials failed | 30/184 | 0/296 | 0/164 | 0/164 | 0/164 |
| fully loaded engineering CPU s | 18.7 | 46.6 | 263.2 | 394.7 | 99.6 |
| own-pipeline repairs | 0 | 0 | 5 | 5 | 4 |
| clarifications / escalations | 0/0 | 0/9 | 0/4 | 0/4 | 0/4 |
| X3 natural: deployed mishandles / detected / repaired / correct | 2/0/0/0 | 2/2/0/0 | 2/2/1/1 | 2/2/1/1 | 2/2/1/1 |
| X4 natural: deployed mishandles / correct | 0 / 0 of 3 | 0 / 2 of 3 | 0 / 2 of 3 | 0 / 2 of 3 | 0 / 2 of 3 |
| **Forced recovery X3**: affected / detected / repaired / correct / silent | 2/0/0/0/0 | 2/2/0/0/0 | 2/2/1/1/0 | 2/2/1/1/0 | 2/2/1/1/0 |
| **Forced recovery X4**: affected / detected / repaired / correct / silent | 3/0/0/0/2 | 3/3/0/0/0 | 3/3/3/2/1 | 3/3/3/2/1 | 3/3/3/2/1 |

* Experienced / Fresh fully loaded CPU: 0.378 (CI 0.272–0.487), cheaper in 5/5. Experienced / Placebo: 0.252.
  End-to-end is equal at 3 = 3. The break-even point is 14.2 projects.
* **Secondary comparison** (same forced deployments and incidents): B1 3/5 at 21.0 s, against B0 2/5 at 42.1 s and 1
  silent error.
* **Component benchmark:** 4/5, with 1 silent error.

**Failure mechanisms (from committed outputs only):**

* **7971 (X4): a silent error.** One silver row differs from the reference while every monitor and the event-level
  reconciliation passed. That holds both naturally and after the forced repair, which correctly redeployed
  `discount_unit=registry_unit` at tick 9. The mechanism is undetermined.
* **7974 (X3):** self-detected in every NEXUS arm, unrepaired, escalated.

### 2.1 Verdicts (frozen rules; the 3 unscored projects cannot change them)

* **Natural: FAIL.** At most 3 + 3 = 6/8 is reachable, below the required 7/8, and every NEXUS arm already has 1 silent
  error.
* **Forced recovery: FAIL.** X4 has 1 silent error in every NEXUS arm. X3 stands at 1/2, so it is undetermined at the
  class level.
* **Learning claim: INCONCLUSIVE.** Only 5 of 8 projects were scored. On those five, the cost criteria are met at equal
  correctness of 3/5. That correctness is inadequate.
* **Experienced against Fixed_Policy:** Experienced is more correct (3/5 against 2/5) but 2.1× more expensive in CPU.

## 3. What R2 established (with bounds)

* **Count-based reconciliation was blind to identity errors, and event-level reconciliation catches them.** It flagged
  48/48 mutation states on dev against R1's 8/48, with 0 false alarms on 8 clean states.
* It is **not sufficient**: one silent silver-row error remains on the test (7971).
* The R1 7953-style "silent error" was reproduced on dev as an **evaluator-reference defect** (an incident relabelled an
  event through its retry duplicate), not as a pipeline fault.
* **B1 beats B0 under a correctly designed rule:** 42/44 against 33/44 on dev. Val 4/4 against 2/4 and test 3/5 against
  2/5 agree in direction.
* **Comparison C:** no improvement over C0.
* **Ops playbooks:** all rejected again.
* **Fixed_Policy:** strong on dev and val after strengthening; 2/5 on the partial test.

## 4. Resources

* **Budget:** R2 used **5,023 s** of ledger wall time, including the 581 s crashed-call estimate. At the end of R2,
  `scripts/r2_budget.py` shows 12,539 s remaining of the 32,390 s allowance. A later grant is accounted separately,
  starting from this number.
* **Commits:**

  | commit | contents |
  |---|---|
  | `19e298f` | pre-registration |
  | `5ddc216` | implementation |
  | `eb898ee` | dev results |
  | `8a92efc` | freeze |
  | val commit | validation |
  | `861b3c7` | seal |
  | `d208ab6` | test results (incomplete) |
  | this commit | report |
* **Protected files:** 912/912 unchanged.
