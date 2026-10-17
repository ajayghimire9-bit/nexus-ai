# H16 same-state library — locked, collection unauthorized

Source-only lock on `cursor/h16-same-state-library-protocol-lock` from
feasibility `929c93c`. `authorized: false`, `runs: 0`. No training,
no MountainCar environment, no collection. H14 and H15 stay closed.
Not a result. Not learning-to-learn, not AGI.

## Locked objects

| Object | SHA256 |
|---|---|
| `configs/mcc_same_state_library.yaml` | `e71b0053331afa39db5b368510c8524d23e454fb490a2bde57e72ac39f32834c` |
| `docs/NEXUS_H16_SAME_STATE_LIBRARY_PROTOCOL.md` | `f757e8a8e1f08d0b5abeb7cffa84071a79e1c5e93ded89b6817fe25e8f7fcea7` |
| `configs/mcc_same_state_library_allocation.json` | `02d4680d308ad17384ecd148ce48b7e319cffa4710be8304165ebc847d7474fd` |

Holdout `mcc_same_state_library_v1` counter 0 / index
`16634735916735444846` selects **(0.0015, 0.0014, 0.055)**. Occupied
H10–H15 and source keys are excluded. The rule reproduces the tuple.

## Readiness

Protocol is locked. A guarded runner is **not** implemented.
`execute()` refuses without a later one-run allocation and, even if
authorized, raises that collection is not implemented on this branch.
Empirical reset-plus-prefix identity remains a runner-time gate.

Caps: 84,000 real / 81,920 imagined / 300 s. Session ledger
unchanged: 303.777 s used, 3296.223 s remain.

Report `NEXUS_H16_SAME_STATE_LIBRARY_PROTOCOL.md`. Provenance
`artifacts/h16_same_state_library_provenance.json`.
