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
    v08_development_target,
    v08_sequence_tasks,
)
from nexus.world.adapt import (
    AdditiveAdapter,
    AdaptedWorldModel,
    ResidualChangeDetector,
    collect_with_actor,
    per_transition_mae,
    run_v08_benchmark,
    split_train_val,
)
from nexus.world.data import collect_transitions, concat_datasets
from nexus.world.experiment import v07_transfer_task
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_KIND, FROZEN_PRIMARY_HORIZON, confirmation_physics_tuples
from nexus.world.memory import PredictiveMemory, checkpoint_nbytes, probe_mae
from nexus.world.planning import RandomShootingMPC
from nexus.world.protocol import CONFIRM_EVAL_SEED_V073, CONTROL_EVAL_SEED, V08_CONFIRM_EVAL_SEED, V08_DEV_EVAL_SEED
from nexus.world.train import train_world_model


def _all_prior_physics() -> set[tuple[float, float, float]]:
    rows = []
    for spec in CARTPOLE_FAMILY.values():
        p = spec.params
        rows.append((float(p["gravity"]), float(p["length"]), float(p["masspole"])))
    for group in (confirmation_targets(), v065_confirmation_targets(), v066_confirmation_targets()):
        for spec in group:
            p = spec.params
            rows.append((float(p["gravity"]), float(p["length"]), float(p["masspole"])))
    rows.extend(confirmation_physics_tuples())
    tr = v07_transfer_task().params
    rows.append((float(tr["gravity"]), float(tr["length"]), float(tr["masspole"])))
    return set(rows)


def test_v07_frozen_recipe_unchanged() -> None:
    assert FROZEN_KIND == "residual"
    assert FROZEN_PRIMARY_HORIZON == 3
    assert FROZEN_CANDIDATES[3] == 16
    assert CONFIRM_EVAL_SEED_V073 == 87_000
    assert CONFIRM_EVAL_SEED_V073 != V08_CONFIRM_EVAL_SEED
    assert V08_CONFIRM_EVAL_SEED != V08_DEV_EVAL_SEED
    assert V08_CONFIRM_EVAL_SEED != CONTROL_EVAL_SEED


def test_v08_physics_unused_in_prior_tracks() -> None:
    prior = _all_prior_physics()
    a, b, c = v08_sequence_tasks()
    assert a.task_id == "cartpole_default"
    for spec in (b, c, v08_development_target()) + v08_confirmation_targets():
        tup = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        assert tup not in prior, tup
        assert spec.params.keys() <= {"gravity", "length", "masspole"}


def test_change_detector_ignores_physics_and_flags_shift() -> None:
    rng = np.random.default_rng(0)
    src = rng.normal(0.01, 0.002, size=200)
    det = ResidualChangeDetector(window=32)
    det.fit(src)
    src_scan = det.scan(rng.normal(0.01, 0.002, size=128))
    shifted = det.scan(rng.normal(0.08, 0.002, size=128))
    assert det.uses_privileged_physics is False
    assert src_scan["uses_privileged_physics"] is False
    assert "gravity" not in ResidualChangeDetector.update.__code__.co_varnames
    assert src_scan["n_alarm"] < shifted["n_alarm"]
    assert shifted["first_alarm"] is not None


def test_world_model_clone_is_independent() -> None:
    spec = source_policy_task()
    tr = collect_transitions(spec, n_transitions=48, env_seeds=(1, 2, 3), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=24, env_seeds=(10, 11), base_seed=1, mix=("random",))
    wm, _ = train_world_model(tr, va, kind="residual", epochs=1, seed=0)
    other = wm.clone()
    w0 = next(wm.net.parameters())
    w0.data += 1.0
    d0 = next(other.net.parameters())
    assert float(np.abs(w0.detach().cpu().numpy() - d0.detach().cpu().numpy()).max()) > 0.5


def test_adapter_step_does_not_use_env() -> None:
    spec = source_policy_task()
    tr = collect_transitions(spec, n_transitions=32, env_seeds=(1, 2), base_seed=2, mix=("random",))
    va = collect_transitions(spec, n_transitions=16, env_seeds=(8, 9), base_seed=3, mix=("random",))
    wm, _ = train_world_model(tr, va, kind="residual", epochs=1, seed=1)
    adapted = AdaptedWorldModel(base=wm, adapter=AdditiveAdapter(4, 2))
    nxt, p = adapted.step(tr.obs[:4], tr.action[:4])
    assert nxt.shape == (4, 4)
    assert p.shape == (4,)
    assert adapted.uses_simulator is False
    assert adapted.uses_privileged_physics is False


def test_memory_retrieves_by_mae_not_task_id() -> None:
    spec = source_policy_task()
    tr = collect_transitions(spec, n_transitions=40, env_seeds=(1, 2, 3), base_seed=4, mix=("random",))
    va = collect_transitions(spec, n_transitions=20, env_seeds=(12, 13), base_seed=5, mix=("random",))
    good, _ = train_world_model(tr, va, kind="residual", epochs=2, seed=0)
    bad, _ = train_world_model(tr, va, kind="direct", epochs=1, seed=99)
    mem = PredictiveMemory(max_entries=4)
    mem.store(bad, va.slice(np.arange(8)), label="should_not_win")
    mem.store(good, va.slice(np.arange(8)), label="good")
    probe = va.slice(np.arange(8, 16))
    picked, meta = mem.retrieve(probe)
    assert meta["used_task_id"] is False
    assert meta["used_privileged_physics"] is False
    assert probe_mae(picked, probe) <= probe_mae(bad, probe) + 1e-9
    assert mem.bytes_used() > 0
    assert checkpoint_nbytes(good) > 0


def test_concat_and_split_preserve_counts() -> None:
    spec = source_policy_task()
    a = collect_transitions(spec, n_transitions=20, env_seeds=(1,), base_seed=0, mix=("random",))
    b = collect_transitions(spec, n_transitions=12, env_seeds=(2,), base_seed=1, mix=("random",))
    mix = concat_datasets(a, b, task_id="mix")
    assert len(mix) == 32
    tr, va = split_train_val(mix, rng=np.random.default_rng(0))
    assert len(tr) + len(va) == 32


def test_collect_with_actor_counts_env_steps() -> None:
    spec = source_policy_task()
    ds = collect_with_actor(spec, n_transitions=17, env_seeds=(3, 4), base_seed=0, actor=lambda o: 0)
    assert ds.env_interactions == 17
    assert len(ds) == 17


def test_mpc_h3_still_reproducible() -> None:
    class _M:
        def step(self, obs, action):  # type: ignore[no-untyped-def]
            o = np.asarray(obs, dtype=np.float32)
            o = o.reshape(1, -1) if o.ndim == 1 else o
            return o, np.zeros(o.shape[0])

    obs = np.zeros(4, dtype=np.float32)
    acts = []
    for _ in range(2):
        mpc = RandomShootingMPC(_M(), n_actions=2, horizon=3, n_candidates=16, seed=0, objective="both")
        mpc.reset_episode(V08_CONFIRM_EVAL_SEED)
        acts.append([mpc.act(obs)[0] for _k in range(3)])
    assert acts[0] == acts[1]


def test_v08_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v08_benchmark(
        n_model_seeds=1,
        artifact_path=tmp_path / "v08.json",
        checkpoint_dir=tmp_path / "ck",
        quick=True,
    )
    dumps_strict(out)
    json.loads((tmp_path / "v08.json").read_text())
    assert out["protocol"]["retuned_on_confirmation"] is False
    assert out["protocol"]["planner_uses_simulator"] is False
    assert out["protocol"]["inference_uses_privileged_physics"] is False
    assert out["protocol"]["v07_preserved"] is True
    assert out["is_agi"] is False
    assert "0" in out["confirmation_summary"]
    assert out["per_seed"][0]["detection"]["source_holdout"]["uses_privileged_physics"] is False
    assert out["per_seed"][0]["explore"]["random"]["env_interactions"] == out["per_seed"][0]["explore"]["uncertainty"]["env_interactions"]
