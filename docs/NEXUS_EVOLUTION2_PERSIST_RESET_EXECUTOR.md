# Evolution-2.16 — Gated persist-versus-reset executor

The real executor is complete behind the existing authorization gate.
Development verification PASSES. Scientific execution stays **BLOCKED**.

Verified without collection:

- fresh budget **17,280** real steps (7,680 source + 7,200 revealed + 2,400 development)
- six matched new-physics residual slots planned, **0 executed**
- four equal-budget methods: persist / reset / random / evolution
- `TrustedEvaluator.hide_development` isolation
- `ReservationLedger` interruption accounting

`dispatch()` still hits the unnamed-holdout gate. Allocation remains
`authorized: false`, `env_cap: 0`. Config hash
`8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e`
is unchanged. H17 blocked. H16 ledger **305.842 / 3294.158**.

Runner-readiness verdict: **DEVELOPMENT_READY_SCIENCE_BLOCKED**.
