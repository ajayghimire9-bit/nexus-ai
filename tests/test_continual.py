from __future__ import annotations

import random

from nexus.cl.curriculum import CurriculumSelector, assert_frozen_eval_rules
from nexus.cl.experiment import run_continual_benchmark
from nexus.cl.metrics import transfer_metrics
from nexus.tasks.cartpole_family import source_tasks


def test_curriculum_cannot_edit_eval_rules() -> None:
    limits = {"independent_eval_seed": 70000, "eval_episodes": 8, "max_timesteps_per_task": 2048}
    assert_frozen_eval_rules(limits, dict(limits))
    try:
        assert_frozen_eval_rules(limits, {**limits, "eval_episodes": 99})
        raise AssertionError("should have refused")
    except RuntimeError:
        pass
    sel = CurriculumSelector(source_tasks())
    sel.observe("cartpole_default", 20.0, 5.0)
    chosen = sel.select(random.Random(0))
    assert chosen.task_id in {t.task_id for t in source_tasks()}


def test_transfer_metrics_signs() -> None:
    metrics = transfer_metrics(
        peak_during_task={"A": 100.0, "B": 80.0},
        final_matrix={"A": {"A": 100.0, "B": 10.0}, "B": {"A": 40.0, "B": 80.0}},
        independent={"A": 90.0, "B": 20.0},
    )
    assert metrics["forgetting"]["A"] == 60.0
    assert metrics["forward_transfer"]["B"] == -10.0
    assert metrics["backward_transfer"]["A"] == -60.0


def test_continual_smoke_runs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_continual_benchmark(
        n_seeds=1, steps_per_task=256, eval_episodes=2, artifact_path=tmp_path / "cl.json"
    )
    assert out["protocol"]["not_acrobot"] is True
    assert set(out["per_seed"][0]["methods"]) == {"independent", "naive", "replay", "ewc", "multihead"}
    assert out["per_seed"][0]["encoder_transfer"]["heldout_task"] == "cartpole_lowg"
    for method in out["per_seed"][0]["methods"].values():
        assert method["steps"] > 0
        assert method["n_params"] > 0
    assert (tmp_path / "cl.json").exists()
