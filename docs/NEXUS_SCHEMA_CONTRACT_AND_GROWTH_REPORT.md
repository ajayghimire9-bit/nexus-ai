# NEXUS lifecycle schema contract, field-mapping repair and growth-rule retest (sc track) — NOT LOCKED

Owner-controlled EXPERIMENTAL workflow. Branch `codex/nexus-data-engineering` (local `claude/s456-work`), starting revision
`4f5315f` (= origin = github at the audit; clean tree). Preserved unchanged: the ba results — learned growth 265/300 vs hand
248 vs shuffled 241 (ba/ep_held2) and the sealed ba scorecard 8/16 independently correct with all eight X6 projects failing
(`artifacts/ba_test/*`, hashes of all 157 ba files in `artifacts/sc_ba_hashes_before.json`), 912 protected files, `main`,
`final_sealed`, Checkers v1–v5, all frozen implementations. All new code is in new `sc_*` files.

## 0. Pre-registration (committed before any sc evaluation outcome)

### 0.1 Budget and execution
* No grant is credited again. Allowance 82,790 s (already recorded); remaining at the audit **11,946 s** (`scripts/sc_budget.py`).
* Every call runs under `scripts/sc_exec.py` (refuses if the remaining budget < cap; cap ≤ 900 s; charges wall time,
  records child CPU and peak RSS; the child's complete stdout + stderr is saved to `artifacts/sc_logs/<run>.log`).
* **Interruptions:** a call that ends without its structured result (TIMEOUT / host interruption) may be re-attempted with
  unchanged code (sha256 = freeze) from its saved state / seeds; every attempt and its cost stays in the ledger. A completed
  result (any outcome) is never rerun. Episode runners append one JSON line per finished episode (resumable); project
  runners write one atomic JSON per (project, arm) (temp file + rename).
* **Scope reduction rule:** if the remaining budget before the validation would not cover validation + confirmation at the
  measured per-project cost × 1.5, the confirmation is reduced *before the freeze* and labelled a pilot.

### 0.2 Part G — separate growth-rule comparison, fallback disabled (meta-learning claim)
* Arms: Learned (TablePolicy on `artifacts/ba_dev/records_bounded.jsonl`), Hand (`oc_learner.hand_policy`), Shuffled (same
  records, signatures permuted with Random(13)), Random — exactly the frozen ba policies (sha256 in `artifacts/ba_freeze.json`).
* Learner: `ba_learn.learn_episode(accept="bounded")` — the growth learner alone; **no full-space fallback**; the identical
  bounded acceptance check and primitive update language; task memory reset per episode.
* Units: 300 **fresh** micro-episodes sc/ep_held3 23000–23299 (never run before), paired across arms.
* Metrics: independently correct solves (accepted ∧ exact) overall and at ≤ 500 / 1k / 2k / 4k queries; wrong machines among
  accepted (numerator / denominator, Wilson 95 % interval); abstentions; queries; CPU; out-of-alphabet scope cases flagged.
* **Rule G (pre-registered):** the learned advantage is RETAINED iff Learned's solves exceed Hand's and Shuffled's with an
  exact one-sided paired sign test p < 0.05 against each, and its false acceptance among accepted is ≤ the lower of the two
  + 1.0 percentage point. "Failure information matters" is supported iff the Learned − Shuffled difference is significant
  (p < 0.05). Similar small error counts are not called equivalent reliability; intervals are reported.
* A positive result supports learned control of hypothesis-space growth; it does not show invention of a learning algorithm.

### 0.3 Part S — schema contract and mapping repair (development, then confirmation)
**Engineering changes (Claude) vs NEXUS behaviour.** The contract layer, the mapping-candidate generator and the corrected
human helper are engineering changes. What NEXUS *learns* per project: which fields each event kind requires (from build
data), which mapping explains a schema change (from incident records + charged oracle queries), and the lifecycle machine.

* **Runtime field contract** (`sc_contract`): inferred at build from the visible build stream and the accepted machine — a
  field is REQUIRED for an event kind iff the machine reads it on that kind (register update using x, or a value source) and
  it was present and numeric on every build event of that kind; NULLABLE if build events of that kind legitimately lack it;
  otherwise not needed. Each runtime event gets an explicit field-access outcome: `PRESENT_VALID`, `LEGITIMATELY_MISSING`
  (not required / nullable under the contract) or `SCHEMA_MISMATCH` (required but absent or non-numeric). A mismatch never
  becomes a number: the event yields an explicit unresolved row, the machine state is not advanced, and an incident is
  recorded (raw input, expected field, observed fields, event kind, mapping version, dependent registers/transitions).
  Detection uses the contract, not the machine's output labels.
* **Mapping repair** (`sc_mapping`): candidate mappings = every numeric top-level field or nested path observed on the
  incident records (no field name, project, domain or old→new pair is hard-coded); evaluated by presence, type, behavioural
  consistency with the oracle-labelled incident archive, then **distinguishing membership queries** (declared oracle API,
  charged) when several fit; if still ambiguous, or the budget is spent → explicit abstain / escalation. A proposed mapping is
  accepted only if the lifecycle program read through it passes the bounded acceptance check on new-schema events (delayed
  effects, loaded registers, boundary draws), mixed old→new histories pass, the old-schema behaviour is unchanged, and the
  platform's independent reconciliation of the replayed tick passes. Mappings are versioned by schema signature (an event
  is read through the version whose field set it carries), so old and new records stay interpretable in replay. If no
  mapping explains the archive, the lifecycle is relearned on the mapped archive (same learner, same fallback).
* **Platform copy** (`sc_platform`): ba platform + the contract alarm + the corrected **simulated human repair** (privileged:
  the reference normalisation; counts as human assistance; never visible to NEXUS) + dev-only conditions. Outcome fields per
  (project, arm): `wrong_machine_deployed` (wrong rows in ticks served by the arm's own programs), `schema_fault_detected` /
  detection tick / `schema_fault_missed`, `unresolved_escalations`, `human_repair_failed` (wrong rows in ticks served by the
  human patch), `data_ok`, `incorrect_healthy_claim` (claims healthy ∧ data wrong). The ba X6 scorecard stays unchanged.
* **Dev conditions (known, never called unseen):** X6 (value field renamed), X6P (moved to a nested path), X6D (renamed +
  an exact-copy decoy field: ambiguous on natural data), X6M (gradual migration: old and new schema mixed), LM (legitimately
  valueless kinds omit the field from the start), plus X3 / X5; split `sc_dev` seeds 13301–13348.
* **Dev ablation (Part S5):** A SchemaRepair_Learned, B SchemaRepair_Hand, C SchemaRepair_Shuffled, D NoMapping_Learned
  (same detection + acceptance, mapping repair disabled); same platform, fallback, budgets and paired schedules; each
  solution's source (growth learner / full-space fallback / mapping repair / human) reported.

### 0.4 Freeze, validation, confirmation (fresh instances of KNOWN classes X3, X5, X6)
* NEXUS_Confirmed = the dev-chosen SchemaRepair arm (A unless the dev ablation shows A is worse than B or C on dev; the
  choice and reasons are written down before the freeze). Comparators: NEXUS_U5, Fixed_Policy, Conventional, on the same
  sc platform (with the corrected human helper).
* **Validation gate** (sc/val 13361–13368: X6 ×4 one per domain, X3 ×2, X5 ×2): PASSED iff NEXUS_Confirmed is independently
  correct (data correct, 0 human repairs) on 8/8 with 0 incorrect healthy claims. One disclosed revision is allowed
  (diagnosed on dev only) followed by fresh sc/val_b with the same gate; otherwise the confirmation is not run.
* **Confirmation** (sc/test 13381–13396: fault = (X6, X3, X6, X5)[i // 4], domains balanced; sealed blobs + committed
  manifest; one shot). **Full-system criterion: 16/16 independently correct, 0 silent (incorrect healthy claims), 0 human
  repairs, crash recovery identical where injected.** If missed, the verdict stays negative and partial improvements are
  reported per outcome field.
