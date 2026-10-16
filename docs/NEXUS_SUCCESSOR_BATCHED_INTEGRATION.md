# Batched successor lookahead — controlled integration (engineering)

## Status

The opt-in batched successor scorer is now integrated for **new** Pendulum-family
experiments through the additive adapter `src/nexus/world/successor_batched.py`,
with the serial historical path untouched. `successor_batched.lookahead_first_action(model, obs, sequences)`
is a drop-in twin of `bellman_backup_control.lookahead_first_action`: same
signature, same `(action, q, preds[action])` triple, same 771 imagined
transitions, **17 model calls instead of 51** (the measured ~2.6× CPU scoring
speedup). `successor_batched.prepare(sequences)` builds the immutable reusable
candidate table once per candidate set.

## Why an additive adapter

The recorded parity artifacts pin the SHA-256 of
`src/nexus/world/bellman_backup_control.py` and `src/nexus/world/successor_search.py`;
editing either would invalidate committed provenance. Historical runners
(`bellman_backup_control`, `pendulum_compute_matched`, all family lookahead
screens) stay byte-identical and their recorded results remain reproducible.
New experiments import the adapter instead; the regression test
`tests/test_successor_batched.py::test_recorded_parity_provenance_still_binds_the_historical_hot_path`
fails if anyone later edits the historical hot path without deliberately
updating the recorded provenance.

## Evidence attached to the adapter

- Synthetic inputs, 30 frozen decoders: 160/160 actions/rankings, 51→17 calls,
  microtimings 2.53–2.61× (`NEXUS_SUCCESSOR_SEARCH_EFFICIENCY_RESULTS.md`).
- Archived observations with genuine saved student contexts: 2160/2160
  actions/rankings/numerics, 8 near ties (`NEXUS_SUCCESSOR_ARCHIVED_PARITY_RESULTS.md`),
  bitwise independent reproduction (`NEXUS_SUCCESSOR_ARCHIVED_PARITY_CLINE_RESCORE_RESULTS.md`).
- Full paired fresh episodes: 60/60 identical action sequences, reward/return
  deviation 0.0 (`NEXUS_SUCCESSOR_EPISODE_PARITY_CLINE_RESULTS.md`).

Parity is established on tested grids, not universally: float32 kernels can
differ across batch sizes on unseen inputs; any new family use requires its
own parity check. The adapter is Pendulum-family only; Acrobot/MountainCar
planner-based lookahead functions are not covered by this twin.

## Tests

`tests/test_successor_batched.py`: bitwise toy parity with the serial original
(actions, Q, chosen successor; 51 vs 17 calls at 771 transitions), immutable
candidate-table reuse across contexts, fail-closed rejection of stateful
models and malformed inputs, and the historical-hot-path provenance guard.
The relevant offline suite (this file plus the successor/parity suites)
passed **136 tests, 4 deselected** after the integration.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_successor_batched.py -p no:cacheprovider
```

No new environment episode, training update, control comparison, closed-split
access or budget consumption occurred in this step. Not learning-to-learn, not AGI.
