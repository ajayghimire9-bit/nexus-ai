# Model-mismatch challenge — protocol

Isolated branch `cursor/seed-mechanism-mismatch` from
`cursor/seed-mechanism-competence` `ff26a18`. Protocol committed before
scoring. Opened C/D/E cells (`c_add4`, `c_count2`, `d_*`, `e_delay`,
`e_threshold`) and `92d6f19` stay closed. Development analysis of
saved records is not a rescore. Not confirmation. Not AGI. Do not
merge `main`.

## Diagnosis (saved competence records)

On `e_threshold`, seed 20:

- Diagnostic first query: `ACT_1 → 0`. No language candidate produces
  0 from input 1, so the version space empties and the run reports
  unresolved.
- Trained and IG first query: `ACT_2 → 1`, leaving `{count, toggle}`.
  A second query makes `{toggle}` a catalogue singleton. They
  `STOP_IDENTIFY toggle`.

The first missed evidence is `ACT_1 = 0`, not a later disagreement
about the same observations. DAgger copies IG, and IG treats a
catalogue singleton as identification. That is premature when the
true mechanism can lie outside the language.

`e_delay` emptied immediately on `ACT_2 → 0`, so trained/IG already
reported unresolved there.

## Stopping rule under test

`identification_supported` is true only after the language is a
singleton **and** one later probe still agrees. `STOP_IDENTIFY` is
then available to every method. Until then, every method may run a
further unused probe or `STOP_UNRESOLVED`. The rule is
programmer-supplied and shared.

## Fresh challenge

| Role | IDs | Mechanisms |
| --- | --- | --- |
| Mismatch | `mm_abs`, `mm_mod3`, `mm_clip0`, `mm_prev` | `abs_val`, `mod3`, `clip0`, `prev_plus` (absent from the language) |
| In-language controls | `ctl_neg`, `ctl_toggle` | `neg`, `toggle` (seen in development; not independence claims) |

Score separately: correct solutions, false identification, unresolved
(correct vs failed), total work. Competence on development own
trajectories is required before this assessment opens.

## Resources

Standing local-CPU grant. No model calls. Frozen debit **0**. Cap 120 s.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_mechanism_mismatch.py tests/test_seed_mechanism_l2l.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_mechanism_mismatch.py artifacts/seed_mechanism_mismatch artifacts/seed_mechanism_competence/seed_mechanism_competence.json
PYTHONPATH=src:.deps python3 scripts/verify_seed_mechanism_mismatch.py artifacts/seed_mechanism_mismatch/seed_mechanism_mismatch.json
```
