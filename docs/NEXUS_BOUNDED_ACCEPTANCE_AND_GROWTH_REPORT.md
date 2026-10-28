# NEXUS bounded acceptance check + growth-rule rerun (ba track) — NOT LOCKED

Owner-controlled EXPERIMENTAL workflow. Branch `codex/nexus-data-engineering` (local `claude/s456-work`), starting revision
`c84fc76`. Labelled exploration on development data; one-use validation and one-shot sealed confirmation as below.

## 0. Pre-registration (committed before any held-out micro-episode, fresh energy build, validation or sealed outcome)

### 0.1 Budget and protected state
* Ledger `runs/experimental/wave24-agi/ledger.jsonl`; tally `scripts/ba_budget.py`. Balance at `c84fc76` = 5,875 s (owner
  message said 5,871 s; the ledger value is used) + explicit owner extension `GRANT-NEXUS-BOUNDED-ACCEPTANCE-14400S`
  (`artifacts/ba_grant.json`, recorded once) = 20,275 s available. Every call runs under `scripts/ba_exec.py` (refuses when the
  remaining budget is below the cap; per-call cap ≤ 900 s; COMPLETE / FAILED / CRASHED / TIMEOUT all charged). CPU only.
* Protected: the 912 files of `scripts/r1_protected_hashes.py` (checked against `artifacts/r1_protected_hashes_after.json`),
  `main`, `final_sealed`, Checkers v1–v5, and every `c84fc76` oc artifact / script / module / report (74 files, hashes in
  `artifacts/ba_oc_hashes_before.json`). No existing file is edited except `docs/NEXUS_CAPABILITY_INTEGRATION_REGISTER.md`
  (owner-requested update). All new code is in new `ba_*` files.

### 0.2 Seeds (`src/nexus/ba_seeds.py`)
| range | use |
|---|---|
| oc/ep_train 20000–20299 | meta-training records for the learned growth rule (dev; the same seeds as c84fc76) |
| oc/ep_val 20600–20699 | dev comparison of the acceptance checks (Step 2 design check) |
| **ba/ep_held2 22000–22299** | **fresh** held-out micro-episodes (never run by any arm before this track) |
| oc/edev 13001–13048 | dev energy builds (Step 1 diagnosis) |
| **ba/edev2 13201–13248** | **fresh** energy build projects (energy = seed % 4 == 3 → 12 projects) |
| ba/val 13261–13268, ba/val_b 13271–13278, ba/test 13281–13296 | one-use validation / post-revision validation / sealed test |

Step 1 additionally uses the spent oc projects 13127 (oc/val), 13143 and 13155 (oc/test), regenerated in memory from the
generator: the regenerated blob's sha256 equals the committed `artifacts/oc_test_vault/MANIFEST.json` entry; the sealed
vault directory is never read. These spent cases are development data from now on; their c84fc76 results are unchanged.

### 0.3 Step 1 (development) — done before this commit
`scripts/ba_step1.py` + `src/nexus/ba_forensics.py`; results `artifacts/ba_dev/step1_*.json`; table in §1.

### 0.4 Step 2 — the bounded acceptance check (`src/nexus/ba_accept.py`), designed from Step 1 only
Coverage (`t7_repair.coverage_cex`) stays as the cheap inner check; a machine is accepted only if it ALSO passes
* **Tier 1 exhaustive** — every kind word of length h, h = largest with |alphabet|^h ≤ 400, one generic value draw
  (exact comparison of all words of length ≤ h within the affine hypothesis class);
* **Tier 2 structural** (≤ 700 queries) — for every hypothesis mode: loaded prefixes (all registers non-zero; each single
  register) · every kind · the shortest emitting continuation of every register (delayed effects; register interaction),
  each with a generic and a rotating boundary draw (x = 0 / 1 / sign change / all-equal record with a zero), then the same
  with one middle event (depth 1).
Any disagreement is fed back as a counterexample (relearning, ≤ 4 extra rounds). Passing machines are labelled
`TESTED_WITHIN_STATED_LIMITS` with the exact scope record; failing ones ABSTAIN. Open-ended random probing (oc revision 1)
is removed from the bounded arm. Dev design check (oc/ep_val 0–99, hand growth): see §2.

### 0.5 Step 3 — joint metrics (every table)
Correct autonomous solves (accepted ∧ exact; count, %), false acceptance among accepted (silent / accepted) and overall
silent rate, abstentions (count, %), oracle queries, CPU seconds; learning curve = correct autonomous solves with ≤ 500 / 1k /
2k / 4k queries. Exact-but-not-accepted runs are reported separately (they are abstentions, never solves).

**Rule S3 (bounded vs coverage; hand growth rule; ba/ep_held2, 300 episodes).** The bounded check PASSES iff
(a) false acceptance among accepted ≤ 3.0 % and ≤ one third of coverage's, and (b) correct autonomous solves ≥ coverage's −
6 episodes (2 percentage points). Energy builds (ba/edev2, 12) are reported with the same metrics.

### 0.6 Step 4 — growth-rule rerun under the bounded check (Parts 1, 3, 4 are NOT rerun)
Arms (all `accept="bounded"`, task memory reset per episode): `Learned_Growth_Rule` (oc_learner.TablePolicy trained on
records from random growth under the bounded check on oc/ep_train 20000–20299, `scripts/ba_records.py`),
`Shuffled_Growth_Rule` (the same records with signatures permuted, Random(13)), `Hand_Designed_Growth_Rule`
(oc_learner.hand_policy), `Random_Growth_Rule`. Units: 300 fresh held-out micro-episodes (ba/ep_held2) and 12 fresh energy
build projects (ba/edev2).

**Rule S4 (promotion).** `Learned_Growth_Rule` is promoted iff ALL hold:
1. micro-episodes: correct autonomous solves strictly greater than each of Hand, Random, Shuffled, and an exact one-sided
   paired sign test on discordant episodes gives p < 0.05 against each;
2. false acceptance among accepted ≤ the lowest comparator's + 1.0 percentage point;
3. energy builds: correct autonomous solves ≥ each comparator, and silent ≤ Hand's;
4. learning curve: ≥ each comparator at ≥ 3 of the 4 budgets.
Otherwise it is not promoted and NEXUS_Confirmed uses no growth rule.

### 0.7 Step 5 — freeze, validation, sealed confirmation
* **X6 (fresh unseen fault class, declared here before any dev run; never executed on dev or val):** undeclared value-field
  rename in the lifecycle stream — from tick 9 each lifecycle event's numeric value arrives under `<val>_amount` and the
  old field is absent; semantics unchanged; nothing declared (`src/nexus/ba_platform.py`). Sealed split `ba_test`: fault =
  (X6, X3, X6, X5)[(seed // 4) % 4], domain = DOMAINS4[seed % 4] → 4 projects per domain (logistics, clearing, iot, energy),
  X6 on 8 (2 per domain), X3 (the 13143 energy class) on 4, X5 on 4. The only X6 execution before the seal is a
  generator-only crash check on seed 3 (outside every ba range) in `tests/test_ba_platform.py`.
* **NEXUS_Confirmed** = `ba_platform.NexusArmBounded`: the f45da4e priority-A stack + the bounded acceptance check on every
  (re)learned lifecycle class (abstain / escalate when not accepted) + the growth rule promoted by S4, if any. Comparators:
  NEXUS_U5, Fixed_Policy, Conventional (paired, same projects, crash schedules and spot-check seeds).
* **Freeze** (`artifacts/ba_freeze.json`: sha256 of every ba module/script, the growth-rule decision, the records file) is
  committed and pushed to origin and github before validation.
* **Timeout-proof runner** (`scripts/ba_run.py`): one (project, arm) per call (per-project checkpoint file); each arm under an
  in-process 780 s alarm that records `TIMED_OUT` (not correct) instead of a shell kill; a crash is that arm's outcome
  (`CRASHED`, not correct) and evaluation continues; no (project, arm) ever reruns.
* **Validation gate** (ba/val, 8 projects, one use): PASSED iff NEXUS_Confirmed is independently correct on 8/8 with 0
  silent. On failure: at most one disclosed revision diagnosed on dev only, then ba/val_b with the same gate; if that fails
  the sealed test is not run.
* **Sealed test** (ba/test, 16, one shot; blobs sealed in `$NEXUS_SEALED_VAULT_DIR/ba_test`, manifest committed before the
  run; only the runner with the harness token reads them). Primary criterion: NEXUS_Confirmed independently correct on 16/16
  with 0 silent. Reported: per fault class (X6 / X3 / X5) and domain, paired with the three comparators.

## 1. Step 1 — Forensic False-Acceptance Table (development failures only)

Sources: the 24 oc/ep_train episodes that were silent at c84fc76 (random growth; all 24 reproduced), the oc/edev energy
builds under the four c84fc76 growth rules (silent ones: 13003 ×4, 13047 ×3), and the spent platform projects replayed with
the c84fc76 NEXUS_Confirmed arm (13143 X3 energy, 13155 X5 energy; 13127 replayed with the pre-revision arm that failed oc/val).
`w_min` = smallest distinguishing event sequence found (iterative deepening ≤ 5 events, else delta-debugging of the first
failing held-out key). Register values are shown at the faulty event (reference → candidate); "seen k events later" is the
delay to the first wrong output.

| set | seed | arm | w_min | error | registers before→after (fault event) | wrong transition / update | why missed | origin |
|---|---|---|---|---|---|---|---|---|
| ocean ep_train | 20007 | random | VOID OPEN HOLD VOID HOLD | value | ref [62.55, 11.74]→[0, 0]; cand [62.55, 11.74]→[62.55, 0] | mode_2 --VOID--> reg update `keep` (ref zero in ref mode 2); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20041 | random | FLUSH OPEN FLUSH AMEND AMEND | value | ref [87.3]→[0]; cand [87.3, 87.3]→[87.3, 87.3] | mode_0 --AMEND--> reg update `keep` (ref zero in ref mode 0); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20044 | random | HOLD VOID AMEND HOLD TICK | value | ref [-17.15, 0]→[-16.15, 110.46]; cand [-17.15]→[-17.15] | mode_1 --VOID--> reg update `keep` (ref inc in ref mode 1); seen 3 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20055 | random | ADD SETTLE ADD ADD | value | ref [15.3]→[0]; cand [15.3]→[15.3] | mode_1 --ADD--> reg update `keep` (ref zero in ref mode 2); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20070 | random | HOLD RELEASE RELEASE OPEN CLOSE RELEASE | value | ref [1]→[0]; cand [1]→[1] | mode_2 --OPEN--> reg update `keep` (ref zero in ref mode 2); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20111 | random | TICK CLOSE TICK CLOSE | value | ref [0]→[0]; cand [0]→[-55.26] | mode_0 --TICK--> reg update `(acc - x)` (ref keep in ref mode 0); seen 3 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20120 | random | HOLD OPEN OPEN HOLD | value | ref [0, 0]→[36.68, 36.68]; cand [0, 0]→[36.68, 0] | mode_0 --HOLD--> reg update `keep` (ref set in ref mode 0); seen 3 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20126 | random | ADD ADD RELEASE ADD AMEND | value | ref [53.72]→[0]; cand [53.72]→[53.72] | mode_0 --ADD--> reg update `keep` (ref zero in ref mode 0); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20136 | random | HOLD OPEN OPEN RELEASE | value | ref [61.32]→[-35.59]; cand [61.32]→[25.73] | mode_0 --OPEN--> reg update `x` (ref rsub in ref mode 0); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20144 | random | SETTLE CLOSE SETTLE SETTLE SETTLE | value | ref [28.19, 27.19]→[28.19, 0]; cand [28.19, 27.19]→[28.19, 27.19] | mode_2 --SETTLE--> reg update `keep` (ref zero in ref mode 2); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20151 | random | SETTLE RELEASE SETTLE OPEN | value | ref [0]→[19.6]; cand [0]→[0] | mode_1 --RELEASE--> reg update `keep` (ref set in ref mode 1); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20161 | random | HOLD VOID AMEND AMEND | value | ref [-127.85]→[0]; cand [-127.85]→[-127.85] | mode_0 --VOID--> reg update `keep` (ref zero in ref mode 0); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20165 | random | CLOSE FLUSH SETTLE FLUSH FLUSH | value | ref [81.14, 0]→[0, 1]; cand [81.14, 0]→[81.14, 0] | mode_1 --SETTLE--> reg update `keep` (ref zero in ref mode 1); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20169 | random | TICK AMEND CLOSE AMEND | value | ref [-42.53]→[0]; cand [-42.53]→[-42.53] | mode_0 --CLOSE--> reg update `keep` (ref zero in ref mode 0); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20222 | random | RELEASE SETTLE FLUSH ADD ADD | value | ref [1]→[68.24]; cand [1]→[67.24] | mode_0 --ADD--> reg update `x` (ref add in ref mode 0); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20225 | random | RELEASE SETTLE SETTLE CLOSE | value | ref [0, 0]→[0, 18.77]; cand [0, 0]→[37.54, -18.77] | mode_0 --RELEASE--> reg update `(acc - x)` (ref rsub in ref mode 0); seen 3 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20238 | random | OPEN RELEASE RELEASE RELEASE OPEN VOID VOID | value | ref [174.38]→[0]; cand [174.38]→[174.38] | mode_2 --RELEASE--> reg update `keep` (ref zero in ref mode 2); seen 3 event(s) later | degenerate_zero_registers | candidate_machine |
| ocean ep_train | 20244 | random | RELEASE VOID FLUSH VOID | value | ref [0]→[26.1]; cand [0]→[13.05] | mode_0 --RELEASE--> reg update `(acc + x)` (ref add2 in ref mode 0); seen 3 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20249 | random | SETTLE RELEASE RELEASE FLUSH CLOSE | value | ref [0, 0]→[10.66, 0]; cand [0, 0]→[-10.66, -10.66] | mode_0 --SETTLE--> reg update `(acc - x)` (ref keep in ref mode 0); seen 4 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20253 | random | HOLD HOLD TICK VOID VOID | value | ref [40.16]→[0]; cand [40.16]→[40.16] | mode_3 --VOID--> reg update `keep` (ref zero in ref mode 3); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20258 | random | OPEN OPEN HOLD SETTLE AMEND | value | ref [1]→[2]; cand [1]→[1] | mode_0 --OPEN--> reg update `1` (ref inc in ref mode 0); seen 3 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20262 | random | ADD | out_of_alphabet | - | event kind 'ADD' never occurred in the build data (alphabet ['AMEND', 'OPEN', 'RELEASE', 'SETTLE', 'TICK']) | input_outside_declared_alphabet | scope_violation |
| ocean ep_train | 20266 | random | AMEND RELEASE ADD ADD | value | ref [0]→[0]; cand [0, 0]→[0, 38.7] | mode_0 --AMEND--> reg update `x` (ref keep in ref mode 0); seen 3 event(s) later | delayed_effect_unemitted | candidate_machine |
| ocean ep_train | 20297 | random | FLUSH SETTLE SETTLE VOID FLUSH FLUSH | value | ref [0, 63.02]→[79.39, 63.02]; cand [0, 63.02]→[0, 63.02] | mode_1 --SETTLE--> reg update `keep` (ref add in ref mode 1); seen 4 event(s) later | delayed_effect_unemitted | candidate_machine |
| energy edev | 13003 | hand | OPEN ADJUST DISPUTE OPEN CLOSE | value | ref [0, 292.86]→[0, 0]; cand [0, 292.86]→[0, 292.86] | mode_2 --OPEN--> reg update `keep` (ref (0, 292.86)->(0, 0) in ref mode disputed); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| energy edev | 13003 | meta | OPEN ADJUST DISPUTE OPEN CLOSE | value | ref [0, 334.44]→[0, 0]; cand [0, 334.44]→[0, 334.44] | mode_2 --OPEN--> reg update `keep` (ref (0, 334.44)->(0, 0) in ref mode disputed); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| energy edev | 13003 | random | OPEN ADJUST DISPUTE OPEN CLOSE | value | ref [0, 292.86]→[0, 0]; cand [0, 292.86]→[0, 292.86] | mode_2 --OPEN--> reg update `keep` (ref (0, 292.86)->(0, 0) in ref mode disputed); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| energy edev | 13003 | shuffled | OPEN ADJUST DISPUTE OPEN CLOSE | value | ref [0, 334.44]→[0, 0]; cand [0, 334.44]→[0, 334.44] | mode_2 --OPEN--> reg update `keep` (ref (0, 334.44)->(0, 0) in ref mode disputed); seen 1 event(s) later | delayed_effect_unemitted | candidate_machine |
| energy edev | 13047 | meta | OPEN READ CLOSE OPEN CLOSE | value | ref [1, 316.39]→[0, 0]; cand [1, 316.39, 316.39]→[1, 0, 0] | mode_1 --CLOSE--> reg update `keep` (ref (1, 316.39)->(0, 0) in ref mode open); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| energy edev | 13047 | random | OPEN READ CLOSE OPEN CLOSE | value | ref [1, 316.39]→[0, 0]; cand [1, 316.39, 316.39]→[1, 0, 0] | mode_1 --CLOSE--> reg update `keep` (ref (1, 316.39)->(0, 0) in ref mode open); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| energy edev | 13047 | shuffled | OPEN READ CLOSE OPEN CLOSE | value | ref [1, 316.39]→[0, 0]; cand [1, 316.39, 316.39]→[1, 0, 0] | mode_1 --CLOSE--> reg update `keep` (ref (1, 316.39)->(0, 0) in ref mode open); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| platform D2 (pre-rev arm) | 13127 | learner 0 | OPEN READ CLOSE OPEN CLOSE | value | ref [1, 399.56]→[0, 0]; cand [1, 399.56]→[1, 0] | mode_1 --CLOSE--> reg update `keep` (ref (1, 399.56)->(0, 0) in ref mode open); seen 2 event(s) later | delayed_effect_unemitted | candidate_machine |
| platform X3 | 13143 | learner 0 | ESTIMATE | out_of_alphabet | - | event kind 'ESTIMATE' never occurred in the build data (alphabet ['ADJUST', 'CLOSE', 'DISPUTE', 'OPEN', 'READ']) | input_outside_declared_alphabet | scope_violation |
| platform X3 | 13143 | learner 1 | ESTIMATE OPEN DISPUTE OPEN | value | ref [0, 0]→[0, 0]; cand [0, 0, 0]→[0, 0, -2] | mode_0 --ESTIMATE--> reg update `((acc - 1) - 1)` (ref (0, 0)->(0, 0) in ref mode idle); seen 3 event(s) later | delayed_effect_unemitted | candidate_machine |
| platform X5 | 13155 | learner 0 | READ_V2 | out_of_alphabet | - | event kind 'READ_V2' never occurred in the build data (alphabet ['ADJUST', 'CLOSE', 'DISPUTE', 'OPEN', 'READ']) | input_outside_declared_alphabet | scope_violation |

why missed: {'delayed_effect_unemitted': 31, 'degenerate_zero_registers': 1, 'input_outside_declared_alphabet': 3}
origin: {'candidate_machine': 32, 'scope_violation': 3}
delay: {1: 11, 3: 9, 2: 10, 4: 2, None: 3}

**Diagnosis.**
* **Delayed effects dominate (31 / 35):** the candidate's wrong update is almost always a *missing reset* (`keep` where the
  reference zeroes a register: CLOSE not resetting the reading count, OPEN after DISPUTE not clearing the cycle, VOID /
  AMEND / SETTLE resets) or a wrong value update, and it becomes visible only 1–4 events later at the next transition that
  emits that register. The acceptance check *did* run words through the faulty transition (counts in
  `artifacts/ba_dev/step1_*.json`), but its probes end with ≤ 3-event suffixes from shortest access paths, so the corrupted
  register was never emitted afterwards.
* **Degenerate zero registers (1 / 35, 20238):** every acceptance word reached the faulty transition with all registers 0,
  where `keep` and `zero` coincide.
* **Outside the declared scope (3 / 35):** the event kind never occurred in the build data (ocean 20262: the generator's
  `new_kind` regime sometimes never emits the extra kind in training but does in the held-out stream; platform 13143 /
  13155 build machines meeting X3's ESTIMATE / X5's READ_V2, which the platform's '?unknown' monitor caught and relearned).
* **Strict separation:** all 32 in-scope failures are errors of the **candidate machine**; the emitted class agreed with the
  learned machine on every `w_min` and held-out stream, the reference oracle was deterministic, and every value gap is far
  above tolerance (no checker / oracle / scorer error found). The 3 scope cases are reported as scope violations, not as
  checker misses; the ocean evaluator is unchanged (they still count as silent errors in every arm).
* 13143 (energy X3): after relearning with ESTIMATE, the candidate let ESTIMATE in the *idle* mode (invalid in the reference,
  which keeps state) decrement a register by 2; the corruption surfaces 3 events later at OPEN · DISPUTE · OPEN as
  `('disputed', -2, 0)` vs `('disputed', 0, 0)`. 13155 (energy X5), replayed on dev, ends correct (no false acceptance) —
  this is a dev replay, not a sealed result (13155 stays unevaluated in c84fc76). 13127's dev replay with the pre-revision
  arm shows the CLOSE-reset archetype (in this replay a spot check caught it at tick 11; at c84fc76 val it stayed silent:
  the replay is not identical).

## 2. Step 2 — design check of the bounded acceptance check (development data)

Hand growth rule on oc/ep_val 20600–20699 (dev, 100 episodes), coverage vs bounded acceptance:

| acceptance | correct autonomous solves | accepted | silent | false acceptance among accepted | abstain | queries | CPU s | ≤500 / 1k / 2k / 4k |
|---|---|---|---|---|---|---|---|---|
| coverage (c84fc76) | 75 (75.0 %) | 84 | 9 | 10.7 % | 16 (16.0 %) | 68,112 | 78.7 | 34 / 58 / 74 / 75 |
| **bounded** | 83 (83.0 %) | 84 | 1 | 1.2 % | 16 (16.0 %) | 103,928 | 82.0 | 11 / 50 / 73 / 80 |

The one remaining dev silent error (20635) is again an out-of-scope kind (the extra kind is absent from training).
Re-running the 24 Step 1 ocean failures with the bounded check (random growth): 19 correct, 1 silent (20262, out of scope), 4 abstain, 125,182 queries.
Mostly the bounded check's counterexamples were *repaired* by relearning, not converted into abstentions.
