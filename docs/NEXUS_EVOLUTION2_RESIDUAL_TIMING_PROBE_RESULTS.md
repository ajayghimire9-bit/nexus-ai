# Evolution-2 residual-MLP timing probe results

Status: **probe_complete**. Not a transfer result.
Parent protocol: `d64925784ecef7878785bee70e1af165703acfc9`.
0 env steps. 0 checkpoint writes. Holdout unnamed. H17 blocked.

Failed attempts 0.335 s plus complete wall 0.777 s are charged.
Ledger **306.954 / 3293.046**.

## Measured rates

Catalogue-faithful successor H=16 on **random** observations, 45
decisions / 67,095 imagined states per frozen file.

| Model | µs / imagined | v2 110,592,000 | v2-pilot 49,152,000 |
|---|---|---|---|
| Pendulum history decoder | 3.01 | 333 s | 148 s |
| Pendulum residual 64×64 | 2.95 | 326 s | 145 s |
| Acrobot residual 64×64 | 5.24 | 580 s | 258 s |
| Historical live Pendulum lookahead | 5.53 | 612 s | 272 s |

Acrobot residual is closest to the historical live rate. Pendulum
files were faster here; that does **not** replace the 68.146 s /
12,324,000 live measurement.

## What this does not decide

Source fitting of 20 residual MLPs is still unmeasured. Random
observations are not environment rollouts. Full v2 planning at the
Acrobot rate already uses most of 900 s. v2-pilot planning
(145–258 s) is more plausible and still not a collection
authorization.

No holdout was named. v2 hashes are unchanged.
