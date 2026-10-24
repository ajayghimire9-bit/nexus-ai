# Mechanism competence gate — development results

Branch `cursor/seed-mechanism-competence`.
Protocol `13dfcac`. This results commit is separate.
Base `92d6f19`. Artifact hash
`e130dd828b8faa68a1f0c0b4e6ef5f41ce46f8c5533fcf16c3f6c6ac97e041b8`.
Verifier `valid: true` on 157 cells; tampers rejected. Prior transfer
grid `92d6f19` was not rescored. Pilot, not confirmation. Not AGI.

## Audit

The previous scorer could not represent the required behavior. Features
did not record which queries were used or whether a query would still
split the remaining language, so “`ACT_2` would teach me something”
and “I already know its answer” were not separable. Training omitted
stops. The policy’s own development trajectories were never scored.

This revision adds used/informative features, complete-trajectory
targets including `STOP_IDENTIFY` / `STOP_UNRESOLVED`, source-only
DAgger, and a programmer-supplied redundant-query mask shared by every
method. Repeats stay legal when any remaining hypothesis would still
disagree.

## Competence (own development trajectories)

All three training seeds passed: 7/7 success, 6 correct IDs, 1 correct
unresolved, 0 budget stops, 0 premature, 0 redundant repeats.
Assessment therefore opened. The policy now stops.

Example own-trajectory: `dev_add3` → `ACT_2` yields 5 → `STOP_IDENTIFY add3`.

## Assessment (6 tasks × 3 seeds)

| Method | Success | Correct ID | Unresolved OK | Wrong ID | Mean work |
| --- | ---: | ---: | ---: | ---: | ---: |
| trained | 15 / 18 | 12 | 3 | 3 | 197.7 |
| reset | 7 / 18 | 1 | 6 | 0 | 253.2 |
| shuffled | 6 / 18 | 0 | 6 | 0 | 178.1 |
| strongest fixed (diagnostic) | **18 / 18** | 12 | **6** | 0 | **186.3** |
| source frequency | 18 / 18 | 12 | 6 | 0 | 211.3 |
| information gain | 15 / 18 | 12 | 3 | 3 | 291.7 |

| Split | trained | strongest fixed | verdict |
| --- | ---: | ---: | --- |
| C within-family | 6 / 6 | 6 / 6 | fixed-baseline tie |
| D composition | 6 / 6 | 6 / 6 | fixed-baseline tie |
| E excluded | 3 / 6 | 6 / 6 | negative |

Trained matches IG, including the same three excluded wrong IDs.
Diagnostic/frequency correctly leave E unresolved. Reset/shuffle
collapse, so the weights are used, but they do not beat the strongest
fixed policy.

## One assessment trajectory

`c_add4`, trained: `ACT_2 → 6`, `ACT_0 → 4`, `STOP_IDENTIFY add4`.

Persisted: three frozen hashes. Reset every task: version space,
transcript, caches.

## Costs

0.141 s wall, 0 model calls, frozen debit **0**. Product chat unused.
Metal unused. Informative-query features charge scoring work on every
method.

## Verdict

**fixed-baseline tie** on within-family and composition; **negative**
on the excluded family; overall **negative** versus the strongest
fixed diagnostic (15/18 vs 18/18). Competence is a training success,
not a learning-to-learn success. Do not rescore `92d6f19` or this
grid. Ranking stays paused.
