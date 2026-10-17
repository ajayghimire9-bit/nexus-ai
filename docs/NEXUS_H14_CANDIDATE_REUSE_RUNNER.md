# H14 candidate-reuse runner — implemented, collection unauthorized

Implementation branch `cursor/h14-candidate-reuse-runner` from locked
prep `05542bb17da0e6f2af9075dce4ea97c135744e67`. The scientific design
in `NEXUS_H14_CANDIDATE_REUSE_PROTOCOL.md` is unchanged. Collection
remains unauthorized (`authorized: false`, `runs: 0`).

This document is not a result. Not learning-to-learn, not AGI.

## Implementation architecture

The locked helpers stay in `src/nexus/world/h14_candidate_reuse.py`.
Execution logic is isolated in
`src/nexus/world/h14_candidate_reuse_runner.py` so frozen H10–H13
files and the locked yaml/protocol/allocation are not edited.

`execute()` loads the locked config, then `require_allocation`. That
check runs before any training import, environment constructor, or
collection. The default CLI still only prints `prep()`.

## Locked scientific invariants

- Config `df155e89b8a4810bdbf04cfc121e93de7c9900235a440057dd66f7128459f81a`
- Protocol `1005e12568f3457f32638f9c7a08b0c29c7090785bf1085d097054224a012c1b`
- Allocation `4155621de732cdc9b9a6cda3d478c3f6aab89693be6cb430ca10a350253cff51`
- Physics `(0.0023, 0.0019, 0.065)` via `mcc_candidate_reuse_v1`
- Seeds `76,000,000+`, shared L0, no arm term
- Primary `D_s = (R_mt_fixed − R_sc_fixed) − (R_mt_redraw − R_sc_redraw)`
- Caps **300 s / 29,760 / 655,360**, no step-0 score cache

Training copies the frozen H10 residual recipe: three sources × 512,
source RMS pretrain, 128+32 target, target RMS, 20 epochs, residual
2×64, Adam 0.001. Scratch sees the same target data and create seed.

## Guarded metering

`GuardedMeter` reserves before every simulator action and every
imagined batch. If `used + n > cap`, the operation does not start.
Attempted and interrupted counts are stored. Reserved-but-failed
steps stay counted. An incomplete grid cannot receive a success
label.

Collection uses a preflight of the exact requested length, then the
inherited collector, then a length check. The collector’s own loop
stops at `n_transitions` env steps. Resets are not counted, matching
the locked H12 semantics.

## Reset and candidate sharing

Every controller and every L0 open-loop candidate starts with
`env.reset(seed=state_seed)`. Observation identity is required.
If `env.unwrapped.state` exists, that vector must also match.
Modes do not transfer visited states.

At `t=0`, all four arm/mode conditions score the same L0. Fixed mode
rescores that complete matrix at every decision. Redraw mode draws
the locked `(seed, state, step)` matrix for `t ≥ 1`. Both arms see
the same proposal. Planners never receive realized counterfactual
returns.

## Artifact schema

Future authorized output is `artifacts/h14_candidate_reuse.json`.
Each controller step stores the locked `TRACE_FIELDS`. Shared L0
open-loop actual returns and per-candidate reward traces are stored
once per state. Optional one-step residuals use the first imagined
next from the already-budgeted score batch versus the executed next
observation. Later-state counterfactual regret is not computed.

Registered statistics reconstruct from the saved cells without
retraining or resimulating.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_h14_candidate_reuse.py tests/test_h14_candidate_reuse_runner.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_h14_candidate_reuse.py
```

`--execute` must raise `PermissionError` before training or
environment creation.

## Remaining risks

The inherited collector is not instrumented per inner `env.step`.
The wrapper reserves the declared `n` and rejects a drifted length.
A hypothetical collector that stepped more than `n` while returning
`n` rows would be a collector bug; the current collector does not
do that.

Hidden-state identity is checked only when the simulator exposes
`.state`.

## Readiness

The runner is ready for a **separate** one-run authorization. This
branch does not authorize or execute H14.
