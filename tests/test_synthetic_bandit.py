from __future__ import annotations

from nexus.meta.synthetic import run_synthetic_bandit


def test_linucb_learns_known_optimal_policy() -> None:
    out = run_synthetic_bandit(n_seeds=20, horizon=200, artifact_path=None)
    by_name = {s["method"]: s for s in out["summary"]}
    lin = by_name["linucb"]["mean_last50_opt_rate"]
    rnd = by_name["random"]["mean_last50_opt_rate"]
    frz = by_name["linucb_frozen"]["mean_last50_opt_rate"]
    assert lin > rnd + 0.15
    assert lin > frz + 0.10
    assert lin > 0.55
    gen = out["generalization_shifted_context"]
    assert gen["linucb"]["mean"] > gen["random"]["mean"]
