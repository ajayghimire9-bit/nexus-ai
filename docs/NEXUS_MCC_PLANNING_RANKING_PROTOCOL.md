# MCC same-state planning-ranking diagnostic — locked protocol

Branch `cursor/mcc-planning-ranking-diagnostic-prep` from `95dbebc`.
Preparation only. Collection unauthorized.

Pendulum already has a completed same-state ranking audit
(`NEXUS_PREDICTION_CONTROL_GAP.md`): student versus zero context,
regret = best realized candidate minus selected realized candidate.
That study is closed and is not MCC. H10/H11 saved no observations or
planner scores, so they cannot answer ranking. This protocol is the
first MCC **multitask-versus-scratch** same-state ranking grid. It is
not another 200-step episode-return study and not a retune of H10/H11.

## Hypothesis (H12)

On unused MountainCarContinuous physics, does the frozen H10 residual
recipe produce **lower sequence regret** than matched scratch when both
arms rank the **same 16 H=16 candidates** from the **same reset
states**?

## Frozen training recipe

Identical to H10: three source physics, 512 each, 15 pretrain epochs
under source RMS, 128+32 target, target RMS on both arms, 20 fine-tune
epochs, residual 2×64, Adam 0.001, H=16 × 16. Independent seeds
`74,000,000+`. H11 seeds 4 and 5 are **not** used to pick physics or
candidates.

## Same-state design

- Holdout `mcc_planning_ranking_v1` **(0.0027, 0.0015, 0.075)**.
- Four reset-only states per seed. No mid-episode snapshots.
- Restore: `env.reset(seed=state_seed)` before every candidate and
  before each closed-loop start. The first reset records `obs0`. Later
  resets of the same seed must match `obs0` or the cell is invalid.
  Planners never see other candidates' realized returns.
- Shared candidate matrix: `candidate_sequences(candidate_base+10s+k)`.
  Both arms score that matrix from the recorded `obs0`.

## Three return objects

1. **Predicted candidate return:** planner H=16 score (imagined height).
2. **Realized open-loop return:** 16-step simulator height sum of that
   exact action sequence after `reset(state_seed)`. Shared ground truth.
3. **Closed-loop controller return:** 16-step receding H=16 from the
   same `obs0` (secondary). Not a 200-step episode and not
   label-deciding. H10/H11 already measured 200-step return.

## Regret

Sequence regret = `max_c R_real(c) − R_real(c_selected)`, `c_selected =
argmax predicted`. Nonnegative by construction.

First-action regret (secondary) = `max_a V_real(a) − V_real(a_hat)`,
where `V(a)` is the max score among candidates whose first action is
`a`, and `a_hat` maximizes predicted `V`.

Primary: per-seed mean over four states of
`sequence_regret_scratch − sequence_regret_multitask`. Student-t 95%,
df 9.

- `mcc_planning_ranking_multitask_better`: mean > 0 and lo > 0.
- `mcc_planning_ranking_scratch_better`: mean < 0 and hi < 0.
- `mcc_planning_ranking_not_established`: otherwise.
- `incomplete`: missing cell, cap failure, reset mismatch; no retune.

## Simulator-step accounting

Ground-truth open-loop is **shared** (not ×2 arms):
10 × 4 × 16 × 16 = **10,240** steps.

Closed-loop recede is per arm: 10 × 2 × 4 × 16 = **1,280**.

Training: 15,360 source + 1,600 target.

**Env cap 28,480.** Imagined: scoring 20,480 + recede 327,680 =
**348,160.** Time cap **300 s**. Local CPU. One later run only.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_mcc_planning_ranking.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_mcc_planning_ranking.py
```

`--execute` must refuse until a later one-run allocation is committed.

Not learning-to-learn, not AGI, not a control-improvement claim.
