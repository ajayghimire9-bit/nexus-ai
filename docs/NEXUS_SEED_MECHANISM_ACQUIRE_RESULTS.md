# Mechanism acquisition — development results

Branch `cursor/seed-mechanism-acquire`.
Protocol `11a08f6`. This results commit is separate.
Base `7ae2432`. Artifact hash
`5fab96735f4a1a59a887189e87c3392ea8bee2b8615f421ae1ad6933e5c8b99b`.
Verifier `valid: true` on 60 cells; opened prior IDs rejected.
Pilot, not confirmation. Not learning-to-learn. Not AGI.

## Three claims

Catalogue identification, predictive competence and exact mechanism
identification are scored separately. Exact identity in an unrestricted
environment is never awarded. Guessing the hidden generator is not
success. Twins such as `add1_twin` score as “consistent with add1;
exact identity unresolved.”

## Stage 1 — synthesis works

Primitives `add1`, `add2`, `mul2`, `neg`, length ≤ 2, shared by every
method.

| Method | Useful / 3 | Predictive | Catalogue useful | Exact | Guessed |
| --- | ---: | ---: | ---: | ---: | ---: |
| fixed_synthesis | **3** | 3 | 0 | 0 | 0 |
| catalogue_only | 0 | 0 | 0 | 0 | 0 |

The synthesizer reports `mul2|add1`, `add1|neg` and `neg|add1` as
scoped classes and predicts a fresh instance. The catalogue empties or
mis-identifies and cannot predict. Gate passed.

## Stage 2 — experience did not beat the synthesizer

Source competence 4/4 on three seeds. Holdout 3 compositions × 3 seeds.
Task solutions reset.

| Method | Useful | Predictive | Scoped | Exact | Interactions | Oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| trained | **9 / 9** | 9 | 9 | 0 | 60 | 78 |
| fixed_synthesis | **9 / 9** | 9 | 9 | 0 | 60 | 78 |
| composition_ig | **9 / 9** | 9 | 9 | 0 | 60 | 80 |
| catalogue_only | 0 / 9 | 0 | 0 | 0 | 57 | 75 |
| reset | 5 / 9 | 5 | 4 | 0 | 64 | 88 |
| shuffled | 1 / 9 | 1 | 1 | 0 | 53 | 76 |

Trained matches the fixed synthesizer on accuracy and interactions.
Reset and shuffle collapse, so the weights are used. Catalogue-only
never acquires a holdout composition.

## Costs

0.163 s wall, 0 model calls, frozen debit **0**. Product chat unused.
Metal unused.

## Verdict

**synthesis_procedure_works** on Stage 1. **fixed-baseline tie** on
Stage 2. The underlying synthesizer can compose primitives, test them
and predict new cases. Source-trained search does not improve
acquisition over that synthesizer. Learning-to-learn remains
unestablished.

Do not rescore this grid or `7ae2432` / `5575762` / `ff26a18` /
`92d6f19`. Ranking stays paused.
