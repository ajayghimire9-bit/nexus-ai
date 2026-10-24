# Model-mismatch challenge — development results

Branch `cursor/seed-mechanism-mismatch`.
Protocol `578ba4d`. This results commit is separate.
Base `ff26a18`. Artifact hash
`83847d410e9344712ea8435fe1f53305a7a79e0a85738bec7ed0d8b8c5ce746d`.
Verifier `valid: true` on 108 cells; opened C/D/E IDs rejected.
Prior grids `92d6f19` and `ff26a18` were not rescored. Pilot, not
confirmation. Not learning-to-learn. Not AGI.

## Diagnosis (saved competence records, not a rescore)

On `e_threshold`, seed 20, the first missed evidence is the first
query, not a later disagreement about the same observations.

- Diagnostic: `ACT_1 → 0`. No catalogue candidate maps input 1 to 0,
  so the language empties and the run reports unresolved.
- Trained: `ACT_2 → 1`, then a second query, then `STOP_IDENTIFY toggle`.
- IG: `ACT_2 → 1`, `ACT_NEG → 0`, then the same toggle identification.

That stop is a catalogue singleton, not independently supported
identification. `e_delay` emptied on `ACT_2 → 0`, so trained/IG were
already unresolved there. DAgger copied IG’s “unique → identify”
rule. The locked stop now requires one later agreeing probe, and
every method may `STOP_UNRESOLVED` instead.

## Competence (own development trajectories)

All three training seeds passed: 7/7 success, 6 correct IDs, 1 correct
unresolved, 0 premature stops. Assessment therefore opened.

## Assessment (4 mismatch + 2 in-language controls × 3 seeds)

Controls `ctl_neg` and `ctl_toggle` were seen in development. They are
not independence claims.

| Method | Correct solutions | False ID | Unresolved (correct / failed) | Mean work |
| --- | ---: | ---: | ---: | ---: |
| trained | **6** | **0** | 12 / 0 | 201.7 |
| reset | 1 | 0 | 12 / 5 | 219.9 |
| shuffled | 0 | 0 | 12 / 6 | 166.6 |
| strongest fixed (diagnostic) | 6 | 9 | 3 / 0 | 227.2 |
| source frequency | 6 | 9 | 3 / 0 | 240.2 |
| information gain | 6 | 3 | 9 / 0 | 305.7 |

Mismatch (`abs_val`, `mod3`, `clip0`, `prev_plus`): trained reports
unresolved on all 12. Diagnostic and frequency name `noisy_add1` on
the three cheap identity-like tasks (9 false IDs) and leave only
`prev_plus` unresolved. IG does the same false ID on 3 of those 9.

Example, seed 20, `mm_abs`:

- Trained: `ACT_2 → 2`, `MEASURE → 0`, `STOP_UNRESOLVED`.
- Diagnostic: `ACT_1 → 1`, `ACT_1 → 1`, `ACT_0 → 0`, `STOP_IDENTIFY noisy_add1`.

The extra singleton probe is not enough when the leftover catalogue
member is cheap identity and the probe is another cheap `ACT`. MEASURE
empties that leftover. IG still sometimes skips MEASURE and identifies.

In-language controls: trained and diagnostic both identify `neg` and
`toggle` on all three seeds (6/6). Reset/shuffle mostly fail those.

## Costs

0.214 s wall, 0 model calls, frozen debit **0**. Product chat unused.
Metal unused. Informative-query features charge scoring work on every
method.

## Verdict

**useful learned investigation advantage** on this mismatch grid only:
same 6/6 control solutions as the strongest fixed method, 0 versus 9
false identifications, and 12 versus 3 correct unresolved reports.
Reset/shuffle collapse the controls, so the weights are used. The
advantage is refusing a catalogue name when MEASURE empties the
language, not a new learning procedure.

Do not rescore this grid, `ff26a18`, or `92d6f19`. Ranking stays
paused. Learning-to-learn remains unestablished.
