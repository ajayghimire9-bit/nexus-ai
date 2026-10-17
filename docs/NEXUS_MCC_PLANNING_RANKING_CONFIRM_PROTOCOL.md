# MCC same-state planning-ranking confirmation — locked protocol

Branch `cursor/mcc-planning-ranking-confirm` from `4dbe664`. H12 on
`mcc_planning_ranking_v1` **(0.0027, 0.0015, 0.075)** is closed
`mcc_planning_ranking_multitask_better`. This lock tests whether that
same-state ranking advantage **replicates** on a new unused holdout.
It does not retune H12, H10, or H11, or convert ranking into a
200-step return study.

## Falsifiable question (H13)

On unused MountainCarContinuous physics disjoint from H12, does the
**frozen H10 residual recipe** produce lower sequence regret than
matched scratch when both arms rank the **same 16 H=16 candidates**
from the **same reset states**?

## Frozen H12 design (unchanged)

Identical to H12/H10: three source physics, 512 each, 15 pretrain
epochs under source RMS, 128+32 target, target RMS on both arms, 20
fine-tune epochs, residual 2×64, Adam 0.001, H=16 × 16, four reset
states, `reset(seed=state_seed)` restore. H11 seeds 4 and 5 are **not**
used to pick physics or candidates.

H12 implementation SHA256
`2cc7342ca747f4a667f14171353dad36a89907ac38bb475a94a7a862ef85d817`
is frozen. Closed H12 raw SHA256
`c65bc9f42e3fbfe99b5b7dc4d68f8a08fb63fc04e08d374e619dba2f35bbcb8f`
must not change.

## New confirmation holdout and seeds

- Target `mcc_planning_ranking_confirm_v1` — **(0.0039, 0.002, 0.075)** —
  rejecting H10 **(0.0032, 0.0022, 0.06)**, H11 **(0.0022, 0.0016, 0.07)**,
  H12 **(0.0027, 0.0015, 0.075)**, sources, and earlier MCC holdouts.
- Seeds: `75,000,000+`, disjoint from H12 `74,000,000+`.
- Shared candidates: `candidate_sequences(candidate_base+10s+k)`.
- Planners see predicted scores only.

## Predeclared primary and labels

Primary: per-seed mean over four states of
`sequence_regret_scratch − sequence_regret_multitask`. Student-t 95%,
df 9.

- `mcc_planning_ranking_confirm_multitask_better`: mean > 0 and lo > 0.
- `mcc_planning_ranking_confirm_scratch_better`: mean < 0 and hi < 0.
- `mcc_planning_ranking_confirm_not_established`: otherwise.
- `incomplete`: missing cell, cap failure, reset mismatch; no retune.

First-action regret and 16-step recede stay secondary. Recede is not
label-deciding.

## Bounds

**300-second hard cap**, **28,480 real environment steps**, **348,160
imagined transitions**, local CPU. Session ledger at lock: 3307.802 s
of 3600 s remain.

Collection is not authorized by this protocol text alone.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_mcc_planning_ranking_confirm.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_mcc_planning_ranking_confirm.py
```

`--execute` must refuse until a later one-run allocation is committed.

Not learning-to-learn, not AGI, not a 200-step control claim.
