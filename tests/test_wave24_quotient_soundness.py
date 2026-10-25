"""Deterministic engineering fixtures, NOT post-freeze scientific evaluations."""
import itertools
import math
from copy import deepcopy

import pytest

from nexus.wave24_quotient_core import (
    MISSING_KEY, Binding, ExactEnumerator, ExhaustiveASTEnumerator, Expr,
    FullSignatureQuotientDAG, Grammar, Operator, WorkExhausted, WorkMeter,
    apply, constant, eval_expr, freeze, prefix_first_trajectories,
    primitive_cost, solve, symkan_accounting, variable,
    validate_program, verify_certificate,
    NoetherConservationGate, MASS_EXPANSIVE, MASS_PRESERVING, MASS_CONTRACTIVE,
)
from nexus.wave24_auto_laws import AutoOperatorFingerprinter
from nexus.wave24_self_evolving_loop import (
    METHODS, DualHeadExecutionScorer, DualHorizonVerifier, JournalSkillView,
    PublicTask, SeededProceduralTaskGenerator, ShadowPair, ZeroDataFrontierSelfPlay,
    execution_features, horizon_break_even, procedural_worlds, run_method,
    FrozenSourceState, source_execution_trace,
    depth_one_fits,
)
from nexus.evolution1.fixtures import verify_journal


def meter():
    return WorkMeter(limit=500_000, wall_limit=5)


def semantic_set(grammar, inputs, bound, *, quotient):
    cls = ExactEnumerator if quotient else ExhaustiveASTEnumerator
    enum = cls(grammar, inputs, bound, quotient=quotient, meter=meter())
    values = {(e.sort, tuple(freeze(v) for v in out)) for e, out, _ in enum}
    assert enum.complete
    return values


def assert_differential(grammar, public, query, output_sort, bound):
    exact = solve(grammar, public, query, output_sort, bound, quotient=False, meter=meter())
    quotient = solve(grammar, public, query, output_sort, bound, meter=meter())
    assert exact.status == quotient.status
    if len(exact.query_values) < 2:
        assert tuple(map(freeze, exact.query_values)) == tuple(map(freeze, quotient.query_values))
    for result in (exact, quotient):
        for expr, value in zip(result.witnesses, result.query_values):
            assert all(freeze(eval_expr(expr, x, grammar.ops)) == freeze(y) for x, y in public)
            assert freeze(eval_expr(expr, query, grammar.ops)) == freeze(value)
    return quotient


def test_missing_is_not_none_and_bool_is_not_int():
    assert len({freeze(None), freeze(MISSING_KEY), freeze(False), freeze(0)}) == 4
    assert freeze(deepcopy(MISSING_KEY)) == freeze(MISSING_KEY)
    assert freeze({"x": None}) != freeze({})


def test_intermediate_classes_are_never_capped_at_two_query_values():
    dag = FullSignatureQuotientDAG()
    for i in range(7):
        assert dag.retain(constant("I", i), "scope", (0, i), 3)
    assert len(dag.classes) == 7
    assert dag.retain(constant("I", 0), "other-scope", (0, 0), 1)
    assert not dag.retain(constant("I", 8), "scope", (0, 0), 3)
    assert dag.retain(constant("I", 8), "scope", (0, 0), 2)


def test_noninjective_parent_needs_third_intermediate_value():
    # The first two child query values collapse under this parent, the third
    # does not. A two-value intermediate cap destroys a real root witness.
    ops = (
        Operator("op_0", ("I",), "I", lambda x: 0),
        Operator("op_1", ("I",), "I", lambda x: int(x == 7)),
        Operator("op_2", ("I",), "I", lambda x: 2*int(x == 7)),
        Operator("op_3", ("I",), "BOOL", lambda z: z == 2),
    )
    g = Grammar("I", ops)
    assert semantic_set(g, (3, 7), 3, quotient=False) == semantic_set(g, (3, 7), 3, quotient=True)
    result = assert_differential(g, ((3, False),), 7, "BOOL", 3)
    assert result.status == "AMBIGUOUS_WITNESS_FOUND"


@pytest.mark.parametrize("kind", ("abs", "mod", "eq", "overwrite", "slice"))
def test_noninjective_operators_differential(kind):
    if kind == "overwrite":
        ops = (Operator("op_0", ("D",), "D", lambda d: {**d, "a": None}),
               Operator("op_1", ("D",), "D", lambda d: {**d, "b": 1}),
               Operator("op_2", ("D",), "V", lambda d: d.get("a", MISSING_KEY)))
        g, xs, sort = Grammar("D", ops), ({}, {"a": None}, {"a": 1}), "V"
    elif kind == "slice":
        ops = (Operator("op_0", ("S",), "S", lambda x: x[:1]),
               Operator("op_1", ("S",), "S", lambda x: x[1:]),
               Operator("op_2", ("S",), "S", lambda x: x[::-1]))
        g, xs, sort = Grammar("S", ops), ((), ("",), ("a", "b")), "S"
    else:
        fn = {"abs": abs, "mod": lambda x: x % 2, "eq": lambda x: int(x == 2)}[kind]
        ops = (Operator("op_0", ("I",), "I", fn),
               Operator("op_1", ("I",), "I", lambda x: -x),
               Operator("op_2", ("I",), "I", lambda x: x+1))
        g, xs, sort = Grammar("I", ops), (-2, 0, 7), "I"
    assert semantic_set(g, xs, 4, quotient=False) == semantic_set(g, xs, 4, quotient=True)
    y = eval_expr(variable(g.input_sort), xs[0], g.ops)
    assert_differential(g, ((xs[0], y),), xs[-1], g.input_sort, 4)


def test_auditor_seven_predicate_uses_parent_reachable_universe():
    # On the original [7], z==2 and False agree. On mod-5's reachable [2]
    # they differ. Binding scopes must use [2], never the original [7].
    mod = Operator("op_0", ("SEQ",), "SEQ", lambda x: tuple(v % 5 for v in x))
    eq2 = Operator("op_1", ("I",), "BOOL", lambda z: z == 2)
    g = Grammar("SEQ", (mod, eq2), (constant("BOOL", False),),
                (Binding("map", "SEQ", "I", "BOOL"),))
    all_exact = semantic_set(g, ((7,), (8,)), 5, quotient=False)
    all_quotient = semantic_set(g, ((7,), (8,)), 5, quotient=True)
    assert all_exact == all_quotient
    target = ("SEQ", (freeze((True,)), freeze((False,))))
    assert target in all_quotient
    result = assert_differential(g, (((7,), (True,)),), (8,), "SEQ", 5)
    assert result.witnesses


def test_filter_uses_every_reachable_element_and_charges_each():
    eq = Operator("op_0", ("I",), "BOOL", lambda z: z == 2)
    g = Grammar("SEQ", (eq,), bindings=(Binding("filter", "SEQ", "I", "BOOL"),))
    expr = Expr("filter", "SEQ", None, (variable("SEQ"), apply(eq, variable("I"))))
    m = meter()
    assert eval_expr(expr, (7, 2, 2, 4), g.ops, m) == (2, 2)
    assert m.total == 1 + 4*(1+1+1)
    assert semantic_set(g, ((7, 2), (2, 4)), 4, quotient=False) == semantic_set(g, ((7, 2), (2, 4)), 4, quotient=True)


@pytest.mark.parametrize("world_name", ("STATE_TRANSITION", "BIT_CELLULAR_AUTOMATA"))
def test_prefix_first_full_state_congruence(world_name):
    world = next(w for w in procedural_worlds() if w.name == world_name)
    exact = list(prefix_first_trajectories(world.grammar.operators, world.inputs[:3], 4, meter(), quotient=False))
    quotient = list(prefix_first_trajectories(world.grammar.operators, world.inputs[:3], 4, meter()))
    signatures = lambda rows: {tuple(map(freeze, p.states)) for p in rows}
    assert signatures(exact) == signatures(quotient)
    for prefix in quotient:
        states = world.inputs[:3]
        for name in prefix.steps:
            states = tuple(world.grammar.ops[name].fn(s) for s in states)
        assert tuple(map(freeze, states)) == tuple(map(freeze, prefix.states))


def test_prefix_projection_cannot_merge_distinct_hidden_full_states():
    ops = (Operator("op_0", ("S",), "S", lambda s: (s[0], 1-s[1])),
           Operator("op_1", ("S",), "S", lambda s: (s[1], s[0])))
    rows = list(prefix_first_trajectories(ops, ((0, 0),), 2, meter()))
    assert ((1, 0),) in [p.states for p in rows]


def test_root_disagreement_discharge_does_not_discard_intermediates():
    ops = (Operator("op_0", ("I",), "I", lambda x: x+1),
           Operator("op_1", ("I",), "BOOL", lambda x: x % 2 == 0))
    g = Grammar("I", ops)
    result = solve(g, ((0, True),), 2, "BOOL", 5, quotient=False, meter=meter())
    assert result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
    assert result.root_equivalence_discharges > 0


def test_work_exhaustion_never_certifies_no_program_or_unique():
    g = Grammar("I", (Operator("op_0", ("I",), "I", lambda x: x+1),))
    r = solve(g, ((0, 99),), 1, "I", 10, meter=WorkMeter(limit=3))
    assert r.status == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED" and not r.complete


def test_contradictory_observations_rejected_before_search():
    r = solve(Grammar("I", ()), ((1, 2), (1, 3)), 4, "I", 1)
    assert r.status == "VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS"


def test_resumable_enumerator_does_not_restart_or_precompute():
    g = Grammar("I", (Operator("op_0", ("I",), "I", abs),))
    m = meter()
    enum = ExactEnumerator(g, (-2, 7), 4, meter=m)
    assert m.total == 0
    stream = iter(enum)
    first = next(stream)
    charged = m.total
    second = next(stream)
    assert first[2] < second[2] and m.total > charged
    list(stream)
    assert enum.complete


@pytest.mark.parametrize("world", procedural_worlds(), ids=lambda w: w.name)
def test_anonymous_laws_exhaustive_differential_all_five_worlds(world):
    m = meter()
    laws = AutoOperatorFingerprinter().discover(world.grammar.operators, world.carriers,
                                              complete_carriers=True, meter=m)
    assert laws.certified and laws.laws and m.counts["setup_work_units"] > 0
    full = ExactEnumerator(world.grammar, world.inputs, 4, quotient=False, meter=meter())
    expected = {(e.sort, tuple(map(freeze, out))) for e, out, _ in full}
    reduced = ExactEnumerator(world.grammar, world.inputs, 4, laws=laws, meter=meter())
    actual = {(e.sort, tuple(map(freeze, out))) for e, out, _ in reduced}
    assert expected == actual
    assert_differential(world.grammar, ((world.inputs[0], world.inputs[0]),), world.inputs[-1], world.output_sort, 4)


def test_commutativity_identities_annihilators_are_execution_discovered():
    add = Operator("op_9", ("B", "B"), "B", lambda a, b: a or b)
    g = Grammar("B", (add,), (constant("B", False), constant("B", True)))
    laws = AutoOperatorFingerprinter().discover((add,), {"B": (False, True)}, complete_carriers=True, meter=meter())
    kinds = {l.kind for l in laws.laws}
    assert {"commutative", "identity_right", "annihilator_left"} <= kinds
    assert semantic_set(g, (False, True), 5, quotient=False) == {
        (e.sort, tuple(map(freeze, out))) for e, out, _ in ExactEnumerator(g, (False, True), 5, laws=laws, meter=meter())}


def test_sampled_or_nonclosed_probes_never_authorize_pruning():
    op = Operator("op_0", ("I",), "I", lambda x: x if x < 2 else x+1)
    laws = AutoOperatorFingerprinter().discover((op,), {"I": (0, 1)}, meter=meter())
    assert not laws.certified and not laws.laws and laws.hypotheses
    g = Grammar("I", (op,))
    expr = apply(op, apply(op, variable("I")))
    assert not laws.redundant(expr, (2,), g, meter())
    nonclosed = AutoOperatorFingerprinter().discover((op,), {"I": (0, 1, 2)}, complete_carriers=True, meter=meter())
    assert not nonclosed.certified
    truncated = AutoOperatorFingerprinter(probe_cap=2).discover((op,), {"I": (0, 1)}, complete_carriers=True, meter=meter())
    assert not truncated.certified


def test_law_scope_and_operator_identity_enforced():
    op = Operator("op_0", ("I",), "I", abs)
    laws = AutoOperatorFingerprinter().discover((op,), {"I": (0, 1)}, complete_carriers=True, meter=meter())
    expr = apply(op, apply(op, variable("I")))
    # abs looks involutive on nonnegative probes but not on -1.
    assert not laws.redundant(expr, (-1,), Grammar("I", (op,)), meter())
    changed = Operator("op_0", ("I",), "I", lambda x: x+1)
    assert not laws.redundant(expr, (0,), Grammar("I", (changed,)), meter())


def test_measure_preconditions_are_local_not_global_family_rules():
    tail = Operator("op_0", ("S",), "S", lambda x: x[1:])
    carrier = ((), (1,), (1, 1))
    laws = AutoOperatorFingerprinter().discover((tail,), {"S": carrier}, complete_carriers=True, meter=meter())
    assert not laws.root_measure_possible("op_0", ((1,),), (1, 1), meter())
    # The exact same local result can be fed to an expanding parent; there is
    # intentionally no API that applies this constraint to that ancestor.
    assert laws.root_measure_possible("op_0", ((1,),), (), meter())


def test_impure_or_nondeterministic_operators_fail_closed():
    def mutate(x):
        x.append(1)
        return x
    with pytest.raises(ValueError, match="mutated"):
        Operator("op_0", ("L",), "L", mutate).call(([],), meter(), "setup_work_units")
    count = itertools.count()
    op = Operator("op_0", ("I",), "I", lambda x: next(count))
    with pytest.raises(ValueError, match="nondeterministic"):
        AutoOperatorFingerprinter().discover((op,), {"I": (0, 1)}, complete_carriers=True, meter=meter())


def test_symkan_nonempty_faithful_and_abstained_accounting():
    rows = [dict(attempted=True, induced_expression="x", faithful_export=True),
            dict(attempted=True, induced_expression="", faithful_export=False),
            dict(attempted=False, induced_expression=None, faithful_export=False)]
    counts = symkan_accounting(rows)
    assert counts == dict(symkan_attempted_count=2, symkan_nonempty_induced_count=1,
                          symkan_abstained_count=1, symkan_faithful_export_count=1)
    for bad in (dict(attempted=True, induced_expression="x", faithful_export=False),
                dict(attempted=False, induced_expression="x", faithful_export=True),
                dict(attempted=True, induced_expression="", faithful_export=True)):
        with pytest.raises(ValueError):
            symkan_accounting([bad])


def test_seeded_generator_reproducible_without_handpicked_bank():
    world = procedural_worlds()[0]
    a, b = SeededProceduralTaskGenerator(71, 3), SeededProceduralTaskGenerator(71, 3)
    for _ in range(4):
        ta, tb = a.sample(world, meter()), b.sample(world, meter())
        assert ta.teacher.key() == tb.teacher.key()
        assert ta.public_view == tb.public_view
        assert ta.minimum_cost is None  # depth alone is not a proof
        assert ta.teacher_primitive_cost <= 6


def test_selfplay_rejects_heldout_world_and_has_strict_attempt_limit():
    player = ZeroDataFrontierSelfPlay(3)
    with pytest.raises(ValueError, match="held-out"):
        player.wake(procedural_worlds()[-1], attempts=1, meter=meter())
    with pytest.raises(ValueError, match="bounded"):
        player.wake(procedural_worlds()[0], attempts=101, meter=meter())
    assert player.wake(procedural_worlds()[0], attempts=0, meter=meter()) == ()


def test_dual_head_uses_only_source_feedback_and_reports_real_predictions():
    rows = [dict(features=(1., float(i), 1., 1., 0., 0.), fit_work=float(10-i),
                 disagree_work=float(i), purpose="training") for i in range(1, 5)]
    scorer = DualHeadExecutionScorer(.5)
    m = meter()
    scorer.fit(rows, meter=m)
    scores = scorer.predict(rows[0]["features"], meter=m)
    assert len(scores) == 2 and all(math.isfinite(v) for v in scores)
    assert scorer.predict(rows[-1]["features"], meter=m)[1] > scores[1]
    assert m.counts["training_work_units"] and m.counts["scorer_work_units"]
    bad = [dict(rows[0], purpose="confirmation")]
    with pytest.raises(ValueError, match="source"):
        scorer.fit(bad, meter=m)
    with pytest.raises(ValueError, match="authorization"):
        scorer.benchmark([rows[0]["features"]], backend="mps")


def test_skill_shadow_hygiene_and_journal_reuse():
    view = JournalSkillView()
    skill = apply(Operator("op_0", ("I",), "I", abs), variable("I"))
    assert not view.promote(skill, [ShadowPair("a", 10, 10), ShadowPair("b", 10, 10)], gain_bound=1)["accepted"]
    pairs = [ShadowPair(str(i), 10, 9) for i in range(100)]
    assert view.promote(skill, pairs, gain_bound=1)["accepted"]
    assert view.snapshot() == (skill,)
    assert verify_journal(view.journal.snapshot(), expected_count=1)
    with pytest.raises(ValueError, match="target"):
        view.promote(skill, [ShadowPair("a", 1, 0, "confirmation"), ShadowPair("b", 1, 0)], gain_bound=1)
    with pytest.raises(ValueError, match="nonduplicate"):
        view.promote(skill, [pairs[0], pairs[0]], gain_bound=1)
    assert JournalSkillView.recurring_subdags([skill, skill]) == (skill,)


def test_dual_horizon_charges_primitive_expansion_and_refuses_fake_tier_two():
    op = Operator("op_0", ("I",), "I", lambda x: -x)
    g = Grammar("I", (op,))
    deep = apply(op, apply(op, variable("I")))
    assert primitive_cost(Expr("macro", "I", None, (deep,)), g.ops) == 3
    task = PublicTask(((1, 1),), 2, "I")
    verifier = DualHorizonVerifier(2, 2)
    with pytest.raises(ValueError, match="expansion"):
        verifier.fixed(g, task, (deep,), meter())
    result = solve(g, task.public_io, task.query, "I", 3, meter=meter())
    audit = verifier.audit_deep(g, task, result, meter())
    assert not audit["horizon_expansion_demonstrated"]


def test_all_five_ablations_are_executable_without_scientific_run():
    world = procedural_worlds()[0]
    task = PublicTask((((), ()), ((0, 1), (1, 0))), (0, 0, 1), "SEQ")
    laws = AutoOperatorFingerprinter().discover(world.grammar.operators, world.carriers,
                                              complete_carriers=True, meter=meter())
    statuses = []
    for method in METHODS:
        result = run_method(method, world, task, b0=3, meter=meter(), laws=laws,
                            library=JournalSkillView())
        statuses.append(result.status)
    assert len(set(statuses)) == 1


def test_horizon_n_break_even_includes_setup_training_and_all_tasks():
    r = horizon_break_even(10, 20, [4]*4, [12]*4)
    assert r["proposed_total"] == 46 and r["baseline_total"] == 48
    assert r["strict_break_even"] and r["first_observed_break_even"] == 4
    assert not horizon_break_even(10, 20, [4], [12])["strict_break_even"]
    with pytest.raises(ValueError):
        horizon_break_even(0, 0, [1], [1, 2])


def test_cooperative_interpreter_matches_direct_including_map_filter():
    from nexus.wave24_quotient_core import eval_expr_steps
    pred = Operator("op_0", ("I",), "BOOL", lambda x: x == 2)
    for kind in ("map", "filter"):
        expr = Expr(kind, "SEQ", None, (variable("SEQ"), apply(pred, variable("I"))))
        direct_meter, step_meter = meter(), meter()
        expected = eval_expr(expr, (7, 2), {pred.name: pred}, direct_meter)
        stream = eval_expr_steps(expr, (7, 2), {pred.name: pred}, step_meter)
        ticks = 0
        while True:
            try:
                assert next(stream) is None
                ticks += 1
            except StopIteration as stop:
                assert stop.value == expected
                break
        assert ticks == direct_meter.total == step_meter.total


def test_work_step_backend_exact_semantic_and_cost_agreement():
    world = procedural_worlds()[0]
    m = meter()
    enum = ExactEnumerator(world.grammar, world.inputs, 4, meter=m)
    rows = [row for row in enum.work_events() if row is not None]
    actual = {(e.sort, tuple(map(freeze, out))) for e, out, _ in rows}
    assert actual == semantic_set(world.grammar, world.inputs, 4, quotient=True)
    assert enum.complete and m.counts["exact_work_units"] == m.total


def test_speculation_is_at_most_twenty_percent_of_metered_shared_work():
    world = procedural_worlds()[0]
    # Impossible target forces baseline completion, so both streams are visited.
    task = PublicTask((((0,), (2,)),), (1,), "SEQ")
    skills = (apply(world.grammar.operators[0], variable("SEQ")),)
    m = meter()
    result = DualHorizonVerifier(3, 3).fixed(world.grammar, task, skills, m)
    assert result.status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
    exact, spec = m.counts["exact_work_units"], m.counts["speculative_work_units"]
    assert spec > 0 and 4*spec <= exact


def test_actual_source_trace_not_predicted_rewards_trains_two_heads():
    g = Grammar("I", (Operator("op_0", ("I",), "I", lambda x: x % 2),))
    task = PublicTask(((0, 0),), 3, "I")
    m = meter()
    trace = source_execution_trace(g, task, 3, m)
    assert trace["training_rows"] and trace["censored"] == 0
    assert trace["training_rows"][0]["disagree_work"] > 0
    assert m.counts["training_work_units"] == m.total
    scorer = DualHeadExecutionScorer().fit(trace["training_rows"], meter=m)
    assert scorer.source_digest


def test_frozen_source_snapshot_detects_parameter_mutation():
    rows = [dict(features=(1., 1., 1., 0., 0., 0.), fit_work=1., disagree_work=2., purpose="training")]
    scorer = DualHeadExecutionScorer().fit(rows, meter=meter())
    library = JournalSkillView()
    snapshot = FrozenSourceState.capture(library, scorer, procedural_worlds()[:-1])
    assert snapshot.verify(library, scorer)
    scorer.models[0][1][0] += 1
    with pytest.raises(ValueError, match="changed"):
        snapshot.verify(library, scorer)
    with pytest.raises(ValueError, match="fifth"):
        FrozenSourceState.capture(library, scorer, procedural_worlds())


def test_independent_certificate_replay_and_forgery_rejection():
    from nexus.wave24_quotient_core import SearchResult
    op = Operator("op_0", ("I",), "I", lambda x: x % 2)
    g = Grammar("I", (op,))
    public, query = ((0, 0),), 3
    result = solve(g, public, query, "I", 3, meter=meter())
    assert verify_certificate(g, public, query, "I", 3, result, meter=meter())
    fake = SearchResult("UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE", result.witnesses[:1], result.query_values[:1], True)
    with pytest.raises(ValueError, match="disagrees"):
        verify_certificate(g, public, query, "I", 3, fake, meter=meter())
    with pytest.raises(ValueError, match="outside"):
        validate_program(constant("I", 99), g)
    with pytest.raises(ValueError, match="outside"):
        validate_program(Expr("macro", "I", None, (apply(op, variable("I")),)), g)


def test_empty_collection_scope_never_invents_grammar_constants():
    op = Operator("op_0", ("I",), "BOOL", lambda x: x == 2)
    g = Grammar("SEQ", (op,), bindings=(Binding("map", "SEQ", "I", "BOOL"),))
    for expr, outputs, _ in ExhaustiveASTEnumerator(g, ((), ()), 4, meter=meter()):
        assert validate_program(expr, g)
        assert outputs == ((), ()) or expr.sort != "SEQ"


def test_commutative_predicate_with_different_result_type_is_discovered():
    eq = Operator("op_0", ("I", "I"), "BOOL", lambda a, b: a == b)
    bundle = AutoOperatorFingerprinter().discover((eq,), {"I": (0, 1), "BOOL": (False, True)},
                                                complete_carriers=True, meter=meter())
    assert bundle.certified
    assert any(l.kind == "commutative" for l in bundle.laws)


def test_depth_one_filter_is_structural_not_a_max_cost_shortcut():
    increment = Operator("op_0", ("I",), "I", lambda x: x+1)
    costly_identity = Operator("op_1", ("I",), "I", lambda x: x, cost=20)
    g = Grammar("I", (increment, costly_identity))
    assert not depth_one_fits(g, PublicTask(((0, 2),), 3, "I"), meter())
    assert depth_one_fits(g, PublicTask(((0, 1),), 3, "I"), meter())


def test_incomplete_evolved_fit_cannot_certify_horizon_expansion():
    from nexus.wave24_quotient_core import SearchResult
    op = Operator("op_0", ("I",), "I", lambda x: x+1)
    g = Grammar("I", (op,))
    expr = apply(op, apply(op, variable("I")))
    partial = SearchResult("UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED", (expr,), (5,), False)
    result = DualHorizonVerifier(2, 3).audit_deep(g, PublicTask(((0, 2),), 3, "I"), partial, meter())
    assert not result["horizon_expansion_demonstrated"]


def test_deceptive_small_probe_commutativity_cannot_cause_false_uniqueness():
    def deceptive(a, b):
        if a == 7:
            return a+2*b
        if b == 7:
            return b+3*a
        return a+b
    op = Operator("op_0", ("I", "I"), "I", deceptive)
    g = Grammar("I", (op,), (constant("I", 1),))
    bundle = AutoOperatorFingerprinter().discover((op,), {"I": tuple(range(-2, 3))}, meter=meter())
    assert not bundle.certified_structural_laws
    assert any(l.kind == "commutative" for l in bundle.empirical_probe_priors)
    public = ((0, 1), (1, 2))
    exhaustive = solve(g, public, 7, "I", 3, quotient=False, meter=meter())
    result = solve(g, public, 7, "I", 3, laws=bundle, meter=meter())
    assert result.status == exhaustive.status == "AMBIGUOUS_WITNESS_FOUND"
    assert set(result.query_values) == {9, 10}
    assert verify_certificate(g, public, 7, "I", 3, result, meter=meter())
    assert bundle.pruned == 0
    # Incomplete deferred checking never upgrades a prior into a proof.
    partial = solve(g, public, 7, "I", 3, laws=bundle, meter=WorkMeter(limit=8))
    assert partial.status == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED"


def test_scoped_cache_matches_uncached_interpreter_and_work_step_backend():
    world = procedural_worlds()[0]
    direct_meter, stepped_meter = meter(), meter()
    direct = ExactEnumerator(world.grammar, world.inputs, 4, meter=direct_meter)
    stepped = ExactEnumerator(world.grammar, world.inputs, 4, meter=stepped_meter)
    a = list(direct)
    b = [row for row in stepped.work_events() if row is not None]
    assert [(e.key(), tuple(map(freeze, out)), c) for e, out, c in a] == [(e.key(), tuple(map(freeze, out)), c) for e, out, c in b]
    assert direct_meter.total == stepped_meter.total
    for expr, outputs, _ in a:
        assert tuple(map(freeze, outputs)) == tuple(freeze(eval_expr(expr, x, world.grammar.ops)) for x in world.inputs)


def test_typed_wire_round_trip_preserves_missing_none_and_scope():
    from nexus.wave24_quotient_core import unfreeze, expression_wire, expression_from_wire
    import json
    values = ({"missing": MISSING_KEY, "null": None}, (), [False, 0], 1.25)
    assert freeze(unfreeze(json.loads(json.dumps(freeze(values))))) == freeze(values)
    op = Operator("op_0", ("I",), "I", abs)
    expr = apply(op, variable("I"))
    assert expression_from_wire(json.loads(json.dumps(expression_wire(expr)))).key() == expr.key()


def test_certified_small_carrier_law_cannot_prune_unseen_seven_operands():
    def deceptive(a, b):
        if a == 7:
            return a+2*b
        if b == 7:
            return b+3*a
        return (a+b+2) % 5-2
    op = Operator("op_0", ("I", "I"), "I", deceptive)
    g = Grammar("I", (op,), (constant("I", 1),))
    bundle = AutoOperatorFingerprinter().discover((op,), {"I": tuple(range(-2, 3))},
                                                complete_carriers=True, meter=meter())
    assert bundle.certified_structural_laws and not bundle.empirical_probe_priors
    public = ((0, 1), (1, 2))
    result = solve(g, public, 7, "I", 3, laws=bundle, meter=meter())
    assert result.status == "AMBIGUOUS_WITNESS_FOUND" and set(result.query_values) == {9, 10}
    assert verify_certificate(g, public, 7, "I", 3, result, meter=meter())


def test_open_python_toolbox_cross_domain_functor_transfer():
    # A bounded unit existence proof, not selection of assessment tasks.
    from test_wave24_roles_ratchet import assert_deep_transfer_mechanism
    assert_deep_transfer_mechanism()


def test_workspace_header_free_compass_cross_type_semantics():
    from test_wave24_workspace import test_canonical_semantics_sort_keys_and_do_not_alias_boundary_values
    test_canonical_semantics_sort_keys_and_do_not_alias_boundary_values()


def test_workspace_two_hop_unfolding_and_parametric_amortization():
    from test_wave24_workspace import test_hops_solve_deep_primitive_programs_and_compile_real_open_skills
    test_hops_solve_deep_primitive_programs_and_compile_real_open_skills(4)


def test_workspace_all_query_variants_survive_noninjective_contexts():
    from test_wave24_workspace import test_workspace_retains_more_than_two_query_variants_and_catches_corruption
    test_workspace_retains_more_than_two_query_variants_and_catches_corruption()


def test_noether_last_step_has_zero_false_certificates():
    ops = (
        Operator("op_0", ("I",), "I", lambda x: x+1),
        Operator("op_1", ("I",), "I", lambda x: x-1),
        Operator("op_2", ("I",), "I", abs),
    )
    g, domain, public, query = Grammar("I", ops), (-2, 0, 1, 3, 7), ((0, 2), (1, 3)), 7
    gate = NoetherConservationGate()
    tags = gate.fingerprint_operators(ops, domain)
    assert MASS_EXPANSIVE in tags["op_0"] and MASS_CONTRACTIVE in tags["op_1"]
    assert gate.should_skip_last_step(ops[0], (0, 1), (2, 3)) is False
    assert gate.should_skip_last_step(ops[1], (0, 1), (2, 3)) is True
    guided = solve(g, public, query, "I", 3, meter=meter(), target_public=(2, 3),
                   noether=gate, inner_heuristics=False)
    reference = solve(g, public, query, "I", 3, quotient=False, meter=meter())
    assert guided.status == reference.status
    assert tuple(map(freeze, guided.query_values)) == tuple(map(freeze, reference.query_values))
    assert verify_certificate(g, public, query, "I", 3, guided, meter=meter())
