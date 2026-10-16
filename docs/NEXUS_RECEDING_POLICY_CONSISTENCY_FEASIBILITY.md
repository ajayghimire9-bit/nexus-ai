# Receding-horizon policy consistency — offline feasibility

Base `0aed2e3cb0283cc7c5ea60c9049bdf84ee51148a`. Branch `cursor/receding-policy-consistency`. Artifact `artifacts/receding_policy_consistency_feasibility.json`. Zero new environment steps. Collection unauthorized. Score-correction closed.

## Archived live suffix mismatch (confounded)

On stored receding live traces, the next executed action differs from the previously selected plan's second action about half the time. That next action uses a **new candidate seed** at a **new state**. Subsequent live reward is not the counterfactual of continuing the original suffix. Development outcomes were not used to choose features, seeds or the screen.

- Visited-commitment development, 2,940 steps, ten decoders: mismatch **0.518 [0.494, 0.543]**. Mean next reward given switch −4.73 versus stay −4.48.
- Action-conditioned development, 2,940 steps, ten decoders: mismatch **0.510 [0.485, 0.535]**. Mean next reward given switch −4.56 versus stay −4.67.

Those two reward comparisons are descriptive and opposite in sign. They do not identify harm. They motivate a same-state paired collection.

## Synthetic lock

Shifting a 16×16 candidate set left preserves the original plan tail. Two independent draws can disagree on first action (search noise). That disagreement is not the same measurement as re-ranking the same suffixes after the state changes.

Checkpoints: 120 verified, 0 missing, 0 mismatched.

## Proposed collection (not authorized)

Primary: commit-16 minus recede-fresh 16-step return on eight source physics, 160 cells, decoder n=10, mean ≥ 1 and lower bound > 0. Strong baseline: execute the already selected H=16 sequence. Search-noise switch at `s0` and same-set receding are secondary.

Budget **120 s**, **8,960** real steps, **1,515,520** imagined transitions.
