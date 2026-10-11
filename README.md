# NEXUS AI

Experimental research system for self-evolving neural intelligence. Long-term aim: investigate whether models can improve their own learning mechanisms, architectures, and problem-solving through measured experiments — including a later financial application (NEXUS Alpha).

This is **not** a chatbot wrapper. Completing the roadmap is **not** AGI.

## Status

**NEXUS Research V0.3 (measured):** multi-seed PPO confirmation, architecture evolution with the working trainer, and an ε-greedy experiment proposer over SQLite memory.

No self-improving system, profitable trading system, or AGI has been demonstrated.

### Measured local runs (2026-10-11, CPU)

CartPole-v1 is solved at mean return ≥ 475 on a given eval set.

| Run | Setup | Timesteps | Eval |
| --- | --- | --- | --- |
| PPO CartPole seed 1 | separate trunks, 10 epochs | 249 856 | **500.0** vs random 22.4 |
| PPO CartPole seed 2 | same | 249 856 | **409.5** vs random 26.2 (**not solved**) |
| PPO CartPole seed 3 | same | 249 856 | **500.0** vs random 21.5 |
| Multi-seed summary | seeds 1,2,3 | 249 856 | mean **469.8**, std 42.7; `solved_cartpole=false` |
| PPO Acrobot seed 2 | separate agent | 249 856 | **−83.25** vs random −500 |
| Evolution gen 0–1 | 49 152 steps/candidate | 49 152 | baseline tanh 64-64 **500**; gen 1 **all four** hit 500 (ceiling) |

A single seed of 500 is **not** a robust solve. Seed 2 failed the 475 bar at the same budget. Evolution cannot rank architectures once they all saturate CartPole; next search should use a harder env or a tighter budget/seed protocol.

The ε-greedy selector (`nexus select`) only **proposes** a mutation of the current best stored spec. It does not train itself and is not meta-RL.

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

# Architecture mutation loop
PYTHONPATH=src:.deps python3 -m nexus.cli evolve --config configs/evolution.yaml

# Activation screen + short matched training
PYTHONPATH=src:.deps python3 -m nexus.cli activations --config configs/activations.yaml

# Independent seeds
PYTHONPATH=src:.deps python3 -m nexus.cli train --config configs/ppo_cartpole.yaml --seeds 1,2,3

# Propose next architecture from stored evals (does not train)
PYTHONPATH=src:.deps python3 -m nexus.cli select --db runs/experiments.sqlite

pytest
```

Trained models are compared against a random-policy baseline on held-out episode seeds. Evolution stores results in SQLite (`runs/experiments.sqlite` by default).

## Layout

| Path | Role |
| --- | --- |
| `src/nexus/nn/` | Architecture spec + PyTorch factory |
| `src/nexus/rl/` | Actor–critic + GAE + PPO |
| `src/nexus/evolution/` | Mutation and generation loop |
| `src/nexus/memory/` | SQLite experiment store |
| `src/nexus/eval/` | Independent policy evaluation |
| `src/nexus/meta/` | ε-greedy next-experiment proposal |
| `docs/MASTER_CONTEXT.md` | Full research context |

## What this is not

V0.3 does not search activations at scale, does not transfer weights across envs, does not trade, and does not modify its own safety or evaluation rules. `nexus select` cannot change those rules.
