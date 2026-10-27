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
