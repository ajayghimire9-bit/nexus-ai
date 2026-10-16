# Acrobot lookahead versus H=16 — preparation

Branch `cursor/acrobot-lookahead-h16` from `5d2e616`. Zero new environment steps. New family. CartPole H=3 unused. Pendulum FiLM unused. Collection unauthorized.

Holdout `911ea726b6ed2111`: (0.95, 1.2, 0.8), (1.25, 1.35, 0.95), (0.75, 1.4, 1.4). Dense upright height, 200-step episodes, no goal termination.

Primary: lookahead minus H=16 episode return, ten training seeds, margin 25.

Budget **300 s**, **24,800**, **6,162,000**. `authorized: false`.
