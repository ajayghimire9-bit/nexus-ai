# NEXUS AI

Experimental research system for self-evolving neural intelligence. Long-term aim: investigate whether models can improve their own learning mechanisms, architectures, and problem-solving through measured experiments — including a later financial application (NEXUS Alpha).

This is **not** a chatbot wrapper. Completing the roadmap is **not** AGI.

## Status

**NEXUS Research V0.1 (implemented and tested):** PyTorch PPO actor–critic, configurable network factory, SQLite experiment memory, and a measured architecture-mutation loop on Gymnasium `CartPole-v1`.

No self-improving system, profitable trading system, or AGI has been demonstrated.

### Measured local runs (2026-10-11, CPU)

Independent eval is 20 episodes on held-out seeds vs a random-policy baseline. CartPole-v1 is not solved (solved ≈ 475).

| Run | Timesteps | Eval mean return | Random baseline |
| --- | --- | --- | --- |
| PPO `(64, 64)` tanh, shared | 49 664 | **227.5** (std 95.9) | 22.5 |
| Evolution, 2 generations × 4 candidates × 8 192 steps | 8 192 each | best **175.7** (tanh 64-64 + residual, gen 1) | 23.5 |

The evolution ranking is noisy at this budget: the same 64-64 tanh MLP scored 37.2 then 26.0 across generations. Treat the residual “winner” as a hypothesis, not a validated architecture improvement.

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
# PPO baseline (default 50k steps, CartPole-v1)
nexus train --config configs/ppo_cartpole.yaml

# Independent eval of a checkpoint
nexus eval --checkpoint checkpoints/ppo_latest.pt

# Architecture mutation loop (trains each candidate, then evaluates)
nexus evolve --config configs/evolution.yaml

# Cheap smoke configs (tests / CI)
nexus train --config configs/smoke.yaml
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
| `docs/MASTER_CONTEXT.md` | Full research context |

## What this is not

V0.1 does not search activation formulas at scale, does not trade, and does not modify its own safety or evaluation rules.
