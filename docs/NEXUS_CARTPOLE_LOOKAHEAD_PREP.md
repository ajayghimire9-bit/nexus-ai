# CartPole lookahead versus H=3 — preparation

Branch `cursor/cartpole-lookahead-h3` from `9800181`. Zero new environment steps. Pendulum confirmation outcomes were not used to choose H=3. Collection unauthorized.

Pendulum FiLM weights are not compatible with CartPole (`obs_dim` 4 vs 3, `n_actions` 2 vs 3). V0.7 already froze CartPole shooting at H=3 × 16. This protocol tests the lookahead mechanism against that frozen planner on unused CartPole physics `4bc1f5866ac6c753`.

Primary: lookahead minus H=3 episode return, ten training seeds, margin 25. Labels: `cartpole_lookahead_established`, `cartpole_lookahead_harm_established`, `cartpole_lookahead_not_established`, `incomplete`.

Budget **300 s**, **42,800** real steps max, **2,190,000** imagined max, frozen-recipe training of ten residual MLPs. `authorized: false`.
