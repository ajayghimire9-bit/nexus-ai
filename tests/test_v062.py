from __future__ import annotations

import torch

from nexus.cl.metrics import cl_evaluation_metrics
from nexus.cl.models import copy_encoder_into, copy_full_policy
from nexus.cl.protocol import HOLDOUT_EVAL_SEED, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.regularizers import EWCPenalty, diagonal_empirical_fisher
from nexus.cl.v062 import run_v062_benchmark
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic


def _tiny_agent(seed: int = 0) -> ActorCritic:
    torch.manual_seed(seed)

    class _Sp:
        n = 2

    return ActorCritic(4, _Sp(), ArchitectureSpec(hidden_sizes=(4,), activation="tanh", shared_backbone=True))


def test_eval_seeds_three_way_split() -> None:
    assert len({VAL_SEED, INDEPENDENT_SEED, HOLDOUT_EVAL_SEED}) == 3


def test_empirical_fisher_is_mean_of_per_sample_squared_grads() -> None:
    agent = _tiny_agent(0)
    obs = torch.randn(6, 4)
    act = torch.zeros(6)
    fisher = diagonal_empirical_fisher(agent, obs, act, max_samples=6)
    acc = {k: torch.zeros_like(v) for k, v in fisher.items()}
    for i in range(6):
        agent.zero_grad(set_to_none=True)
        logp, _, _ = agent.evaluate_actions(obs[i : i + 1], act[i : i + 1])
        logp.reshape(()).backward()
        for name, p in agent.named_parameters():
            if p.grad is not None:
                acc[name] += p.grad.detach().cpu() ** 2
    for name in fisher:
        acc[name] /= 6.0
        assert torch.allclose(fisher[name], acc[name], atol=1e-6)


def test_empirical_fisher_not_batch_mean_then_square() -> None:
    agent = _tiny_agent(1)
    obs = torch.randn(8, 4)
    act = torch.randint(0, 2, (8,))
    per = diagonal_empirical_fisher(agent, obs, act, max_samples=8)
    agent.zero_grad(set_to_none=True)
    logp, _, _ = agent.evaluate_actions(obs, act)
    logp.mean().backward()
    name, p = next((n, q) for n, q in agent.named_parameters() if q.grad is not None)
    wrong = p.grad.detach().cpu() ** 2
    scale = float(per[name].abs().max()) + 1e-12
    rel = float((per[name] - wrong).abs().max() / scale)
    assert rel > 0.05


def test_ewc_keeps_task_snapshots() -> None:
    agent = _tiny_agent(2)
    ewc = EWCPenalty(lam=1.0, max_samples=4)
    obs = torch.randn(4, 4)
    act = torch.zeros(4)
    ewc.consolidate(agent, obs, act, task_id="A")
    snap_a = {k: v.clone() for k, v in ewc.tasks[0].params.items()}
    fisher_a = {k: v.clone() for k, v in ewc.tasks[0].fisher.items()}
    with torch.no_grad():
        for p in agent.parameters():
            p.add_(0.5)
    ewc.consolidate(agent, obs, act, task_id="B")
    assert ewc.n_tasks == 2
    assert ewc.tasks[0].task_id == "A"
    for k, v in snap_a.items():
        assert torch.equal(ewc.tasks[0].params[k], v)
        assert torch.equal(ewc.tasks[0].fisher[k], fisher_a[k])
    assert not torch.equal(ewc.tasks[1].params[next(iter(snap_a))], snap_a[next(iter(snap_a))])


def test_ewc_penalty_zero_at_snapshot_and_positive_after_shift() -> None:
    agent = _tiny_agent(3)
    ewc = EWCPenalty(lam=4.0, max_samples=4)
    obs = torch.randn(4, 4)
    act = torch.zeros(4)
    ewc.consolidate(agent, obs, act, task_id="A")
    z = float(ewc.loss(agent).item())
    assert z == 0.0 or abs(z) < 1e-6
    with torch.no_grad():
        for p in agent.parameters():
            p.add_(1.0)
    moved = float(ewc.loss(agent).item())
    assert moved > 1e-6
    for name, p in agent.named_parameters():
        p.data.copy_(ewc.tasks[0].params[name])
    restored = float(ewc.loss(agent).item())
    assert restored < 1e-6


def test_cl_metrics_do_not_use_specialist_as_zero_shot_baseline() -> None:
    matrix = {
        "A": {"A": 100.0, "B": 12.0},
        "B": {"A": 40.0, "B": 80.0},
    }
    m = cl_evaluation_metrics(
        matrix=matrix,
        task_order=["A", "B"],
        untrained={"A": 9.0, "B": 10.0},
        independent={"A": 90.0, "B": 85.0},
    )
    assert m["forgetting"]["A"] == 60.0
    assert m["backward_transfer"]["A"] == -60.0
    assert m["zero_shot_forward_transfer"]["B"] == 2.0  # 12 - 10, not 12 - 85
    assert m["forward_adaptation"]["B"] == -5.0  # 80 - 85
    assert abs(m["average_return"] - 60.0) < 1e-9


def test_copied_encoder_is_used_in_forward() -> None:
    src = _tiny_agent(4)
    dst = _tiny_agent(5)
    n = copy_encoder_into(dst, src)
    assert n > 0
    for (a, b) in zip(src.backbone.parameters(), dst.backbone.parameters(), strict=True):
        assert torch.equal(a, b)
    obs = torch.randn(2, 4)
    with torch.no_grad():
        logits0 = dst._distribution(dst._features(obs)[0]).logits.clone()
        next(dst.backbone.parameters()).add_(3.0)
        logits1 = dst._distribution(dst._features(obs)[0]).logits
    assert not torch.allclose(logits0, logits1)


def test_full_policy_copy_matches_source_and_encoder_copy_leaves_heads() -> None:
    src = _tiny_agent(6)
    full = _tiny_agent(7)
    enc = _tiny_agent(8)
    copy_full_policy(full, src)
    copy_encoder_into(enc, src)
    assert torch.equal(full.policy_head.weight, src.policy_head.weight)
    assert not torch.equal(enc.policy_head.weight, src.policy_head.weight)


def test_v062_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v062_benchmark(
        n_seeds=1,
        source_budgets=(256,),
        transfer_steps=256,
        cl_steps_per_task=128,
        eval_episodes=2,
        artifact_path=tmp_path / "v062.json",
        checkpoint_dir=tmp_path / "ckpts",
    )
    assert out["protocol"]["curriculum_sees_independent"] is False
    assert out["protocol"]["ewc"].startswith("per-task")
    modes = set(out["per_seed"][0]["heldout_transfer"])
    assert modes == {
        "scratch",
        "full_zero_shot",
        "encoder_new_heads_zero_shot",
        "full_finetune",
        "encoder_new_heads_finetune",
        "frozen_encoder_new_heads",
    }
    assert out["per_seed"][0]["heldout_transfer"]["full_finetune"]["tensors_copied"] > 0
    naive = out["per_seed"][0]["methods"]["naive"]["transfer"]
    assert "mean_zero_shot_forward_transfer" in naive
    assert (tmp_path / "v062.json").exists()
