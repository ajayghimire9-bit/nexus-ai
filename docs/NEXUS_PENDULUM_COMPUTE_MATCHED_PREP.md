# Pendulum lookahead versus compute-matched H=16 — preparation

Branch `cursor/pendulum-compute-matched-h16` from `cceb4b1`. Zero new environment steps. Frozen FiLM checkpoints reused read-only. Confirmation physics unused. 16-candidate lookahead successor not retuned. Collection unauthorized.

Development physics `pendulum_ctx_dev*` with fresh seeds `15000000+`. Matched H=16 uses 48 candidates (768 imagined/step). Lookahead stays 16-candidate successor (771/step).

Primary: lookahead minus matched-H=16 200-step return, ten decoders, both visitors, margin 25.

Budget **180 s**, **24,000**, **18,468,000**, **0** updates. Config SHA256 `5a553ab3a3718c0ef4e3404a44e284f20bc0aebc09e15884e197d405ebf36673`. Protocol SHA256 `bcc77ee3c6e3fdd886d66840f07100dd7b9da1a61407e77be83fb31b569e3f24`. `authorized: false`.
