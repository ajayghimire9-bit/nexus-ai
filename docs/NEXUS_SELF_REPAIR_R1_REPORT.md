# NEXUS self-repair increment R1: detect and repair faults in pipelines NEXUS builds (NOT LOCKED)

Branch `codex/nexus-data-engineering` (worktree `claude/s456-work`). Starting revision **`f7bc420`** (verified on both
remotes, worktree clean). Carried budget at start: **10,544 s** of the 17,990 s grant (ledger rows `w41*`, `de-*`, `de2-*`;
`scripts/de_budget.py` omits the `de2-` rows and prints 15,656 s, so it is wrong; `scripts/r1_budget.py` is the corrected
tally; the protected script is left unchanged). Protected files at start: 912 (`artifacts/r1_protected_hashes_before.json`:
the 391 Stages 1–3 / checker-kernel files plus every Stages 4–6 result, bundle, manifest, library, calibration and the
Stages 4–6 report).

## 0. Pre-registration (committed before any R1 dev outcome)

### 0.1 Corrected premises (from the Stages 4–6 record, not re-litigated)

* **Stage 6** reduced cost at **unchanged, inadequate** correctness. It did not pass its correctness gate.
* **test-7934:** its operator had used 31 shadow tests when it escalated. The exact cause is undetermined. The documented
  mismatch was that the freeze said "40 per operator turn" while the code capped 40 per run. R1 caps shadow tests at
  40 per turn and 200 per run, and the code and this text agree. Budget exhaustion is **not** claimed as the cause.
* **The post-test partition-birth fix (`0bc3e0c`)** is tested independently here (§0.3). Its implementation is not
  counted as an R1 result.
* **Inspected mechanisms become development data.** These were all inspected in Stages 4–6: W1 partition growth, W2
  epoch-ms timestamps, U1 clock skew, U2 poison message and the five seen incidents. In R1 they occur in src, dev, val
  and test worlds alike.

### 0.2 Splits (namespace `de3`, registered in `src/nexus/r1_seeds.py`; one-use ranges go to the spent ledger)

| split | seeds | use |
|---|---|---|
| src | 941–946 | library learning only (Stage 6 procedure) |
| dev | 951–958 | all development, the A/B comparisons, mutation benchmarks |
| val | 7941–7944 | one-use admission gate (seen classes only). If validation changes the implementation, val is spent and reclassified as dev, and val_b 7945–7948 is used once |
| test | 7951–7958 | one-use sealed confirmation (vault blobs + sha256 manifest committed before the runner; RULE 1) |

**Two genuinely withheld classes, chosen now, before dev.** They are realised only in test worlds, from tick 9, after the
build window (ticks 1–8), so they hit build held-out ticks 9–12 and ops ticks 9–14. Each test world gets exactly one of
them: even seeds X1, odd seeds X2.

* **X1 aborted producer transactions** (orders_cdc). From tick 9, some CDC records carry `txn_id`. A control record
  `txn_commit` / `txn_abort` with that `txn_id` follows on the same partition. Aborted transactions carry phantom
  changes with high `source_version`s that must never be applied. This is the Kafka read-committed situation.
* **X2 delayed segment publication with a gap** (orders_cdc). From tick 9, one segment of one partition becomes visible
  two ticks late, while the next segment is already visible. A consumer that advances its offset past the hole loses
  those changes permanently.

Both rules are **declared in every spec (all splits)**, because a contract that only appears at test time would be
unfair:

* "records carrying txn_id take effect only if their transaction commits"
* "offsets within a partition are contiguous; segments may become visible out of order; never acknowledge an offset you
  have not durably consumed"

The generator code for X1 and X2 is never executed on src, dev or val worlds. The template options that handle them
(`txn_isolation=read_committed`, `gap_handling=wait_contiguous`) are unit-tested only on hand-written spec-conformant
mini-logs. The author knows both mechanisms (disclosed). What is withheld is their realisation and any tuning on it.

**Build-time probe set is frozen at the Stage 4 set.** No probe is written for X1 or X2. A property with no build-time
evidence is reported **UNKNOWN**, not PASS (§0.5). The increment tests whether NEXUS notices such mismatches **at run
time**, repairs its own pipeline and reconciles the data. Build-time probes for every declared rule are the obvious
alternative. They are the next ablation, not part of R1.

### 0.3 The independent observation-to-replay check (built first)

* **Authoritative observations.** Every log root carries `log/_obs/tick_NNNN.json`, written by the environment (the
  broker / registry metadata API). Each file holds only facts as of that tick:
  * partition lifecycle (topic, partition, created tick, state);
  * available segments (base / end offset, publication tick, retained or not);
  * per-partition log-end offset and the contiguous-available offset;
  * registry versions per subject with their offset and tick;
  * transaction boundaries (txn_id, partition, first / last offset, status open / committed / aborted at that tick).
* **Monitor** `src/nexus/r1_monitor.py`, stdlib only. It imports nothing from NEXUS, the replay helper, the checks or the
  template. At a checkpoint k it reads only `tick_k` (no future observations) and the view under test. Violations:
  * `partition_early`, `partition_missing`;
  * `segment_missing`, `segment_future`, `segment_retained_wrongly`;
  * `schema_future` (a registry record, or a record naming a version, not registered as of k);
  * `order_violation` (record offsets differ from the observed contiguous segment ranges);
  * on consumer state: `ack_beyond_available` (committed offset beyond the contiguous-available end) and
    `ack_beyond_durable` (committed offset beyond the durably recorded consumed offsets).
* **Replay helper** `grow_obs` in `src/nexus/r1_checks.py`. It materialises a tick-k view from the observations (partition
  directories by lifecycle, segments by availability), not from the first surviving data record. Metamorphic rewrites
  carry the partition lifecycle from the source observations.
* **Dev demonstration.** For each of 5 replay mutations, on all 8 dev worlds, at checkpoints 1–8 of the build view and
  1–14 of the ops view, the monitor must flag a violation at the first checkpoint where the mutation changes
  visibility. It must also give 0 violations on the unmutated `grow_obs` view. It never sees mutation labels. The 5
  mutations:
  1. partition exposed early;
  2. partition or segment omitted;
  3. future schema exposed;
  4. source events reordered within a partition;
  5. ack beyond durable effects (crash after offsets_store, before the sink commit).
* The **pre-fix** `grow` (`f7bc420^` behaviour: every partition directory at tick 1) and the **post-fix** `grow` (`0bc3e0c`)
  are both run through the same monitor and reported as measured. The post-fix result is **not** assumed to pass.
* **P / PObserve** is evaluated on cost only: its value is checking a model of the replay protocol. The properties above
  are finite set comparisons per checkpoint. Integrating P needs a .NET toolchain and a Java runtime. That integration
  cost is only justified if a property needs temporal reasoning across checkpoints that the explicit monitor cannot
  express, and none does, so it is NOT IMPLEMENTED with this reason. No P model is claimed.

### 0.4 Build connected to operations

* Operations run on **each arm's own submitted pipeline and configuration**. A not-submitted build (abstain, hard fail)
  counts as an end-to-end failure.
* The supplied-correct-pipeline operations run is kept as a separately labelled **component benchmark**
  (NEXUS_Fresh's operator only).
* Each operator's API adds `redeploy(decisions)`, a change of its own pipeline's build decisions inside the template's
  repair language, applied to its own bundle copy.
* **Reconciliation gate.** An incident or mismatch is recorded as resolved only after reconciliation passes in the shadow
  **and** after the real application:
  * coverage: every observed offset below the committed offset is accounted in `_consumed`;
  * output: silver, gold revenue and status counts, and late_events re-derived per the spec from the archived records
    below the committed offsets, compared with the pipeline's tables.
  * The archive is a read-only, tiered-storage copy of every published segment, available to operators only.
* Reported separately: service recovery, data recovery, escalations, unresolved at end, and self-detected failures.

### 0.5 Scoped evidence (replaces pass/fail lists)

* **Evidence records.** Each required property gets one record:
  `{property, checker (module@sha256[:12]), evidence_source, assumptions, bounds, cost (cpu_s, runs), result}`.
* **Results:** PASS_WITHIN_SCOPE, FAIL, UNKNOWN or NOT_APPLICABLE. NOT_APPLICABLE is used only when the spec rules the
  property out, and no current property qualifies.
* **Outcome mapping** (`src/nexus/outcome_contract.py` labels):
  * all PASS_WITHIN_SCOPE → `COMPLETED_VERIFIED`;
  * no FAIL but some UNKNOWN → `COMPLETED_UNVERIFIED`, with the unknown properties listed; it is still submitted, and
    those properties are monitored at run time;
  * a FAIL that the repair search cannot remove → `ABSTAIN_UNSUPPORTED`.
* **Requirements:**
  * Input-coverage and output-reconciliation evidence is required for every build, in addition to protocol checks.
  * Crash-sweep evidence is bounded to its enumerated crash points.
  * Metamorphic evidence is bounded to its transformations, whose preconditions are recorded. For example, chunking
    within a tick preserves the semantics only because the spec defines the watermark per ingest tick and transactions
    never span a chunk boundary in visible data. Arrival permutation applies only to same-key CDC records, respecting
    registry causality.
* **External tools, not used, and not claimed:**
  * CrossHair: no counterexample is not a proof.
  * VeriEQL: there is no SQL query pair to compare.
  * Elle: transaction histories are not the main risk.
  * Differential testing against an old pipeline: it shares defects.

### 0.6 Development comparisons (at most three)

* **A. Conformance and metamorphic testing.** Mutants: every single wrong option of every decision applied to a correct
  pipeline, on dev worlds. Arms:
  * A0, the corrected baseline: Stage 4 NEXUS suite with post-fix `grow`;
  * A1: A0 with `grow_obs` and the monitor (replay conformance + ack checks, run at every replayed checkpoint and after
    every crash point);
  * A2: A1 with the chunking metamorphic transform and the input-coverage / output-reconciliation properties.

  Metrics: mutants rejected / total, false rejections of the 2 × 2 × 2 correct-option combinations (commit protocol,
  gold maintenance, snapshots = per_tick), and CPU.
* **B. Failure localisation and repair.** Same single-fault mutants, plus ops runs on mutated own pipelines. Arms:
  * B0: the existing `localize` (implicated decisions first, severity hill-climbing, conflict pairs);
  * B1: failure-trace shrinking (ddmin over counterexample keys, keeping causal dependencies: registry records,
    snapshot / transaction controls, per-partition order) + provenance-assisted localisation (features of the
    counterexample's source records contrasted with those of agreeing keys → typed holes) + typed CEGIS (candidate
    options for the suspect holes checked first against the accumulated shrunk counterexamples, then the full suite;
    a failing full check adds a counterexample).

  Metrics: suspect-set size, whether the true decision is in the suspect set (accuracy, top-1), trials, CPU, repaired.
  No unique one-pass diagnosis is promised.
* **C. Diagnostic selection** runs **only if A and B both work** (the A2 / B1 arms meet their dev criteria below). If it
  runs, it compares fixed ordering, a cheap contextual policy and our cost/information-gain **heuristic**, which is
  not standard IDS. Otherwise it is NOT RUN.
* All arms get the same tools, observations, repair language and acceptance checks. Every arm is charged for
  diagnostic scoring, failed repairs, shrinking and CEGIS trials. There are 0 model calls (none are used).
* **Dev selection criteria (chosen now):**
  * A2 is adopted if it rejects ≥ the mutants A0 rejects, with 0 false rejections.
  * B1 is adopted if its localisation accuracy is ≥ B0's and its mean CPU per repaired mutant is lower; otherwise B0 is
    kept.

### 0.7 Confirmation arms (environments and memories reset between arms)

| arm | build | operations |
|---|---|---|
| Conventional_Checked | STANDARD checks, same proposer | ConventionalOps (runbooks on error text), on its own pipeline |
| Fixed_Policy (strong fixed policy) | one configuration: the src-majority option per decision (proposer order where src has no evidence), full NEXUS suite, no repair search; abstains on a FAIL | the same monitors and reconciliation as NEXUS, a fixed canonical runbook (first diagnosed composition, no search, no redeploy search) |
| NEXUS_Fresh | full suite + adopted localisation, no library | NexusOps-R1 (monitors, reconciliation gate, incident search, own-pipeline repair) |
| NEXUS_Placebo | as Fresh + size-matched permuted library | as Fresh + permuted playbooks |
| NEXUS_Experienced | as Fresh + library learned on de3/src | as Fresh + learned playbooks |

* The library is learned only on src. It is frozen before val. There is no learning during useful work (online
  learning is disabled, so that cost is 0 by construction). The dedicated source-learning CPU is reported separately.
* The ops detector is `fixed_ratio`, as in Stages 4–6. The BOCPD comparison is not repeated: N1 showed no downstream
  benefit.

### 0.8 Metrics and decision rules (primary metric fixed now)

* **PRIMARY:** end-to-end correct completed projects per arm on the 8 test projects. A project counts if all of these hold:
  * the build was submitted;
  * the ops final data equals the truth reference;
  * service is restored at the end;
  * there is no duplicate key;
  * conservation holds;
  * no unresolved incident is claimed resolved.
* **Silent error:** the arm ends claiming a healthy, reconciled pipeline (no open escalation) while the final data is
  wrong.
* **Also reported:** self-detected failures, abstentions, escalations, clarifications, service and data recovery, the
  build-only scorecard (Stage 4 measures) and fully loaded cost. Fully loaded engineering CPU = build agent + every check
  and search run + library retrieval / applicability / failed reuse + ops agent + shadow tests + reconciliation +
  localisation / CEGIS trials.
* **Paired project-level comparisons:** Experienced / Fresh, Experienced / Placebo and Fresh / Fixed_Policy, as the ratio
  of pooled sums, with a paired bootstrap 95% CI over projects and sign counts.
* **R1 PASS** (all must hold):
  1. NEXUS_Experienced end-to-end correct ≥ 7/8;
  2. 0 silent errors for every NEXUS arm;
  3. on withheld worlds, for every NEXUS arm, every project whose deployed pipeline mishandles its X class is
     self-detected, and ≥ 3 of the 4 projects per class end end-to-end correct.
* **Learning claim** (all must hold; otherwise "no learning claim"):
  1. the Experienced / Fresh fully loaded CPU CI upper bound is < 1.0;
  2. Experienced end-to-end correct ≥ Fresh's (maintained coverage);
  3. Experienced / Placebo < 1.0.

  The break-even point is reported including the source-learning cost.
* **Val gate** (4 projects, seen classes): NEXUS_Fresh end-to-end ≥ 3/4, 0 silent errors and monitor violations 0 on the
  correct replay. A failure means val is spent, the implementation may change, and val_b is used once.
* **Missing / failure rules:**
  * A crashed arm counts as a failure for that project.
  * A cap hit is saved as a CHECKPOINT row, and the runner resumes without re-running finished projects (a resume is not
    a re-run).
  * The sealed test is never re-run. A post-test fix is a separate commit and is not a result.
* **Caps:**
  * per build: 40 proposals and 900 CPU-s;
  * shadow tests: 40 per operator turn, 200 per run;
  * localisation: 60 trials;
  * CEGIS: 12 full verifications per repair;
  * scheduler: 6 runs per tick;
  * at most 900 s per call;
  * total R1 compute ≤ the 10,544 s remaining.
