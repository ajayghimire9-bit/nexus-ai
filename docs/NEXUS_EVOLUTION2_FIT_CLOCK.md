# Evolution-2.9 — residual-MLP fit-clock preparation

Branch `cursor/evolution2.9-fit-clock` from
`d91df2dd5d2c3583baaf2acb374539a0b14c85d8`.
Does **not** rewrite v2, v2-pilot, or n=3. Does **not** collect.

Scientific purpose: measure wall-clock of **six** disposable residual
64×64 Adam 1e-3 20-epoch fits on the locked Evolution-2.8
family-default 1024/256 arrays. That is the missing n=3 fit cost. It
is not persist-versus-reset science and cannot be promoted to a
twenty-fit / n=10 confirmation. Weights are disposable. No control
evaluation. Zero new environment steps.

H16 scientific ledger remains **305.842 / 3294.158**.

## Approval (not inferred from continue)

A later or same-branch allocation may grant this clock only by citing
this configuration hash and setting:

| field | granted value |
|---|---|
| `env_cap` | **0** |
| `time_cap_s` | **300** |
| `n_fits` | **6** |

`25600` / twenty fits remain unauthorized. The standing grant alone
does not start training.

## Bound arrays

Exactly the twelve Evolution-2.8 files. Hashes are locked in
`evolution2.fit_clock`. Physics stay at occupied defaults
`(10, 1, 1)` and `(1, 1, 1)`. Closed confirmation, lookahead unused,
and H17 keys are rejected.

## Recipe

`nexus.world.train.train_world_model`, residual, hidden `(64, 64)`,
Adam `1e-3`, 20 epochs, batch 128, 1024 train / 256 val. Reuses the
existing trainer; do not open a second dynamics MLP.

## What this lock does not do

- No `collect_transitions` and no second persist.
- No n=10 bundle expansion and no v2 df=9 gate.
- No named holdout and no H17 unlock.
- No debit of the H16 scientific ledger.
- No reuse of disposable weights as confirmation residuals.
