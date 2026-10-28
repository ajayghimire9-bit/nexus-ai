"""t7 unit tests (toy budgets, smoke-only seeds; no experiment runs, no sealed data)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus import t7_seeds, t7_world  # noqa: E402,F401


def test_energy_domain_registered_without_editing_u5_world():
    from nexus import u5_world as W
    assert "E.cost" in W.FAMILIES and W.domain_of("E.cost") == "energy"
    assert "E.cost" not in (ROOT / "src/nexus/u5_world.py").read_text()


def test_t7_platform_defaults_reproduce_u5_behaviour_and_add_energy():
    from nexus import t7_platform as T7, u5_platform as U
    a, b = T7.Project(8090, "dev"), U.Project(8090, "dev")
    assert a.domain == U.DOMAINS[8090 % 3] or a.domain == T7.PL.DOMAINS4[8090 % 4]
    assert T7.PL.DOMAINS4[12403 % 4] == "energy"
    assert not T7.NexusArm.boost and T7.NexusArmStrong.boost


def test_covered_learner_fixes_partial_then_commit():
    from nexus import t7_repair as TR, u5_stateful as SF, u5_statesplit as SP
    t = SF.StreamTask("C.clearing", 12101, n_train_keys=16, x3_train=True, x3_test=True)
    r = TR.learn_class_covered(t.train, t.y_train, t.query, seed=12101)
    cls = SP.compile_class(r["source"], r["name"])
    assert t.score(lambda evs: SP.run_class(cls, evs))["exact"]


def test_crossing_probes_combine_two_failure_conditions():
    from nexus import t7_repair as TR
    envs = [{"r": {"a": 1.0, "m": "S1"}, "t": {}}, {"r": {"a": "N/A", "m": "S1"}, "t": {}}, {"r": {"a": 2.0, "m": "ZZ"}, "t": {}}]
    hy = TR.crossing_records(envs, ["ok", "q:missing", "q:unknown_member"])
    assert any(h["r"]["a"] == "N/A" and h["r"]["m"] == "ZZ" for h in hy) or any(h["r"]["m"] == "ZZ" and h["r"]["a"] == "N/A" for h in hy)


def test_bounded_infeasibility_is_complete_search_not_timeout():
    from nexus import t7_jointtool as J
    ev = J.gen("U", 1)
    H = J.histories(ev, J.reference("U", ev))
    uns, nodes = J.bounded_unsat(H, J.FAMS["U"])
    assert uns and nodes == len(J.G) ** len(J.FAMS["U"])


def test_memory_contract_detects_fabrication():
    from nexus import t7_memory as M
    from nexus import u5_world as W
    t = W.Task("x", "C.notional", 12000)
    prog = ("b", "*", ("b", "get", ("var", "r"), ("const", t.names["qty"])), ("b", "get", ("var", "r"), ("const", t.names["price"])))
    old = dict(programs={"x": prog}, counts={"get": 2, "*": 1}, unsolved=["y"])
    bad = dict(programs={"x": prog, "y": prog}, counts={"get": 4, "*": 2}, unsolved=["y"], cuts=frozenset(), evidence={})
    ok, v = M.check_contract(old, bad, {"x": t, "y": t})
    assert not ok and any("silently marked solved" in x for x in v)


def test_genome_under_64kb():
    from nexus import t7_genome as GN
    g = GN.Genome(0)
    assert g.size() <= GN.LIMIT and g.n_params() > 10000
