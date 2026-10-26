# Wave 28 — postcondition filter on every tier, Wave 26 library certification restored, compositional Phase 6 (locked before 4016–4020, 5016–5020, 6016–6020)

Branch `codex/wave28-postcondition-core-filter` (from Wave 27 `83e1ce3`). Owner request, 2026-10-26.

Code:
* `src/nexus/wave28_core.py`: the engine.
* `src/nexus/wave28_eval.py`: the Wave 27 loops with `solve28`, plus compositional Phase 6 targets.
* `scripts/wave28_confirm.py`: the driver.
* `tests/test_wave28_core.py`: 3 equivalence tests. The Wave 27 tests still pass.

## Changes from Wave 27

### 1. Pre-enumeration postcondition filter in every tier, including core and ΔB with unproved tools

**What Wave 27 did.** It disabled its index in any tier containing an unproved tool. Phase 5 puts an opaque
tool in every tier, so the whole Phase 5 ladder ran unpruned. That was the source of the ΔB-world interference
spike.

**What Wave 28 does.** It uses a contract-signature algebra:
* **Postconditions.** len_le k, all p and distinct path (closed under any proved sub-multiset map), plus a new
  **sorted(path)** postcondition for field-ordered mechanisms. Sortedness is preserved only by proved
  subsequence maps: F, and S / comp in position-ascending order.
* **Which chains can fit.** A tool t whose postcondition some public output violates can only occur in a fitting
  chain if a later tool fails to preserve that postcondition.
* **Depth-2 tiers.** Such tools leave the enumerated set, and their only possible completions (t, g) are
  re-admitted as macro hypotheses. They join the certificate at depth 2, and only if no depth-1 program fits:
  `run_to` certifies at minimal size. Following the Searcher convention, they extend one representative per
  observational class.
* **Exactness.** The hypothesis answer set equals the unpruned tier's. A test compares them on random ΔB / ΔC / ΔM
  tasks, with and without an unproved tool.
* **Other tiers.** Depth-3 tiers drop only tools nothing can rescue. The ΔM synthesis scan applies the same pair
  rule, and a test checks that its hits are identical to Wave 26's.

### 2. Wave 26 library certification restored

* The Wave 27 library-route withdrawal audit is removed (owner instruction).
* Kept: the core-tier audit (drift detector for consolidated schemas), the cross-task MDL / falsification
  admission filter, and the ladder.
* **Declared risk.** Wave 27 dev run 1 had one false library-tier certificate, the same mode Wave 26 disclosed,
  and that audit caught it. G_soundness will show whether it returns.

### 3. Promotion economics (dev decision, disclosed)

* **Problem.** With the index, invention is cheap: about 10k on records-F. A probationary reuse, though, pays
  the full union scan: 65k–240k. So Wave 27's net benefit, (support − 1) × invention cost, delayed
  consolidation.
* **Wave 28.** Each further use is valued at max(invention cost, mean measured work of the probationary-library
  reuses so far). Class verification and the expanded-AST price are still subtracted.

### 4. Phase 6 compositional transfer

**Target worlds.** Each of 16 held-out target worlds per ordering has a teacher that composes **two different**
source mechanisms (h1 ∈ s1, h2 ∈ s2, s1 ≠ s2, s1 item-preserving). No such combination appears in source
training. Each task is a verified base-tier failure that rebinding and depth-3 recombination also fail
(field-name seeds 600000 + 100 × seed + j).

**Reported metrics.**
* raw least-squares slope;
* cumulative area under the work curve (AUC = Σᵢ cumulative work through task i);
* per-arm coverage (solved).

**Note on AUC.** It is floor-adjusted: an arm already fast on task 1 is not penalised. It ranks arms almost like
total cost, so it is not a learning-rate measure.

## Dev evidence (reusable dev seeds)

**Run 1.**
* Phase 5: revisit ratios 0.32 / 0.26 / 0.92, interference 1.1% (Wave 27 dev 0.7%; Wave 27 confirmation 14.6%),
  retirement 5/5, 0 false certificates.
* Phase 4: F 4/10 streams (first 13.6k → later 27.8k), S 6/10, Sort 9/10; 0 false certificates.
* Phase 6: Experienced cheaper in 1/2 orderings, solving more (13 vs 11; 11 vs 10).

**Run 2 (class-representative macros).** Essentially unchanged: macro evaluation was not the dominant cost.

**Run 3 (locked; promotion economics).**
* Phase 4: F later mean 17.5k vs first 13.6k (4/10 streams); S 12.7k → 10.2k (6/10); Sort 2.3k → 1.6k (9/10).
* Router: ΔB 30/30, ΔC 30/30 (23 solved), ΔM 30/30 (29 solved); 0 false certificates.
* Phase 5: same as run 1 (0.289 / 0.268 / 0.907, interference 1.1%).

Phase 6 (cost / AUC / solved):

| Ordering | Experienced | Fresh | Placebo |
| --- | --- | --- | --- |
| 741 | 3.00M / 25.8M / 13 of 13 | 0.96M / 7.3M / 11 | = Fresh |
| 742 | 0.38M / 2.0M / 11 of 12 | 0.49M / 3.6M / 10 | 0.43M / 2.9M / 11 |

**Dev diagnosis for 741.** The expensive Experienced tasks end in a projection schema. No item-preservation
proof applies there, so the ΔM scan cannot prune its partners, and Experienced's 3 retained schemas make that
scan larger than Fresh's (664k–737k vs 288k–510k). The "bigger library costs more" effect has moved into the
projection branch of the ΔM scan.

## Confirmation protocol (single shot, fresh one-use ranges, checkpointed per unit; replay in fresh processes, `PYTHONHASHSEED=271828`, run sequentially)

* **Phase 4 (4016–4020), gate unchanged from Wave 26:**
  * router ≥ 80% correct per fault kind;
  * per primitive: first encounters routed ΔM ≥ 80%, solved ≥ 80%, and later encounters cheaper than the first
    in ≥ 80% of streams;
  * 0 false certificates.
* **Phase 5 (5016–5020), gate unchanged:** revisit ratio < 1 at lags 5, 10 and 20; interference ≤ 10%; every
  drift-broken opaque contract retired, with 0 false certificates.
* **Phase 6 (6016–6020), compositional targets. Primary gate (owner-directed, declared before data):** in 5/5
  orderings, all of:
  * Experienced cost < Fresh and < Placebo;
  * Experienced AUC < Fresh and < Placebo;
  * Experienced solved ≥ Fresh and ≥ Placebo (so a cheap give-up cannot count as a cost win);
  * 0 false certificates overall.

  Secondary, reported for continuity: the Wave 26 raw-slope gate (5/5).
* **Standing gates:** G_soundness, G_replay (every unit) and G_tycho.
* **Post-lock `wave28_paired_check`.** Group B + external ARC, 2 tasks per seed, orderings 6001–6005, Fresh
  evaluated once with seed 0 (Wave 26 / 27 design). Owner registry override; vault verified before any claim;
  aggregates only. This is a **third** pass on those splits.
  * **Coverage restored** iff every arm solves ≥ 10/40 in every ordering, with 0 false certificates.
  * Cost and AUC are reported alongside.

**Expected outcomes (declared)**
* Phase 5: PASS is plausible.
* Phase 4: FAIL on F (4/10 streams on dev). Invention is now cheaper than any reuse that pays the union scan.
* Phase 6: uncertain; likely FAIL (1/2 dev orderings).
* Group B + ARC: coverage should return toward Wave 26's 10/40, since the withdrawal audit is gone. But the MDL
  filter admits fewer schemas than Wave 26 did, which may cost some library-route solves.

**Budget.** 17,586 s remained at lock (Wave 28 dev about 1,640 s), ≤ 900 s per call.

Locked code sha256 (first 16 hex digits):
* `wave28_core.py` `66b00ae079e8aec6`
* `wave28_eval.py` `a494448264c4c78a`
* `wave28_confirm.py` `8fcbe48c3af096b5`

## Confirmation results (locked `038f228`; fresh seeds; all replays identical)

**Runs.**
* Phase 4: 165 s. Phase 5: 616 s. Phase 6: 526 s.
* Replays: 15/15 units identical (5 per phase).

**Artifacts (sha256, first 16 hex digits).**
* Phase 4: `1215698b1c810f9c`. Phase 5: `a60d14c28b1b9212`. Phase 6: `6e2afd6b06351050`.
* Group B + ARC check: `984f6f0718982ad1`.

| Phase | Gate | Result |
| --- | --- | --- |
| 4 (4016–4020) | router | PASS: 90/90 routed (ΔB 26 solved, ΔC 25, ΔM 30) |
| | primitives | **FAIL**. F **8/10** streams (47.4k → 35.5k), S 5/10 (11.6k → 12.0k), Sort 10/10 (4.2k → 1.5k) |
| | false certificates | **2** (both ΔB, fresh library) |
| 5 (5016–5020) | revisit | **FAIL**: 0.458 / 0.905 / **1.103** |
| | interference | PASS: −4.6% |
| | retirement | 15/15 retired, but 1 false certificate, so **FAIL** |
| 6 (6016–6020, compositional) | cost | 5/5 |
| | AUC | 4/5 |
| | coverage | 5/5 |
| | joint (cost + AUC + coverage) | **4/5: FAIL** |
| | raw slope (secondary) | 3/5 |
| | false certificates | **5** (Fresh 2, Placebo 2, Experienced 1) |
| Paired Group B + ARC | coverage ≥ 10/40 every arm | **FAIL**: 9/40 for each arm in every ordering (Wave 26 10, Wave 27 0 / 2 / 2) |
| | Experienced cost / AUC wins | 5/5 / 5/5 (13.1M vs 44.3M) |
| | false certificates | 0 |

**G_soundness FAIL: 8 false certificates.** All 8 were re-solved after the run: every one reproduces with the
Wave 27 engine and with the unpruned certifier. **None is caused by the Wave 28 index or by removing the library
audit.**
* **Phase 4 (2).** Minimal-size certificates: a 1-step program fits the public pairs of a 2-step ΔB teacher.
* **Phase 6 (5).** On compositional targets, a single ΔM invention fits the public pairs of a 2-mechanism teacher
  outside the single-invention space. One Experienced core answer passed its reordered-query audit.
* **Phase 5 (1).** A library-route coincidence on a drifted world (5019:11:2). The Wave 27 engine's library
  audit *passed* the same certificate.

The compositional targets and new seeds exposed a limitation that the Wave 26 and Wave 27 seeds did not happen to
contain.
