# NEXUS Data Engineering, Stages 4–6: Report (NOT LOCKED)

* **Branch:** `codex/nexus-data-engineering`. Work happens in an isolated worktree on local branch `claude/s456-work`, because
  a concurrent Antigravity agent shares the main checkout. Commits reach the active branch by fast-forward push only.
* **Starting state:** `18f53b6`, verified 2026-10-27. Both remotes are at `18f53b6`.
* **Carried budget:** 15,656 s remaining of the 17,990 s grant (`scripts/de_budget.py`).
* **Protected files:** 391 Stage 1–3 and kernel files, hashed before work began (aggregate sha256 `69335a66…`).
  README.md and AGENTS.md are in no frozen manifest.

## 0. Pre-registration (committed before any Stages 4–6 dev evaluation)

### 0.1 Splits (fresh; registered in `src/nexus/s456_seeds.py` without editing the locked seed registry)

| Split | Seeds | Use |
| --- | --- | --- |
| `de2/src` | 921–926 | Reusable. Source projects: the only experience the Stage 6 library may learn from |
| `de2/dev` | 931–936 | Reusable development |
| `de2/val` | 7921–7924 | One-use admission validation. `de2/val_b` (7925–7928) only if val fails and is reclassified as dev |
| `de2/test` | 7931–7938 | One-use. Sealed before use. **One combined paired confirmation** scores Stages 4, 5 and 6 together |

Stage 3's `de1/test` is consumed and is not reused. `final_sealed` is not used.

### 0.2 Genuinely withheld failure classes

These are absent from src, dev and val worlds (`withheld = split == "test"` in the generator). They are new failure
classes, not renamed or reparameterised familiar ones.

| Id | Stage | Class | Why it is a distinct failure mode |
| --- | --- | --- | --- |
| W1 | 4 | **Partition growth mid-stream**: orders_cdc gains a 3rd partition at tick 7 | Consumers that bind their partition set at start silently stop reading new keys. No dev or val world ever changes its partition count |
| W2 | 4 | **Event-time encoding switch**: the telemetry subject moves to epoch-millisecond `event_ts` at tick 7 (announced in the registry) | A type / encoding change of the event-time field. Dev and val evolve only the orders subject (rename, widening) |
| U1 | 5 | **Producer clock skew**: one telemetry partition emits event times days in the future | Poisons the watermark, so later on-time events look late. No dev or val incident involves time itself |
| U2 | 5 | **Poison message**: an undecodable record at a fixed offset causes a crash loop | A deterministic per-record crash that restarts cannot clear. Dev and val incidents are environmental or data-semantic |

The generator and the template contain *capabilities* that can handle these classes: dynamic partition discovery,
registry-typed timestamps, a future-event guard, a dead-letter list. All were written by the same author who chose the
classes. What is withheld is the **failure data and any tuning on it**. Whether checks and repair search detect and fix
these classes without having seen them is the generalization under test.

### 0.3 Contract (spec excerpt; full text in `src/nexus/s4_env.spec`)

* **Event identity:** `msg_id`. A redelivered record with the same id is the same event.
* **CDC order:** per key, by `source_version` (a monotone commit position, like a WAL LSN). Snapshot rows carry the snapshot's
  version. Tombstones block lower-versioned rows that arrive later. Arrival order and `event_ts` never decide CDC order.
* **Event time and watermark:** `watermark(tick k)` is the max telemetry `event_ts` of ticks before k, minus the allowed
  lateness. Late records are listed, counted in accounting, and excluded from the SLA. Future-dated records are quarantined.
* **Visibility:** outputs change only at a run's final commit.
* **Accounting:** every consumed record is applied, a duplicate, late, or quarantined. Nothing silently disappears.
* **Exactly-once effects:** verified by crashes before writes, after writes but before offset acknowledgement, and during
  recovery (a crash during the restart).
* **Rollback:** restores the end-of-tick-K state. Acknowledged later records are re-read, not lost. A crash during rollback
  must be recovered. The atomicity boundary is declared by the implementation and is not called "global atomic".

### 0.4 Arms (identical generator, proposer, tools, observations and caps; environments and memories reset between arms)

| Arm | Build (Stage 4) | Operations (Stage 5) | Library |
| --- | --- | --- | --- |
| `Conventional_Checked` (primary comparator) | Standard engineering checks: every tick runs, schema / unique / not-null keys, rerun of the last tick leaves the state unchanged, non-empty outputs. Retries on exceptions; may ask clarifications | Restart and retry; follows explicit error text for authored remediations (rotate an expired credential, wait for an unavailable source) | none |
| `NEXUS_Fresh` | Full NEXUS invariants: crash sweeps (before / after write / during recovery), metamorphic, conformance, lag / accounting, rollback drill | Investigation from logs, metrics and lineage; compositional repair search with shadow tests; reconciliation | none |
| `NEXUS_Placebo` | as Fresh | as Fresh | size-matched library of permuted procedures |
| `NEXUS_Experienced` | as Fresh | as Fresh | admitted library learned on `de2/src` only, frozen before confirmation |
| `Conventional_NoCheck` (descriptive ablation only) | stops at the first exception-free run | restart only | none |

The independent evaluator grades every arm identically. No solver receives expected outputs, generator decisions or
fault-class ids.

### 0.5 Still to be fixed on dev data, before the freeze

* The primary cost metric and its effect threshold.
* Admission thresholds.
* Drift-detector settings.

Each of these will be committed in the freeze section before `de2/val` is opened.

### 0.6 FREEZE (committed before `de2/val` or `de2/test` is opened)

**Frozen code.** `s4_env`, `s4_template`, `s4_evaluator`, `s4_checks`, `s4_agent`, `s5_incidents`, `s5_ops`, `s6_library`,
`s456_seeds`, `scripts/s456_run.py`. The one-use runners refuse to start if any of these differs from HEAD.

**Frozen library.** `artifacts/s6_library.json`, learned on `de2/src` only:
* 10 build procedures admitted;
* 2 retired because the src evidence disagrees (two options are correct there);
* all 5 ops playbooks retired, because their measured saving does not exceed retrieval + applicability + amortised maintenance.

**Frozen detector settings.** `artifacts/s5_detector_calibration.json`. The operator detector is `fixed_ratio` (w = 4, k = 1.4).
The strict operating point (at most 1 false alarm per 1,000 records and at most 10% misses) was infeasible for both detectors
on src + dev. That is recorded; selection used min-miss-first.

**Caps.** Per project per arm: at most 40 proposals, 900 CPU-s per build, 40 shadow tests per operator turn, 6 runs per tick,
and a pod quota of 300 records per run (simulated).

**Primary cost metric (chosen on dev).** Per-project **engineering CPU**: build (agent, every check and repair-search pipeline
run, library retrieval, applicability and failed reuse) plus operations engineering (operator agent and shadow tests).
Scheduled production runs are reported separately as operating cost. Dev results (`artifacts/s456_dev.json`):
* Experienced / Fresh: 0.179 (95% CI 0.13–0.29, 6/6 projects);
* Placebo / Fresh: 1.56.

**Verdict rules for the one combined paired confirmation on `de2/test` (8 sealed projects, one shot).**

| Stage | PASS iff |
| --- | --- |
| 4 | `NEXUS_Fresh` **and** `NEXUS_Experienced` builds independently correct on 8/8 (checkpoints 4, 8 and 12 incl. held-out ticks, 0 failed crash trials, rollback drill), incl. the withheld W1 / W2 worlds, with 0 silent errors; **and** the real integration (`scripts/s4_integration.py`, fresh seeds 10 and 11) ends with Delta == PostgreSQL after the crash sweep and after rollback + replay |
| 5 | `NEXUS_Fresh` ops: final data correct **and** service restored **and** 0 unresolved incidents on 8/8, incl. the withheld U1 / U2 incidents; **and** `ConventionalOps` (restart / runbooks) fails data on at least one project, showing that a restart without repair does not pass |
| 6 | `NEXUS_Experienced`: 0 silent errors; build-correct and ops-correct counts each at least Fresh's; **and** pooled engineering CPU at most **0.70× Fresh and at most 0.70× Placebo**, with the paired bootstrap 95% CI upper bound below 0.90 and cheaper in at least 7/8 projects against each. Total cost including library construction is reported with break-even (descriptive) |

**Further reporting rules.**
* Drift detectors (descriptive): false alarms, true alarms, delay, CPU and downstream ops correctness for `bocpd_merge_exact`,
  `fixed_ratio` and `disabled`. The N1 hypothesis counts as **supported** only if BOCPD gives more correct ops outcomes, or the
  same outcomes with fewer false alarms, than `fixed_ratio`.
* Failure reporting: a failed gate is FAIL. INCONCLUSIVE applies if fewer than 8 projects complete. Nothing is rerun.

**Admission gate on `de2/val` (4 projects, one use).**
* `NEXUS_Fresh` and `NEXUS_Experienced` must each be build-correct 4/4 and ops-correct 4/4, with 0 silent errors, and
  Experienced / Fresh engineering CPU must be at most 0.70.
* If the gate fails, val is reclassified as dev, the failure is fixed and disclosed, and `val_b` is used once.

**Missing-data rule.**
* The runner checkpoints per project, and a resume after the call cap is not a re-run.
* A crashed project is recorded as FAIL for the affected arm.

## 1. What is real, what is simulated, what is unsupported

| Component | Status | Evidence |
| --- | --- | --- |
| Offset log, exactly-once contract, backfill, registry evolution, watermarks, retractions, rollback (Stage 4) | **Semantic harness (simulated)**: JSONL segment files plus sqlite state, run as separate OS processes | `s4_env`, `s4_template`, `s4_evaluator` |
| Database CDC | **REAL**: PostgreSQL **14.18** logical replication slot with the built-in `test_decoding` plugin. (My earlier "15+" was wrong.) Debezium is **not** used | `scripts/s4_integration.py` |
| Persistent source checkpoint | **REAL**: the replication slot's confirmed position, advanced only after the sink commit and with a delayed-acknowledgement window | same |
| Lakehouse table backend | **REAL**: Delta Lake via delta-rs 1.6.6 (ACID MERGE, optimistic concurrency, `restore`) | same |
| Process crashes | **REAL**: `os._exit` at every write / ack boundary (harness), and external `SIGKILL` at phase boundaries, during recovery and at random times (both paths) | evaluator and integration |
| Rollback atomicity | **One atomic Delta commit (`restore`)**, then **coordinated** replay from the retained slot. In the harness: one-file `os.replace` of `lake.db`, plus a rollback-intent journal for `offsets.json`. **Not a global atomic rollback** across database and lake | `s4_template.rollback`, integration step 3 |
| Pod memory quota, credential expiry, source unavailability (Stage 5) | **Simulated**: a record-count quota with state revert, `chmod`-based read-only sink and unreadable source | `s5_incidents` |
| Model / LLM proposer | **Unsupported here**: 0 model calls. Build generation is selection over a 14-decision template; ops repairs are compositions of **authored** primitives with **authored** parameter inference, found by **search** | `s4_template`, `s5_ops` |

**Compositional search, and its limits.**
* **Build:** hill-climbing with severity scores; a regression guard (every check that passed before must still pass);
  conflict-directed pairs (a change that improves the check but breaks guard G is paired with changes to the decisions G
  implicates).
* **Ops:** subsets of up to 3 primitives in canonical order, with two-round deepening (re-diagnosis inside the shadow).
* **Expressiveness limit:** nothing outside the 14 template decisions and the 7 ops primitive types can be synthesized. The
  composition is synthesized; the parts are authored.

**The real integration consumer is engineered by me**, not built by a NEXUS agent. It demonstrates that the contract holds
on real components; it does not show that NEXUS can build such a consumer.

## 2. Results: one combined paired confirmation on 8 sealed `de2/test` projects (code `647bb48`, run once)

**Conditions.** Every test world contains the withheld classes W1 and W2 and one withheld incident class (4 × U1 clock skew,
4 × U2 poison message).

### Stages 4–6 unified 7-measure scorecard (`scripts/s456_analyze.py artifacts/s456_test.json artifacts/s6_library.json`)

| Measure | Metric | Conventional_Checked | NEXUS_Fresh | NEXUS_Placebo | NEXUS_Experienced | Conventional_NoCheck (ablation) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 Correctness | build independently correct (checkpoints 4 / 8 / 12, crash trials, rollback) | 0/8 | **4/8** | 4/8 | **4/8** | 0/8 |
| | build silent errors (submitted, wrong) | 8 | **4** | 4 | **4** | 7 |
| | held-out ticks 9–12 correct | 0/8 | 4/8 | 4/8 | 4/8 | 0/8 |
| | ops: final data correct | 0/8 | **7/8** | 7/8 | **7/8** | 0/8 |
| | quarantined / late records (accounted) | 16 / 104 | 30 / 97 | 30 / 97 | 30 / 97 | 13 / 83 |
| 2 Completion | builds submitted / abstained / hard fail | 8/0/0 | 8/0/0 | 8/0/0 | 8/0/0 | 7/1/0 |
| | incidents unresolved at end | 5 | 0 (2 escalations) | 0 | 0 | 13 |
| 3 Reliability | failed exactly-once crash trials / trials run | 50/314 | **0/296** | 0/296 | **0/296** | 48/286 |
| | rollback drill ok | 0/8 | 4/8 | 4/8 | 4/8 | 0/8 |
| | ops service restored at end | 4/8 | 8/8 | 8/8 | 8/8 | 2/8 |
| | freshness violations (ticks) | 11 | 0 | 0 | 0 | 25 |
| | duplicate rows / secret leaks | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| 4 Cost | **PRIMARY engineering CPU s** (8 projects) | 17.2 | **347.6** | 556.2 | **119.4** | 7.4 |
| | build CPU / rejected + repair-search CPU (s) | 17.2 / 11.2 | 339.9 / 230.3 | 548.4 / 390.1 | 111.6 / 55.0 | 7.4 / 4.0 |
| | check runs (all) / final accepted suite | 420 / 72 | 8,271 / 1,176 | 13,430 / 1,176 | 2,824 / 1,176 | 182 / 56 |
| | proposals / ops shadow tests | 13 / 0 | 54 / 76 | 92 / 76 | 15 / 76 | 28 / 0 |
| | library retrieval + applicability CPU (s) | 0 | 0 | 0.019 | 0.018 | 0 |
| | failed reuse (count / CPU s) | 0 | 0 | **79 / 337.9** | **0 / 0** | 0 |
| | operating CPU (production runs, s) | 1.7 | 4.1 | 4.2 | 4.2 | 1.5 |
| 5 Human dependence | clarifications / escalations / human repairs | 0 / 0 / 0 | 1 / 2 / 0 | 1 / 2 / 0 | 1 / 2 / 0 | 0 / 0 / 0 |
| 6 Learning | Experienced / Fresh engineering CPU | | | | **0.343 (95% CI 0.235–0.421), cheaper on 8/8** | |
| | Placebo / Fresh | | | **1.600 (CI 1.35–2.11), cheaper on 0/8** | | |
| | Experienced / Placebo | | | | **0.215 (CI 0.134–0.289), 8/8** | |
| | library construction (source curriculum 231.2 + leave-one-out maintenance 89.5 s) | | | | 320.7 s; saving 28.5 s per project; **break-even 11.2 projects**; including learning, 1.27× Fresh over these 8 | |
| 7 Generalization | withheld-class worlds: build / ops correct | 0/8 / 0/8 | 4/8 / 7/8 | 4/8 / 7/8 | 4/8 / 7/8 | 0/8 / 0/8 |

**How the withheld classes went.**

| Class | Outcome |
| --- | --- |
| W1 partition growth | **0 of the 4 projects where it mattered were detected.** In all 4 build failures the proposer picked `static_initial`, which passed every NEXUS check. In the other 4 it picked `dynamic` first, by chance |
| W2 epoch-ms timestamps | 8/8 handled. It fails loudly, so even Conventional repaired it via exception attribution |
| U2 poison message | 4/4 repaired (dead-letter at the crash offset) |
| U1 clock skew | 3/4 repaired (future guard + rollback + replay). test-7934 escalated twice and ended with wrong SLA, late and quarantine tables |

**Drift detectors** (NEXUS_Fresh ops; every variant also has the producer-metadata trigger):

| Detector | Ops correct | Alarms | On shifted suppliers | Other (false) | Mean delay | Detector CPU |
| --- | --- | --- | --- | --- | --- | --- |
| bocpd_merge_exact | 7/8 | 14 | 6 | 8 | −0.3 ticks (alarms before the shift also counted) | 0.005 s |
| fixed_ratio | 7/8 | 26 | 13 | 13 | 2.7 ticks | 0.001 s |
| disabled | 7/8 | 0 | 0 | 0 | n/a | 0.001 s |

### 2.1 Verdicts (predeclared rules, applied unchanged)

| Stage | Verdict | Why |
| --- | --- | --- |
| **4** | **FAIL** | The NEXUS_Fresh and Experienced builds were correct on 4/8 (rule: 8/8), with 4 silent errors, all W1. The exactly-once components passed: 0 failed crash trials out of 296 per NEXUS arm. **Real integration: PASS** (seeds 10 and 11: Delta == PostgreSQL after 29 SIGKILLs at every phase boundary and during recovery, and after a bad deploy (22 / 25 wrong rows) was restored and replayed) |
| **5** | **FAIL** | NEXUS_Fresh ops correct on 7/8 (rule: 8/8), with 2 escalations. The second requirement holds: ConventionalOps restored service on 4/8 and **data on 0/8**, so a restart without repair does not pass |
| **6** | **FAIL** (cost criterion met, correctness requirement not) | Experienced used 0.343× Fresh and 0.215× Placebo engineering CPU (CI upper bounds 0.421 and 0.289, below 0.90; cheaper on 8/8 against each), with 0 failed reuse. It had the **same** correctness as Fresh (4/8 build, 7/8 ops), but the rule requires 0 silent errors, and it had 4. The library neither caused nor fixed them |
| **N1 drift hypothesis** | **Supported by the letter of the predeclared rule; no downstream benefit** | Equal ops correctness (7/8) with fewer false alarms than fixed_ratio. But `disabled` also scores 7/8: the producer-metadata trigger and the stakeholder question did the work. Neither detector changed any outcome |

### 2.2 Root causes (post-hoc; the sealed test is not re-run)

1. **W1 (4 silent build errors).** NEXUS's own replay harness (`s4_checks.grow`) created every partition directory at tick 1.
   Partition growth therefore never happened in NEXUS's self-tests. The NEXUS self-model of its environment lacked fidelity
   for exactly the unseen failure mode.
   * A post-test fix (separate commit, after the test) makes partitions appear only with their first segment. On an
     unregistered probe world, `static_initial` now fails the lag check and the correct pipeline passes.
   * This is a fix for the future, not a result: confirming it needs a fresh sealed split.
2. **test-7934 (one ops failure).** A clock skew at tick 13 was detected (watermark sanity), and the right primitives (future
   guard, rollback) were among the candidates, but no shadow test passed, so the operator escalated twice.
   * The same composition repairs a late clock skew on a probe world.
   * The exact cause is **undetermined**, because inspecting the sealed world outside the locked runner is not allowed
     (RULE 1).
   * Disclosure: the freeze text says "40 shadow tests per operator turn", but the code caps 40 per run. test-7934 had used 31.

### 2.3 Stage 3 reinterpretation (addendum item 2)

* **What it showed:** Stage 3 showed validation and clarification over a fixed 14-decision generator on about 70 orders per
  project, with 0 model calls.
* **What it did not show:** general coding ability, unfamiliar-fault diagnosis, or learned transfer.
* **The ablation:** here, NEXUS_Experienced against NEXUS_Fresh on the same projects attributes about 66% of Fresh's
  engineering CPU to starting without procedures. That figure is specific to this Stage 4–6 workload and generator. The
  Stage 3 numbers (32.73 s, 22.98 s, 712 checks) are descriptive and were not used as thresholds.

## 3. Capability-by-capability evidence

| Capability | Verdict | Evidence |
| --- | --- | --- |
| Exactly-once effects under process crashes (harness) | **DEMONSTRATED on the evaluated cases** | 0/296 failed crash trials per NEXUS arm on the sealed test (before every write / ack boundary, during recovery, random SIGKILL); Conventional_Checked failed 50/314 |
| Exactly-once CDC → lakehouse on real components | **DEMONSTRATED on 2 fresh + 3 dev seeds** | PostgreSQL slot + Delta MERGE with source row versions; 0 duplicate keys; exact match after the crash sweep and after restore + replay. The first design (LSN precedence) **failed** dev seed 1 (a resurrected delete) |
| Backfill concurrent with live CDC without overwriting newer changes | **DEMONSTRATED** (harness checkpoint at tick 4 + real integration) | source-version precedence, tombstones |
| Schema evolution (add, rename, widen) | **DEMONSTRATED in the harness** | all NEXUS builds handled v2 / v3; v1-name decoders are caught |
| Bad-deploy rollback | **Harness 4/8** (it failed wherever W1 corrupted the run); **real 5/5 runs** | coordinated recovery, not global atomic |
| Detecting unseen failure classes | **MIXED** | loud classes (W2, U2) 12/12; silent class W1 **0/4**; U1 3/4 |
| Hidden-cause incident repair restoring service and data | **7/8 projects** (FAIL against the 8/8 gate) | 23 shadow-verified repairs: 14 single, 9 compositions; restart-only / runbook operations: 0/8 data |
| Verified experience reuse cutting cost at matched quality | **Cost effect DEMONSTRATED; quality matched (both 4/8)** | 0.343× Fresh, 0.215× Placebo, 8/8; break-even 11.2 projects when learning is counted |
| N1-merge-exact as a drift detector | **No downstream benefit** | the disabled detector does equally well because of the metadata trigger |
| General coding / LLM-level synthesis | **NOT IMPLEMENTED** | template selection plus authored primitives |

## 4. Resources and provenance

* **Budget.** Stages 4–6 used 5,112 s (every run in the hash-chained ledger; one 420 s entry is an estimate for interactive
  dev trials, disclosed). Total 17,990 s; remaining **10,544 s**.
* **Protected files.** 391 Stage 1–3 and kernel files are byte-identical before and after
  (`artifacts/s456_protected_hashes_{before,after}.json`).
* **Tests.** `tests/test_s456.py` 6/6; Stage 1 regression and the Stage 3 tests still pass.
* **Dependencies.** Shared `.venv` unchanged. The integration uses a separate venv (`~/.claude-worktrees/venv-s456`: deltalake
  1.6.6, psycopg 3.3.6, pyarrow 26.0.0) and the local Homebrew PostgreSQL 14.18. No paid service.

**Commits** (`codex/nexus-data-engineering`, fast-forwarded from the isolated worktree branch `claude/s456-work`):

| Commit | Contents |
| --- | --- |
| `c4ec6e0` | Pre-registration |
| `f5c271f` | Stage 4 code |
| `73ef7db` | Stage 5 code |
| next commit | Implementation complete |
| `647bb48` | Freeze + dev results |
| `0b2ca04` | Val |
| `3dd164d` | Seal |
| then | Test results, post-test fix, this report |

## 5. Next experiment (one)

**A fresh sealed split with the fidelity fix, plus an environment-fidelity check.**
* Before any build, NEXUS should validate its own replay harness against the observable log (partition birth times, segment
  ordering, registry causality). The W1 failure was a self-model fidelity error, not a missing capability.
* Then rerun Stages 4–6 on a new one-use split with at least two **new** withheld classes. Reusing W1 would no longer be
  withheld, because the fix was designed after seeing it.
