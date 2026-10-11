from __future__ import annotations

import random

from nexus.meta.controller import LinUCBController, _fill_action, build_controller_state
from nexus.meta.schedule import enumerate_candidates, reject_reason
from nexus.meta.schema import ExperimentAction


def _action(kind: str = "mutate_architecture", ts: int = 256) -> ExperimentAction:
    return ExperimentAction(
        kind=kind,
        env_id="CartPole-v1",
        architecture={"hidden_sizes": [8], "activation": "tanh"},
        learning_rate=3e-4,
        train_timesteps=ts,
        train_seeds=(1,),
        holdout_eval_seed=1,
        assessment_eval_seed=2,
    )


def test_duplicate_and_unaffordable_are_rejected() -> None:
    act = _action()
    assert reject_reason(act, seen=set(), remaining_steps=10_000, champion_exists=True) is None
    assert reject_reason(act, seen={act.fingerprint()}, remaining_steps=10_000, champion_exists=True) == "duplicate"
    assert reject_reason(act, seen=set(), remaining_steps=10, champion_exists=True) == "unaffordable"


def test_extra_eval_without_champion_is_impossible() -> None:
    act = _action("extra_evaluation", ts=0)
    assert reject_reason(act, seen=set(), remaining_steps=0, champion_exists=False) == "impossible_no_champion"
    assert reject_reason(act, seen=set(), remaining_steps=0, champion_exists=True) is None


def _state() -> dict:
    spec = {
        "hidden_sizes": [8],
        "activation": "tanh",
        "use_residual": False,
        "dropout": 0.0,
        "layer_norm": False,
        "shared_backbone": True,
        "init": "orthogonal",
    }
    from nexus.nn.spec import ArchitectureSpec

    return build_controller_state(
        remaining_frac=1.0,
        n_prior=0,
        fail_rate=0.0,
        best_score=0.0,
        last_reward=0.0,
        n_params=10,
        budget_used_frac=0.0,
        extra_eval_recent=0.0,
        elites=[ArchitectureSpec.from_dict(spec)],
        default_architecture=spec,
        best_expr=None,
    )


def _limits(remaining: int, train: int = 256, explore: int = 64) -> dict:
    return {
        "env_id": "CartPole-v1",
        "transfer_env_id": "Acrobot-v1",
        "train_timesteps": train,
        "explore_timesteps": explore,
        "train_seeds": [1],
        "holdout_eval_seed": 1,
        "assessment_eval_seed": 2,
        "learning_rate": 3e-4,
        "remaining_timesteps": remaining,
        "max_experiments": 4,
        "max_timesteps": remaining,
    }


def test_enumerate_drops_unaffordable_and_impossible() -> None:
    valid, filtered = enumerate_candidates(
        fill=_fill_action,
        state=_state(),
        limits=_limits(remaining=80, train=256, explore=64),
        rng=random.Random(0),
        seen=set(),
        remaining_steps=80,
        has_champion=False,
    )
    reasons = {row["reason"] for row in filtered}
    assert "unaffordable" in reasons
    assert "impossible_no_champion" in reasons
    assert all(a.estimated_timesteps() <= 80 for a in valid)
    assert all(a.kind != "extra_evaluation" for a in valid)


def test_select_ranks_only_valid_candidates() -> None:
    valid, _filtered = enumerate_candidates(
        fill=_fill_action,
        state=_state(),
        limits=_limits(remaining=10_000, train=256, explore=64),
        rng=random.Random(1),
        seen=set(),
        remaining_steps=10_000,
        has_champion=True,
    )
    ctrl = LinUCBController()
    proposal = ctrl.select_from_candidates(valid, _state(), _limits(10_000), random.Random(2))
    assert proposal is not None
    fps = {a.fingerprint() for a in valid}
    assert proposal.action.fingerprint() in fps
    assert ctrl.select_from_candidates([], _state(), _limits(10_000), random.Random(0)) is None
