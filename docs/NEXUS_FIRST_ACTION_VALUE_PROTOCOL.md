# Source-trained first-action value — locked protocol v1

Base `ff2619315caeb24da6af5311b3cb33d104076c92` (`codex/action-value-alignment-audit`). Branch `cursor/first-action-value-learning`. This protocol precedes any new environment collection, fitting or evaluation. World models, context encoders, the frozen 78-coefficient sequence-value readout, H=16 and 16 candidates stay unchanged.

## Question

The recorded alignment audit found that the best 16-action sequence's first action loses **20.254 [11.382, 29.127]** against the best first-action-plus-zero-replanning branch. That is an objective/future-policy mismatch on a finite visited-state sample. It does not prove that a new estimator will help.

**H-aligned-Q:** a small source-only readout trained to first-action-plus-common-zero 64-step returns will raise actual selected first-action 64-step return on fresh development visited states, relative to unchanged H=16 scoring.

**H-sequence-V-still-better:** the frozen sequence-commitment correction remains at least as good as this aligned estimator on that same first-action return.

**H-no-decision-gain:** prediction of the aligned target can improve without a one-point, decoder-level first-action return gain. Prediction error cannot pass the screen.

## Estimator and labels

One linear ridge Q per independently pretrained decoder. Inputs: current observation (3), frozen context (8) and one-hot first action (3). Fifteen coefficients including an unpenalized intercept. Ridge λ=1 on the 14 non-intercept weights. Source-only mean/scale of those 14 features; floor 1e-8. No quadratic expansion, grid search, clipping or neural layers. This is smaller than the frozen 78-coefficient sequence V; the test is the **label**, not added capacity.

Training targets are the actual 64-step return of a forced first action followed by 63 zero-context replanning steps. Features use the **actual** restored observation and the frozen context vector, never imagined endpoints. The same physical source state is labeled under all six frozen contexts; the continuation policy is always that decoder's zero-context planner, so labels do not depend on scoring context. Repeated context rows are not extra independent examples.

Fit once on the eight source tasks, freeze the ten readouts to disk, then reload them before any development environment step. Development outcomes never enter the design matrix.

## Source and evaluation grids

Source: eight `pendulum_context_train` physics, one new reset per task (seeds 4000000+t). No new support collection; reuse the saved source contexts. For each of ten decoders, restore that state and execute all three first actions with action-independent continuation seeds `4010000+64*t+k`. Unique source environment steps: 10×8×3×64 = **15,360**.

Evaluation: three known development physics, not confirmation. New visited phase-50 states, two visitors per decoder/task (student `(d+t) mod 5` and zero), new seeds `4100000+`. Fifty live steps collect the state; all five students plus zero then score the same 16 candidates. Execute all three first-action+63-zero branches with action-independent seeds. Do not reuse source-scalar, visited-commitment or alignment-audit episodes.

At each restored state the three selectors see the same candidates and the same three measured first-action returns:

1. **H=16:** argmax of frozen original planner scores; take that candidate's first action.
2. **Sequence-value:** argmax of frozen original score plus survival×V(predicted endpoint); take that first action.
3. **Aligned Q:** score each candidate by Q(obs, z, first_action); argmax over the 16 Q values (lowest index on ties); take that first action.

Primary return is the already measured 64-step common-zero continuation of the selected first action. It is not a deployed receding-horizon episode and not a student-policy continuation.

## Primary estimand, aggregation and screen

Decoder n=10, Student-t 95%, df 9, critical 2.262. Inside each decoder: average five student seeds, then the two visitor groups with equal weight, then the three tasks with equal weight. Candidates, states, students and episodes are not extra replications.

Primary contrast: aligned-minus-H=16 first-action 64-return. Pass `aligned_first_action_gain` only if the complete grid is valid, the mean is at least 1, and the lower bound is above 0. If the interval is entirely negative, `aligned_first_action_harm`. Otherwise `aligned_first_action_gain_not_established`. Incomplete, timed-out or invalid runs are `incomplete`, not scientific negatives.

Secondary, cannot upgrade the primary label: aligned-minus-sequence-value return; sequence-value-minus-H=16; Q RMSE against the three actual first-action returns; action agreement. Task and visitor intervals are unadjusted sensitivity. The shared source fit is a common learned object; intervals are conditional on it and do not include fit uncertainty.

## Budget and authority

Hard cap **150 seconds**, **29,880** new real steps, **7,741,440** imagined transitions. Breakdown: source labels 15,360; live collection 3,000; evaluation first-action branches 11,520. No new support. Local CPU only.

Standing grant of 2026-10-16 in `AGENTS.md`: 900 s/experiment, 100,000 real steps, 3600 s/session. Conservative Codex leftover after the alignment audit is **174.408 s**. The 150 s cap is the smaller of the protocol cap and that leftover, and is inside the standing 900 s/100,000-step limit. This allocation does not authorize a second run, architecture expansion, confirmation physics or checkpoint replacement.

## Tests and execution

Tests must lock restoration, identical candidates, action-independent continuation seeds, source-only fitting, equal visitor weights, decoder-level intervals, complete-grid rejection, closed-seed rejection, reward sums, context fingerprints, and the distinction between `incomplete` and a complete negative/inconclusive label. They must not collect the registered grid.

Commit protocol, implementation, tests and this exact allocation before collection. Require a clean tree. Save the frozen fit before development steps. Refuse overwrite. On timeout, save an honest partial capture. After a complete run, audit arithmetic from raw traces without refitting.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_first_action_value.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_first_action_value.py
# Once, from the clean protocol commit:
PYTHONPATH=src:.deps python3 scripts/run_first_action_value.py --execute
PYTHONPATH=src:.deps python3 scripts/run_first_action_value.py --audit
```

A pass would be a same-state first-action improvement under the registered continuation, not full-episode control, learning-to-learn or AGI. A miss would say this linear aligned Q did not beat H=16 here; it would not recommend an architecture change.

<!-- protocol-lock
starting_sha: ff2619315caeb24da6af5311b3cb33d104076c92
horizon: 16
n_candidates: 16
total_steps: 64
n_weights: 15
ridge: 1.0
practical_margin: 1
time_cap_s: 150
env_cap: 29880
model_cap: 7741440
source_state_base: 4000000
reset_base: 4100000
primary: aligned_minus_h16_first_action_64
statistical_unit: decoder
architecture_change_authorized: false
-->
