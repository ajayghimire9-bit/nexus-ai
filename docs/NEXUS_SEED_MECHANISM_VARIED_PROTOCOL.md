# Varied-probe challenge — protocol

Isolated branch `cursor/seed-mechanism-varied-probes` from
`cursor/seed-mechanism-mismatch` `5575762`. Protocol committed before
scoring. Opened C/D/E and mismatch cells stay closed. Not confirmation.
Not AGI. Do not merge `main`.

The last mismatch grid left MEASURE as an untested habit. This study
adds the missing fixed baseline and a family where MEASURE, sequences
and twins are different problems.

## Missing baseline

`fixed_diagnostic_measure` follows the diagnostic order, then runs a
confirmation MEASURE whenever the language is a singleton and MEASURE
has not yet been charged. Oracle cost 3 is billed through
`apply_hidden`. Cost-aware information gain is a separate non-learned
baseline: it maximises language split per charged cost and uses a
cheap confirmation probe, not an automatic MEASURE.

## Fresh family

| Role | IDs | Mechanism | Evidence |
| --- | --- | --- | --- |
| Exposed by MEASURE | `vp_id0` | `id_exact0` | Cheap acts match `noisy_add1`; MEASURE empties |
| Survives MEASURE, sequence empties | `vp_mod2`, `vp_plus` | `mod2`, `plus_prev` | MEASURE leaves members. `ACT_1,ACT_0,ACT_2` empties `mod2`; diagnostic may still name `noisy_add1`. `plus_prev` empties on the diagnostic sequence. |
| Indistinguishable in budget | `vp_twin` | `add1_twin` | Observationally identical to `add1` |
| Ordinary in-language | `vp_add2`, `vp_neg`, `vp_count` | `add2`, `neg`, `count` | Cheap identification; MEASURE is unnecessary checking |

Ordinary tasks were seen as mechanisms in development, not as these
task IDs. They measure extra cost, not independence.

## Methods and scores

Trained linear policy (source IG + DAgger) versus reset, shuffle,
diagnostic, diagnostic+MEASURE, cost-aware IG, and vanilla IG.

Score separately: correct solutions, false identification, demonstrated
catalogue inconsistency (empty language, unresolved), unresolved
uncertainty (non-empty leftover, unresolved), and charged oracle cost.
Competence on own development trajectories is required before this
assessment opens.

## Resources

Standing local-CPU grant. No model calls. Frozen debit **0**. Cap 120 s.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_mechanism_varied.py tests/test_seed_mechanism_mismatch.py tests/test_seed_mechanism_l2l.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_mechanism_varied.py artifacts/seed_mechanism_varied
PYTHONPATH=src:.deps python3 scripts/verify_seed_mechanism_varied.py artifacts/seed_mechanism_varied/seed_mechanism_varied.json
```
