"""Deterministic authored correctness fixtures, not a post-freeze task bank."""
from copy import deepcopy
import zlib

import pytest

from nexus.wave24_quotient_core import (
    MISSING_KEY, Operator, Grammar, WorkMeter, ExactEnumerator, ExhaustiveASTEnumerator,
    apply, variable, eval_expr, primitive_cost, freeze, solve, unfold_workspace_expr,
)
from nexus.wave24_self_evolving_loop import (
    PhenotypeAffinityCompass, StigmergicWorkspaceEngine, PublicTask,
    verify_workspace_certificate,
)


def meter():
    return WorkMeter(limit=20_000_000, wall_limit=10.)


@pytest.mark.parametrize("values", [
    (1, 2, 90), ([1, 2, 3], [1, 2, 4], [8, 8, 8, 8, 8]),
    ("abcdefgh", "abcdefgx", "ZZZZZZZZZZZZZZZZ"),
    ({"a": 1, "b": 2}, {"a": 1, "b": 3}, {"z": 99}),
    ((1, 0, 1), (1, 0, 0), (9, 9, 9, 9, 9)),
])
def test_header_free_compass_is_deterministic_symmetric_and_metered(values):
    m = meter(); c = PhenotypeAffinityCompass(m)
    a, b, far = values
    assert c.phenotype_distance((a,), (a,)) == 0.
    near = c.phenotype_distance((a,), (b,))
    assert near == c.phenotype_distance((b,), (a,))
    assert 0 <= near <= c.phenotype_distance((a,), (far,)) <= 1
    assert c.phenotype_distance((a,), (b,)) == PhenotypeAffinityCompass(meter()).phenotype_distance((a,), (b,))
    raw = c.canon_bytes(a)
    compressor = zlib.compressobj(level=6, wbits=-15)
    assert c.raw_complexity(raw) == len(compressor.compress(raw)+compressor.flush())
    assert m.counts["compass_work_units"] > 0


def test_canonical_semantics_sort_keys_and_do_not_alias_boundary_values():
    b = PhenotypeAffinityCompass.canon_bytes
    assert b({"b": 2, "a": MISSING_KEY}) == b({"a": MISSING_KEY, "b": 2})
    assert len({b(v) for v in (MISSING_KEY, None, False, 0, [], (), "")}) == 7
    assert b([1, 2]) != b((1, 2))


def increment_fixture(amount=4):
    op = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    g = Grammar("INT", (op,))
    return g, PublicTask(((0, amount), (2, amount+2)), 7, "INT")


@pytest.mark.parametrize("amount", [3, 4])
def test_hops_solve_deep_primitive_programs_and_compile_real_open_skills(amount):
    g, task = increment_fixture(amount)
    assert solve(g, task.public_io, task.query, "INT", 3, meter=meter()).status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
    engine, trace = StigmergicWorkspaceEngine(meter=meter()), {}
    result = engine.run(g, task, trace=trace)
    assert result.status == "UNIQUE_QUERY_OUTPUT_IN_DECLARED_BOUNDED_SPACE"
    assert result.query_values == (7+amount,) and len(trace["workspace"]["hops"]) == 2
    assert primitive_cost(result.witnesses[0], g.ops) in (4, 5)
    assert all(n.kind not in ("island", "skill_call") for n in walk(result.witnesses[0]))
    assert engine.last_report["compiled_candidates"]
    skills = engine.compile_trajectory(result.witnesses[0], g)
    assert skills and all(2 <= s.expansion_cost(g.ops) <= 3 for s in skills)
    call = max(skills, key=lambda s: s.expansion_cost(g.ops)).call(variable("INT"))
    assert eval_expr(call, 10, g.ops, meter()) >= 12
    enum = ExactEnumerator(g, (0, 2, 7), 3, meter=meter(), macros=skills, evolved=True, primitive_cap=6)
    assert enum.cost(call) == 2
    assert verify_workspace_certificate(g, task, result, trace["workspace"], meter=meter())


def walk(e):
    yield e
    for child in e.children:
        yield from walk(child)


def test_workspace_retains_more_than_two_query_variants_and_catches_corruption():
    # Three public-equivalent intermediate values must survive a non-injective
    # parent. The third variant is necessary to reach query=1 under ==2.
    ops = tuple(Operator(f"op_{i}", ("INT",), "INT", lambda x, i=i: i if x == 7 else x+1)
                for i in range(3))
    parent = Operator("op_3", ("INT",), "BOOL", lambda z: z == 2)
    g = Grammar("INT", (*ops, parent))
    inputs = (0, 1, 7)
    engine = StigmergicWorkspaceEngine(meter=meter())
    enum = ExactEnumerator(g, inputs, 3, meter=meter(), evolved=True, primitive_cap=6)
    entries = list(enum)
    next_workspace, selected, _ = engine._choose(g, entries, (), inputs, (1, 2))
    seq_variants = [e for e in next_workspace if e.sort == "INT"
                    and tuple(eval_expr(e, x, g.ops) for x in inputs[:-1]) == (1, 2)]
    assert {eval_expr(e, 7, g.ops) for e in seq_variants} == {0, 1, 2}
    assert any(s["query_variant_count"] >= 3 for s in selected)
    q = {(e.sort, tuple(freeze(y) for y in ys)) for e, ys, _ in ExactEnumerator(g, inputs, 3,
        meter=meter(), workspace=next_workspace, evolved=True, primitive_cap=6)}
    ex = {(e.sort, tuple(freeze(y) for y in ys)) for e, ys, _ in ExhaustiveASTEnumerator(g, inputs, 3,
        meter=meter(), workspace=next_workspace, evolved=True, primitive_cap=6)}
    assert q == ex
    assert ("BOOL", tuple(map(freeze, (False, True, True)))) in q
    # A separate solved two-hop proof cannot have an island silently removed.
    g2, t = increment_fixture(); tr = {}
    result = StigmergicWorkspaceEngine(meter=meter()).run(g2, t, trace=tr)
    broken = deepcopy(tr["workspace"]); broken["hops"][1]["workspace"].pop()
    with pytest.raises(ValueError, match="lost a query variant"):
        verify_workspace_certificate(g2, t, result, broken, meter=meter())


def test_empty_twin_search_does_not_claim_uniqueness_and_budget_exhaustion_is_unknown():
    a = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    b = Operator("op_1", ("INT",), "INT", lambda x: 99 if x == 7 else x+1)
    g = Grammar("INT", (a, b)); t = PublicTask(((1, 2), (2, 3)), 7, "INT")
    trace = {}
    r = StigmergicWorkspaceEngine(meter=meter(), twin_mutations=0).run(g, t, trace=trace)
    assert r.status == "AMBIGUOUS_WITNESS_FOUND"
    assert not trace["workspace"]["hops"][0]["twin"]["witness_found"]
    assert verify_workspace_certificate(g, t, r, trace["workspace"], meter=meter())
    limited = StigmergicWorkspaceEngine(meter=WorkMeter(limit=1, wall_limit=2.)).run(g, t)
    assert limited.status == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED" and not limited.complete


def test_stagnation_and_primitive_cap_are_explicit():
    g = Grammar("INT", (Operator("op_0", ("INT",), "INT", lambda x: x),))
    engine = StigmergicWorkspaceEngine(meter=meter()); tr = {}
    r = engine.run(g, PublicTask(((0, 1), (2, 3)), 7, "INT"), trace=tr)
    assert r.status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
    assert len(tr["workspace"]["hops"]) == 1
    assert tr["workspace"]["hops"][0]["stop_reason"] == "no_new_public_signatures"
    assert verify_workspace_certificate(g, PublicTask(((0, 1), (2, 3)), 7, "INT"), r, tr["workspace"], meter=meter())
    g2, t = increment_fixture(8)
    engine2 = StigmergicWorkspaceEngine(meter=meter()); tr2 = {}
    r2 = engine2.run(g2, t, trace=tr2)
    assert not r2.witnesses and len(tr2["workspace"]["hops"]) <= 3
    assert all(primitive_cost(row[0], g2.ops) <= 6 for row in engine2.run(g2, t, explore=True))


def test_role_bridge_is_allowed_to_take_a_worse_phenotype_step():
    from nexus.wave24_auto_laws import AutoOperatorFingerprinter
    shrink = Operator("op_0", ("STR",), "STR", lambda s: s[1:])
    rev = Operator("op_1", ("STR",), "STR", lambda s: s[::-1])
    g = Grammar("STR", (shrink, rev)); inputs = ("abcd", "efgh", "ij")
    roles = AutoOperatorFingerprinter().fingerprint_roles(g.operators, {"STR": inputs}, meter=meter())
    engine = StigmergicWorkspaceEngine(roles=roles, meter=meter())
    entries = list(ExactEnumerator(g, inputs, 3, meter=meter(), evolved=True, primitive_cap=6))
    _, selected, _ = engine._choose(g, entries, (), inputs, ("bcd", "fgh"))
    assert selected[0]["slot"] == "EXPLOIT"
    assert any(s["slot"] == "ROLE_BRIDGE" and s["phenotype_distance"] >= selected[0]["phenotype_distance"] for s in selected)


def test_hidden_query_answers_are_not_compass_or_workspace_inputs():
    import inspect
    params = inspect.signature(StigmergicWorkspaceEngine.run).parameters
    assert "teacher_query" not in params and "answer" not in params
    g, t = increment_fixture(); traces = []
    for _hidden_answer in (-999, 999):
        tr = {}; r = StigmergicWorkspaceEngine(meter=meter()).run(g, t, trace=tr)
        traces.append((r, tr))
    assert traces[0] == traces[1]


def test_source_workspace_compilation_uses_only_source_and_cannot_train_fifth_world():
    from nexus.wave24_self_evolving_loop import World, ZeroDataFrontierSelfPlay, select_ratcheted_source_skills, JournalSkillView
    g, _ = increment_fixture()
    world = World("UNIT_SOURCE", g, "INT", tuple(range(10)), {"INT": tuple(range(10))})
    player = ZeroDataFrontierSelfPlay(24199, 3, public_count=2, behavioral_features=True)
    m = meter(); player.wake(world, attempts=6, meter=m)
    player.augment_workspace_frontier(world, meter=m, roles={})
    assert player.diagnostics["workspace_extra_tasks"] == 2
    assert player.diagnostics["workspace_compiled_candidates"]
    assert len(player.diagnostics["workspace"]["hops"]) == 3
    skills, _ = select_ratcheted_source_skills(player, world, max_skills=3, meter=m)
    lib = JournalSkillView()
    assert skills
    for skill in skills:
        assert lib.promote_ratcheted(skill, player, world, meter=m)["accepted"]
    forbidden = World("BIT_CELLULAR_AUTOMATA", g, "INT", world.inputs, world.carriers)
    with pytest.raises(ValueError, match="permitted"):
        player.augment_workspace_frontier(forbidden, meter=m, roles={})


def test_consumed_role_preflight_is_portable_and_preserves_the_executed_snapshot(monkeypatch):
    import hashlib
    from pathlib import Path
    from nexus.seed.experimental import read
    import scripts.run_wave24_azr_ruler_cegis as runner
    from scripts.verify_wave24_azr_ruler_cegis import verify_payload
    root = Path(__file__).resolve().parents[1]
    record = read(root/"docs/evidence/wave24_azr_dev_role_v3.json")
    for path, text in record["executed_source_snapshot"].items():
        assert hashlib.sha256(text.encode()).hexdigest() == record["payload"]["source_hashes"][path]
    report = verify_payload(record["payload"], replay=True)
    assert report["integrity_valid"], report["errors"]
    assert report["scientific_gates_passed"]
    monkeypatch.setattr(runner.Wave24ResourceHost, "supervise", lambda *a, **k: pytest.fail("consumed worker launched"))
    with pytest.raises(ValueError, match="already consumed"):
        runner.main(["--dev-preflight", "--allocation-file", str(root/"configs/wave24_azr_dev_role_allocation.json")])


def test_saved_workspace_preflight_remains_a_complete_negative_not_a_retry(monkeypatch):
    import hashlib
    from pathlib import Path
    from nexus.seed.experimental import read
    import scripts.run_wave24_azr_ruler_cegis as runner
    from scripts.verify_wave24_azr_ruler_cegis import verify_payload
    root = Path(__file__).resolve().parents[1]
    record = read(root/"docs/evidence/wave24_azr_dev_workspace_v4.json")
    for path, text in record["executed_source_snapshot"].items():
        assert hashlib.sha256(text.encode()).hexdigest() == record["payload"]["source_hashes"][path]
    report = verify_payload(record["payload"], replay=True)
    assert report["integrity_valid"], report["errors"]
    assert report["scientific_gates"]["certificate_b_deep_horizon"]
    assert not report["scientific_gates"]["source_workspace_exploration_and_compilation"]
    assert not report["ready_for_freeze"]
    source = record["payload"]["source_preparation"]
    assert source["receipts"][0]["mining"]["workspace_extra_tasks"] == 0
    assert source["unseen_world_training_rows"] == source["unseen_world_selfplay_tasks"] == 0
    monkeypatch.setattr(runner.Wave24ResourceHost, "supervise", lambda *a, **k: pytest.fail("second worker launched"))
    with pytest.raises(ValueError, match="already consumed"):
        runner.main(["--dev-preflight", "--allocation-file", str(root/"configs/wave24_azr_dev_workspace_allocation.json")])


def test_workspace_contradiction_is_distinct_from_bounded_grammar_failure():
    g, _ = increment_fixture(); t = PublicTask(((1, 2), (1, 3)), 7, "INT")
    trace = {}; result = StigmergicWorkspaceEngine(meter=meter()).run(g, t, trace=trace)
    assert result.status == "VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS"
    assert verify_workspace_certificate(g, t, result, trace["workspace"], meter=meter())
    with pytest.raises(ValueError, match="false deterministic"):
        verify_workspace_certificate(g, PublicTask(((1, 2), (2, 3)), 7, "INT"), result, trace["workspace"], meter=meter())


def test_failed_source_consolidation_consumes_its_cycle():
    from nexus.wave24_self_evolving_loop import OpenToolboxLearningEngine
    engine = OpenToolboxLearningEngine(meter=meter(), max_source_cycles=1)
    engine.enter_toolbox((lambda x: x,), lambda: iter((0, 1, 2)))
    result, report = engine.solve_and_learn(((0, 9), (1, 10)), 2)
    assert not report["consolidated"] and result.status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
    assert engine.source_cycles == 1
    with pytest.raises(ValueError, match="exhausted"):
        engine.solve_and_learn(((0, 9), (1, 10)), 2)


def test_raw_callable_stream_is_bounded_before_materialization():
    from nexus.wave24_auto_laws import OpenPythonToolboxAdapter
    pulled = []
    def functions():
        for i in range(100):
            pulled.append(i)
            if i > 2:
                pytest.fail("ingestion read beyond the limit plus one overflow witness")
            yield lambda x: x
    with pytest.raises(ValueError, match="bounded raw callable"):
        OpenPythonToolboxAdapter(max_callables=2).ingest(functions(), (1, 2), meter=meter())
    assert pulled == [0, 1, 2]


def test_workspace_skill_layer_cap_cannot_be_expanded_by_a_direct_caller():
    from itertools import repeat
    from nexus.wave24_quotient_core import ParametricSkillMacro, typed_hole
    op = Operator("op_0", ("INT",), "INT", lambda x: x+1)
    skill = ParametricSkillMacro(apply(op, apply(op, typed_hole("INT"))), ("INT",))
    for supplied in ((skill,)*4, repeat(skill)):
        with pytest.raises(ValueError, match="at most three"):
            StigmergicWorkspaceEngine(skills=supplied, meter=meter())
