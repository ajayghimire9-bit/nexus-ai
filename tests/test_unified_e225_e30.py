"""Small deterministic grammar/proposer tests; no real worlds or checkpoints."""
import copy
import json
import time

import numpy as np
import pytest

from nexus.evolution1.catalogue import Generator, Rule, Variant, digest
from nexus.evolution1.toy_loop import VARIANTS
from nexus.evolution1.fixtures import verify_journal
from nexus.evolution2.generated_strategies import (
    Strategy, leaf, compose, universe, execute, StrategyGenerator, AdvantagePredictor,
)
from nexus.evolution2.planner_adapter import FakeStepModel, decide, AdapterDecision
from nexus.core.strategy_memory_decide_bench import family_context, _task, near_zero_support
from nexus.evolution2.unified_source_bench import CONFIG, proxy_table, validate_config, feedback_unit, validate
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator


def test_typed_grammar_is_finite_deduplicated_and_canonical():
    choices = universe()
    assert len(choices) == len({s.fingerprint for s in choices}) == 342
    a, b = VARIANTS[0], VARIANTS[1]
    assert compose("rank_blend", a, b) == compose("rank_blend", b, a)
    assert compose("switch", a, a) == leaf(a)
    with pytest.raises(ValueError): Strategy("eval_python", a)
    with pytest.raises(ValueError): Strategy("switch", a, b, 123.)


def test_switch_changes_executed_operator_and_is_not_seed_renaming():
    a, b = VARIANTS[0], VARIANTS[-1]
    s = compose("switch", a, b, .25)
    assert s.active(np.array([0., 0., 0.])) == a
    assert s.active(np.array([1., 0., 0.])) == b
    for obs in (np.zeros(3), np.array([1., 0., 0.])):
        model = FakeStepModel(3, 3)
        assert execute(s, "pendulum", obs, model, seed=7) == decide("pendulum", s.active(obs), obs, model, seed=7).action


def test_ranking_composition_can_choose_an_action_neither_child_selected():
    a = Variant(Rule.SUCCESSOR, Generator.IID, 4)
    b = Variant(Rule.SUCCESSOR, Generator.BALANCED, 4)
    s = compose("rank_blend", a, b)
    def resolve(v, cap):
        assert cap == 768
        return AdapterDecision(1 if v == a else 2, (2., 3., 0.) if v == a else (2., 0., 3.), 0, np.zeros((1, 4)), "fixture")
    assert execute(s, "pendulum", np.zeros(3), None, seed=7, resolve=resolve) == 0
    assert s.bound(np.zeros(3), 3) <= 1536
    with pytest.raises(ValueError): s.components(np.zeros(3), cap=10000)


def test_feedback_changes_proposals_and_withheld_feedback_does_not():
    ctx = family_context("pendulum")
    changed = False
    for v in VARIANTS:
        base, learned, withheld = [StrategyGenerator(7) for _ in range(3)]
        learned.update(leaf(v), 1., np.zeros(3), ctx, event="informative")
        withheld.update(leaf(v), 1., np.zeros(3), ctx, event="informative", withheld=True)
        assert base.inner.learned_state() == withheld.inner.learned_state()
        assert base.propose(ctx).payload() == withheld.propose(ctx).payload()
        changed |= learned.propose(ctx).payload() != StrategyGenerator(7).propose(ctx).payload()
        assert verify_journal(learned.journal.snapshot())
    assert changed


def test_no_free_duplicate_feedback_or_hidden_feedback():
    gen = StrategyGenerator(7)
    gen.update(leaf(VARIANTS[0]), .5, np.zeros(3), family_context("pendulum"), event="once")
    with pytest.raises(ValueError): gen.update(leaf(VARIANTS[0]), .5, np.zeros(3), family_context("pendulum"), event="once")
    with pytest.raises(ValueError): gen.update(leaf(VARIANTS[0]), .5, np.zeros(3), family_context("pendulum"), event="hidden", provenance="hidden")


def test_random_generator_does_not_learn_even_when_feedback_is_recorded():
    a, b = StrategyGenerator(17, adaptive=False), StrategyGenerator(17, adaptive=False)
    a.update(leaf(VARIANTS[0]), 1., np.zeros(3), family_context("pendulum"), event="feedback")
    assert a.propose(family_context("pendulum")) == b.propose(family_context("pendulum"))


def test_repeated_parent_cannot_exhaust_a_six_receipt_episode():
    for seed in (7, 17, 27):
        g = StrategyGenerator(seed)
        used = set()
        for i in range(16):
            s = g.propose(family_context("pendulum"), excluded=used)
            assert s.fingerprint not in used
            used.add(s.fingerprint)
            g.update(s, .75, np.zeros(3), family_context("pendulum"), event=str(i))
        assert len(used) == 16


def test_pair_predictor_generalizes_on_informative_descriptor_fixture():
    p = AdvantagePredictor()
    for i, x in enumerate((-.8, -.3, .3, .8)):
        p.observe(np.array([x, 0.]), .4*x, event=str(i), provenance="revealed_source")
    assert abs(p.predict([.5, 0.]) - .2) < .08
    assert p.predict([.5, 0.]) == -p.predict([-.5, 0.])
    before = copy.deepcopy(p.y)
    with pytest.raises(ValueError): p.observe([1., 0.], 1., event="hidden", provenance="held_out_truth")
    assert p.y == before
    with pytest.raises(ValueError): p.observe([1., 0.], float("nan"), event="invalid", provenance="revealed_source")


def test_fixed_feedback_does_not_depend_on_unrevealed_query_extrema():
    outputs = []
    for secret in (-1e8, 1e8):
        table = {VARIANTS[0]: -12., VARIANTS[1]: 1., VARIANTS[2]: secret}
        evaluator = TrustedEvaluator(VARIANTS, family="pendulum", bundle_id=0,
                                     produce_score=lambda v: table[v])
        outputs.append([feedback_unit(evaluator.evaluate("public", v)) for v in VARIANTS[:2]])
        assert VARIANTS[2] not in evaluator.training_feedback("public")
    assert outputs[0] == outputs[1]
    assert feedback_unit(-12.) < feedback_unit(1.)
    with pytest.raises(ValueError): feedback_unit(float("nan"))


def test_small_proxy_table_is_deterministic_and_all_work_reserved():
    ctx = family_context("pendulum")
    task = _task("test", "train", "pendulum", 0, near_zero_support(ctx, 1), np.zeros(3))
    resources = {"fake_calls": 0, "fake_imagined_transitions": 0, "ledger_reports": []}
    table, actions = proxy_table(task, 7, time.perf_counter() + 10, resources)
    assert len(table) == 342 and all(np.isfinite(v) for v in table.values())
    report = resources["ledger_reports"][0]
    assert report["status"] == "complete_execution" and not any(report["unknown"].values())
    assert report["completed"]["imagined_transitions"] == resources["fake_imagined_transitions"]
    assert report["completed"]["model_calls"] == resources["fake_calls"]
    second = {"fake_calls": 0, "fake_imagined_transitions": 0, "ledger_reports": []}
    t2, a2 = proxy_table(task, 7, time.perf_counter() + 10, second)
    assert table == t2 and actions == a2


def test_config_cannot_silently_disconnect_yaml_or_change_budget():
    c = json.loads(CONFIG.read_text()); validate_config(c)
    c["ridge"] = 0.1
    with pytest.raises(ValueError): validate_config(c)


def test_missing_whole_method_grid_fails():
    with pytest.raises(ValueError, match="incomplete_method_grid"):
        validate({"rows": []}, json.loads(CONFIG.read_text()))
