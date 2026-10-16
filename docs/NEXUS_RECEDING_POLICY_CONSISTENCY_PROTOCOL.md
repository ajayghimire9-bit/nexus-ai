# Receding-horizon policy consistency — locked protocol v1

Base `0aed2e3cb0283cc7c5ea60c9049bdf84ee51148a` (`cursor/action-conditioned-q-resume`). Branch `cursor/receding-policy-consistency`. Terminal-value and first-action Q score-correction are **closed**. This protocol does not edit those files, refit those readouts, or reopen confirmation physics.

Frozen FiLM world models, encoders, saved contexts, H=16, 16 candidates, published pendulum reward, and all 120 checkpoints stay read-only.

## Question

Repeated receding replanning can change the action that a previously selected plan intended to take next. That change may be harmless (new search or a better local continuation) or associated with lower realized return than following the original plan.

**H-commit-beats-replan:** from identical restored source states, executing the H=16 selected 16-action sequence returns more than taking the same first action and then receding with fresh candidate draws, by mean ≥ 1 with a decoder-level 95% lower bound > 0.

**H-replan-beats-commit:** the reverse interval (mean ≤ −1 and upper bound < 0). Receding would then be the better 16-step controller on this screen.

**H-search-not-state:** first-action disagreement between two independent candidate sets at the same state matches or exceeds receding disagreement after the state changes. Search noise would then be sufficient to explain action changes; state-driven re-ranking would not be identified.

These are competing descriptions, not unique causes. Distinct trajectories can differ for several reasons at once.

## Offline diagnostic (no new steps)

Archived receding live traces already store per-step seeds, selected indices and actions. Reconstructing `candidate_sequences(seed)[index, 1]` versus the next live action measures **confounded** suffix mismatch: the next step uses a new candidate seed and a new state. Subsequent live reward is not the counterfactual of continuing the original suffix. That reconstruction cannot pass or fail H-commit-beats-replan.

Same-state search noise and state-driven re-ranking of a frozen candidate set require the paired collection below.

## Locked collection design (unauthorized)

Source only: eight `pendulum_context_train` physics, not development or confirmation. One new phase-0 reset per decoder and task (seeds `7000000+`). Two visitors per reset: student `(d+t) mod 5` and zero. Ten independently pretrained decoders are the statistical units. Average eight tasks then two visitors inside each decoder. Student seeds are not extra decoder replications.

At each restored state `s0`, draw candidate set `C` with a visitor-specific seed. Score `C` with the visitor's frozen H=16 planner (`base` scores only; V and Q unused). Select plan `π`. Independently draw `C2` at the same `s0` (search-noise). Then restore `s0` for each executed arm:

1. **Commit-16 (baseline):** execute `π` open-loop for 16 steps.
2. **Recede-same-set:** execute `π[0]`; at each later state re-score the remaining suffixes of the **same** 16 sequences (no new search); take the new first action.
3. **Recede-fresh (deployed receding):** execute `π[0]`; at each later state draw a new 16×16 set with action-independent seeds and replan. This is the current receding controller.
4. **Common-zero:** execute `π[0]`; continue with the decoder's zero-context receding planner using the same continuation seeds as recede-fresh. When the visitor is already zero, this arm is identical and is not re-collected.

Primary return is the **16-step** sum of published environment rewards. It is not a 200-step episode, not a Q/V score, and not a prediction error.

## Primary estimand and screen

Primary contrast: commit-16 minus recede-fresh, decoder n=10, Student-t 95%, df 9. Pass `open_loop_commitment_gain` only if the complete 160-cell grid is valid, mean ≥ 1, and lower bound > 0. Entirely negative with mean ≤ −1: `receding_replanning_gain`. Otherwise `replan_consistency_not_established`. Incomplete runs are `incomplete`. Do not change this screen after seeing results.

Secondary, cannot upgrade the primary label: commit minus recede-same-set; recede-fresh minus recede-same-set; recede-fresh minus common-zero; search-noise first-action switch rate at `s0`; state-driven switch (`π[1]` versus recede-same-set's first action at `s1`); recede-fresh switch at `s1`; per-task and per-visitor intervals. A high switch rate without a return gap is not harm. A return gap without a switch-rate difference is not identified as inconsistency.

Do not treat a difference between distinct trajectories as a unique causal explanation of the closed fresh-episode gap or of Q/V failure.

## Budget and authority

Hard cap **120 seconds**, **8,960** new real steps, **1,515,520** imagined transitions. Breakdown: commit 2,560; recede-same 2,560; recede-fresh 2,560; common-zero 1,280. Imagined: s0 scoring of `C` by six contexts 245,760; search-noise `C2` 40,960; recede-same suffixes 307,200; recede-fresh 614,400; common-zero 307,200. No new support. No Q/V refit. Local CPU only.

The exhausted 3,600-second standing session and the consumed Q one-runs are unmodified and are not this budget. Collection is unauthorized until a new explicit human approval binds this configuration hash. The committed allocation has `authorized: false` and `runs: 0`.

## Tests and execution

Tests must lock suffix-shift identity, search-noise versus same-set suffix, label rules, seed disjointness from closed Q/commitment blocks, unauthorized collection, preservation of Q protocol hashes, and offline live-mismatch reconstruction without environment steps. They must not collect the registered grid.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_receding_policy_consistency.py tests/test_receding_policy_consistency_feasibility.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_receding_policy_consistency.py --feasibility
PYTHONPATH=src:.deps python3 scripts/run_receding_policy_consistency.py
# Collection is blocked until a fresh approved allocation is committed:
PYTHONPATH=src:.deps python3 scripts/run_receding_policy_consistency.py --execute
```

architecture_change_authorized: false
authorized: false
runs: 0
horizon: 16
n_candidates: 16
time_cap_s: 120
env_cap: 8960
model_cap: 1515520
score_correction_closed: true
