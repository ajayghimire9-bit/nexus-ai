# Capacity-matched first-action Q — locked protocol v1

Base `a833a2c8f128a6c5edc76b28f411eba5afff0890` (`cursor/first-action-value-learning`). Branch `cursor/capacity-matched-first-action-value`. This protocol precedes any new environment collection, fitting or development evaluation. World models, context encoders, the frozen 78-coefficient sequence-value readout, H=16 and 16 candidates stay unchanged. The failed 15-coefficient linear Q remains a closed historical result.

## Question

The 15-coefficient linear first-action Q did not beat frozen H=16 on development first-action 64-return: **−3.535 [−9.840, +2.769]**. Source-fit RMSE was about 70; development RMSE 107.546. Sequence-value V uses 78 coefficients (77 polynomial observation/context coordinates plus intercept). The linear Q therefore did not test aligned labels at V's feature capacity.

**H-capacity-matched-Q:** an 81-coefficient ridge Q that reuses V's exact 77 polynomial coordinates, plus three first-action indicators and an intercept, trained only on source first-action-plus-common-zero 64-step returns, will raise actual selected first-action 64-step return on fresh development visited states relative to unchanged H=16.

**H-capacity-still-insufficient:** the same screen fails, so the previous miss was not merely the 15-coefficient restriction. In that case this terminal-value score-correction branch closes. Do not enlarge the readout or tune closed data.

**H-no-decision-gain:** better source prediction cannot pass the screen. Prediction error is reported separately.

## Estimator, features and regularization

One ridge Q per independently pretrained decoder. Observation/context coordinates are the **same 11 inputs** used by sequence-value V (observation 3 + frozen context 8). Polynomial expansion is the **imported** `terminal_value.polynomial_features` map: the 11 linear terms plus the 66 upper-triangular products, **77** non-intercept coordinates. Concatenate three one-hot first-action indicators. Add an unpenalized intercept. **81 coefficients.** Do not change V's feature definition, V's frozen weights, or V's own mean/scale. The new Q has its own source-only mean/scale on its 80 non-intercept features; floor 1e-8; ridge λ=**1.0** on those 80 weights, intercept unpenalized — the same ridge convention as V, prespecified, not chosen from source CV or development outcomes.

Targets are the actual 64-step return of a forced first action followed by 63 zero-context replanning steps. Features use the **actual** restored observation and the frozen context vector, never imagined endpoints. The same physical source state is labeled under all six frozen contexts; the continuation policy is always that decoder's zero-context planner, so labels do not depend on scoring context.

### Effective sample size and identifiability (locked before collection)

Per decoder, the design stacks 8 source tasks × 6 contexts × 3 actions = **144 rows**. There are only **24 distinct (task, action) labels**. Repeated context rows are not independent targets. Unique observations = 8; unique (observation, context) pairs = 48. The three action dummies sum to the intercept, so the unregularized 81-column map is rank-deficient; ridge λ=1 makes the Gram matrix solvable.

This feature class is additive in action: Q(s,z,a) = poly(s,z)·w + b_a + intercept (after the locked standardization). At a fixed restored state the 16 candidates share (s,z), so action ranking cannot depend on the state. That is a property of the requested 81-coefficient map, not a silent extra interaction. The experiment tests this map against H=16, not a larger action-interaction model.

An offline feasibility audit must record row count, unique-label count, matrix rank, Gram condition, and the additive-ranking implication **before** any development step. It may probe historical source observations and frozen contexts. It must not inspect historical development returns, confirmation physics, or the previous Q weights for tuning.

Fit once on the eight source tasks with **new** source seeds, freeze the ten readouts to disk, then reload them before any development environment step. Development outcomes never enter the design matrix.

## Source and evaluation grids

Source: eight `pendulum_context_train` physics, one new reset per task (seeds 5000000+t). No new support; reuse saved source contexts. For each of ten decoders, restore that state and execute all three first actions with action-independent continuation seeds `5010000+64*t+k`. Unique source environment steps: 10×8×3×64 = **15,360**. These seeds are disjoint from the closed 15-coefficient Q collection.

Evaluation: three known development physics, not confirmation. New visited phase-50 states, two visitors per decoder/task (student `(d+t) mod 5` and zero), new seeds `5100000+`. Fifty live steps collect the state; all five students plus zero then score the same 16 candidates. Execute all three first-action+63-zero branches with action-independent seeds. Do not reuse first-action-value, source-scalar, visited-commitment or alignment-audit episodes.

At each restored state the three selectors see the same candidates and the same three measured first-action returns:

1. **H=16:** argmax of frozen original planner scores; take that candidate's first action.
2. **Sequence-value:** argmax of frozen original score plus survival×V(predicted endpoint); take that first action. V is the frozen 78-coefficient readout, not refit.
3. **Capacity-matched Q:** score each candidate by Q(obs, z, first_action); argmax over the 16 Q values (lowest index on ties); take that first action.

Primary return is the already measured 64-step common-zero continuation of the selected first action. It is not a deployed receding-horizon episode and not a student-policy continuation.

## Primary estimand, aggregation and screen

Decoder n=10, Student-t 95%, df 9, critical 2.262. Inside each decoder: average five student seeds, then the two visitor groups with equal weight, then the three tasks with equal weight. Candidates, states, students and episodes are not extra replications.

Primary contrast: capacity-matched-Q minus H=16 first-action 64-return. Pass `aligned_first_action_gain` only if the complete grid is valid, the mean is at least 1, and the lower bound is above 0. If the interval is entirely negative, `aligned_first_action_harm`. Otherwise `aligned_first_action_gain_not_established`. Incomplete, timed-out or invalid runs are `incomplete`, not scientific negatives. Do not change this screen after seeing results.

Secondary, cannot upgrade the primary label: Q minus sequence-value return; sequence-value minus H=16; source-fit RMSE; development Q RMSE against the three actual first-action returns; action agreement; task and visitor intervals; design rank/condition. The shared source fit is a common learned object; intervals are conditional on it.

## Decision after evaluation

If the registered gain label is assigned, record the result and propose a **separate** fresh-physics / full-episode confirmation protocol. Do not treat this visited-state first-action screen as control generalization.

If the complete run does not assign `aligned_first_action_gain`, **close this terminal-value score-correction branch**. Do not increase coefficient count, add layers, or retune on closed data. The next research plan should address receding-horizon policy consistency, action selection and online adaptation, under a new preregistered protocol.

## Budget and authority

Hard cap **150 seconds**, **29,880** new real steps, **7,741,440** imagined transitions. Breakdown: source labels 15,360; live collection 3,000; evaluation first-action branches 11,520. No new support. Local CPU only.

The previous standing session ledger (`artifacts/research_session_first_action_value_usage.json`) has **47.766 s** remaining, which is below this 150 s cap. This protocol **does not** reuse, reset or extend that session. Collection is unauthorized until a new explicit human approval binds this configuration hash and a session remainder ≥ 150 s. The committed allocation record has `authorized: false` and `runs: 0`. Tests and the offline feasibility audit are not the scientific simulation.

## Tests and execution

Tests must lock the imported 77-coordinate polynomial, 81 weights, source-only fitting, unique-label accounting, additive action ranking, restoration, identical candidates, action-independent continuation seeds, equal visitor weights, decoder-level intervals, complete-grid rejection, closed-seed rejection, unchanged H=16/sequence-value selection, and the distinction between `incomplete` and a complete negative/inconclusive label. They must not collect the registered grid. Feasibility may inspect historical source observations without development outcomes.

Commit protocol, implementation, tests and the unauthorized allocation before collection. Require a clean tree. Save the frozen fit before development steps. Refuse overwrite. On timeout, save an honest partial capture. After a complete authorized run, audit arithmetic from raw traces without refitting.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_capacity_matched_q.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_capacity_matched_q.py --feasibility
PYTHONPATH=src:.deps python3 scripts/run_capacity_matched_q.py
# Collection is blocked until a fresh approved allocation is committed:
PYTHONPATH=src:.deps python3 scripts/run_capacity_matched_q.py --execute
PYTHONPATH=src:.deps python3 scripts/run_capacity_matched_q.py --audit
```

A pass would be a same-state first-action improvement under the registered continuation, not full-episode control, learning-to-learn or AGI. A miss would close this score-correction branch for now.

<!-- protocol-lock
starting_sha: a833a2c8f128a6c5edc76b28f411eba5afff0890
horizon: 16
n_candidates: 16
total_steps: 64
n_poly: 77
n_action: 3
n_weights: 81
ridge: 1.0
practical_margin: 1
time_cap_s: 150
env_cap: 29880
model_cap: 7741440
source_state_base: 5000000
reset_base: 5100000
primary: aligned_minus_h16_first_action_64
statistical_unit: decoder
authorized: false
architecture_change_authorized: false
score_correction_closes_if_gain_not_established: true
-->
