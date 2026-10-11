from __future__ import annotations

import json

import numpy as np

from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    CARTPOLE_FAMILY,
    confirmation_targets,
    source_policy_task,
    v065_confirmation_targets,
    v066_confirmation_targets,
    v08_confirmation_targets,
    v081_confirmation_targets,
    v081_development_target,
    v081_safety_ok,
    v081_sequence_tasks,
)
from nexus.tasks.spec import make_task_env
from nexus.world.adapt import ResidualChangeDetector, WindowThresholdDetector, split_train_val, split_train_val_episodes
from nexus.world.data import collect_transitions, split_by_episodes
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import confirmation_physics_tuples
from nexus.world.memory import PredictiveMemory
from nexus.world.protocol import V08_CONFIRM_EVAL_SEED, V081_CONFIRM_EVAL_SEED, V081_DEV_EVAL_SEED
from nexus.world.train import train_world_model
from nexus.world.v081 import run_v081_benchmark


def _phys(spec) -> tuple[float, float, float]:  # type: ignore[no-untyped-def]
    p = spec.params
    return float(p["gravity"]), float(p["length"]), float(p["masspole"])


def test_episode_disjoint_split_has_no_shared_episodes() -> None:
    spec = source_policy_task()
    ds = collect_transitions(spec, n_transitions=80, env_seeds=(1, 2, 3, 4), base_seed=0, mix=("random",))
    tr, va = split_by_episodes(ds, val_frac=0.3, rng=np.random.default_rng(0))
    assert set(tr.episode_id).isdisjoint(set(va.episode_id))
    assert len(tr) + len(va) == len(ds)
    leaked = split_train_val(ds, rng=np.random.default_rng(0))
    # shuffled split may share episode ids; that is the V0.8 leak this test documents
    _tr2, _va2 = leaked
    tr_e, va_e = split_train_val_episodes(ds, rng=np.random.default_rng(1))
    assert set(tr_e.episode_id).isdisjoint(set(va_e.episode_id))


def test_v081_physics_and_seeds_are_new() -> None:
    assert V081_CONFIRM_EVAL_SEED != V08_CONFIRM_EVAL_SEED
    assert V081_CONFIRM_EVAL_SEED != V081_DEV_EVAL_SEED
    prior = set()
    for spec in CARTPOLE_FAMILY.values():
        prior.add(_phys(spec))
    for group in (confirmation_targets(), v065_confirmation_targets(), v066_confirmation_targets(), v08_confirmation_targets()):
        for spec in group:
            prior.add(_phys(spec))
    prior.update(confirmation_physics_tuples())
    a, b, c = v081_sequence_tasks()
    assert a.params.get("obs_noise_std") == 0.08
    for spec in (b, c, v081_development_target()) + v081_confirmation_targets():
        assert v081_safety_ok(spec)
        assert spec.obs_dim == 4 and spec.n_actions == 2
        if spec.task_id != "cartpole_v081_A":
            assert _phys(spec) not in prior


def test_wrappers_keep_cartpole_interface() -> None:
    spec = v081_sequence_tasks()[0]
    env = make_task_env(spec, seed=0)
    obs, _ = env.reset(seed=0)
    assert np.asarray(obs).reshape(-1).shape == (4,)
    nxt, _r, _t, _u, _i = env.step(1)
    assert np.asarray(nxt).reshape(-1).shape == (4,)
    env.close()


def test_detectors_use_only_residuals() -> None:
    rng = np.random.default_rng(0)
    src = rng.normal(0.01, 0.002, size=200)
    ph = ResidualChangeDetector()
    win = WindowThresholdDetector(k=3.0)
    ph.fit(src)
    win.fit(src)
    assert "gravity" not in ResidualChangeDetector.update.__code__.co_varnames
    assert "gravity" not in WindowThresholdDetector.update.__code__.co_varnames
    clean = win.scan(rng.normal(0.01, 0.002, size=96))
    shift = win.scan(rng.normal(0.06, 0.002, size=96))
    assert shift["n_alarm"] > clean["n_alarm"]
    assert shift["missed"] is False


def test_clone_and_memory_independence() -> None:
    spec = source_policy_task()
    tr = collect_transitions(spec, n_transitions=40, env_seeds=(1, 2), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=20, env_seeds=(8, 9), base_seed=1, mix=("random",))
    wm, _ = train_world_model(tr, va, kind="residual", epochs=1, seed=0)
    snap = wm.clone()
    mem = PredictiveMemory(max_entries=3, replay_cap=64)
    mem.store(wm, va.slice(np.arange(8)))
    next(wm.net.parameters()).data += 3.0
    picked, meta = mem.retrieve(va.slice(np.arange(8, 16) if len(va) > 16 else np.arange(min(8, len(va)))))
    assert meta["used_task_id"] is False
    w0 = next(snap.net.parameters()).detach().cpu().numpy()
    w1 = next(picked.net.parameters()).detach().cpu().numpy()
    assert float(np.abs(w0 - w1).max()) < 1e-5
    dummy = WorldModel.create(4, 2, kind="residual", seed=1)
    assert isinstance(dummy, WorldModel)


def test_v081_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v081_benchmark(
        n_model_seeds=1,
        artifact_path=tmp_path / "v081.json",
        checkpoint_dir=tmp_path / "ck",
        quick=True,
    )
    dumps_strict(out)
    json.loads((tmp_path / "v081.json").read_text())
    assert out["protocol"]["retuned_on_confirmation"] is False
    assert out["protocol"]["episode_disjoint_splits"] is True
    assert out["protocol"]["planner_uses_simulator"] is False
    assert out["is_agi"] is False
    assert "finetune_minus_frozen" in out["paired_planning_vs_frozen"]["0"]
