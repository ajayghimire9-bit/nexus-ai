# Evolution-2.9 — residual-MLP fit-clock results

Branch `cursor/evolution2.9-fit-clock`. Protocol commit `656d631`.
Does **not** rewrite the locked protocol hash
`3846f4ecb4161455f8954e6ae363f47d43b873031fd38ea68118e0683393fd52`.

**Approval cited:** config
`277d7ba628fcd4e528b27bf4407ed45f9e41ec9051bd9e26b4baef33c6df0ff0`,
`env_cap=0`, `time_cap_s=300`, `n_fits=6`. Allocation `79e53592…`.

This is a development-pilot cost clock. It is not v2 confirmation, not
n=10, not persist-versus-reset science, and not a control result.

## Measured clock

Command: `PYTHONPATH=src:.deps python3 scripts/run_evolution2_fit_clock.py --env-cap 0 --n-fits 6`

| field | value |
|---|---|
| env_steps | 0 |
| n_fits | 6 |
| wall_s | 1.215 |
| cpu_s | 0.974 |
| mean_s_per_fit | 0.203 |
| v2_confirmation | false |
| hold_named | false |

| family | bundle | best_val | disposable path |
|---|---|---|---|
| pendulum | 0 | 0.00378 | `artifacts/evolution2_fit_clock_disposable/pendulum/bundle0.pt` |
| pendulum | 1 | 0.00253 | `artifacts/evolution2_fit_clock_disposable/pendulum/bundle1.pt` |
| pendulum | 2 | 0.00226 | `artifacts/evolution2_fit_clock_disposable/pendulum/bundle2.pt` |
| acrobot | 0 | 0.01106 | `artifacts/evolution2_fit_clock_disposable/acrobot/bundle0.pt` |
| acrobot | 1 | 0.02912 | `artifacts/evolution2_fit_clock_disposable/acrobot/bundle1.pt` |
| acrobot | 2 | 0.00598 | `artifacts/evolution2_fit_clock_disposable/acrobot/bundle2.pt` |

A second write raises `duplicate_or_partial_fit_clock`. H16 usage
`ff4c51e2…` is untouched at **305.842 / 3294.158**.

Twenty-fit / n=10 training was not run. Do not treat 6 × (20/6) as a
v2 fitting cost. Disposable weights are not confirmation residuals.
The historical E2.3 label `SOURCE_FITTING_UNAVAILABLE` still applies
to the twenty-fit v2 clock.
