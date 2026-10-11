from __future__ import annotations

from nexus.memory.store import ExperimentStore
from nexus.meta.select import propose_next_experiment


def test_select_explores_when_empty(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = tmp_path / "e.sqlite"
    ExperimentStore(db).close()
    out = propose_next_experiment(str(db), epsilon=0.0, seed=1)
    assert out["mode"] == "explore"
    assert out["proposal"]["hidden_sizes"]


def test_select_can_exploit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = tmp_path / "e.sqlite"
    store = ExperimentStore(db)
    store.add(
        env_id="CartPole-v1",
        generation=0,
        architecture={
            "hidden_sizes": [64, 64],
            "activation": "tanh",
            "use_residual": False,
            "dropout": 0.0,
            "layer_norm": False,
            "shared_backbone": False,
            "init": "orthogonal",
        },
        train_config={},
        mean_return=500.0,
        std_return=0.0,
        timesteps=1000,
        seed=1,
    )
    store.close()
    out = propose_next_experiment(str(db), epsilon=0.0, seed=3)
    assert out["mode"] == "exploit_mutate"
    assert out["n_prior"] == 1
    assert out["parent"]["activation"] == "tanh"
