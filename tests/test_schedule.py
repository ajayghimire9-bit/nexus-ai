from __future__ import annotations

from nexus.meta.schedule import reject_reason
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
