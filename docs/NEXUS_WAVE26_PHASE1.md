# Wave 26 Phase 1 — economical-transfer crossover map (status: dev grid NOT yet completed)

Branch `codex/wave26-phase1-crossover` (from Phase 0 `c9abac3`). Code: `src/nexus/wave26_phase1.py`,
driver `scripts/phase1_crossover.py`.

## Grid (declared)

* **Oracle cost:** `c_oracle ∈ {20, 200, 2000, 20000}`.
* **World cells:** depth 2 / 3 fields / small grammar; depth 2 / 5 fields / medium; depth 2 / 8 fields /
  large; depth 3 / 5 fields / medium.
* **Records:** 1 bool, 1 score, F−3 score-correlated distractors and 1 tag field, with names randomised
  per seed.
* **Infeasible cells:** depth 4 and 5 are reported as infeasible. The exact certifier enumerates to depth 3,
  and depth-4 enumeration is outside the per-session budget.
* **Arms:** exact_eig_enum, s2_transferred_rule, myopic_s3, revisable_controller, full_nexus_vault. All of
  them are exact-certified.
* **Amortised one-time costs:** S2 mining (~330k per seed) and contract learning (~33k) are charged at
  episodes / 100 per cell.
* **Selection and pass rules:** as in the driver docstring.

## What happened in session 2026-10-25

* A smoke run on non-registry seed 1 (depth-3 cell, 2 episodes) gave fully loaded work at
  `c_oracle = 20000` of:
  * exact_eig_enum 609k
  * s2_transferred_rule 616k
  * myopic_s3 840k (1 of 2 queries unsolved)
  * revisable_controller 392k
  * full_nexus_vault 177k

  This is a smoke run only, not evidence.
* The dev grid on seeds 701–705 hit the 900-second per-experiment cap. The first driver held all results
  in memory, so **nothing was saved**. The full 900 s was charged to the session ledger, which exhausted
  the standing 3600-second session allowance. No further experiment ran in this session.
* Fix: the driver now appends every finished (seed, cell) unit to `--checkpoint` and resumes from it. It
  also stops cleanly between units before `--wall-cap` (default 840 s). The grid can therefore be
  completed over several bounded runs without losing work.

## Next session (in order)

1. `python3 scripts/phase1_crossover.py --grid --n 4 --checkpoint runs/experimental/wave26_phase1_grid.jsonl
   --out artifacts/wave26_phase1_dev_grid.json`, repeated until the status is COMPLETE. Seeds 701–705 are
   dev seeds; resuming them is allowed.
2. Apply the declared selection rule, lock the chosen cell in this file, commit.
3. Run the confirmation once (seeds 1001–1005, one-use, registry-enforced) with fresh-process replay.

Phase 1 has **not** passed yet. Phases 3, 2, 4, 5 and 6 are blocked on it (Phase 3 also needs the owner's
blind vault-generation session).
