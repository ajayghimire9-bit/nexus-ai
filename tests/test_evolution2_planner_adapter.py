"""Source-only planner-adapter contracts. Fake models only. No collection."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from nexus.evolution1.catalogue import Generator, Rule, Variant, catalogue, plan_bound
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2 import planner_adapter as a
from nexus.world.rewards import acrobot_step_reward, pendulum_step_reward


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_adapter_does_not_use_mpc_for_model_or_gymnasium():
    source = Path(a.__file__).read_text()
    imported = _imports(Path(a.__file__))
    assert "gymnasium" not in imported
    assert "nexus.tasks.spec" not in imported
    assert "nexus.evolution1.adapters" not in imported
    assert "make_task_env" not in source
    assert "mpc_for_model(" not in source
    assert "from nexus.world.planning import mpc_for_model" not in source


def test_iid_matches_historical_candidate_draw():
    seq = a.iid_sequences(123, 16, 16, 3)
    rng = np.random.default_rng(123)
    expected = rng.integers(0, 3, size=(16, 16), dtype=np.int64)
    assert np.array_equal(seq, expected)


def test_balanced_first_actions_cover_all_actions_and_define_remainder():
    first = a.balanced_first_actions(8, 3)
    assert first.shape == (8,)
    assert list(first).count(0) == 3
    assert list(first).count(1) == 3
    assert list(first).count(2) == 2
    seq = a.generate_candidates(Variant(Rule.FLAT, Generator.BALANCED, 8), 8, 3, 0)
    assert seq.shape == (8, 8)
    assert np.array_equal(seq[:, 0], first)


def test_compatibility_matrix_covers_twelve_variants_per_family():
    rows = a.compatibility_matrix()
    artifact = Path(__file__).resolve().parents[1] / "artifacts" / "evolution2_planner_compatibility.json"
    artifact.write_text(json.dumps({"scientific": False, "ledger": False, "rows": rows}, indent=2) + "\n")
    assert len(rows) == 24
    by = {(row["family"], row["rule"], row["generator"], row["horizon"]): row for row in rows}
    assert len(by) == 24
    for variant in catalogue():
        for family in ("pendulum", "acrobot"):
            row = by[(family, variant.rule.value, variant.generator.value, variant.horizon)]
            if variant.generator is Generator.BALANCED:
                assert row["status"] == "IMPLEMENTED_adapter_DISPATCH_BLOCKED"
            else:
                assert row["status"] == "IMPLEMENTED_catalogue_faithful"
            bound = plan_bound(variant, 3, 1536)
            assert row["historical_parity"] is (
                variant.generator is Generator.IID
                and variant.horizon == 16
                and bound.candidates_per_root == 16
            )
            assert row["historical_parity"] is False
            assert row["scientific"] is False


def test_catalogue_faithful_decision_accounts_imagined_states():
    binding = reviewed_binding("pendulum")
    model = a.FakeStepModel(binding.obs_dim, binding.n_actions)
    obs = np.zeros(binding.obs_dim, dtype=np.float32)
    variant = Variant(Rule.SUCCESSOR, Generator.IID, 16)
    bound = plan_bound(variant, 3, 1536)
    first = a.decide("pendulum", variant, obs, model, seed=7)
    second = a.decide("pendulum", variant, obs, model, seed=7)
    assert first.action == second.action
    assert first.imagined == second.imagined
    assert first.imagined <= bound.imagined_per_decision
    assert first.imagined == bound.imagined_per_decision
    assert first.sequences.shape == (bound.candidates_per_root, 16)


def test_pendulum_historical_successor_ignores_root_probability():
    binding = reviewed_binding("pendulum")
    model = a.FakeStepModel(binding.obs_dim, binding.n_actions)
    obs = np.array([1.0, 0.0, 0.2], dtype=np.float32)
    seq = a.iid_sequences(9, 16, 16, 3)
    q = a.successor_values(binding, model, obs, seq, pendulum_step_reward)
    ref = []
    for action in range(3):
        nxt, _p = model.step(obs.reshape(1, -1), np.asarray([action], dtype=np.int64))
        nxt = np.asarray(nxt, dtype=np.float32).reshape(1, -1)
        r = float(np.asarray(pendulum_step_reward(obs.reshape(1, -1), action, nxt)).reshape(-1)[0])
        scores = a.score_open_loop(model, nxt, seq, pendulum_step_reward)
        ref.append(r + float(np.max(scores)))
    assert q == ref
    assert int(np.argmax(q)) == int(np.argmax(ref))


def test_acrobot_historical_successor_multiplies_root_survival():
    binding = reviewed_binding("acrobot")
    model = a.FakeStepModel(binding.obs_dim, binding.n_actions)
    obs = np.array([1.0, 0.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    seq = a.iid_sequences(11, 16, 16, 3)
    q = a.successor_values(binding, model, obs, seq, acrobot_step_reward)
    ref = []
    for action in range(3):
        nxt, p = model.step(obs.reshape(1, -1), np.asarray([action], dtype=np.int64))
        nxt = np.asarray(nxt, dtype=np.float32).reshape(1, -1)
        r = float(np.asarray(acrobot_step_reward(obs.reshape(1, -1), action, nxt)).reshape(-1)[0])
        p = float(np.clip(np.asarray(p, dtype=np.float64).reshape(-1)[0], 0.0, 1.0))
        scores = a.score_open_loop(model, nxt, seq, acrobot_step_reward)
        ref.append(r + (1.0 - p) * float(np.max(scores)))
    assert q == pytest.approx(ref)
    assert reviewed_binding("pendulum").root_survival != binding.root_survival


def test_argmax_tie_is_first_maximum():
    scores = np.array([1.0, 3.0, 3.0, 2.0])
    assert int(np.argmax(scores)) == 1


def test_historical_rate_makes_full_v2_likely_incomplete_under_900s():
    bench = a.inference_microbenchmark(n_decisions=2, seed=0)
    assert bench["scientific"] is False
    assert bench["ledger"] is False
    assert bench["gymnasium"] is False
    assert bench["historical_extrapolated_110592000_s"] == pytest.approx(611.57, abs=0.1)
    assert bench["wall_s"] >= 0
    assert bench["imagined"] > 0


def test_reuses_planning_counter_and_score_batch_not_mpc_for_model():
    source = Path(a.__file__).read_text()
    imported = _imports(Path(a.__file__))
    assert "nexus.world.planning" in imported
    assert "mpc_for_model(" not in source
    assert "class InferenceCounter" not in source
    assert "for t in range(horizon):" not in source
    from nexus.world.planning import InferenceCounter as Historical
    assert a.InferenceCounter is Historical


def test_twelve_arm_scientific_dispatch_is_blocked_by_balanced_host():
    report = a.twelve_arm_scientific_dispatch()
    assert report["ready"] is False
    assert report["status"] == "BLOCKED"
    assert report["blocked_variants"] == 6
    assert report["enabled_dispatch"] is False
    from nexus.evolution2.bindings import bind_evaluation
    from nexus.evolution1.catalogue import ContractError
    binding = reviewed_binding("pendulum")
    for variant in catalogue():
        if variant.generator is Generator.BALANCED:
            with pytest.raises(ContractError, match="unsupported_balanced_generator"):
                bind_evaluation(
                    "pendulum",
                    variant,
                    checkpoint_id=binding.checkpoint_id,
                    world_model_id=binding.world_model_id,
                    model_obs_dim=binding.obs_dim,
                    model_n_actions=binding.n_actions,
                )
    assert a.SCIENTIFIC is False
