# Mechanism competence gate — protocol

Isolated branch `cursor/seed-mechanism-competence` from
`cursor/seed-mechanism-l2l` `92d6f19`. Protocol committed before
scoring. The opened transfer assessment in `92d6f19` stays closed and
is not rescored. Closed API grids stay closed. Not confirmation. Not
AGI. Do not merge `main`.

## Audit of the failed scorer

The `92d6f19` policy could not represent the required behavior:

- Features ignored which queries had been asked and whether a query
  would still split the remaining language.
- Two decisions — “`ACT_2` would teach me something” versus “I already
  know its answer” — were not separated by a used/informative pair.
- Training rows dropped `STOP_*` and only rewarded chosen queries, so
  the fit copied the common first probe and never stopped.
- Development never ran the policy on its own trajectories.

## Fixes, all programmer-declared

1. Features now include remaining size, budget, last observation,
   per-query `used_*` since reset, and per-query `informative_*`
   (whether remaining hypotheses still disagree). Hidden IDs stay out.
2. Complete source trajectories supervise queries, off-actions,
   `STOP_IDENTIFY` and `STOP_UNRESOLVED`. const0/const7 source tasks
   teach unresolved stops. A source-only DAgger pass relabels the
   policy’s own prefixes with IG.
3. Development runs the learned policy on its **own** trajectories.
4. A shared redundant-query mask drops a repeat that cannot change the
   version space. It is given to every method and labeled
   `programmer_supplied`. Repeats remain legal when any remaining
   hypothesis would still disagree (stateful or cheap-vs-exact).

## Competence gate (required before transfer)

On development own-trajectories, every seed must:

- finish every identifiable task with `STOP_IDENTIFY` of the gold;
- finish outside-language tasks with `STOP_UNRESOLVED`;
- take no budget stops, no premature stops, no redundant repeats.

If any seed fails: verdict `training_failure`, assessment stays
**closed**. Do not open C/D/E.

## Resources

Standing local-CPU grant. No model calls. Frozen debit **0**. Cap
120 s. Pilot.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_mechanism_l2l.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_mechanism_competence.py artifacts/seed_mechanism_competence
PYTHONPATH=src:.deps python3 scripts/verify_seed_mechanism_competence.py artifacts/seed_mechanism_competence/seed_mechanism_competence.json
```
