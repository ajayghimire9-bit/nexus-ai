# Evolution-2.19 — persist-versus-reset policy-state diagnostic

Source-only. **Not a scientific experiment.** E2.17 stays
**inconclusive**. Grant remains consumed. No new environment steps,
fits, or physics.

Does not replace `AdaptiveProposer`, `PersistentAdaptive`,
`ResetAdaptive`, or `MethodSensitiveHiddenEval`.

## Code-level mechanism

`AdaptiveProposer` stores one 6-vector and updates it by normalized
linear SGD on public catalogue features
`(1, successor, balanced, h/16, successor*obs/16, h*n_actions/16)`.
`choose` is `argmax(w·x, -tie_rank)` and does not consume RNG.

`PersistentAdaptive` keeps those weights across tasks.
`ResetAdaptive.reset_task` rebuilds the inner proposer, then restores
`tie_rank` and `rng_state`. Only weights, update count, and
`feedback_seen` clear.

Protocol slots 0–1 are forced anchors (flat-IID-16, successor-IID-16).
Free training choices are slots 2–3, after two current-task updates.
Corrected hidden evaluation takes two `choose()` calls on the full
revealed set after training.

## Exact intervention (saved E2.17 revealed returns)

Same initial seed and tie order. Persist keeps family-1 weights. Reset
clears only those weights. Both then receive the same current-task
unit scores.

| Bundle | After intervention, unconstrained choose | After anchors, training sequence | Hidden 2-slot order |
|---|---|---|---|
| 0 | persist successor-16 vs reset flat-4 | identical | identical |
| 1 | persist successor-16 vs reset flat-16 | identical | persist (flat-16, successor-16); reset reversed |
| 2 | persist successor-16 vs reset successor-8 | identical | identical |

Weights change on every bundle (post-second-family L2 0.080, 0.074,
0.052). Forced anchors restore the same free-slot argmax. Earlier-task
state is still accessible: unconstrained first choice differs on all
three bundles, and hidden order flips on bundle 1.

## Mechanism tests (authored scores, not transfer)

Successor prior then conflicting flat current-task: persist free slots
stay successor-8/4; reset switches to flat-8/4. Neutral control stays
identical. Prior-only hidden order is successor-16/8 versus 8/16.

These are mechanism tests, not transfer evidence.

## Evaluator sensitivity

`MethodSensitiveHiddenEval` follows the selected planner. On the
prior-only fixture, persist scores 16.0 and reset scores 20.0. Logical
charges stay 4 per method. Physical cache hits apply. Hidden
development returns cannot enter training. Persist and reset keep the
same RNG/tie stream; other baselines may use their own seeds.

## Decision

**GO.** Memory-to-choice functions. Recommended next scientific
experiment: one new-physics n=3 persist-versus-reset screen with
method-sensitive hidden evaluation, matched persist/reset RNG, equal
logical hidden slots, physical cache hits, a new unused four-role
holdout, and fresh upper `env_cap=24480`. New grant required. Do not
reuse the consumed E2.17 grant or its development outcomes. Do not
unlock H17. Do not start Evolution-3.

`dispatch()` stays refused.
