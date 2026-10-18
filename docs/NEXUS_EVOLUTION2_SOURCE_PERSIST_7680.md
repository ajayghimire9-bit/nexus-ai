# Evolution-2.8 — 7680-step source persist grant

Branch `cursor/evolution2.8-source-persist-7680` from
`6d8f31b47b3a76628ec323654144234b58e298d2`.

**Approval (not inferred from continue):** config
`325cd42b99bd4ff03d7a993bda71272933bd9ed0644103cd55274ab2303a9c76`,
`env_cap=7680`.

Scientific purpose: persist matched Pendulum/Acrobot family-default
train/val arrays so a later disposable residual-MLP fit clock can be
measured. This is not the v2 persist-versus-reset screen and cannot
be promoted to ten-bundle confirmation.

## Bound source

| family | task | physics | files |
|---|---|---|---|
| Pendulum | `pendulum_default` | (10, 1, 1) | bundle0–2 train/val |
| Acrobot | `acrobot_default` | (1, 1, 1) | bundle0–2 train/val |

Closed confirmation, lookahead unused, and H17 keys are rejected.
`pendulum_default.train_split` is historically labeled
`confirm_pendulum`; the physics key is the occupied source default,
not g=8.3/12.1.

Train and val env-seed blocks are disjoint. Writes are atomic
`.npz.tmp` → replace. Duplicate or leftover files abort. Time cap
300 s. Hard step cap 7680. No model training.

H16 scientific ledger remains **305.842 / 3294.158**.
