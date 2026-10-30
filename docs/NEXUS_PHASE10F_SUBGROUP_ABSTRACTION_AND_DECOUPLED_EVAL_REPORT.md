# NEXUS Phase 10F — subgroup abstraction, decoupled evaluation, frozen-guidance and atomic-dedup controls (NOT LOCKED)

## Revisions and scope

| Item | Revision |
|---|---|
| Start | `343778e` |
| Commit 1: protocol, ledger, code, manifest | `3aa134d` |
| Training and freeze | `0c7d2c3` |
| `main` | `d7ac8c5`, untouched |

- **Protocol:** `docs/NEXUS_PHASE10F_PROTOCOL.md`.
- **Raw data:** `artifacts/agi10f_train/`, `artifacts/agi10f_eval/rows_c*.jsonl` and `artifacts/agi10f_eval/result.json`.
- **Logs:** `artifacts/mi_logs/a10f-*`.

**Primary question.** Can NEXUS's abstraction extract and keep a useful specific method from disagreeing experience, without
hand-fixing the dream teacher? And does that method transfer to held-out compositions once the quantity / sequence shortcut is
broken?

## Answer in one paragraph

**Abs_subgroup did recover the method that whole-group intersection destroyed.**
- In both training streams it admitted the `(unique_key, arrival_sequence)` replay macro: at step 90 in rep0, step 100 in rep1.
- Abs_current never admitted a valid one. In rep1 it admitted a `ckey`-stripped macro at step 50.
- Neither rule had a valid macro at step 50, so by the pre-registered rule Abs_subgroup is **not reliable**: verdict
  *subgroup insufficient*.

**The shortcut is gone:** 0 of 340 evaluation rows ordered the replay dedup by quantity (Phase 10E: 16 / 24 for A4_rep1), and
0 wrong.

**But held-out success is now saturated by learned guidance alone.**
- On the 22 complete held-out compositions, A2 (primitives plus `G_L0`) verifies 22 / 22 in both streams.
- The atomic-dedup baseline with learned guidance (Bl) also verifies 22 / 22.
- So the macro adds no completions beyond guidance or beyond simply having an atomic dedup (A4 − A2 = 0, A4 − Bl = 0).
- The macro matters only under fixed guidance (A3 − A1 = +17 in both streams).
- Its "pure execution" value with frozen `G_L*` is +18 in rep1 but 0 in rep0, so that control is **mixed**.

## 1. Tracked compute ledger (audit finding 5)

- **File:** `docs/NEXUS_COMPUTE_LEDGER.json`, the ledger lines from the first Phase 10C row onward, copied verbatim. Hash chain
  intact.
- **Verification:** `python scripts/agi10f_ledger.py verify` re-checks the chain, every per-phase and per-stage sum, and the
  surplus reconciliation from the tracked file alone. All checks pass, including in a unit test.

| Phase | Used / cap (s) |
|---|---|
| 10C | 1,425.736 / 1,800 |
| 10D | 935.864 / 2,400 |
| 10E | 927.771 / 1,400 (pool 1,838.4, surplus **910.629**) |
| **10F** | **≈ 700 / 950** (s1 176.2, s2 275.3, s3 240.4, s4 ≈ 8) |

- The 300 s buffer was **not drawn**: 10F used less than the 910.629 s surplus.

## 2. Abstraction under disagreeing demonstrations (Stage 2)

**Setup.**
- Dream teacher, primitive substrate, admission gate and rankers are unchanged.
- One learner per stream runs until the two rules first **select** different candidates, then forks. Both arms share the
  identical prefix of experience.
- The first divergence was at step **90** in rep0 and step **100** in rep1. Before that, every sleep was identical under both
  rules.

**Valid replay macro in the library** (`ckey` on the partition key slot, `arrival` on the order slot):

| Stream / rule | Step 50 | Step 100 |
|---|---|---|
| rep0 Abs_current | none | none |
| rep0 Abs_subgroup | none | **L7** (admitted at 90) |
| rep1 Abs_current | none (L6 `ckey`-stripped) | none (L6 `ckey`-stripped) |
| rep1 Abs_subgroup | none (L6 `ckey`-stripped) | **L10** (admitted at 100) |

**What happened at step 50.** This was before the fork, so both rules acted identically.
- The only replay candidate was the whole-group one, with `ckey` stripped by a dream witness that partitioned by the arrival
  column. rep0 rejected it (no modular progress); rep1 admitted it with support 2.
- The `ckey` subgroup needs at least 3 verified source projects. At step 50 that support did not yet exist, so no rule could
  propose it.

**Verdict (pre-registered H1): subgroup insufficient.** Abs_subgroup acquired and retained the valid macro at step 100 in both
streams, which Abs_current never did. It failed the step-50 cells because the support threshold was not yet reachable.

**Training wrong submissions:** rep0 0 / 100. rep1 1 / 100, which is task 104529, S_dirty, path partition → post NOT NULL
filter → `set_dedup` on `stg_orders`.
- It came before the fork, so it is in both arms.
- It is the residual "unjustified dedup" gap disclosed in the protocol: Phase 10E's distractor variant is closed (`justified_dedup`),
  but this shape still slips through.
- Its exact mechanism is not yet confirmed.

**Training verified (wake):** rep0 97 / 100, rep1 94 / 100. S_replay: 4 / 6 and 3 / 5. 0 searches ended on the wall cap.

## 3. Shortcut elimination (audit finding 1)

- **Generator** `world10f`: a replay correction lowers quantity half the time.
- **Dev check:** 38.8 % of visible corrections decrease; the quantity alias fails visible acceptance and is hidden-wrong on 9 / 9
  replay projects; the quantity column never carries the `arrival` role (0 / 26).
- **Evaluation:** verified rows ordering the item dedup by quantity **0**, and **0** submitted ones, across all arms and 340 rows.
  Phase 10E: 16 / 24.

## 4. Held-out compositions (Stage 3, one-use 105000–105047)

**Coverage.** 340 of 576 rows. All 4 chunks reached their 60 s caps; the pre-registered held-out-first priority applied.
- Held-out: **22** targets with all 12 arms. 105043 is missing 1 arm and 105047 never started.
- Ordinary: 5 complete targets (223 ordinary rows missing).
- Every table below uses complete targets only. Missing rows are never counted as failures and never rerun.

**Held-out verified, of 22**

| Arm | rep0 | rep1 | Verified in both streams |
|---|---|---|---|
| A1 fixed + L0 | 0 | 0 | 0 |
| A2 G_L0 + L0 | 22 | 22 | 22 |
| A3 fixed + L0 ∪ L\* | 17 | 17 | 17 |
| A4 G_L\* + L0 ∪ L\* | 22 | 22 | 22 |
| **A4f** frozen G_L\*, replay macros removed | 22 | **4** | 4 |
| Bf atomic + fixed | 0 | 0 | 0 |
| Bl atomic + G_atomic | 22 | 22 | 22 |

**Pre-registered contrasts (held-out)**

| Contrast | rep0 | rep1 | Verdict |
|---|---|---|---|
| H2 macro execution, frozen guide (A4 − A4f) | 0 | +18 | **mixed** |
| H3 macro vs atomic, learned (A4 − Bl) | 0 | 0 | replicated null (both at ceiling) |
| H3 macro vs atomic, fixed (A3 − Bf) | +17 | +17 | replicated positive |
| L\* under fixed guidance (A3 − A1) | +17 | +17 | — |
| Learned guidance (A2 − A1) | +22 | +22 | — |
| A4 − A2 | 0 | 0 | — |
| Atomic vs split (Bl − A2; Bf − A1) | 0; 0 | 0; 0 | — |

**Mechanism attribution.** All 18 targets that A4_rep1 verifies and A4f_rep1 does not carry the replay macro on the verified
path.

**Why A4f fails in rep1 but not rep0 (interpretation, not tested).**
- rep1 held a replay macro (L6) from step 50. The `G_L*` ranker is trained on records in which macro tokens replace the primitive
  partition steps, so it may not have learned to rank the primitive partition.
- rep0 got its macro only at step 90.
- So the frozen-guide control measures how much the *ranker* came to depend on the macro, not a stable execution value.

**Execution counts** (held-out, every row of each arm; arms sharing a stream are on the same targets):

| Arm | Executions |
|---|---|
| Bl | 2,395 / 2,416 |
| A4 | 2,934 / 2,652 |
| A2 | 4,477 / 6,294 |
| A3 | 5,615 |
| A4f | 6,168 / 13,321 |
| A1 | 13,200 |
| Bf | 13,800 |

**Ordinary (5 complete targets):** A1 4, Bf 4; every learned arm 5. No arm loses an ordinary target against A1.

**Evaluation wrong: 0** in all 340 rows.

## 5. What this establishes and what it does not

**Established (NOT LOCKED, two streams, one fresh draw):**
- A generic subgroup-preserving abstraction recovers a role-consistent method from disagreeing demonstrations. Here that is a
  dream teacher whose tie strips a role, without touching the teacher.
- It did so in both streams by step 100. Whole-group intersection did not.
- The quantity shortcut is removed and audited at 0.
- The Phase 10E training-wrong mechanism is closed by a general rule (5 wrong accepted paths → 0).

**Not established:**
- *Reliable* acquisition: none at step 50, under the support threshold of 3.
- Any completion gain from macros beyond learned guidance or beyond an atomic dedup. With the shortcut removed, the `arrival`
  role became unique, and learned guidance alone saturates the held-out set (22 / 22). **This held-out set can no longer
  discriminate A4 from A2 or Bl.**
- A stable "pure execution" value of the macro (0 versus +18).
- Learning-to-learn: the macros reduce executions modestly, but Bl is cheaper still.

**Open:**
- the residual dirty-partition training wrong (1 / 200 learner-tasks: one task in rep1's shared prefix, so in both arms);
- 236 unmeasured rows (mostly ordinary).

## 6. Recommended next experiment

Make the held-out set discriminative again, **without** reintroducing a shortcut.
- Add a second, independent monotone column in every replay relation that is *not* the arrival order: for example an
  update-timestamp copy that decreases on half the replays only in hidden batches.
- The role-only ranker then faces genuine role twins, and A4 / A4f / Bl can separate.

Alongside it:
- lower Abs_subgroup's support threshold to 2, pre-registered, to test step-50 acquisition;
- confirm and close the dirty-partition gap with a cheap dedicated diagnostic before training.

## 7. Protection and tests

- **Protection:** `artifacts/agi10f_protect_before.json` and `artifacts/agi10f_protect_after.json`, **0** violations.
- **Frozen files:** 2,638 Phase 1–10E files unchanged; checkers v1–v5 match their pins; `main` is `d7ac8c5`.
- **Tests:** `tests/test_agi10f.py` (12), `tests/test_agi10e.py` (9) and `tests/test_checker_kernel.py` all pass.
- **Disclosure:** after the run, `score()` was amended to use complete targets only. This is analysis only, and the rows are
  unchanged.
