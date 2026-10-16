# CartPole lookahead versus H=3 on the unsaturated holdout — preparation

Branch `cursor/cartpole-lookahead-sat-h3` from `18ed8e4`. Zero new environment steps. Same six-task split `a69833ab38a34ab4`. Ceilinged tasks kept. H=3 was not retuned. Collection unauthorized.

Holdout: (13.2, 0.27, 0.23), (15.6, 0.25, 0.28), (15.4, 0.27, 0.20), (15.5, 0.30, 0.28), (16.0, 0.34, 0.20), (13.8, 0.31, 0.27).

Primary: lookahead minus H=3 episode return, ten training seeds, six tasks, margin 25.

Budget **300 s**, **72,800**, **4,380,000**. `authorized: false`.
