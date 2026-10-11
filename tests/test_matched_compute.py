from __future__ import annotations

from nexus.config import load_config
from nexus.meta.matched import apply_matched_compute, bind_slots_to_timestep_budget


def test_bind_slots_so_timestep_cap_binds() -> None:
    cfg = load_config("configs/smoke.yaml")
    cfg.meta.max_timesteps = 1024
    cfg.meta.explore_timesteps = 128
    cfg.meta.train_timesteps = 256
    cfg.meta.max_experiments = 2
    bound = bind_slots_to_timestep_budget(cfg.meta)
    assert bound.max_experiments >= 1024 // 128 + 2
    assert bound.max_timesteps == 1024
    cfg2 = apply_matched_compute(cfg)
    assert cfg2.meta.max_experiments >= bound.max_experiments


def test_v051_and_v052_artifacts_exist_and_are_not_overwritten() -> None:
    from pathlib import Path
    import json

    a = Path("artifacts/v051_synthetic_bandit.json")
    b = Path("artifacts/v052_synthetic_paired.json")
    assert a.exists() and b.exists()
    ja = json.loads(a.read_text())
    jb = json.loads(b.read_text())
    assert ja["task"] == "synthetic_linear_contextual_bandit"
    assert jb["task"] == "paired_linear_contextual_bandit"
    assert ja["n_seeds"] == 20
    assert jb["n_seeds"] == 20
