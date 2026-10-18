# Evolution-2.21 — executable method-sensitive scoring

Development fixtures only. **Not science.** E2.17 stays inconclusive.
Grant consumed. No collection. No new holdout named.

## Isolation

Hidden-feedback isolation now tracks **return provenance**, not variant
fingerprints. A planner may be trained and later selected for hidden
evaluation. Hidden-physics returns must not become training scores.

## Executable scoring

`MethodSensitiveHiddenEval` plus `corrected_hidden_scores()` call
`decide()` on the **method-selected** planner. Unit scores use a
`FrozenRevealedScale` locked from revealed returns before any hidden
call. Persist and reset start from the same RNG and tie order; random
and evolution remain separate equal-budget controls.

Fixture path PASS: forced-selection swaps change scores; identical
selections match and cache; logical charges are 4/method; hidden
returns cannot enter training. No Gymnasium.

## Screen comparison (planning only)

E2.17 wall 22.027 s / 17,280 steps and E2.9 1.215 s / 6 fits are
planning evidence, not proof of a new run.

| Screen | Upper steps | Fits | df | Bonferroni t | Planned wall |
|---|---:|---:|---:|---:|---:|
| n=3 | 24,480 | 6 (measured) | 2 | 9.925 | 31 s from E2.17 scale |
| n=10 | 81,600 | 20 (unmeasured) | 9 | 3.250 | 104 s from E2.17 scale; 4 s fit plan; 162 s E2.14 planner prior |

Both sit under standing 100,000 steps and 900 s if those linear
priors hold. n=10 has the usable power. Existing E2.17/E2.20 locks
are not rewritten.

## Recommendation

**n=10 prospective screen**, `env_cap=81600`, method-sensitive hidden
evaluation, new unused four-role physics, new grant. Twenty-fit wall
is still unmeasured. Do not reuse the consumed E2.17 grant, its
development, or H17. `continue` is not approval. `dispatch()` stays
refused.
