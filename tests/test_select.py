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
    assert out["is_meta_rl"] is False


def test_select_refuses_cross_env_ranking(tmp_path) -> None:  # type: ignore[no-untyped-def]
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
    store.add(
        env_id="Acrobot-v1",
        generation=0,
        architecture={
            "hidden_sizes": [8],
            "activation": "relu",
            "use_residual": False,
            "dropout": 0.0,
            "layer_norm": False,
            "shared_backbone": False,
            "init": "orthogonal",
        },
        train_config={},
        mean_return=-80.0,
        std_return=0.0,
        timesteps=1000,
        seed=2,
    )
    store.close()
    out = propose_next_experiment(str(db), epsilon=0.0, seed=3)
    assert out["mode"] == "explore"
    assert out["comparability"] == "refused_cross_env_ranking"
    assert out["n_prior"] == 0


def test_select_does_not_mix_unequal_budgets(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = tmp_path / "e.sqlite"
    store = ExperimentStore(db)
    arch = {
        "hidden_sizes": [32],
        "activation": "tanh",
        "use_residual": False,
        "dropout": 0.0,
        "layer_norm": False,
        "shared_backbone": False,
        "init": "orthogonal",
    }
    store.add(
        env_id="CartPole-v1",
        generation=0,
        architecture={**arch, "activation": "relu"},
        train_config={},
        mean_return=400.0,
        std_return=0.0,
        timesteps=250_000,
        seed=1,
    )
    store.add(
        env_id="CartPole-v1",
        generation=0,
        architecture={**arch, "activation": "tanh"},
        train_config={},
        mean_return=50.0,
        std_return=0.0,
        timesteps=1024,
        seed=2,
    )
    store.close()
    # Without an explicit budget, exploit only among the modal (most common) budget.
    # Two different budgets: first listed modal is 250k (tie -> first most_common).
    out = propose_next_experiment(str(db), epsilon=0.0, seed=3, env_id="CartPole-v1", timesteps=1024)
    assert out["mode"] == "exploit_mutate"
    assert out["n_prior"] == 1
    assert out["parent"]["activation"] == "tanh"
