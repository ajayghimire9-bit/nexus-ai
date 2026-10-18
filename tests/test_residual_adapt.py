"""Development tests for residual selection memory. No collection."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import torch

from nexus.core.residual_adapt import ResidualMemory, adapt_clone
from nexus.core.residual_adapt_bench import write_artifact
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2.persist_reset_path import disposable_model


def test_residual_adapt_bench_is_development_only_and_equal_budget():
    payload = write_artifact(7)
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["used_e217_science_arrays"] is False
    assert payload["used_e217_science_fits"] is False
    assert grant.grant_unused() is False
    assert len(set(payload["revealed_evals"].values())) == 1
    assert payload["revealed_evals"]["memory"] == 6
    assert "memory" in payload["summary"]
    assert "persist" in payload["summary"]
    assert "persist_best" in payload["summary"]
    assert payload["summary"]["memory"]["development"]["arms"] != [2, 2]
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"


def test_memory_exploit_changes_arm_when_neighbors_differ():
    mem = ResidualMemory(seed=7)
    near = np.zeros(12)
    far = np.ones(12)
    mem.update("pendulum", near, 0, 0.01)
    mem.update("pendulum", far, 1, 0.01)
    assert mem.choose("pendulum", near, policy="memory", explore=False) == 0
    assert mem.choose("pendulum", far, policy="memory", explore=False) == 1


def test_adapt_clone_does_not_write_source_checkpoint():
    model = disposable_model("pendulum", 0)
    path = Path("artifacts/evolution2_fit_clock_disposable/pendulum/bundle0.pt")
    before = path.stat().st_mtime_ns
    before_state = {key: value.detach().clone() for key, value in model.net.state_dict().items()}
    data = np.load("artifacts/evolution2_source_arrays/pendulum/bundle0_train.npz")
    other = adapt_clone(model, data["obs"][:32], data["action"][:32], data["next_obs"][:32], steps=2, seed=0)
    assert path.stat().st_mtime_ns == before
    assert any(not torch.equal(before_state[key], other.net.state_dict()[key]) for key in before_state)
    assert all(torch.equal(before_state[key], model.net.state_dict()[key]) for key in before_state)
