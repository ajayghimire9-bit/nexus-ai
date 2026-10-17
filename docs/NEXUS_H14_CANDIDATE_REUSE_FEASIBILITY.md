# H14 candidate-reuse feasibility — source-only design audit

Design analysis only. No collection, no training, no allocation, no
lock. H12/H13 outcomes are not reinterpreted. Not learning-to-learn,
not AGI.

Branch `cursor/h14-candidate-reuse-feasibility` from audit
`da8941b`. Session ledger unchanged: 3304.945 s remain.

## 1. Scientific motivation

H12 and H13 established better same-state ranking for the frozen H10
recipe versus scratch. H13 redraw recede favored scratch
(`multitask − scratch` **−0.253 [−0.431, −0.074]**) and was
secondary. The `da8941b` audit could not name a mechanism. The
smallest identifiable next question is whether **candidate
resampling**, rather than model quality or later-state scoring,
changes the relative closed-loop comparison.

Fixed-library recede is not open-loop commitment. The library is
frozen; scores are recomputed from the current observation each
decision.

## 2. Source finding: arm-specific recede randomness

`recede_closed_loop()` seeds candidates as

`closed_loop_step_base + 1000 * seed + 100 * arm_index + step`.

There is an arm term and **no state term**. Direct check:
`candidate_sequences` for seed 0, step 0, arm 0 versus arm 1 are
not equal. The four reset states of one seed/arm reuse the same 16
step-wise matrices.

**Primary H12/H13 metrics survive.** Ranking uses
`candidate_base + 10s + k`, shared across arms, and shared
open-loop ground truth. Sequence regret and first-action regret do
not use recede seeds. Labels
`mcc_planning_ranking_multitask_better` and
`mcc_planning_ranking_confirm_multitask_better` stand.

**Secondary recede comparisons are confounded.** Multitask and
scratch did not necessarily face the same proposal stream. The
audit’s recede-over-commitment “bonus” is an accounting identity,
not a causal mechanism: it mixes model scores, later occupancy, and
**different candidate libraries**. It does not establish that scratch
gains more from recede *because* it is a weaker ranker.

Historical Spearman in the audit is a secondary diagnostic only. Its
implementation ranks ties by stable argsort order, not average
ranks. On `[1,1,0]` it returns −0.5 or +0.5 according to which tied
item is paired with the large `y`. That does not change registered
primaries. Duplicate-seed validation in the audit used a dict keyed
by seed: eleven cells covering `0–9` plus a duplicate `0` still
pass. H12/H13 raw grids are ten unique seeds; the hole did not
alter those artifacts. Neither bug is silently patched here.

## 3. Exact mode definitions

**Shared first library** `L0 = candidate_sequences(library_base+10s+k)`.
Both arms and both modes use `L0` at decision 0.

**Fixed-library recede.** For `t = 0…15`, score `L0` from the
current observation, take `argmax` (first index), execute that
sequence’s first action. Horizon stays 16. No shrinking suffix.

**Redraw recede.** Decision 0 uses `L0`. For `t ≥ 1`, score
`candidate_sequences(redraw_base+1000s+10k+t)` from the current
observation. Both arms receive that same matrix at `(s,k,t)` even
if their observations differ. No arm term.

Planners see only observations and proposed matrices. Realized
counterfactual returns are not arguments. Reward, discounting,
tie-break, action map, and termination stay as in H12.

## 4. Proposed experimental grid

Ten independent model seeds. Four reset states per seed. Frozen H10
recipe versus matched scratch. New unused MCC holdout, chosen only
at a later lock by a new rule that rejects H10–H13 and the three
sources. Do not reuse H13 physics `(0.0039, 0.002, 0.075)`.

Two recede modes above. Optional shared open-loop realization of
`L0` (once per state) as a secondary ranking/commitment baseline.

Log, during already-paid recede steps only: observation, candidate
seed, scores, selected index, first action, reward. No extra
counterfactual rollouts. Mid-episode `reset(seed)` cannot restore a
visited state; `set_state` was rejected for this family. Later-state
regret therefore needs either saved snapshots plus a new restore
method, or extra rollouts. Neither is added automatically.

## 5. Recommended primary

Per seed, average the four states, then

`D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`.

Positive `D` means the multitask-versus-scratch gap is larger under
the fixed library than under redraw. Student-t 95%, df 9, n = 10.
Practical margin 0.0 (same as H12).

- `h14_fixed_library_helps_multitask_relative`: mean > 0 and lo > 0.
- `h14_redraw_helps_multitask_relative`: mean < 0 and hi < 0.
- `h14_resampling_effect_not_established`: otherwise.
- `incomplete`: missing cell, failed reset, cap, nonfinite; no retune.

This DiD matches the resampling question. The simple
`R_mt_fixed − R_sc_fixed` contrast is the right secondary for “does
ranking persist under fixed-library recede,” but it does not isolate
resampling. Do not elevate secondaries after seeing data.

Forty states are not forty training replications.

## 6. Fairness and identifiability

The two-mode comparison can establish **C**: whether shared-library
resampling changes relative closed-loop returns, without the H12/H13
arm-specific proposal confound.

It cannot distinguish **A** (later ranking decay) from **B**
(compounding model error). Both can appear in both modes. **D**
(exploiting inaccuracies) is also not identified from returns alone.

To test A: later-state scores of a *shared* library (loggable during
fixed-library recede at no extra env cost).
To test B: predicted versus realized one-step or H=16 error on
visited states (needs saved predictions and next observations;
next observations are already produced by `env.step`).
To test D: those errors plus selected-action residuals, still not
counterfactual regret.
Counterfactual later-state regret needs restoration of visited
states and extra rollouts. Restore-by-reset cannot do that. Cost
would be `n_visited × n_counterfactual × remaining_horizon` extra
env steps. Not in this design.

## 7. Exact resources

Training: `3×512×10 + (128+32)×10 = 16,960`.
Recede: `10×2×2×4×16 = 2,560`.
Shared `L0` open-loop (recommended secondary): `10×4×16×16 = 10,240`.
**Env total 29,760.**

Imagined, naive (score every mode/step):
`10×2×2×4×16×16×16 = 655,360`.
If step-0 scores are computed once per arm and reused across modes:
`634,880`. Proposed cap **655,360** so a naive implementation stays
legal. Time cap **300 s** (H12/H13 wall ≈ 3 s at 348,160 imagined).

Standing limits (not authorization): 29,760 < 100,000 env; 300 < 900
experiment seconds; 300 < 3,304.945 remaining. Local CPU.

Incomplete runs save an honest partial and take label `incomplete`.

## 8. Toy-test results

`tests/test_h14_candidate_reuse.py`: 6 passed. Shared first library
across modes; no arm argument; fixed reuse; redraw changes after
step 0 and across states; first-index ties; DiD sign; missing and
duplicate seeds; duplicate states; nonfinite returns; meter overflow;
scoring API has no realized-return arguments. No MountainCar env.

## 9. Risks and unresolved decisions

- Physics and the 76M seed block are not frozen here.
- Include or drop the 10,240 shared open-loop steps.
- Cap imagined at 655,360 versus 634,880.
- Whether first-lock logging of later obs/scores is mandatory
  (recommended) or deferred.
- Practical margin 0.0 versus a nonzero threshold.
- H13 recede numbers remain confounded; do not use them to pick
  physics or to retune.

## 10. Lock recommendation

The design is **feasible and identifiable for question C**. It is
**not** locked. A separately reviewed protocol may freeze physics,
seeds, the 29,760 / 655,360 / 300 caps, and the DiD rule. This
document is not that lock. Do not create an allocation. Do not
execute.
