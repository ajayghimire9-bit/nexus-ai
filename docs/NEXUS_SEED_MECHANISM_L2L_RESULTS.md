# Mechanism investigation policy — development results

Branch `cursor/seed-mechanism-l2l`.
Protocol `11b934d`. This results commit is separate.
Base `ebfd5b9`. Artifact hash
`5606f869222d62f9acb0b8b62357756b2ab5508444e96d8ba998f014e5b4e4fb`.
Verifier `valid: true` on 132 cells; both tampers rejected. Closed API
grids were not rescored. Pilot, not confirmation. Not AGI. Coding
interface stays paused.

## What was tested

A compact linear policy chooses `act` / `RESET` / `MEASURE` / stop on
executed hidden mechanisms. The full hypothesis language is the version
space. Shortlist agreement is not identification. Ties are randomized.
Task hypotheses and traces reset every episode. Only frozen weights
persist.

IG source traces are **training supervision**. They are not assessment
features.

## Headroom (development, 6 tasks)

| Method | Success | Mean work | Mean oracle | Mean scoring |
| --- | ---: | ---: | ---: | ---: |
| information gain | 6 / 6 | 100.0 | 2.33 | 96.0 |
| fixed diagnostic | 6 / 6 | 4.0 | 2.00 | 0 |
| source frequency | 6 / 6 | **3.33** | 1.67 | 0 |
| random | 6 / 6 | 5.33 | 3.00 | 0 |

The locked numeric gate fired (`work_spread = 30`) because IG scoring
is expensive. That is not the intended headroom. Every cheap fixed
policy already solves development, and source-frequency is cheaper
than IG's environment cost (oracle+acts). A learned policy cannot beat
that by skipping scoring: frequency already skipped it. The run still
trained because the committed spread rule fired. Do not treat this as
a reason to retune the gate and rescore.

## Assessment (6 tasks × 3 seeds = 18 / method)

| Method | Success | Correct ID | Unresolved OK | Wrong ID | Premature | Mean work |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| trained | 6 / 18 | 0 | 6 | 0 | 0 | 16.0 |
| reset | 6 / 18 | 0 | 6 | 0 | 7 | 5.44 |
| shuffled | 6 / 18 | 0 | 6 | 0 | 0 | 10.67 |
| strongest fixed (frequency) | **15 / 18** | **12** | 3 | 3 | 0 | **3.67** |
| source frequency | 15 / 18 | 12 | 3 | 3 | 0 | 3.67 |
| information gain | 15 / 18 | 12 | 3 | 3 | 0 | 100.89 |

All six trained successes are excluded-family budget timeouts
(never naming a hypothesis). That is not identification skill.

| Split | trained | strongest fixed | verdict |
| --- | ---: | ---: | --- |
| C within-family (`add4`, `count2`) | 0 / 6 | 6 / 6 | negative |
| D composition | 0 / 6 | 6 / 6 | negative |
| E excluded (`delay`, `threshold`) | 6 / 6 unresolved | 3 / 6 | inconclusive |

Frequency wrongly named 3 / 6 excluded episodes. Trained named none.

## What persisted and what reset

Persisted: three frozen weight hashes
`466a72b8…`, `200fb952…`, `e85bef6c…` (22 supervised IG steps each).
Reset every task: version space, transcript, caches. No capsules.

Source retention: trained 0 / 12, IG 12 / 12. Later fitting did not
preserve source identification because the scorer never stops.

## One investigation

`c_add4`, information gain, seed 20:

1. `ACT_2` → 6
2. `ACT_1` → 5 (IG tie)
3. `STOP_IDENTIFY` → `add4`

The matched trained episode issued `ACT_2` eight times and hit the
budget. Source IG almost always starts with `ACT_2`; the linear fit
copied that query and was not supervised to stop.

## Costs

0.091 s wall, 0 model calls, frozen debit **0**. Product chat unused.
Metal unused. RSS parent 38.4 MiB. Process local CPU only.

## Verdict

**negative.** Parameter updates occurred and are verified. They did
not produce a useful learned investigation advantage. Within-family
and composition transfer are negative. Excluded-family “success” is
never-identifying. Frequency already solved development. Pilot n=3
seeds. Not learning-to-learn.

## Next

Do not rescore this grid or reopen API apply-modes. A later family
needs an **accuracy** gap for cheap fixed policies, not an IG scoring
bill. Broader ranking stays paused.
