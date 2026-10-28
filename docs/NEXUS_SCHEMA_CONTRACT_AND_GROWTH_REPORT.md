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

## 1. Part G — learned vs hand vs shuffled vs random growth, fallback disabled (fresh sc/ep_held3, 300 paired episodes)

Raw rows `artifacts/sc_dev/eps_<arm>_ep_held3_0.jsonl`; analysis `artifacts/sc_partg.json` (`scripts/sc_partg.py`). Same bounded
acceptance check and update language as ba; the growth learner alone (no full-space fallback); task memory reset per episode.

| growth rule (fallback disabled) | correct (95 % CI) | ≤500 / 1k / 2k / 4k | wrong among accepted (95 % CI) | abstain | queries | CPU s |
|---|---|---|---|---|---|---|
| Learned | 278/300 = 92.7 % (89.1–95.1) | 39 / 143 / 227 / 262 | 0/278 = 0.0 % (-0.0–1.4); 0 out of scope | 22 | 409,193 | 912.2 |
| Hand | 256/300 = 85.3 % (80.9–88.9) | 36 / 141 / 216 / 245 | 0/256 = 0.0 % (0.0–1.5); 0 out of scope | 44 | 365,602 | 501.4 |
| Shuffled | 248/300 = 82.7 % (78.0–86.5) | 39 / 141 / 218 / 243 | 0/248 = 0.0 % (-0.0–1.5); 0 out of scope | 52 | 552,404 | 1336.8 |
| Random | 226/300 = 75.3 % (70.2–79.9) | 37 / 128 / 194 / 212 | 0/226 = 0.0 % (0.0–1.7); 0 out of scope | 74 | 363,199 | 954.7 |

Paired exact one-sided sign tests (Learned vs X, discordant episodes): vs Hand 23 : 1 (p = 1.5e-6), vs Shuffled 30 : 0
(p = 9.3e-10), vs Random 53 : 1 (p = 3.1e-15).

* **Rule G — advantage RETAINED; failure information matters.** The learned rule solves 278/300 vs 256 (hand), 248
  (shuffled), 226 (random); removing the signature → action pairing (shuffled) removes the advantage (30 : 0 discordant).
  Same direction as ba (265 / 248 / 241 on ba/ep_held2; that result is unchanged).
* **Wrong machines among accepted: 0/278, 0/256, 0/248, 0/226** on this fresh set (95 % upper bounds 1.4–1.7 %). This is
  not a claim of equal or perfect reliability: the ba held-out set had 2 in-scope false acceptances per arm, and no
  out-of-alphabet episode occurred here.
* Costs: Learned used 409k queries and 912 CPU s vs Hand 366k / 501 s; Shuffled 552k / 1,337 s. Source-policy learning
  (fully loaded, ba): 300 random-growth dev episodes, 1,061.5 CPU s, 458,869 queries, 746 records.
* Scope: this supports learned control of hypothesis-space growth from failure signatures. It does not show invention of a
  new learning algorithm.

## 2. Part S — schema contract, mapping repair, corrected helper (development)

**Helper validation, independent of NEXUS** (`artifacts/sc_dev/helper_check.json`): the corrected simulated human repair
reproduces the oracle on all 48 sc_dev projects (0 wrong rows; also when resumed from a tick-8 checkpoint), including
mixed old / new records (X6M). The ba helper (DocMachine) was wrong on every X6-family condition **and on X5** (389 rows on 4
X5 projects) — so earlier X5 escalations could not have ended correct either; the ba / oc scorecards stay unchanged.

**Dev ablation** (14 sc_dev projects: X6 ×4, X6P ×2, X6D ×2, X6M ×2, LM ×2, X3, X5; `artifacts/sc_ablation.json`; identical
platform, acceptance check, fallback, budgets and paired schedules; known development conditions, never called unseen):

| arm | indep. correct | data correct | incorrect healthy claim | wrong machine deployed | schema fault detected | escalations (human) | human repair failed | crash identical | abstain | sources | mq | CPU s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SchemaRepair_Learned | 13/14 | 13 | 0 | 0 | 10/10 | 0 | 0 | 13/13 | 1 | {'build:growth': 13, 'mapping:MAPPING_ACCEPTED': 10, 'relearn:growth': 1} | 20,600 | 309.0 |
| SchemaRepair_Hand | 12/14 | 12 | 0 | 0 | 9/9 | 0 | 0 | 12/12 | 2 | {'build:growth': 9, 'mapping:MAPPING_ACCEPTED': 9, 'build:full_space': 3, 'relearn:growth': 1} | 19,108 | 325.7 |
| SchemaRepair_Shuffled | 12/14 | 12 | 0 | 0 | 9/9 | 0 | 0 | 12/12 | 2 | {'build:growth': 11, 'mapping:MAPPING_ACCEPTED': 9, 'build:full_space': 1, 'relearn:growth': 1} | 20,859 | 350.7 |
| NoMapping_Learned | 3/14 | 11 | 0 | 0 | 8/8 | 8 | 0 | 11/11 | 1 | {'build:growth': 11, 'mapping:DISABLED (relearn only)': 8, 'relearn:growth': 1} | 19,453 | 281.3 |
| Fixed_Policy | 2/14 | 3 | 11 | 11 | 0/10 | 7 | 0 | 14/14 | 0 | {} | 0 | 0.1 |

* Mapping repair is what fixes X6: A/B/C detect every X6-family fault at tick 9 and repair it themselves (10/10 for A);
  D (same detection, mapping repair disabled → relearn only) cannot fit a machine to the mixed archive and escalates every
  X6-family case (data correct only through the corrected human helper; 0 independent).
* Ambiguity: with the exact-copy decoy (X6D) and the nested path (X6P), *all* numeric candidates (incl. distractors and the
  sequence field) were consistent with the incident tick's labels; one distinguishing membership query separated the true
  field (13308: `legacy_reading` vs `reading_amount`).
* Legitimately missing values (LM): no false schema alarm; nullable kinds handled. This needed an engineering change: the
  u5 learner drops a field that is not numeric on every record, so the schema arm gives the learner a *learning view*
  (explicit 0 where a numeric field is absent / None — at build, or on a relearn only where the prior contract marks it
  nullable; structured values left out); the runtime contract still sees the original records.
* Growth rule inside the system: 13311 (energy X6D) was built only by the learned rule (hand / shuffled: build abstained);
  13327 (energy) abstained at build in every arm — the full-space learner itself fails register search there (learner
  limitation, not a false acceptance). NoMapping crashed on X6P before a fix (nested dict values in u5 field discovery);
  fixed for every arm before the freeze and re-checked (`artifacts/sc_dev/ablation_fix1`).
* Freeze `0c4d908`: NEXUS_Confirmed = SchemaRepair_Learned (pre-registered default; A 13/14 ≥ B, C 12/14).

## 3. One-use validation (sc/val 13361–13368) — gate PASSED

| arm | evaluated | independently correct | silent | data correct | human repairs | wrong machine deployed | schema fault detected | schema missed | human repair failed | crash identical | by fault | by domain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NEXUS_Confirmed | 8/8 | 8 | 0 | 8 | 0 | 0 | 4/4 | 0 | 0 | 8/8 | {'X3': '2/2', 'X5': '2/2', 'X6': '4/4'} | {'clearing': '2/2', 'energy': '2/2', 'iot': '2/2', 'logistics': '2/2'} |
| NEXUS_U5 | 8/8 | 1 | 5 | 2 | 5 | 5 | 0/4 | 0 | 0 | 7/7 | {'X3': '1/2', 'X5': '0/2', 'X6': '0/4'} | {'clearing': '1/2', 'energy': '0/2', 'iot': '0/2', 'logistics': '0/2'} |
| Fixed_Policy | 8/8 | 0 | 5 | 3 | 6 | 5 | 0/4 | 1 | 0 | 8/8 | {'X3': '0/2', 'X5': '0/2', 'X6': '0/4'} | {'clearing': '0/2', 'energy': '0/2', 'iot': '0/2', 'logistics': '0/2'} |
| Conventional | 8/8 | 0 | 8 | 0 | 0 | 8 | 0/4 | 4 | 0 | 8/8 | {'X3': '0/2', 'X5': '0/2', 'X6': '0/4'} | {'clearing': '0/2', 'energy': '0/2', 'iot': '0/2', 'logistics': '0/2'} |

## 4. Confirmation on fresh instances of KNOWN classes (sc/test 13381–13396; manifest `46c9007`) — full-system criterion PASSED

All 16 × 4 (project, arm) runs evaluated; 0 timeouts, 0 crashes, 0 interruptions, no re-attempt.

| arm | evaluated | independently correct | silent | data correct | human repairs | wrong machine deployed | schema fault detected | schema missed | human repair failed | crash identical | by fault | by domain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NEXUS_Confirmed | 16/16 | 16 | 0 | 16 | 0 | 0 | 8/8 | 0 | 0 | 16/16 | {'X3': '4/4', 'X5': '4/4', 'X6': '8/8'} | {'clearing': '4/4', 'energy': '4/4', 'iot': '4/4', 'logistics': '4/4'} |
| NEXUS_U5 | 16/16 | 6 | 8 | 8 | 6 | 8 | 0/8 | 3 | 0 | 16/16 | {'X3': '3/4', 'X5': '3/4', 'X6': '0/8'} | {'clearing': '2/4', 'energy': '0/4', 'iot': '2/4', 'logistics': '2/4'} |
| Fixed_Policy | 16/16 | 0 | 14 | 2 | 13 | 14 | 0/8 | 1 | 0 | 16/16 | {'X3': '0/4', 'X5': '0/4', 'X6': '0/8'} | {'clearing': '0/4', 'energy': '0/4', 'iot': '0/4', 'logistics': '0/4'} |
| Conventional | 16/16 | 0 | 16 | 0 | 0 | 16 | 0/8 | 8 | 0 | 16/16 | {'X3': '0/4', 'X5': '0/4', 'X6': '0/8'} | {'clearing': '0/4', 'energy': '0/4', 'iot': '0/4', 'logistics': '0/4'} |

| seed | domain | fault | NEXUS_Confirmed | NEXUS_U5 | Fixed_Policy | Conventional |
|---|---|---|---|---|---|---|
| 13381 | clearing | X6 | CORRECT | SILENT | SILENT | SILENT |
| 13382 | iot | X6 | CORRECT | COMPLETED/human1/data_ok | SILENT | SILENT |
| 13383 | energy | X6 | CORRECT | SILENT | SILENT | SILENT |
| 13384 | logistics | X6 | CORRECT | SILENT | SILENT | SILENT |
| 13385 | clearing | X3 | CORRECT | CORRECT | SILENT | SILENT |
| 13386 | iot | X3 | CORRECT | CORRECT | SILENT | SILENT |
| 13387 | energy | X3 | CORRECT | COMPLETED/human1/data_ok | SILENT | SILENT |
| 13388 | logistics | X3 | CORRECT | CORRECT | SILENT | SILENT |
| 13389 | clearing | X6 | CORRECT | SILENT | SILENT | SILENT |
| 13390 | iot | X6 | CORRECT | SILENT | COMPLETED/human1/data_ok | SILENT |
| 13391 | energy | X6 | CORRECT | SILENT | SILENT | SILENT |
| 13392 | logistics | X6 | CORRECT | SILENT | SILENT | SILENT |
| 13393 | clearing | X5 | CORRECT | CORRECT | COMPLETED/human1/data_ok | SILENT |
| 13394 | iot | X5 | CORRECT | CORRECT | SILENT | SILENT |
| 13395 | energy | X5 | CORRECT | SILENT | SILENT | SILENT |
| 13396 | logistics | X5 | CORRECT | CORRECT | SILENT | SILENT |

**NEXUS_Confirmed: 16/16 independently correct, 0 silent, 0 human repairs, 0 wrong machines deployed, crash recovery
identical 16/16.** X6 8/8 — every schema change detected at tick 9 (the tick it starts) and repaired by an accepted mapping;
X3 4/4 and X5 4/4 by accepted relearns with the growth rule. This is generalisation to fresh instances of known classes,
not to an unseen fault class. The ba sealed verdict (8/16, all X6 failing) stays as recorded.

## 5. Examples generated by NEXUS (verbatim, from our result files)

Incident record + mapping for sc/test 13391 (energy, X6):
```
incident: raw {"batch": 1, "msg_type": "READ", "ref": "E39100078", "retry": 3, "ts": 9008, "value_amount": 61.67}
          expected ['value'], observed ['batch','msg_type','ref','retry','ts','value_amount'], kind READ,
          mapping_version 0, dependencies {'value': ['reg_1 update in mode_1']}
candidates ['batch', 'retry', 'ts', 'value_amount'] -> consistent ['value_amount']
mapping v1: read 'value' from 'value_amount' when 'value' absent and 'value_amount' numeric   (420 charged queries)
acceptance: TESTED_WITHIN_STATED_LIMITS - exhaustive horizon 3 (125 words), 150 structural tests, 120 mixed old->new tests
```
The deployed lifecycle program for that project (build machine, unchanged by the mapping; excerpt):
```python
        elif m == 1:
            if s == 'ADJUST':
                self.reg_1[k] = (r1 + x1)
            elif s == 'CLOSE':
                out = [('bill', r0, r1)]; self.reg_0[k] = 0; self.reg_1[k] = 0; self.mode[k] = 0
            elif s == 'DISPUTE':
                self.mode[k] = 2
            elif s == 'READ':
                self.reg_0[k] = (r0 + 1); self.reg_1[k] = (r1 + x1)
        elif m == 2:
            if s == 'OPEN':
                out = [('disputed', r0, r1)]; self.reg_0[k] = 0; self.reg_1[k] = 0
```
(`x1 = rec.get('value')` is supplied by the contract layer through mapping v1 for new-schema records. The class also reads
a distractor field `batch` for `reg_0`, whose updates never use it — harmless, but not minimal.)

## 6. Engineering changes (Claude) vs behaviour NEXUS learned

* **Engineering:** the runtime contract layer and its outcome vocabulary, the mapping-candidate generator and evaluation
  procedure, the learning view, the corrected human helper, the dev conditions, the runner and its outcome fields.
* **Learned by NEXUS per project:** the lifecycle machines (states, registers, updates), which fields each kind requires
  (from build data), which mapping explains a schema change (from incident records + oracle queries), and — across
  episodes — the growth policy (from dev experience records).

## 7. Resources and status

* sc ledger: 7,168 s (Part G 3,840; dev ablation 2,093; dev / debug / helper 230; val 295; confirmation 709). Remaining
  **4,778 s**. Confirmation target cost (NEXUS_Confirmed, 16 projects): build CPU 309 s, operate CPU 40 s, 39,413 membership
  queries, 9,056 build labels, 5,760 incident labels, 1,820 spot-check labels. Fully loaded adds the dev ablation, the
  source-policy learning (1,061.5 CPU s) and Part G.
* Protected: 912/912, 157/157 ba files, 74/74 oc files unchanged.
* Limits: X6 here is a single-field rename / nest / decoy / migration; multi-field changes give an explicit unresolved
  status (not tested); 13327-type energy builds can still abstain; the decoy case needs oracle queries; acceptance remains
  tested within stated limits.
* **Next experiment:** a genuinely unseen schema-change class (e.g. a unit-scaled or split value field) on fresh data,
  with the dev conditions above as the training set — to test whether the mapping procedure generalises beyond renames.
