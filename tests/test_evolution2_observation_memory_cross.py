"""Source-only tests for E2.23 cross-bundle calibration. No collection."""
from __future__ import annotations

import json

import numpy as np

from nexus.core.strategy_memory_decide_bench import family_context
from nexus.evolution1.toy_loop import TrainingFeedback, VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2.observation_memory import (
    ObservationAwareAdaptive,
    calibrate_cross_bundle,
    calibrate_from_source,
    fit_family_normalizers,
)
from nexus.evolution2.observation_memory_cross_bench import write_artifact


def test_cross_bundle_gate_is_looser_than_within_and_frozen():
    normalizers = fit_family_normalizers()
    within = calibrate_from_source(normalizers, seed=7)
    cross = calibrate_cross_bundle(normalizers, seed=7)
    assert cross.frozen is True
    assert cross.rule == "cross_bundle_lobo_p95"
    assert cross.extra["used_e222_shifted_outcomes"] is False
    assert cross.gate_threshold > within.gate_threshold
    assert cross.extra["recall_at_cross_gate"] >= cross.extra["recall_at_within_gate"]
    assert cross.extra["false_accept_far"] == 0.0


def test_cross_bundle_gate_retrieves_typical_neighbor():
    normalizers = fit_family_normalizers()
    cross = calibrate_cross_bundle(normalizers, seed=7)
    method = ObservationAwareAdaptive(seed=7, gated=True, label="observation_cross_bundle")
    method.normalizers = normalizers
    method.calibration = cross
    context = family_context("acrobot")
    stored = normalizers["acrobot"].mean
    method.observe("acrobot", stored, context, provenance="bundle0")
    method.update(TrainingFeedback(VARIANTS[0].fingerprint, 1.0, False, "a" * 64), context)
    jitter = stored + 0.25 * normalizers["acrobot"].std
    method.observe("acrobot", jitter, context, provenance="bundle1")
    method.choose(tuple(VARIANTS), context)
    assert method.last_decision()["action"] == "retrieve"
    assert method.last_decision()["nearest"] <= cross.gate_threshold


def test_reset_fallback_clears_proposer_not_memory():
    normalizers = fit_family_normalizers()
    method = ObservationAwareAdaptive(seed=7, gated=True, reset_inner=True, label="observation_cross_reset_fallback")
    method.normalizers = normalizers
    method.calibration = calibrate_cross_bundle(normalizers, seed=7)
    context = family_context("pendulum")
    method.observe("pendulum", normalizers["pendulum"].mean, context, provenance="t0")
    method.update(TrainingFeedback(VARIANTS[0].fingerprint, 1.0, False, "d" * 64), context)
    assert len(method._store) == 1
    before = method.inner._updates
    method.reset_task()
    assert method.inner._updates == 0
    assert before > 0
    assert len(method._store) == 1


def test_far_observation_still_abstains_after_cross_calibration():
    normalizers = fit_family_normalizers()
    method = ObservationAwareAdaptive(seed=7, gated=True, label="observation_cross_bundle")
    method.normalizers = normalizers
    method.calibration = calibrate_cross_bundle(normalizers, seed=7)
    context = family_context("pendulum")
    method.observe("pendulum", normalizers["pendulum"].mean, context, provenance="src")
    method.update(TrainingFeedback(VARIANTS[0].fingerprint, 1.0, False, "e" * 64), context)
    method.observe("pendulum", normalizers["pendulum"].far_observation(), context, provenance="far")
    method.choose(tuple(VARIANTS), context)
    assert method.last_decision()["action"] == "fallback"


def test_e223_bench_is_development_only_and_matched():
    payload = write_artifact(7)
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["used_e217_science_arrays"] is False
    assert payload["used_e222_shifted_outcomes_for_calibration"] is False
    assert payload["development_scenarios_are_confirmation"] is False
    assert grant.grant_unused() is False
    assert len(set(payload["lookups"].values())) == 1
    assert payload["matched_proposals"] == 6
    assert "observation_cross_bundle" in payload["summary"]
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"
