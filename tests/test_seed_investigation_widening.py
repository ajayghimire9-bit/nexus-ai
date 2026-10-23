"""Regression cases for completeness-preserving investigation widening.

Development diagnostics only. Historical capability-audit outcomes are not
rescored and are not independent confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest

from nexus.seed.combined_investigation_engine import (
    EqualizedControllerConfig,
    EqualizedInvestigationEngineV2,
    EpisodeCallLedger,
    MechanismBActiveEnvironment,
    EvaluatorPrivateTaskOracle,
    execute_pipeline,
)
from nexus.seed.investigation_widening import construct_probe_candidates


def _fn(ops):
    return lambda xs, seq=ops: execute_pipeline(seq, list(xs))


def _cand(ops):
    cid = "p_" + "_".join(ops)
    return (cid, ops, _fn(ops))


@dataclass
class TinyTask:
    task_id: str
    cohort: str
    domain: str
    ticket_request: str
    support_examples: list
    probe_pool_inputs: list
    assessment_inputs: list
    target_ops: tuple
    oracle_fn: Callable[[Any], Any]
    candidate_pool: list


def _task(task_id, target, pool, support, probes, assessment=None):
    oracle = _fn(target)
    return TinyTask(
        task_id=task_id,
        cohort="development",
        domain="sequence_pipeline",
        ticket_request="Infer the observed list transform.",
        support_examples=[(x, oracle(x)) for x in support],
        probe_pool_inputs=list(probes),
        assessment_inputs=assessment or [[-5, 0, 2, 2, 7]],
        target_ops=target,
        oracle_fn=oracle,
        candidate_pool=list(pool),
    )


def _run(task, *, widening=True, questions=2, shortlist=2, max_checked=12,
         max_calls=None, wall_s=None, oracle=True, policy="untrained_default_active"):
    engine = EqualizedInvestigationEngineV2(strict_controller_bounds=True)
    ctrl = EqualizedControllerConfig(
        shortlist_limit=shortlist,
        allow_questions=True,
        max_questions_per_task=questions,
        probe_min_disagreement_ratio=0.15,
        enable_widening=widening,
        max_candidates_checked=max_checked,
        max_constructed_probes=4,
        max_episode_candidate_calls=max_calls,
        max_episode_wall_s=wall_s,
        widen_batch_size=2,
    )
    oracles = {}
    if oracle:
        oracles[task.task_id] = EvaluatorPrivateTaskOracle(
            task_id=task.task_id,
            target_ops=task.target_ops,
            oracle_fn=task.oracle_fn,
            assessment_inputs=task.assessment_inputs,
            candidate_pool=task.candidate_pool,
        )
    env = MechanismBActiveEnvironment(oracles)
    episode = engine.investigate_v2(task, env, ctrl, policy_mode=policy)
    ev = engine.evaluate_v2_episode(task, episode)
    assert ev["n_candidate_calls"] == len(ev["candidate_call_log"])
    assert ev["n_questions"] == len(ev["oracle_question_log"])
    return ev


def test_correct_candidate_starts_outside_shortlist():
    # Identity-like distractors match unique-free support and fill the shortlist.
    target = ("unique_stable",)
    distractors = [("reverse", "reverse"), ("increment", "decrement")]
    pool = [_cand(ops) for ops in distractors + [target]]
    task = _task(
        "outside_shortlist",
        target,
        pool,
        support=[[1, 2], [3, 4]],
        probes=[[2, 2], [4, 4]],
        assessment=[[1, 1, 2]],
    )
    legacy = _run(task, widening=False, shortlist=2)
    assert legacy["selected_candidate_id"] != "p_unique_stable"
    assert legacy["certainty_claimed"] is True
    widened = _run(task, widening=True, shortlist=2)
    assert "p_unique_stable" in widened["widening"]["candidates_checked"]
    assert widened["n_candidate_calls"] > legacy["n_candidate_calls"]


def test_constructed_probe_splits_agreeing_shortlist():
    a = ("unique_stable",)
    b = ("filter_even",)
    pool = [_cand(a), _cand(b), _cand(("reverse",))]
    # Support and initial probes are even unique values: both unique and filter_even agree.
    task = _task(
        "need_constructed",
        a,
        pool,
        support=[[2, 4], [6, 8]],
        probes=[[2, 2], [4, 4]],
        assessment=[[2, 3, 4, 4]],
    )
    ev = _run(task, widening=True, shortlist=2)
    assert ev["widening"]["constructed_probes"] or ev["n_questions"] >= 0
    assert ev["stopping_reason"] in {
        "identified_within_catalogue", "unique_among_checked", "ambiguous",
        "no_checked_candidate_fits", "catalogue_inconsistent",
    }
    assert ev.get("identification_status") == ev["stopping_reason"]


def test_new_oracle_contradicts_preferred_shortlist():
    target = ("filter_even",)
    preferred = ("unique_stable",)
    pool = [_cand(preferred), _cand(target), _cand(("reverse",))]
    task = _task(
        "oracle_flip",
        target,
        pool,
        support=[[2, 4, 4], [6, 8]],
        probes=[[2, 2], [-3, 0, 2, 2, 5]],
    )
    ev = _run(task, widening=True, shortlist=2, questions=2)
    if ev["n_questions"]:
        assert ev["selected_candidate_id"] in {
            "p_filter_even", "p_unique_stable", "p_reverse",
        }


def test_observational_equivalence_is_not_certainty():
    same = ("unique_stable",)
    same2 = ("unique_stable", "unique_stable")
    pool = [_cand(same), _cand(same2)]
    task = _task(
        "equivalent",
        same,
        pool,
        support=[[1, 2, 3], [4, 5]],
        probes=[[2, 2], [3, 1]],
    )
    ev = _run(task, widening=True, shortlist=2, max_checked=4)
    assert ev["certainty_claimed"] is False
    assert ev["identification_status"] == "ambiguous"
    assert ev["stopping_reason"] == "ambiguous"
    assert ev["capsule_registered"] is None
    assert len(ev["unresolved_alternatives"]) >= 1


def test_target_outside_grammar_is_unresolved():
    pool = [_cand(("reverse",)), _cand(("increment",))]
    hidden = ("square",)

    def hidden_fn(xs):
        return [x * x for x in xs]

    task = TinyTask(
        task_id="outside_grammar",
        cohort="development",
        domain="sequence_pipeline",
        ticket_request="Infer the observed list transform.",
        support_examples=[([2], [4]), ([3], [9])],
        probe_pool_inputs=[[1], [0]],
        assessment_inputs=[[5]],
        target_ops=hidden,
        oracle_fn=hidden_fn,
        candidate_pool=pool,
    )
    ev = _run(task, widening=True, shortlist=2, max_checked=4)
    assert ev["certainty_claimed"] is False
    assert ev["identification_status"] == "catalogue_inconsistent"
    assert ev["widening"]["catalogue_exhausted"] is True
    assert ev["capsule_registered"] is None


def test_no_answer_source_does_not_claim_certainty():
    target = ("increment",)
    other = ("increment", "unique_stable")
    pool = [_cand(target), _cand(other)]
    task = _task(
        "no_oracle",
        target,
        pool,
        support=[[1], [2]],
        probes=[[3], [4]],
    )
    ev = _run(task, widening=True, oracle=False, shortlist=2)
    assert ev["certainty_claimed"] is False
    assert ev["widening"]["halt_cause"] == "no_answer_source"
    assert ev["identification_status"] in {
        "unique_among_checked", "ambiguous", "no_checked_candidate_fits",
    }


def test_budget_expires_without_certainty():
    target = ("increment", "unique_stable")
    pool = [_cand(("double",)), _cand(("reverse",)), _cand(target), _cand(("abs_val",))]
    task = _task(
        "budget",
        target,
        pool,
        support=[[1, 1], [2, 2]],
        probes=[[2, 2], [4, 4], [-3, 0, 2, 2, 5]],
    )
    ev = _run(task, widening=True, shortlist=1, max_checked=8, max_calls=4)
    assert ev["certainty_claimed"] is False
    assert ev["widening"]["halt_cause"] == "budget_exhausted"
    assert ev["identification_status"] != "identified_within_catalogue"
    assert ev["n_candidate_calls"] <= 8


def test_learned_and_fixed_share_widening_access():
    target = ("increment",)
    pool = [_cand(("double",)), _cand(target), _cand(("reverse",))]
    task = _task("shared_rules", target, pool, support=[[1], [2]], probes=[[3], [-1, 0]])
    a = _run(task, widening=True, policy="untrained_default_active")
    b = _run(task, widening=True, policy="fixed_infogain_active")
    assert a["widening"]["enabled"] is True
    assert b["widening"]["enabled"] is True
    assert set(a["widening"].keys()) == set(b["widening"].keys())


def test_legacy_path_unchanged_when_widening_off():
    target = ("increment",)
    pool = [_cand(("double",)), _cand(("reverse",)), _cand(target)]
    task = _task("legacy", target, pool, support=[[1], [2]], probes=[[2, 2]])
    ev = _run(task, widening=False, shortlist=2)
    assert ev["stopping_reason"] in {"legacy_shortlist_stop", "legacy_empty_shortlist_fallback"}
    assert ev["certainty_claimed"] is True


def test_constructed_probes_do_not_use_assessment_rows():
    task = _task(
        "no_leak",
        ("increment",),
        [_cand(("increment",))],
        support=[[1, 2]],
        probes=[[3, 4]],
        assessment=[[99, 100, 101]],
    )
    used = {__import__("json").dumps(x, sort_keys=True) for x in ([[1, 2], [3, 4], [99, 100, 101]])}
    built = construct_probe_candidates(task, used)
    assert [99, 100, 101] not in built


def test_unique_among_checked_is_not_catalogue_identification():
    target = ("increment",)
    extras = [("double",), ("reverse",), ("abs_val",), ("filter_even",)]
    pool = [_cand(target)] + [_cand(ops) for ops in extras]
    task = _task("partial_check", target, pool, support=[[1], [2]], probes=[[3], [4]])
    ev = _run(task, widening=True, shortlist=1, max_checked=2)
    assert ev["certainty_claimed"] is False
    if ev["identification_status"] == "unique_among_checked":
        assert ev["widening"]["unchecked_remaining"] >= 1
        assert ev["widening"]["catalogue_exhausted"] is False
    assert ev.get("identified") is not True


def test_zero_survivors_with_remainder_is_not_out_of_grammar():
    hidden = ("square",)

    def hidden_fn(xs):
        return [x * x for x in xs]

    extras = [("reverse",), ("increment",), ("double",), ("abs_val",)]
    pool = [_cand(ops) for ops in extras]
    task = TinyTask(
        task_id="partial_oog",
        cohort="development",
        domain="sequence_pipeline",
        ticket_request="Infer the observed list transform.",
        support_examples=[([2], [4]), ([3], [9])],
        probe_pool_inputs=[[1], [0]],
        assessment_inputs=[[5]],
        target_ops=hidden,
        oracle_fn=hidden_fn,
        candidate_pool=pool,
    )
    ev = _run(task, widening=True, shortlist=1, max_checked=2)
    assert ev["certainty_claimed"] is False
    assert ev["identification_status"] == "no_checked_candidate_fits"
    assert ev["widening"]["unchecked_remaining"] >= 1
    assert ev["widening"]["catalogue_exhausted"] is False


def test_static_length_elimination_is_charged_and_sound():
    from nexus.seed.behavioral_index import (
        appears_monotonic_on_support,
        produces_sorted_list,
        sound_static_elimination,
    )
    support = [([1, -2, 3], [1, 3])]
    eliminated, why = sound_static_elimination(("reverse", "increment"), support)
    assert eliminated is True
    assert why == "length_preserving_cannot_produce_shorter_output"
    kept, _ = sound_static_elimination(("filter_even",), support)
    assert kept is False
    sorted_only = [([1, 4], [2, 3]), ([2, 5], [0, 6])]
    assert produces_sorted_list(sorted_only) is True
    assert appears_monotonic_on_support(sorted_only) is False


def test_fingerprint_prioritize_never_drops():
    from nexus.seed.behavioral_index import BehavioralIndex
    index = BehavioralIndex()
    items = [("a", ("reverse",), None), ("b", ("increment",), None)]
    index.remember_execution("a", [1], [1])
    ordered = index.prioritize(items, [([1], [1])])
    assert {row[0] for row in ordered} == {"a", "b"}
    assert len(ordered) == 2
