from __future__ import annotations

import torch

from nexus.cl.experiment import _curriculum_compare
from nexus.cl.metrics import continual_metrics
from nexus.cl.protocol import INDEPENDENT_SEED, VAL_SEED
from nexus.cl.regularizers import EWCPenalty, ReplayBuffer
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic
from nexus.tasks.cartpole_family import source_tasks


def test_val_and_independent_seeds_differ() -> None:
    assert VAL_SEED != INDEPENDENT_SEED


def test_replay_is_balanced_across_tasks() -> None:
    buf = ReplayBuffer(capacity_per_task=16)
    a = torch.zeros(4, 3)
    b = torch.ones(20, 3)
    buf.add_batch(a, torch.zeros(4), task_id="A")
    buf.add_batch(b, torch.ones(20), task_id="B")
    sizes = buf.task_sizes()
    assert sizes["A"] == 4
    assert sizes["B"] == 16
    assert buf.by_task["A"][0][0].sum() == 0


def test_ewc_fisher_accumulates() -> None:
    spec = ArchitectureSpec(hidden_sizes=(4,), activation="tanh")

    class _Sp:
        n = 2

    agent = ActorCritic(4, _Sp(), spec)
    ewc = EWCPenalty(lam=1.0, max_samples=4)
    obs = torch.randn(8, 4)
    act = torch.zeros(8)
    ewc.consolidate(agent, obs, act, task_id="t0")
    ewc.consolidate(agent, obs, act, task_id="t1")
    assert ewc.n_tasks == 2
    assert ewc.tasks[0].task_id == "t0"
    assert ewc.tasks[1].task_id == "t1"


def test_continual_metrics_from_matrix() -> None:
    matrix = {
        "A": {"A": 100.0, "B": 10.0},
        "B": {"A": 40.0, "B": 80.0},
    }
    m = continual_metrics(matrix=matrix, task_order=["A", "B"], scratch={"A": 90.0, "B": 20.0})
    assert m["forgetting"]["A"] == 60.0
    assert m["backward_transfer"]["A"] == -60.0
    assert m["forward_transfer"]["B"] == -10.0
    assert abs(m["acc"] - 60.0) < 1e-9


def test_curriculum_observes_val_not_independent() -> None:
    tasks = source_tasks()
    out = _curriculum_compare(
        tasks,
        seed=0,
        n_phases=1,
        steps_per_phase=128,
        eval_episodes=1,
        eval_seed=INDEPENDENT_SEED,
        val_seed=VAL_SEED,
    )
    for mode in out.values():
        assert mode["curriculum_observed_independent"] is False
        assert mode["val_seed"] == VAL_SEED
        assert mode["independent_seed"] == INDEPENDENT_SEED
