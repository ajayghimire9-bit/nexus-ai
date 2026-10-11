# NEXUS AI

Experimental research system for self-evolving neural intelligence. Long-term aim: investigate whether models can improve their own learning mechanisms, architectures, and problem-solving through measured experiments — including a later financial application (NEXUS Alpha).

This is **not** a chatbot wrapper. Completing the roadmap is **not** AGI.

## Status

**NEXUS Research V0.5 (code + tests):** budget-aware experiment controller (random / ε-greedy / LinUCB), validated research actions, and PPO dummy-reset loss masking. LinUCB is a **contextual bandit**, not meta-RL.

**NEXUS Research V0.4 (measured, retained):** Acrobot architecture evolution and a longer retrain of the failing CartPole seed. Those numbers are still the last full PPO/evolution benchmarks.

No self-improving system, profitable trading system, or AGI has been demonstrated.

See `docs/NEXUS_PROGRESS.md` for the V0.5 test log and the tiny equal-budget controller comparison (LinUCB did **not** beat random there).

### Measured local runs (2026-10-11, CPU) — V0.4 retained

CartPole-v1 is solved at mean return ≥ 475 on a given eval set.

| Run | Setup | Timesteps | Eval |
| --- | --- | --- | --- |
| PPO CartPole seed 1 | separate trunks, 10 epochs | 249 856 | **500.0** vs random 22.4 |
| PPO CartPole seed 2 | same | 249 856 | **409.5** vs random 26.2 (**not solved**) |
| PPO CartPole seed 2 (retrain) | same recipe | **399 872** | **500.0** vs random 26.3 |
| PPO CartPole seed 3 | same | 249 856 | **500.0** vs random 21.5 |
| Multi-seed @ 250k | seeds 1,2,3 | 249 856 | mean **469.8**, std 42.7 |
| PPO Acrobot | separate agent | 249 856 | **−83.25** vs random −500 |
| CartPole evolution | 49 152 / candidate | 49 152 | all gen-1 candidates **500** (ceiling) |
| **Acrobot evolution** | 81 920 / candidate, 2 gen × 4 | 81 920 | best **−75.2** (tanh 64-64, separate trunks, gen 1) |

Seed 2 **did** solve when given more steps, but training was unstable. 250k is not a reliable CartPole budget across seeds.

The ε-greedy selector (`nexus select`) only **proposes** a mutation of comparable stored specs. `nexus research` runs a frozen-budget loop; the controller cannot change caps or evaluation rules.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

If `venv` creation is blocked, install into a local folder:

```bash
python3 -m pip install --target .deps torch numpy gymnasium pyyaml pytest
PYTHONPATH=src:.deps python3 -m pytest tests
PYTHONPATH=src:.deps python3 -m nexus.cli train --config configs/ppo_cartpole.yaml
```

## Commands

```bash
# PPO baseline (CartPole-v1, default 250k steps)
PYTHONPATH=src:.deps python3 -m nexus.cli train --config configs/ppo_cartpole.yaml

# Second independent task
PYTHONPATH=src:.deps python3 -m nexus.cli train --config configs/ppo_acrobot.yaml

# Independent eval of a checkpoint
PYTHONPATH=src:.deps python3 -m nexus.cli eval --checkpoint checkpoints/ppo_latest.pt

# Architecture mutation loop (CartPole saturates; use Acrobot to rank)
PYTHONPATH=src:.deps python3 -m nexus.cli evolve --config configs/evolution.yaml
PYTHONPATH=src:.deps python3 -m nexus.cli evolve --config configs/evolution_acrobot.yaml

# Activation screen + short matched training
PYTHONPATH=src:.deps python3 -m nexus.cli activations --config configs/activations.yaml
PYTHONPATH=src:.deps python3 -m nexus.cli activations --config configs/activations.yaml --expr

# Architecture-genome transfer (matched seeds; weights not copied)
PYTHONPATH=src:.deps python3 -m nexus.cli transfer --config configs/evolution_acrobot.yaml

# Budgeted research loop (LinUCB default in configs/meta.yaml)
PYTHONPATH=src:.deps python3 -m nexus.cli research --config configs/meta.yaml --no-resume

# Equal-budget random vs ε-greedy vs LinUCB
PYTHONPATH=src:.deps python3 -m nexus.cli compare-controllers --config configs/meta.yaml
PYTHONPATH=src:.deps python3 scripts/compare_controllers.py

# Independent seeds
PYTHONPATH=src:.deps python3 -m nexus.cli train --config configs/ppo_cartpole.yaml --seeds 1,2,3

# Propose next architecture from stored evals (does not train; not meta-RL)
PYTHONPATH=src:.deps python3 -m nexus.cli select --db runs/experiments.sqlite

pytest
```

## Layout

| Path | Role |
| --- | --- |
| `src/nexus/nn/` | Architecture spec, factory, restricted expression activations |
| `src/nexus/rl/` | Actor–critic + GAE + PPO |
| `src/nexus/evolution/` | Mutation / crossover generation loop |
| `src/nexus/memory/` | SQLite experiment store |
| `src/nexus/eval/` | Independent policy evaluation + architecture transfer |
| `src/nexus/meta/` | Schemas, research reward, LinUCB/ε-greedy/random, research loop |
| `docs/MASTER_CONTEXT.md` | Full research context |
| `docs/NEXUS_PROGRESS.md` | Measured logs and incomplete items |

## What this is not

V0.5 does not demonstrate that NEXUS learns to pick better experiments than random. The smoke controller comparison did not support that claim. It does not trade, and it does not modify its own safety or evaluation rules.
