# NEXUS AI

Experimental research system for self-evolving neural intelligence. Long-term aim: investigate whether models can improve their own learning mechanisms, architectures, and problem-solving through measured experiments — including a later financial application (NEXUS Alpha).

This is **not** a chatbot wrapper. Completing the roadmap is **not** AGI.

## Status

**Current: amortized latent inference, development gate failed.** Write-up: `docs/NEXUS_AMORTIZED_LATENT_INFERENCE.md`. Artifact `artifacts/amortized_latent_dev.json`. No confirmation and no control sweep.

The existing history encoder, trained to match support-fit teacher latents, reached development angular velocity **0.1747** versus zero context **0.1587** and the frozen encoder **0.1773**. The teacher on the same decoder was **0.0781**. Every grid cell lost to zero context, so the new confirmation physics were not collected. This is **not** AGI, learning-to-learn, or a control result.

The earlier locked latent rule (Adam 0.1, 256 updates, decoder frozen) lowered confirmation angular velocity to **0.152** versus zero **0.308**, a global vector **0.314**, and a wrong-support vector **0.398**. The frozen encoder stayed at **0.307**.

Prior measured tracks (V0.4 PPO/evolution, V0.5–V0.6 CL, V0.7 planning, V0.8–V0.8.3 adaptation) are retained in `docs/NEXUS_PROGRESS.md` and `artifacts/`.

No self-improving system, profitable trading system, or AGI has been demonstrated.

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

# V0.8.9 learning efficiency (does not overwrite prior artifacts)
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v089_benchmarks.py

# Planning-generality diagnostic (does not overwrite cross_environment.json)
PYTHONPATH=src:.deps python3 scripts/run_planning_generality.py

# Pendulum adaptation / transfer (does not overwrite prior artifacts)
PYTHONPATH=src:.deps python3 scripts/run_pendulum_transfer.py

# Reptile vs multitask meta-learning pilot
PYTHONPATH=src:.deps python3 scripts/run_meta_learning_pilot.py

# Context-adaptation development pilot (does not evaluate confirmation physics unless the gate passes)
PYTHONPATH=src:.deps python3 scripts/run_context_adaptation_pilot.py dev

# Context-length diagnosis (development only; does not evaluate confirmation physics)
PYTHONPATH=src:.deps python3 scripts/run_context_adaptation_diagnosis.py dev

# Bounded context-optimization diagnostic (source prediction only)
PYTHONPATH=src:.deps python3 scripts/run_context_optimization_diagnostic.py dev

# Frozen-dynamics context diagnostic (source prediction only; does not evaluate confirmation)
PYTHONPATH=src:.deps python3 scripts/run_frozen_dynamics_context.py dev

# Direct latent context diagnostic (source prediction only)
PYTHONPATH=src:.deps python3 scripts/run_direct_latent_context.py dev

# Direct latent confirmation on the reserved physics (locked rule; no retune)
PYTHONPATH=src:.deps python3 scripts/run_direct_latent_confirmation.py

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

V0.8.9, Pendulum transfer, the meta-learning pilot, the context-adaptation screen, the context-length diagnosis, and the optimization diagnostic do not demonstrate AGI or learning-to-learn. The stack does not trade, and it does not modify its own safety or evaluation rules.
