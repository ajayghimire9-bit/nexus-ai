# Tree-reuse lookahead versus frozen H=16 — preparation, not a result

Branch `cursor/lookahead-generalization-synthesis` from `57cff66`. Source-only synthesis is in `docs/NEXUS_LOOKAHEAD_GENERALIZATION_SYNTHESIS.md`. This file is the executable next-experiment lock.

Frozen MountainCar development checkpoints are reused read-only. Confirmation physics unused. MountainCarContinuous unused. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. No ridge Q. No terminal-value readout.

Primary: tree-reuse minus 16-candidate H=16 200-step dense-height return, ten training seeds, mean ≥ 25 and lower bound > 0.

Budget **180 s / 18,000 / 7,716,000 / 0 updates**. Imagined per step: H=16 **256**, tree-reuse **259**, lookahead **771**.

**Authorized: false.** `runs: 0`. Not a result. Not learning-to-learn. Not AGI.
