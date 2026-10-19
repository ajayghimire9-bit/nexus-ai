"""Authored receipts and clocks only: no worlds, planners or neural models."""
import copy
import math

import pytest

from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution1.toy_loop import ANCHORS
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator, feedback_reference_digest
from nexus.evolution2.persist_reset_scoring import analyze_return_grid, freeze_shared_reference

METHODS = ("persist", "reset", "random", "evolution")
FAMILIES = ("pendulum", "acrobot")


def shared_scale(bundle, family):
    source = TrustedEvaluator(ANCHORS, family=family, bundle_id=bundle,
                              produce_score=lambda v: 0. if v == ANCHORS[0] else 10.)
    for method in METHODS:
        for v in ANCHORS: source.evaluate(method, v)
    ref = feedback_reference_digest(family, bundle, tuple(ANCHORS))
    scale = freeze_shared_reference(source, method_names=METHODS, reference=tuple(ANCHORS),
                                    expected_reference_digest=ref)
    return scale, source


def fixture():
    rows, scales, operations = [], {}, []
    for b in range(10):
        for f in FAMILIES:
            scale, _ = shared_scale(b, f)
            scales[b, f] = scale
            for slot in (0, 1):
                for m in METHODS:
                    better = m in ("persist", "random")
                    raw = float(10 + b if better else 0)
                    physical = f"b{b}_{f}_s{slot}_{int(better)}"
                    cached = m in ("random", "evolution")
                    if not cached: operations.append(Operation(physical, "environment", Work(real_steps=1)))
                    mapped = scale.transform(raw)
                    rows.append(dict(bundle=b, family=f, slot=slot, method=m,
                        variant_id=ANCHORS[int(better)].fingerprint, episode_id=f"fixture_{b}_{f}_{slot}",
                        raw=raw, unit=mapped["unit"], clipped=mapped["clipped"],
                        snapshot_digest=scale.snapshot_digest, cached=cached, steps=1,
                        physical_receipt=physical, measurement="environment_return"))
    # Synthetic Work metadata are not executed scientific interactions.
    ledger = ReservationLedger(tuple(operations), Limits(Work(real_steps=80), Work(real_steps=80), 10000, 10000))
    for i, op in enumerate(operations):
        ticket = ledger.reserve(op.key, Clock(i * 2, i * 2))
        ledger.settle(ticket, "success", Clock(i * 2 + 1, i * 2 + 1))
    report = ledger.close(Clock(200, 200))
    return rows, dict(bundle_ids=tuple(range(10)), families=FAMILIES, slots=(0, 1),
                      scales=scales, raw_spans={f: 100. for f in FAMILIES}, execution_report=report)


def test_raw_contrasts_pair_within_independent_bundle_not_episodes():
    rows, args = fixture()
    result = analyze_return_grid(rows, **args)
    values = [(10 + b) / 100 for b in range(10)]
    mean = sum(values) / 10
    se = math.sqrt(sum((v - mean) ** 2 for v in values) / 9 / 10)
    estimate, lo, hi = result["contrasts"]["reset"]["interval"]
    assert estimate == pytest.approx(mean)
    assert lo == pytest.approx(mean - result["critical_value"] * se)
    assert hi == pytest.approx(mean + result["critical_value"] * se)
    assert result["n"] == 10 and result["df"] == 9
    assert result["physical_episodes"] == 80 and result["logical_receipts"] == 160
    assert result["clipped_by_method"]["persist"] == 36
    assert result["contrasts"]["random"]["interval"] == (0., 0., 0.)
    assert result["practical_threshold"] is None and not result["promotion_authorized"]


@pytest.mark.parametrize("scope", ["bundle", "family", "slot", "method", "cell"])
def test_missing_entire_planned_scope_cannot_shrink_expectation(scope):
    rows, args = fixture()
    if scope == "cell": rows.pop()
    else:
        value = {"bundle": 0, "family": "pendulum", "slot": 0, "method": "reset"}[scope]
        rows = [r for r in rows if r[scope] != value]
    with pytest.raises(ValueError, match="incomplete_return_grid"):
        analyze_return_grid(rows, **args)


@pytest.mark.parametrize("field,value", [("raw", True), ("unit", "1"), ("raw", float("nan")),
    ("raw", float("inf")), ("bundle", False), ("slot", True), ("steps", True),
    ("cached", 1), ("measurement", "model_forecast"), ("snapshot_digest", "wrong"),
    ("clipped", True), ("unit", 0.123)])
def test_invalid_receipts_never_reach_aggregation(field, value):
    rows, args = fixture()
    rows[0][field] = value
    with pytest.raises(ValueError): analyze_return_grid(rows, **args)


def test_duplicate_bundle_in_expected_grid_rejected_before_result_validation():
    rows, args = fixture()
    args["bundle_ids"] = (0,) * 10
    with pytest.raises(ValueError): analyze_return_grid(rows, **args)
    args["bundle_ids"] = tuple(range(10))
    rows[-1] = copy.deepcopy(rows[0])
    with pytest.raises(ValueError, match="duplicate_cell"): analyze_return_grid(rows, **args)


@pytest.mark.parametrize("mutation", ["reset", "cache", "origin", "scale", "spans"])
def test_pairing_reference_cache_and_family_units_are_enforced(mutation):
    rows, args = fixture()
    if mutation == "reset": rows[1]["episode_id"] = "unpaired"
    if mutation == "cache": rows[2]["physical_receipt"] = rows[1]["physical_receipt"]
    if mutation == "origin": rows[2]["cached"] = False
    if mutation == "scale": del args["scales"][0, "pendulum"]
    if mutation == "spans": args["raw_spans"]["pendulum"] = 0
    with pytest.raises(ValueError): analyze_return_grid(rows, **args)


def test_shared_source_reference_same_hash_without_four_physical_repeats():
    scale, evaluator = shared_scale(0, "pendulum")
    assert evaluator.physical == 2 and evaluator.charged == 8 and evaluator.cached == 6
    assert {s.snapshot_digest for s in evaluator._feedback_scales.values()} == {scale.snapshot_digest}
    with pytest.raises(ValueError):
        freeze_shared_reference(evaluator, method_names=METHODS, reference=tuple(ANCHORS),
                                expected_reference_digest=scale.reference_digest)


def test_asymmetric_source_exposure_rejected_before_any_freeze():
    source = TrustedEvaluator(ANCHORS, family="pendulum", bundle_id=0, produce_score=lambda v: 1.)
    for m in METHODS:
        source.evaluate(m, ANCHORS[0])
    with pytest.raises(ValueError):
        freeze_shared_reference(source, method_names=METHODS, reference=tuple(ANCHORS),
                                expected_reference_digest="untrusted")
    assert not source._feedback_scales


def test_interrupted_reservation_preserves_unknown_work_and_blocks_complete_analysis():
    rows, args = fixture()
    ops = (Operation("done", "environment", Work(real_steps=1)),
           Operation("interrupted", "environment", Work(real_steps=1)))
    ledger = ReservationLedger(ops, Limits(Work(real_steps=2), Work(real_steps=2), 100, 100))
    first = ledger.reserve("done", Clock(0, 0))
    ledger.settle(first, "success", Clock(1, 1))
    ledger.reserve("interrupted", Clock(2, 2))
    report = ledger.close(Clock(3, 3))
    assert report.physical_reserved.real_steps == 2
    assert report.physical_completed_reported.real_steps == 1
    assert report.physical_unknown_upper_bound.real_steps == 1
    assert report.status == "incomplete_execution"
    args["execution_report"] = report
    with pytest.raises(ValueError, match="incomplete_or_invalid_execution"):
        analyze_return_grid(rows, **args)


def test_physical_step_counts_cannot_be_filled_in_from_cached_receipts():
    rows, args = fixture()
    rows[0]["steps"] = 2
    rows[2]["steps"] = 2
    with pytest.raises(ValueError, match="step_accounting"):
        analyze_return_grid(rows, **args)


def test_slots_cannot_reuse_one_episode_as_independent_opportunities():
    rows, args = fixture()
    for r in rows:
        if r["bundle"] == 0 and r["family"] == "pendulum": r["episode_id"] = "same_episode"
    with pytest.raises(ValueError, match="reused_episode"):
        analyze_return_grid(rows, **args)


def test_clipping_cannot_erase_raw_return_advantage():
    rows, args = fixture()
    for r in rows:
        r["raw"] = 100. if r["method"] in ("persist", "random") else 20.
        scale = args["scales"][r["bundle"], r["family"]]
        r.update({k: v for k, v in scale.transform(r["raw"]).items() if k != "snapshot_digest"})
    result = analyze_return_grid(rows, **args)
    assert all(r["unit"] == 1. for r in rows)
    assert result["contrasts"]["reset"]["interval"][0] == pytest.approx(0.8)


def test_family_spans_are_applied_before_equal_family_aggregation():
    rows, args = fixture()
    args["raw_spans"]["acrobot"] = 200.
    result = analyze_return_grid(rows, **args)
    expected = [((10 + b) / 100 + (10 + b) / 200) / 2 for b in range(10)]
    assert result["contrasts"]["reset"]["per_bundle"] == pytest.approx(expected)
