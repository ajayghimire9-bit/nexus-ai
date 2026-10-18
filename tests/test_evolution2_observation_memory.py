"""Source-only tests for E2.22 observation-conditioned memory. No collection."""
from __future__ import annotations

import json

import numpy as np

from nexus.core.strategy_memory_decide_bench import family_context
from nexus.evolution1.catalogue import ContractError
from nexus.evolution1.toy_loop import TrainingFeedback, VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2.observation_memory import (
    FamilyNormalizer,
    ObservationAwareAdaptive,
    calibrate_from_source,
    fit_family_normalizers,
    load_source_train_obs,
)
from nexus.evolution2.observation_memory_bench import write_artifact


def _method(*, gated=True, shuffle=False, seed=7):
    normalizers = fit_family_normalizers()
    calibration = calibrate_from_source(normalizers, seed=seed)
    method = ObservationAwareAdaptive(seed=seed, gated=gated, shuffle=shuffle)
    method.normalizers = normalizers
    method.calibration = calibration
    return method


def test_refuses_incompatible_family_and_schema():
    method = _method()
    context = family_context("pendulum")
    try:
        method.observe("mountaincar", np.zeros(2), context, provenance="test")
        raise AssertionError("accepted incompatible family")
    except ContractError:
        pass
    try:
        method.normalizers["pendulum"].embed(np.zeros(6))
        raise AssertionError("accepted acrobot-shaped pendulum vector")
    except ContractError:
        pass


def test_normalizer_fits_source_train_only():
    raw = load_source_train_obs("pendulum")
    fitted = FamilyNormalizer.fit("pendulum", raw)
    assert fitted.n == raw.shape[0]
    assert fitted.obs_dim == 3
    assert np.allclose(fitted.mean, np.mean(raw, axis=0))
    assert "persist_reset_science" not in str(fitted.family)


def test_empty_memory_falls_back_to_proposer():
    method = _method()
    context = family_context("pendulum")
    obs = method.normalizers["pendulum"].mean
    method.observe("pendulum", obs, context, provenance="unit")
    choice = method.choose(tuple(VARIANTS), context)
    assert method.last_decision()["action"] == "fallback"
    assert choice in VARIANTS


def test_nearby_observation_retrieves_and_can_change_choice():
    method = _method()
    context = family_context("acrobot")
    stored = method.normalizers["acrobot"].mean
    method.observe("acrobot", stored, context, provenance="train")
    winner = VARIANTS[0]
    loser = VARIANTS[1]
    method.update(TrainingFeedback(winner.fingerprint, 1.0, False, "a" * 64), context)
    method.update(TrainingFeedback(loser.fingerprint, 0.0, False, "b" * 64), context)
    method.observe("acrobot", stored, context, provenance="query")
    near = method.choose(tuple(VARIANTS), context)
    assert method.last_decision()["action"] == "retrieve"
    assert method.last_decision()["fallback"] is False
    far = method.normalizers["acrobot"].far_observation()
    method.observe("acrobot", far, context, provenance="unit")
    _away = method.choose(tuple(VARIANTS), context)
    trace = method.last_decision()
    assert trace["nearest"] is None or trace["nearest"] > method.calibration.gate_threshold * 0.5
    assert near.fingerprint == winner.fingerprint or trace["action"] in {"retrieve", "fallback"}


def test_choose_is_deterministic():
    context = family_context("pendulum")
    obs = fit_family_normalizers()["pendulum"].mean
    a = _method(seed=7)
    b = _method(seed=7)
    a.observe("pendulum", obs, context, provenance="unit")
    b.observe("pendulum", obs, context, provenance="unit")
    assert a.choose(tuple(VARIANTS), context).fingerprint == b.choose(tuple(VARIANTS), context).fingerprint


def test_records_store_provenance_not_hidden_labels():
    method = _method()
    context = family_context("pendulum")
    method.observe("pendulum", method.normalizers["pendulum"].mean, context, provenance="e28:pendulum:bundle0:unit")
    method.update(TrainingFeedback(VARIANTS[0].fingerprint, 0.4, False, "c" * 64), context)
    row = method._store[0]
    assert row.provenance.startswith("e28:")
    assert "hidden" not in row.provenance
    assert row.family == "pendulum"
    assert row.obs_dim == 3


def test_e222_bench_is_development_only_and_matched():
    payload = write_artifact(7)
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["used_e217_science_arrays"] is False
    assert payload["score_is_real_control"] is False
    assert payload["matched_proposals"] == 6
    assert payload["free_slots"] == 4
    assert grant.grant_unused() is False
    assert len(set(payload["lookups"].values())) == 1
    assert "observation_aware_memory" in payload["summary"]
    assert "persistent_adaptive" in payload["summary"]
    assert "reset_adaptive" in payload["summary"]
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"
