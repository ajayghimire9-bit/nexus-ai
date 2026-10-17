# H15 candidate-reuse confirmation runner — implemented, collection unauthorized

Implementation branch `cursor/h15-candidate-reuse-confirm-runner` from
locked prep `ff91a940f5a4ebca18f212942e8134c5ee6c22ee`. The scientific
design in `NEXUS_H15_CANDIDATE_REUSE_CONFIRM_PROTOCOL.md` is unchanged.
Collection remains unauthorized (`authorized: false`, `runs: 0`).

This document is not a result. Not learning-to-learn, not AGI.

## Implementation architecture

Locked helpers stay in `src/nexus/world/h15_candidate_reuse_confirm.py`.
Execution logic is isolated in
`src/nexus/world/h15_candidate_reuse_confirm_runner.py`. The H14 runner
is not pointed at the H15 yaml. Frozen H10–H14 files and the locked
H15 yaml/protocol/allocation are not edited.

`execute()` loads the locked H15 config, then `require_allocation`.
That check runs before any training import, environment constructor,
or collection. The default CLI still only prints `prep()`.

## Locked scientific invariants

- Config `bc263e69e3a57ae3bcb4c27616f0c4736deaf123dab6c0c3cb49311b3804c193`
- Protocol `4e5f7a5d0f55c6f183d1c78046597a99f5dfd8f788546a1d91c8270dad0116af`
- Allocation `210f3a631a3081152f63e7a6b4d53bf98a2b8e157be52e515a7c7b5a53e39362`
- Physics `(0.004, 0.0021, 0.05)` via `mcc_candidate_reuse_confirm_v1`
- Seeds `77,000,000+`, shared L0, no arm term
- Primary `D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`
- H15 labels only; H14 cells are never pooled
- Caps **300 s / 29,760 / 655,360**, no step-0 score cache
- Redraw stride remains `1000s+10k+t` (450 unique / 600 intended)

Training copies the frozen H10 residual recipe: three sources × 512,
source RMS pretrain, 128+32 target, target RMS, 20 epochs, residual
2×64, Adam 0.001. Scratch sees the same target data and create seed.

## Guarded metering

`GuardedMeter` reserves before every simulator action and every
imagined batch. If `used + n > cap`, the operation does not start.
The collector’s `make_task_env` path is wrapped so an extra inner
`env.step` fails before it executes. Incomplete grids receive only
`incomplete`.

## Artifact schema

Future authorized output is `artifacts/h15_candidate_reuse_confirm.json`.
Registered statistics reconstruct from saved cells without retraining
or resimulating.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_h15_candidate_reuse_confirm.py tests/test_h15_candidate_reuse_confirm_runner.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_h15_candidate_reuse_confirm.py
```

`--execute` must raise `PermissionError` before training or
environment creation.

## Readiness

The runner is ready for a **separate** one-run authorization. This
branch does not authorize or execute H15. H14 stays closed.
