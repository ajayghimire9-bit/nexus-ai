# Evolution-2.14 — Receding stored-obs clock

Branch `cursor/evolution2.14-recede-clock` from `7699a35`.
Status: **DEVELOPMENT CLOCK — SCIENCE BLOCKED — 7680 NOT GRANTED**.

Walked 200 locked default-family observations through
`planner_adapter.decide` for both H=16 anchors on Pendulum and Acrobot.
No Gymnasium. No new steps. No new fits. Holdout unnamed.

H17 blocked. H16 ledger **305.842 / 3294.158**.

## Measured

| Quantity | Value |
|---|---|
| Decisions | 800 |
| Episode equivalents | 4 × 200 |
| Imagined | 1,210,800 |
| Wall | 2.305 s |
| Seconds per decision | 0.00288 |
| Episode planner prior | 0.576 s |
| 9,600-decision prior | 27.7 s |

This agrees with the E2.13 one-state catalogue prior (27.3 s). It is
still **not** a new-physics 9,600-step env-rollout clock.

## Unchanged blockers

Fresh total remains **17,280**. Imagined upper bound remains
**14,745,600**. `env_cap=7680` is refused. Source-fitting, holdout
naming, and scientific dispatch stay BLOCKED.

Next: a separately authorized persist-versus-reset run that cites
`8e90b74a`, names a four-role unused holdout, and sets `env_cap=17280`.
`continue` is not that approval. Protocol draft:
`NEXUS_EVOLUTION2_PERSIST_RESET_PROTOCOL.md`.
