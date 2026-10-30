# NEXUS Phase 10F — pre-registered protocol (NOT LOCKED)

This protocol is committed **before** any Phase 10F training outcome, and before the 48 one-use evaluation targets are opened.

- **Branch:** `codex/nexus-data-engineering`, starting at revision `343778e`.
- **`main`:** `d7ac8c5`, untouched.
- **Budget:** `artifacts/agi10f_grant.json`.
  - The owner authorised at most **950 charged seconds**. The pool is the Phase 10E surplus **910.629 s** plus the
    owner-authorised **300 s** buffer, drawn only if needed.
  - Stage ceilings (`artifacts/agi10f_allocation.json`): s1 180, s2 420, s3 250, s4 100. No transfers.
  - Every run is metered by `scripts/agi10f_exec.py` (prefix `a10f-`).
- **Tracked ledger:** `docs/NEXUS_COMPUTE_LEDGER.json` copies the hash-chained ledger verbatim from the first Phase 10C row.
  - `python scripts/agi10f_ledger.py verify` re-checks the chain, every per-phase and per-stage sum, and the surplus
    reconciliation using only the tracked file.
  - Phase 10C used 1,425.736 of 1,800 s; Phase 10D 935.864 of 2,400; Phase 10E 927.771 of 1,400 (pool 1,838.4, surplus 910.629).
- **Frozen code:** Phase 1–10E files are protected (`scripts/agi10f_protect.py` adds every Phase 10E file).
  - All Phase 10F code is new, in `src/nexus/de_phase10f/`.
  - The protection snapshot before Phase 10F: `artifacts/agi10f_protect_before.json` (0 violations).

## What the Phase 10E audit found, and what changes

**1. Quantity–sequence shortcut.** Verified on the committed Phase 10E rows: 16 of A4_rep1's 24 verified held-out repairs ordered
the replay dedup by `units`.
- Cause: `world10d` always increased quantity on a replay correction.
- Fix, new generator `de_phase10f.world10f`:
  - a correction now **lowers** the quantity with probability 1/2 when it can;
  - a replay project must show at least one visible later-sequence / lower-quantity item;
  - the quantity alias (the truth with the dedup ordered by quantity) must **fail visible acceptance and change a hidden batch**.
- Applies to training, dreams, admission and evaluation.

**2. Whole-group role intersection.** The new rule is `de_phase10f.abstract10f`.
- **Abs_current** = `invent7` unchanged.
- **Abs_subgroup** = the same candidates **plus** role-consistent subgroups.
  - For each per-demonstration role signature, the maximal compatible subset of a skeleton cluster gives one candidate.
  - Keep conditions: ≥ 3 verified source projects, strictly more specific than the whole-cluster candidate, no empty slot,
    and ΔMDL > 0.
  - Candidates are proposed alongside the broad one, and the unchanged admission gate decides.
- **Not changed:** the dream teacher (`witness`, including its tie behaviour), the primitive substrate, the admission gate and
  the rankers.

**3. Confounded A4 vs A2.** New control **A4f** (A4_frozen_no_replay): the *same* `G_L*` as A4, with only the replay macros
removed from the action set.

**4. Split-dedup architecture.** New baseline **B_atomic**, in `de_phase10f.atomic10f`.
- Same features as the split arms: the Phase 10D one-step `set_dedup` with the Phase 10E column roles and acceptance rules, and
  without `add_partition`.
- **B_atomic_fixed (Bf):** the fixed operator order.
- **B_atomic_learned (Bl):** `G_atomic`, trained on the *same* step records as `G_L0`, rewritten into the atomic substrate.

**5. Untracked ledger.** Fixed by the tracked ledger above.

**Phase 10E training wrong (1 / 238), audited and closed.**
- Project: rep1 `P10D.T_cdc_key+dirty.sqlite.postgres.101524`. Sources: `scripts/agi10f_diag_wrong*.py`,
  `artifacts/agi10f_diag_wrong*.json`.
- Mechanism:
  - the path partitioned `stg_orders` by a distractor int that is unique on both visible batches, so the partition was a visible
    no-op;
  - it existed only because a post-dedup NOT NULL filter is offered only on deduped relations;
  - Occam pruning could not remove it;
  - on the hidden batches the distractor collides and drops orders.
- New shared acceptance rule `dag10f.justified_dedup`: a dedup must partition by a documented unique key, or by a key with at
  least one **non-null** duplicate group on a visible batch.
- Effect on 101524: of the 12 accepted paths of that shape, 5 were hidden-wrong; under the new rule 1 remains accepted and
  0 are wrong.
- Truth false rejects: 0 / 26 dev projects (`artifacts/agi10f_devcheck.json`).
- The non-null clause was added after a forced-fork dev rehearsal produced 2 hidden-wrong repairs of the shape partition →
  post filter → `set_dedup` on `stg_orders`. Its diagnostic enumeration hit the 40 s cap, so that mechanism is **not confirmed**.
  The residual risk is disclosed in `dag10f`.

## Stage 1 design checks (agi10fde/dev only; `artifacts/agi10f_devcheck.json`)

| Check | Result |
|---|---|
| Truth passes every acceptance rule | 26 / 26 projects |
| Visible replay corrections that decrease quantity | 38.8 % |
| Replay projects whose quantity alias fails visible acceptance | 9 / 9 |
| Replay projects whose quantity alias is hidden-wrong | 9 / 9 |
| Quantity column carrying the `arrival` role | 0 / 26 |
| Sequence column carrying `arrival` on replay projects | 9 / 9 |
| Atomic substrate: truth dedup is one root candidate | 9 / 9 |
| Atomic substrate: median fixed-order position of the truth dedup | 453 |

**Unit tests (`tests/test_agi10f.py`, 12)** include the Phase 10E failure cases.
- On the committed Phase 10E checkpoints rep0 N60 / N118 and rep1 N120, Abs_current yields only the `ckey`-stripped macro.
- Abs_subgroup also proposes the `ckey` macro, whose canonical form is identical to rep1's admitted L5.
- On the rep0 N60 state the two rules select different candidates.

## Stage 2: paired abstraction training

- **Streams:** 2 numeric-seeded streams (rep0, rep1; `agi10fde/train` 104000 + 500 r).
- **Families:** Phase 10E's, with replay only as S_replay.
- **Length:** **N = 100** tasks, sleep every 10, checkpoints at **50 and 100**.
- **Pairing** (`scripts/agi10f_train.py`):
  - One learner runs the stream under Abs_current.
  - Before every sleep, both rules' selections are computed on the same state.
  - At the **first sleep where they differ**, the learner forks into `rep{r}.current` and `rep{r}.subgroup`, both from the
    identical state.
  - Until then every sleep is provably identical under both rules, so the shared prefix is each arm's own history.
- **Time guards:** the learner's own guards (skip abstraction / dreams below 30 s left) are disabled for both arms.
  - The job runs to N = 100 or is killed at its cap.
  - Checkpoints are written as reached; a kill is reported as TIMEOUT.
- **Jobs:** rep0 and rep1, cap 210 s each; new tasks stop launching at 200 s.
- **Shared pure caches** (both arms, and evaluation): project builds, parsed workspaces and interpreter memos, and per-candidate
  evidence by (project, engine, spec hash).
  - The work counter still increments on every cached execution, so results are unchanged and only wall time drops.
  - After the fork the branch that runs first alternates per task.
  - Every wake row records `wall_bound`.

## Stage 3: one-use evaluation

- **Targets:** fresh `agi10fde/eval` 105000–105047, from `world10f`.
  - 24 held-out replay compositions (R1–R8 × 3) plus 24 ordinary targets.
  - Frozen manifest `artifacts/agi10f_manifest.json`, sha256 `4c98a51a…`.
- **Search:** each arm runs once per target with work 600 and wall 4 s, verified on the declared engine against 2 hidden batches.
- **Memories:** L\*\_r, G_L0_r, G_L\*\_r and G_atomic_r come from `rep{r}.subgroup.final.json`.

| Arm | Guidance | Actions |
|---|---|---|
| A1 | fixed | L0 split (shared) |
| A2_r | G_L0_r | L0 split |
| A3_r | fixed | L0 ∪ L\*\_r |
| A4_r | G_L\*\_r | L0 ∪ L\*\_r |
| A4f_r | G_L\*\_r (the same weights as A4_r) | L0 ∪ (L\*\_r minus every macro containing `add_partition`) |
| Bf | fixed | atomic dedup (shared) |
| Bl_r | G_atomic_r | atomic dedup |

That is 12 arm-runs × 48 targets = 576 rows.
- **Execution:** 4 chunks of 12 targets, cap 60 s each.
- **Pre-registered priority:** inside each chunk, held-out targets run first, and every arm of a target runs before the next
  target. Rows a cap prevents are reported as **missing**, never rerun.

## Decision rules

**H1, acquisition reliability.** A *valid replay macro* is an admitted library skill whose `add_partition` key slot keeps `ckey`
and whose `set_dedup` order slot keeps `arrival`. Its presence is read from the checkpoints at N = 50 and N = 100, for each rule
and each stream.
- A rule is **reliable** only if the macro is present in all 4 cells.
- A missing checkpoint (budget kill) or an absent macro counts as **failure**, never "untestable".
- Verdicts:
  - *subgroup fixes acquisition*: Abs_subgroup reliable and Abs_current not;
  - *no difference*: same outcome in every cell;
  - *subgroup insufficient*: Abs_subgroup not reliable;
  - otherwise *mixed*.

**H2, pure execution value of the replay macro** (held-out, per stream). D = A4 − A4f.
- *Replicated positive*: D ≥ +2 in both streams, with 0 evaluation wrong in A4.
- *Replicated null*: |D| ≤ 1 in both.
- Otherwise *mixed*.
- A stream without a replay macro has A4 ≡ A4f (D = 0) and cannot be positive.

**H3, macro versus atomic dedup** (held-out, per stream). A4 − Bl and A3 − Bf, with the same thresholds.

**Shortcut audit.** The number of verified (and of submitted) evaluation rows whose item dedup orders by the quantity column.
Expected: 0 (Phase 10E: 16 / 24).

**Wrong submissions.** Training (per rule and stream) and evaluation, reported separately. Target: 0.

**Also reported:**
- A2 − A1, A3 − A1, A4 − A2, Bl − A2, Bf − A1;
- per-stream and unconditional tables: verified in both streams and in either;
- execution counts;
- ordinary-target results as far as the budget allows;
- attribution: for targets A4 verifies and A4f does not, whether a replay macro is on the path.

**Sign-flip p-values** are descriptive only. No retro-adoption, no rerun of a written row, no reuse of the one-use range.

## Disclosures recorded before outcomes

- **Stage 1 spending:** 175 s of the 180 s ceiling, through one failed rehearsal (a code bug), two rehearsals and a 40 s timeout
  of the dev-wrong diagnostic. No dev evaluation timing was possible, which is why the held-out-first priority exists.
- **Pairing:** Abs_current here is re-run on the decoupled generator, so its outcomes are not Phase 10E's.
- **Dev wrongs:** the forced-fork dev rehearsal had 2 wrong of 30 dev tasks, before the non-null clause.
