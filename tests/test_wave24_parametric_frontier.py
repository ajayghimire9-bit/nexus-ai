"""Deterministic mathematical fixtures, not procedural assessment outcomes."""
from copy import deepcopy

import pytest

from nexus.wave24_quotient_core import (
    Expr, Grammar, Operator, WorkMeter, ExactEnumerator, ExhaustiveASTEnumerator,
    ParametricSkillMacro, apply, variable, typed_hole, primitive_cost, eval_expr,
    eval_expr_steps, expanded_skill_call, skill_wire, skill_from_wire,
    validate_program, solve, verify_certificate, freeze,
)
from nexus.wave24_self_evolving_loop import (
    World, ZeroDataFrontierSelfPlay, DerivationOutcomeCritic,
    DualHeadExecutionScorer, DualHorizonVerifier, PublicTask, JournalSkillView,
    ShadowPair, mine_parametric_skills, procedural_worlds,
)


def meter():
    return WorkMeter(limit=2_000_000, wall_limit=5.)


def fixture():
    op = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    grammar = Grammar("INT", (op,))
    world = World("source_unit", grammar, "INT", tuple(range(9)), {"INT": tuple(range(9))})
    body = typed_hole("INT")
    for _ in range(3):
        body = apply(op, body)
    return world, ParametricSkillMacro(body, ("INT",))


def test_parametric_call_changes_with_intermediate_argument_and_exact_cost():
    world, skill = fixture()
    x = variable("INT")
    intermediate = apply(world.grammar.operators[0], x)
    call = skill.call(intermediate)
    assert skill.expansion_cost(world.grammar.ops) == 3
    assert primitive_cost(skill, world.grammar.ops) == 4
    assert primitive_cost(call, world.grammar.ops) == 5
    assert eval_expr(skill.call(x), 10, world.grammar.ops) == 13
    assert eval_expr(call, 10, world.grammar.ops) == 14
    assert ExactEnumerator(world.grammar, (0, 1), 5, macros=(skill,), mdl=True).cost(call) == 4
    assert ExactEnumerator(world.grammar, (0, 1), 5, macros=(skill,)).cost(call) == 5
    assert validate_program(call, world.grammar, macros=(skill,))
    with pytest.raises(ValueError):
        validate_program(call, world.grammar)
    assert skill_from_wire(skill_wire(skill)) == skill


def test_two_typed_holes_are_real_arguments_and_invalid_holes_are_rejected():
    op = Operator("op_0", ("INT", "INT"), "INT", lambda a, b: a-b)
    g = Grammar("INT", (op,))
    skill = ParametricSkillMacro(apply(op, typed_hole("INT", 0), typed_hole("INT", 1)), ("INT", "INT"))
    call = skill.call(variable("INT"), apply(op, variable("INT"), variable("INT")))
    assert eval_expr(call, 7, g.ops) == 7
    assert primitive_cost(call, g.ops) == 5
    for bad in (apply(op, typed_hole("INT"), typed_hole("INT")), variable("INT")):
        with pytest.raises(ValueError):
            ParametricSkillMacro(bad, ("INT",))
    with pytest.raises(ValueError):
        skill.call(variable("STR"), variable("INT"))
    with pytest.raises(ValueError):
        ParametricSkillMacro(Expr("hole", "INT", True), ("INT",))
    with pytest.raises(ValueError):
        ParametricSkillMacro(Expr("hole", "INT", 0, (variable("INT"),)), ("INT",))


@pytest.mark.parametrize("mdl", [False, True])
def test_parametric_quotient_and_independent_syntax_search_agree(mdl):
    world, skill = fixture()
    args = (world.grammar, (0, 1, 4), 5)
    kwargs = dict(macros=(skill,), mdl=mdl)
    q = {(e.sort, tuple(freeze(x) for x in ys)) for e, ys, _ in ExactEnumerator(*args, meter=meter(), **kwargs)}
    ex = {(e.sort, tuple(freeze(x) for x in ys)) for e, ys, _ in ExhaustiveASTEnumerator(*args, meter=meter(), **kwargs)}
    assert q == ex


def test_certificate_b_really_extends_a_primitive_horizon_and_replays():
    world, skill = fixture()
    public = ((0, 4), (2, 6))
    static = solve(world.grammar, public, 5, "INT", 4, meter=meter())
    result = solve(world.grammar, public, 5, "INT", 4, meter=meter(), macros=(skill,), mdl=True)
    assert static.status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
    assert result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
    assert all(primitive_cost(e, world.grammar.ops) == 5 for e in result.witnesses)
    assert verify_certificate(world.grammar, public, 5, "INT", 4, result, macros=(skill,), mdl=True, meter=meter())


def test_certificate_a_does_not_extend_horizon_or_expose_macro_witnesses():
    world, skill = fixture()
    task = PublicTask(((0, 4), (2, 6)), 5, "INT")
    assert DualHorizonVerifier(4, 4).fixed(world.grammar, task, (skill,), meter()).status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
    task = PublicTask(((0, 3), (2, 5)), 5, "INT")
    result = DualHorizonVerifier(4, 4).fixed(world.grammar, task, (skill,), meter())
    assert verify_certificate(world.grammar, task.public_io, task.query, "INT", 4, result, meter=meter())


def test_cooperative_skill_interpreter_agrees_and_charges_substitution():
    world, skill = fixture()
    expr = skill.call(variable("INT"))
    m = meter()
    stream = eval_expr_steps(expr, 4, world.grammar.ops, m)
    ticks = 0
    while True:
        try:
            next(stream)
            ticks += 1
        except StopIteration as stop:
            assert stop.value == eval_expr(expanded_skill_call(expr), 4, world.grammar.ops)
            break
    assert ticks == m.total and ticks > primitive_cost(expr, world.grammar.ops)


def test_direct_frontier_mining_produces_minimal_classes_and_derivation_rows():
    world, _ = fixture()
    m = meter()
    player = ZeroDataFrontierSelfPlay(12, 5)
    tasks = player.wake(world, attempts=6, meter=m)
    assert len(tasks) == 3
    assert player.attempts == 1 and player.diagnostics["quotient_complete"]
    assert player.diagnostics["training_rows_generated"] > 0
    # A grammar with only increment has one class per tier: there is no real
    # same-tier nonancestor. Do not invent negative rows to balance the labels.
    assert {r["J_fit"] for r in player.training_rows} == {1}
    assert all(t.minimum_cost == t.teacher_primitive_cost for t in tasks)
    assert m.counts["training_work_units"] > 0
    for task in tasks:
        exhaustive = list(ExhaustiveASTEnumerator(world.grammar,
            [x for x, _ in task.public_view.public_io]+[task.public_view.query], task.minimum_cost-1, meter=meter()))
        target = [freeze(y) for _, y in task.public_view.public_io]+[freeze(task.teacher_query)]
        assert all([freeze(y) for y in ys] != target for _, ys, _ in exhaustive)
    with pytest.raises(ValueError, match="one bounded"):
        player.wake(world, attempts=1, meter=m)


def test_full_signature_minimality_is_not_a_public_only_proof():
    # Identity and abs agree on every nonnegative public input, differ on query.
    g = Grammar("INT", (Operator("op_0", ("INT",), "INT", abs),))
    entries = list(ExactEnumerator(g, (1, 2, -3), 2, meter=meter()))
    assert len(entries) == 2
    assert entries[1][2] == 2
    assert entries[0][1][:-1] == entries[1][1][:-1]
    assert entries[0][1][-1] != entries[1][1][-1]


def test_derivation_critic_uses_binary_labels_not_censored_work_labels():
    world, _ = fixture()
    player = ZeroDataFrontierSelfPlay(2, 5)
    player.wake(world, attempts=6, meter=meter())
    critic = DerivationOutcomeCritic()
    report = player.sleep(world, critic, meter())
    assert report["scorer_fitted"] and critic.models is not None
    rows = deepcopy(player.training_rows)
    rows[0]["purpose"] = "evaluation"
    with pytest.raises(ValueError):
        critic.fit(rows, meter=meter())
    with pytest.raises(ValueError):
        player.sleep(world, DualHeadExecutionScorer(), meter())


def test_anti_unification_finds_open_template_with_positive_exact_compression():
    world, _ = fixture()
    player = ZeroDataFrontierSelfPlay(2, 5)
    player.wake(world, attempts=6, meter=meter())
    candidates = mine_parametric_skills(player, world, meter=meter())
    assert candidates
    best = candidates[0]
    assert best["primitive_expansion_cost"] > best["mdl_call_cost"]
    assert best["compression_utility"] > 0 and best["occurrence_classes"] >= 2
    assert isinstance(best["skill"], ParametricSkillMacro)
    assert best["distinct_arguments"] >= 2


def test_library_size_changes_real_compression_not_just_a_name():
    world, skill = fixture()
    op = world.grammar.operators[0]
    other = ParametricSkillMacro(apply(op, apply(op, typed_hole("INT"))), ("INT",))
    expr = skill.call(variable("INT"))
    one = ExactEnumerator(world.grammar, (0, 1), 5, macros=(skill,), mdl=True)
    two = ExactEnumerator(world.grammar, (0, 1), 5, macros=(skill, other), mdl=True)
    assert one.cost(expr) == 3 < primitive_cost(expr, world.grammar.ops)
    assert two.cost(expr) == 4 == primitive_cost(expr, world.grammar.ops)
    # A second name may erase compression; it cannot get a free 2-unit code.


def test_disagreement_rows_come_from_real_public_equivalence_groups():
    # Identical public predictions, genuinely different query results.
    op0 = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    op1 = Operator("op_1", ("INT",), "INT", abs)
    world = World("split_unit", Grammar("INT", (op0, op1)), "INT", tuple(range(-6, 7)), {})
    from types import SimpleNamespace
    player = ZeroDataFrontierSelfPlay(1, 4, public_count=2)
    # Authored unit inputs, not a scientific seed selection: these expose the
    # identity/abs ambiguity while allowing nonconstant public frontier tasks.
    player.generator.rng = SimpleNamespace(sample=lambda population, n: [1, 2, -3])
    player.wake(world, attempts=30, meter=meter())
    # The data, rather than a requirement to emit both classes, determines
    # whether there is a positive disagreement label. No label is invented.
    groups = {}
    for expr, outputs, cost in player.derivations:
        groups.setdefault((expr.sort, tuple(freeze(y) for y in outputs[:-1])), set()).add(freeze(outputs[-1]))
    assert player.diagnostics["disagreement_classes"] == sum(len(v) >= 2 for v in groups.values())
    assert player.diagnostics["disagreement_classes"] > 0
    assert {r["J_fit"] for r in player.training_rows} == {0, 1}
    assert any(r["J_disagree"] == 1 for r in player.training_rows)


def test_empty_skill_interval_is_reported_not_fabricated_at_current_bound_three():
    world, _ = fixture()
    player = ZeroDataFrontierSelfPlay(2, 3)
    player.wake(world, attempts=6, meter=meter())
    assert player.accepted and player.training_rows
    assert mine_parametric_skills(player, world, meter=meter()) == ()


def test_empty_frontier_and_heldout_prohibition_fail_honestly():
    g = Grammar("INT", (Operator("op_0", ("INT",), "INT", lambda x: x),))
    world = World("identity_unit", g, "INT", (0, 1, 2), {"INT": (0, 1, 2)})
    player = ZeroDataFrontierSelfPlay(2, 5)
    assert player.wake(world, attempts=4, meter=meter()) == ()
    assert player.diagnostics["frontier_classes_available"] == 0
    with pytest.raises(ValueError, match="held-out"):
        ZeroDataFrontierSelfPlay(2, 5).wake(procedural_worlds()[-1], attempts=4, meter=meter())


def test_skill_quarantine_is_an_append_only_source_action():
    _, skill = fixture()
    view = JournalSkillView()
    pairs = [ShadowPair(str(i), 100, 0) for i in range(50)]
    assert view.promote(skill, pairs, gain_bound=100)["accepted"]
    before = view.journal.snapshot()
    view.quarantine(skill, source_net_utility=-1)
    assert view.snapshot() == ()
    assert view.journal.snapshot()[:len(before)] == before
    with pytest.raises(ValueError):
        view.quarantine(skill, source_net_utility=-1, purpose="evaluation")


def test_observed_nonpositive_source_utility_automatically_quarantines():
    _, skill = fixture()
    view = JournalSkillView()
    view.promote(skill, [ShadowPair(str(i), 100, 0) for i in range(50)], gain_bound=100)
    assert view.observe_source_utility(skill, source_net_utility=1)
    assert view.snapshot() == (skill,)
    assert not view.observe_source_utility(skill, source_net_utility=0)
    assert view.snapshot() == ()
