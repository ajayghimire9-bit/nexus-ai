"""Authored source-only correctness fixtures; never a final task bank."""
from dataclasses import replace
import math
import operator

import pytest

from nexus.wave24_auto_laws import AutoOperatorFingerprinter, OpenPythonToolboxAdapter
from nexus.wave24_quotient_core import (
    Operator, Grammar, Expr, WorkMeter, FullSignatureQuotientDAG, ExactEnumerator,
    ExhaustiveASTEnumerator, ParametricSkillMacro, PopperianTwinVerifier,
    variable, typed_hole, apply, eval_expr, primitive_cost, solve, verify_certificate, freeze,
    constant,
)
from nexus.wave24_self_evolving_loop import (
    BehavioralDiffController, DerivationOutcomeCritic, ZeroDataFrontierSelfPlay,
    JournalSkillView, AlgebraicRoleFunctor, OpenToolboxLearningEngine, PublicTask,
    procedural_worlds, select_ratcheted_source_skills, zero_shot_role_transfer,
)


def meter():
    return WorkMeter(limit=8_000_000, wall_limit=10.)


@pytest.mark.parametrize("prediction,target,shape", [
    ((1, 9), (1, 2), "PARTIAL_SUBSET_MATCH"),
    (("abc", "def"), ("a", "d"), "MEASURE_EXCESS"),
    (("ab", "cd"), ("xy", "uv"), "SAME_SHAPE_RESIDUAL"),
    (({}, {}), ("a", "b"), "DEAD_UNCORRELATED"),
    ((1, 2), (1, 2), "EXACT_PUBLIC_FIT"),
])
def test_behavioral_shapes_are_public_only_and_domain_neutral(prediction, target, shape):
    diff = BehavioralDiffController.classify_error_shape(prediction, target, meter=meter())
    assert diff.error_shape == shape and len(diff.features) == 4
    assert all(0 <= v <= 1 for v in diff.features)


def test_conditional_split_constructs_only_declared_boolean_guards():
    positive = Operator("op_0", ("INT",), "BOOL", lambda x: x >= 0)
    negate = Operator("op_1", ("INT",), "INT", operator.neg)
    g = Grammar("INT", (positive, negate), conditionals=True)
    public = ((-2, 2), (1, 1))
    x = variable("INT")
    split = BehavioralDiffController().conditional_branch_split(g, public, x, [apply(positive, x)], meter=meter())
    assert split["D_fail"] == ((-2, 2),) and split["D_pass"] == ((1, 1),)
    program = Expr("if", "INT", None, (split["guard"], x, apply(negate, x)))
    assert [eval_expr(program, a, g.ops) for a, _ in public] == [2, 1]
    q = solve(g, public, -3, "INT", 6, meter=meter())
    assert verify_certificate(g, public, -3, "INT", 6, q, meter=meter())
    assert BehavioralDiffController().conditional_branch_split(g, public, x, [], meter=meter()) is None
    trace = {}
    guided = solve(g, public, -3, "INT", 6, meter=meter(), trace=trace,
                   proposal_controller=BehavioralDiffController())
    assert guided.witnesses and trace["behavioral_proposals"] > 0
    assert verify_certificate(g, public, -3, "INT", 6, guided, meter=meter())


def test_projection_and_involution_roles_are_empirical_even_on_complete_seeds():
    ops = (Operator("op_0", ("INT",), "INT", abs), Operator("op_1", ("INT",), "INT", operator.neg))
    profiler = AutoOperatorFingerprinter()
    roles = profiler.fingerprint_roles(ops, {"INT": tuple(range(-3, 4))}, meter=meter())
    assert roles["op_0"].primary == "PROJ_IDEMPOTENT"
    assert roles["op_1"].primary == "INVOLUTION_DUAL"
    assert ("MONOTONE_STEP", "PRESERVING_STEP") in roles["op_1"].transfer_roles()
    assert all(r.evidence == "empirical_ordering_and_transfer_only" for r in roles.values())


def test_open_adapter_probes_actual_raw_builtins_and_math_without_family_wrappers():
    profile = OpenPythonToolboxAdapter().ingest((str, list, dict, math.floor),
        lambda: iter((1, -2, "ab", "ba", (("a", 1),), (("b", 2),), 1.25, -2.5)), meter=meter())
    assert profile.callable_count == 4
    assert any(op.inputs == ("INT",) and op.output == "STR" for op in profile.grammar.operators)
    assert any(op.inputs == ("TUPLE",) and op.output == "DICT" for op in profile.grammar.operators)
    assert any(op.inputs == ("FLOAT",) and op.output == "INT" for op in profile.grammar.operators)
    assert any(row["status"] == "rejected_overload" for row in profile.probe_log)
    assert all(op.name.startswith("op_") for op in profile.grammar.operators)


def test_raw_binary_tools_and_vetted_imports_are_bounded():
    profile = OpenPythonToolboxAdapter().ingest((operator.add,), lambda: iter((1, 2, 3)), meter=meter())
    assert profile.grammar.operators[0].inputs == ("INT", "INT")
    assert OpenPythonToolboxAdapter.safe_import("math", ("floor",))[0] is math.floor
    for module in ("os", "subprocess", "importlib"):
        with pytest.raises(ValueError):
            OpenPythonToolboxAdapter.safe_import(module, ("system",))


def test_raw_dictionary_tool_solves_a_real_typed_lookup_without_a_family_adapter():
    engine = OpenToolboxLearningEngine(meter=meter(), frozen=True)
    engine.enter_toolbox((operator.getitem,), lambda: iter(({"a": 1}, {"a": 2}, "a")),
                         constants=(constant("STR", "a"),))
    result = engine.solve_public((({"a": 3}, 3), ({"a": 7}, 7)), {"a": 9})
    assert result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
    assert result.query_values == (9,)
    assert engine.source_cycles == 0 and engine.critic.models is None


def test_impure_and_nondeterministic_raw_callables_fail_closed():
    def mutate(x):
        x.append(1)
        return x
    with pytest.raises(ValueError):
        OpenPythonToolboxAdapter().ingest((mutate,), lambda: iter(([1], [2])), meter=meter())
    state = [0]
    def unstable(x):
        state[0] += 1
        return x+state[0]
    with pytest.raises(ValueError):
        OpenPythonToolboxAdapter().ingest((unstable,), lambda: iter((1, 2)), meter=meter())


def test_pareto_signatures_preserve_low_primitive_and_low_evolved_representatives():
    dag = FullSignatureQuotientDAG()
    x = variable("INT")
    assert dag.retain(x, "scope", (1, 2), 2, primitive_expansion=4)
    assert dag.retain(x, "scope", (1, 2), 3, primitive_expansion=3)
    assert not dag.retain(x, "scope", (1, 2), 4, primitive_expansion=5)
    assert len(next(iter(dag.frontiers.values()))) == 2


def test_ratchet_pareto_counterexample_and_independent_exhaustive_agreement():
    inc = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    add_three = Operator("op_1", ("INT",), "INT", lambda x: x+3, cost=2)
    g = Grammar("INT", (inc, add_three))
    body = typed_hole("INT")
    for _ in range(3):
        body = apply(inc, body)
    skill = ParametricSkillMacro(body, ("INT",))
    kw = dict(macros=(skill,), evolved=True, primitive_cap=4)
    q = {(tuple(freeze(y) for y in ys)) for e, ys, _ in ExactEnumerator(g, (0, 1, 2), 4, meter=meter(), **kw)}
    ex = {(tuple(freeze(y) for y in ys)) for e, ys, _ in ExhaustiveASTEnumerator(g, (0, 1, 2), 4, meter=meter(), **kw)}
    assert q == ex
    assert tuple(freeze(y) for y in (4, 5, 6)) in q


def test_two_operator_skill_has_full_cost_in_a_and_one_evolved_step_in_b():
    inc = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    g = Grammar("INT", (inc,))
    skill = ParametricSkillMacro(apply(inc, apply(inc, typed_hole("INT"))), ("INT",))
    program = skill.call(skill.call(variable("INT")))
    fixed = ExactEnumerator(g, (0, 1), 3, macros=(skill,))
    evolved = ExactEnumerator(g, (0, 1), 3, macros=(skill,), evolved=True, primitive_cap=6)
    assert primitive_cost(program, g.ops) == 5
    assert fixed.cost(program) == 5 and evolved.cost(program) == 3
    assert evolved.description_cost(program) == 5
    public = ((0, 4), (1, 5))
    assert solve(g, public, 2, "INT", 3, meter=meter()).status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
    result = solve(g, public, 2, "INT", 3, macros=(skill,), evolved=True, primitive_cap=6, meter=meter())
    assert result.witnesses and verify_certificate(g, public, 2, "INT", 3, result, macros=(skill,), evolved=True, primitive_cap=6, meter=meter())


def test_twin_finds_real_counterexample_but_never_certifies_uniqueness():
    a = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    b = Operator("op_1", ("INT",), "INT", lambda x: 99 if x == 7 else x+1)
    g = Grammar("INT", (a, b))
    twin = PopperianTwinVerifier(max_mutations=2)
    result = solve(g, ((1, 2), (2, 3)), 7, "INT", 2, twin_verifier=twin, meter=meter())
    assert result.status == "AMBIGUOUS_WITNESS_FOUND"
    assert twin.last_report["witness_found"] and not twin.last_report["uniqueness_certified"]
    assert verify_certificate(g, ((1, 2), (2, 3)), 7, "INT", 2, result, meter=meter())


def test_failed_or_empty_twin_neighborhood_continues_exact_search():
    g = Grammar("INT", (Operator("op_0", ("INT",), "INT", abs),))
    trace = {}
    result = solve(g, ((1, 1), (2, 2)), -3, "INT", 2,
        twin_verifier=PopperianTwinVerifier(max_mutations=0), trace=trace, meter=meter())
    assert result.status == "AMBIGUOUS_WITNESS_FOUND"
    assert not trace["twin"]["witness_found"]


def learned_source_functors():
    found = {}
    for world in procedural_worlds()[:2]:
        m = meter()
        roles = AutoOperatorFingerprinter().fingerprint_roles(world.grammar.operators, world.carriers, meter=m)
        player = ZeroDataFrontierSelfPlay(24012, 3, public_count=2, behavioral_features=True)
        player.wake(world, attempts=6, meter=m)
        selected, audit = select_ratcheted_source_skills(player, world, max_skills=3, meter=m)
        library = JournalSkillView()
        for skill in selected:
            assert library.promote_ratcheted(skill, player, world, meter=m)["accepted"]
            for functor in AlgebraicRoleFunctor.lift(skill, roles):
                found[functor.key()] = functor
        assert selected
    return tuple(found[k] for k in sorted(found))


def assert_deep_transfer_mechanism():
    """Existence proof on unit carriers, NOT fresh assessment performance."""
    functors = learned_source_functors()
    assert functors
    bit = procedural_worlds()[-1]
    bit_roles = AutoOperatorFingerprinter().fingerprint_roles(bit.grammar.operators, bit.carriers, meter=meter())
    raw = OpenPythonToolboxAdapter().ingest((operator.neg, abs, operator.invert),
        lambda: iter((-5, -3, -1, 0, 1, 2, 4, 7)), meter=meter())
    for grammar, roles, inputs in ((bit.grammar, bit_roles, bit.inputs), (raw.grammar, raw.roles, raw.seed_inputs)):
        m = meter()
        skills, lineage = zero_shot_role_transfer(functors, grammar, roles, inputs, meter=m)
        assert skills and all(row["target_training_tasks"] == 0 for row in lineage)
        primitive = list(ExactEnumerator(grammar, inputs, 5, meter=m))
        checked = 0
        # Search the deterministic unit grammar for a nontrivial deep example;
        # no evaluator outcome is used to select an assessment or freeze seed.
        for teacher, outputs, cost in primitive:
            if cost not in (4, 5):
                continue
            public = tuple(zip(inputs[:-1], outputs[:-1]))
            static = solve(grammar, public, inputs[-1], teacher.sort, 3, meter=m)
            if static.status != "NO_PROGRAM_IN_BOUNDED_GRAMMAR":
                continue
            evolved = solve(grammar, public, inputs[-1], teacher.sort, 3, macros=skills,
                            evolved=True, primitive_cap=6, meter=m)
            if evolved.witnesses:
                assert verify_certificate(grammar, public, inputs[-1], teacher.sort, 3, evolved,
                    macros=skills, evolved=True, primitive_cap=6, meter=m)
                checked += 1
                break
        assert checked > 0


def test_bounded_open_toolbox_runtime_learns_and_frozen_targets_cannot_update():
    engine = OpenToolboxLearningEngine(meter=meter())
    engine.enter_toolbox((operator.neg, abs, operator.invert), lambda: iter((-5, -3, -1, 0, 1, 2, 4, 7)))
    report = engine.learn_source(seed=24012)
    assert report["training_rows"] > 0 and report["skills"] > 0 and report["functors"] > 0
    target = OpenToolboxLearningEngine(meter=meter(), frozen=True)
    target.enter_toolbox((operator.neg, abs, operator.invert), lambda: iter((-5, -3, -1, 0, 1, 2, 4, 7)))
    transfer = target.receive_source_functors(engine.functors)
    assert transfer["transferred_skills"] > 0 and target.source_cycles == 0
    before = (target.critic.fingerprint(), tuple(s.key() for s in target.library.snapshot()))
    result = target.solve_public(((-2, 2), (1, 1)), -3)
    assert result.witnesses
    assert before == (target.critic.fingerprint(), tuple(s.key() for s in target.library.snapshot()))
    with pytest.raises(ValueError, match="frozen"):
        target.learn_source()


def test_behavioral_critic_has_ten_features_and_no_query_answer_feature():
    world = procedural_worlds()[0]
    player = ZeroDataFrontierSelfPlay(24012, 3, public_count=2, behavioral_features=True)
    player.wake(world, attempts=6, meter=meter())
    assert player.training_rows and all(len(r["features"]) == 10 for r in player.training_rows)
    critic = DerivationOutcomeCritic(feature_count=10).fit(player.training_rows, meter=meter())
    assert critic.models is not None
    with pytest.raises(ValueError):
        critic.predict((0.,)*6, meter=meter())


def test_source_solve_consolidates_actual_derivations_but_not_predicted_rewards():
    engine = OpenToolboxLearningEngine(meter=meter())
    engine.enter_toolbox((operator.neg, abs, operator.invert), lambda: iter((-5, -3, -1, 0, 1, 2, 4, 7)))
    before = engine.critic.fingerprint()
    result, report = engine.solve_and_learn(((-3, 3), (-1, 1), (0, 0), (2, 2), (7, 7)), -5)
    assert result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
    assert report["consolidated"] and report["source_rows"] > 0
    assert not report["external_query_answer_used"] and not report["predicted_reward_used_as_observed"]
    assert engine.critic.fingerprint() != before and engine.source_cycles == 1


def test_source_role_runner_replay_detects_fabricated_transfer_on_a_unit_world():
    from copy import deepcopy
    from pathlib import Path
    import json
    from nexus.wave24_self_evolving_loop import World
    from nexus.wave24_quotient_core import skill_wire
    from scripts.run_wave24_azr_ruler_cegis import prepare_role_source, ROOT, CONFIG_PATH
    from scripts.verify_wave24_azr_ruler_cegis import verify_role_source
    config = json.loads((ROOT/CONFIG_PATH).read_text())
    inc = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    grammar = Grammar("INT", (inc,))
    worlds = tuple(World(name, grammar, "INT", tuple(range(9)), {"INT": tuple(range(9))})
        for name in ("UNIT_A", "UNIT_B", "UNIT_C", "UNIT_D", "BIT_CELLULAR_AUTOMATA"))
    critic, libraries, source = prepare_role_source(worlds, config, 24123, meter(), None)
    payload = dict(seed=24123, source_preparation=source,
        libraries={name: [skill_wire(s) for s in library.snapshot()] for name, library in libraries.items()})
    for key in ("intra_domain_promoted_skills_count", "cross_domain_role_functors_count", "unseen_world_selfplay_tasks",
                "unseen_world_training_rows", "unseen_world_zero_shot_transferred_skills_count"):
        payload[key] = source[key]
    gates, errors = verify_role_source(payload, {w.name:w for w in worlds}, config, meter(), replay=True)
    assert not errors, errors
    assert gates["zero_shot_transfer_without_target_training"]
    corrupt = deepcopy(payload)
    corrupt["source_preparation"]["transfer_lineage"][0]["source_skill"] = "forged"
    _, errors = verify_role_source(corrupt, {w.name:w for w in worlds}, config, meter(), replay=True)
    assert any("transfer_lineage" in e for e in errors)
