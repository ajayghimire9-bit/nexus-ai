from __future__ import annotations

from nexus.meta.synthetic import PairedBanditDataset, run_paired_synthetic_bandit, run_synthetic_bandit


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


def test_paired_world_is_identical_across_methods() -> None:
    a = PairedBanditDataset(n_arms=4, dim=8, horizon=16, n_holdout=8, seed=123)
    b = PairedBanditDataset(n_arms=4, dim=8, horizon=16, n_holdout=8, seed=123)
    assert (a.train_x == b.train_x).all()
    assert (a.train_noise == b.train_noise).all()
    assert (a.holdout_x == b.holdout_x).all()
    assert (a.shift_x == b.shift_x).all()


def test_paired_linucb_beats_random_on_deltas() -> None:
    out = run_paired_synthetic_bandit(n_seeds=20, horizon=200, n_holdout=200, artifact_path=None)
    d = out["paired_deltas"]["linucb_minus_random"]
    assert d["last50_opt_rate"]["mean"] > 0.15
    assert d["final_regret"]["mean"] < -50.0
    assert d["heldout_in_distribution"]["mean"] > 0.15
    assert d["heldout_shifted"]["mean"] > 0.15
    frozen = out["paired_deltas"]["linucb_minus_frozen"]
    assert frozen["last50_opt_rate"]["mean"] > 0.10
