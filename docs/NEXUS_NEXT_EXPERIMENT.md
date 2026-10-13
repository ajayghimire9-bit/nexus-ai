# Next NEXUS experiment (minimal, falsifiable)

Not AGI. Do not retune MAE 0.97 from V0.8.5–V0.8.9 confirmation. Do not start finance or a large architecture search.

## Comparison of directions

| | A. More CartPole WM adaptation | B. Frozen recipe on a second family | C. Meta-learn adaptation rules |
| --- | --- | --- | --- |
| Relation to “learn unfamiliar environments” | Weak: remaining work is CartPole-length/gravity noise | **Direct:** a new observation/action/reward structure | Direct in name, empty in practice without a working inner adapter |
| What we already know | Detector works; low-LR candidates miss 0.97 by ~3%; control CIs include 0; ABC↛D | Residual+H=3 **does** plan on CartPole (V0.7.3). **Never** measured on another family | V0.5 LinUCB failed on real PPO; V0.8.9 past tasks did not cut D’s data |
| Risk of theater | High: another gate/LR/cycle count | Medium: family 2 may be too hard at local compute | High: meta-fit noise from a 0-accept inner loop |
| Falsifiable cheaply? | Only with a **new candidate class**, not another 0.97 tweak | Yes: planning vs random on family 2 | Not until A or B produces an adapter that sometimes helps |

**Status after Pendulum transfer:** H=16 planning works vs random. Pre-registered **MAE-gated vs frozen failed** (`pendulum_transfer.json`, +29 includes 0). Ungated fine-tuning **did** beat frozen. A→B→C did **not** help D. **C (meta-learn adaptation rules) remains unjustified.**

**Primary direction now:** stop iterating MAE 0.97. If continued, pre-register a **control-based** commit rule on Pendulum H=16 vs frozen, n=10 — or a model-free PPO inner loop on two families. Do not start a large meta-learner, finance, or NAS.

CartPole physics variants are not “unfamiliar environments.” Continuing A on CartPole without a new candidate generator repeats V0.8.x.

Keep A only as a **stop-rule coda**: no new CartPole MAE-threshold, cycle-count, or detector-k experiments.

## Minimal experiment (B)

**Question:** Does the frozen V0.7 residual MLP (64,64) + H=3 random-shooting MPC beat a trivial controller on a **second Gymnasium family**, with the CartPole recipe frozen (no retune on family-2 confirm)?

**Suggested family (pick one, freeze before seeing returns):** Pendulum-v1 (continuous torque; discretize to 3 actions if the planner stays discrete) **or** Acrobot-v1 (already in-repo; V0.5 PPO was −500 at 8k, so this is a hard but honest test). Prefer Pendulum if we need a distinct obs/action structure from CartPole.

**Baselines (all paired, same eval seed):**

1. Random actions.
2. Family-2 heuristic if a standard one exists (Pendulum: energy / residual swing-up heuristic); else omit and say so.
3. Frozen CartPole-recipe WM + H=3 MPC trained on family-2 transitions (scratch WM, **same** hidden/horizon/candidates/objective as V0.7 freeze).
4. Negative control: CartPole-trained WM zero-shot on family 2 (must fail if the recipe is not magic).

**Budgets (pre-register):** train 1024 / val 256 transitions; 20 epochs; n=10 seeds if feasible, else n=5 and say so. Eval: 2 episodes, independent seed unused in V0.8.x. Report env interactions, wall time.

**Success (must all hold):**

- MPC vs random: seed-paired Δ CI **excludes 0** and Δ > 0.
- Protocol hash frozen before confirm; CartPole H, width, MAE 0.97 **untouched**.
- No claim of transfer from CartPole weights unless the zero-shot control is also reported.

**Failure (stop, do not “fix” with NAS):**

- MPC vs random CI includes 0, **or** MPC worse than random.
- Training diverges (NaNs) on >2/10 seeds.
- We change horizon/width after seeing family-2 returns.

If **failure:** the world-model stack is a CartPole planner, not a general learning engine. Do not add V0.8.10 CartPole online learning. Revisit whether a different inner problem (e.g. model-free PPO at V0.4 scale on two families) is the honest next step.

If **success:** then a **small A-on-family-2** test is allowed: low-LR + frozen MAE 0.97 on a shifted pendulum/acrobot, n=10, vs never-adapt. Success = paired return CI excludes 0. Failure = same as V0.8.9; then C remains unjustified.

## Explicitly out of scope

- Retuning `V085_MAE_RATIO`.
- New activations, transformers, ensembles-as-product.
- Meta-RL / PBT / population of agents.
- Finance, paper trading, V0.9 product work.
- Claiming learning-to-learn from RMS copy or from detector FPR=0.

## Commands (checkpoint)

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v089_checkpoint.py
# Do not run a family-2 benchmark in this checkpoint branch.
```
