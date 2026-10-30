"""Phase 11 unit tests (development fixtures only; no learned library, no target)."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from nexus.de_phase11 import abstr11 as A, core11 as C, sql11 as Q, synth11 as S, tasks11 as T

ROOT = Path(__file__).resolve().parents[1]
I, N, ST, B = C.INT, C.NUM, C.STR, C.BOOL
col, const = (lambda n: ("col", n)), (lambda v, t: ("const", v, t))


def _ev(e, cols, row):
    return C.compile_scalar(e, tuple(cols))(row)


def test_three_valued_logic_null_false_error():
    assert _ev(("cmp", "gt", col("a"), const(1, I)), ["a"], (None,)) is None
    assert _ev(("and", ("cmp", "gt", col("a"), const(1, I)), const(False, B)), ["a"], (None,)) is False
    assert _ev(("or", ("cmp", "gt", col("a"), const(1, I)), const(True, B)), ["a"], (None,)) is True
    assert _ev(("not", ("cmp", "gt", col("a"), const(1, I))), ["a"], (None,)) is None
    assert _ev(("isnull", col("a")), ["a"], (None,)) is True
    big = ("arith", "mul", col("a"), col("a"))
    assert _ev(big, ["a"], (2 ** 40,)) is C.ERR                                     # int64 overflow -> ERR
    assert _ev(("branch", const(False, B), big, const(0, I)), ["a"], (2 ** 40,)) == 0     # lazy: unchosen ERR arm never evaluated
    assert _ev(("arith", "div", col("a"), const(0, I)), ["a"], (5,)) is None and _ev(("arith", "mod", const(-7, I), const(4, I)), [], ()) == -3
    assert _ev(("cast", col("s"), I), ["s"], ("12x",)) is None and _ev(("cast", col("s"), I), ["s"], ("-12",)) == -12
    assert C.json_get('{"a": 1.50}', ("a",)) == "1.5" and C.json_get("{bad", ("a",)) is None and C.json_get('{"a": null}', ("a",)) is None
    assert C.json_get('{"a": {"b": 1}}', ("a",)) == '{"b":1}' and C.json_get('{"a": true}', ("a",)) == "true"


def test_relational_semantics_and_duckdb_conformance():
    R = C.Rel(["k", "v"], [I, I], [(1, 2), (1, 5), (None, 3), (None, 4), (2, None)])
    S2 = C.Rel(["k", "w"], [I, I], [(1, 9), (1, 8), (None, 7)])
    env = {"R": R, "S": S2}
    fold = ("fold", ("rel", "R"), ("k",), (("n", "count_star", None), ("s", "sum", col("v")), ("c", "count", col("v"))))
    got = C.evaluate(fold, env)
    assert sorted(got.rows, key=repr) == sorted([(1, 2, 7, 2), (None, 2, 7, 2), (2, 1, None, 0)], key=repr)      # NULL keys form ONE group
    empty = C.evaluate(("fold", ("rel", "R"), (), (("n", "count_star", None), ("s", "sum", col("v")))), {"R": C.Rel(R.cols, R.types, [])})
    assert empty.rows == [(0, None)]                                                # keys=() on empty input: exactly one row
    j = C.evaluate(("join", "inner", ("rel", "R"), ("rel", "S"), ("k",), ("k",)), env)
    assert len(j.rows) == 4 and j.cols == ("k", "v", "k_r", "w")                    # NULL keys never match; duplicates multiply
    rk = C.evaluate(("rank", ("rel", "R"), ("k",), ((col("v"), True),), 1), env)
    assert sorted(rk.rows, key=repr) == sorted([(1, 5), (None, 4), (2, None)], key=repr)
    for prog in (fold, ("join", "left", ("rel", "R"), ("rel", "S"), ("k",), ("k",)), ("join", "anti", ("rel", "R"), ("rel", "S"), ("k",), ("k",)),
                 ("rank", ("rel", "R"), ("k",), ((col("v"), False),), 1), ("union", ("rel", "R"), ("filter", ("rel", "R"), ("cmp", "gt", col("v"), const(2, I))))):
        ref, nat = C.evaluate(prog, env), Q.execute(prog, env, "duckdb")
        assert C.same_bag(ref, nat), prog


def _search_stub():
    s = object.__new__(S.Search)
    s.b, s.log = S.Budget(), Counter()
    return s


def test_observational_refinement_recovers_split_alternative():
    rows = [(v,) for v in (-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11)]                   # the 10-row slice never reaches x >= 10
    consts = S._Consts({I: [0, 10]})
    pool = S.Pool(("x",), (I,), rows, consts, [], {}, S.Costs(), S.Budget(), Counter())
    for _ in range(7):
        pool.grow()
    want = ("branch", ("cmp", "lt", col("x"), const(10, I)), col("x"), const(0, I))
    f = C.compile_scalar(want, ("x",))
    cid = pool.index[(I, tuple(C.enc(r[0]) for r in rows[:S.SLICE]))]
    assert pool.rep(cid) == col("x") and len(pool.classes[cid]["members"]) > 1     # x and the branch collapse on the slice
    s = _search_stub()
    got = s._passing(pool, cid, [[r] for r in rows], [[C.enc(f(r))] for r in rows], lambda v: sorted(C.enc(z) for z in v))
    assert got and all(C.compile_scalar(g, ("x",))((10,)) == 0 for g in got) and s.log["refinement_recovered"] == 1


def test_fingerprints_keep_null_error_false_and_bag_duplicates_apart():
    pool = S.Pool(("a",), (I,), [(1,)], S._Consts({}), [], {}, S.Costs(), S.Budget(), Counter())
    pool._new(("x1",), B, (None,), ("leaf", ("x1",)), 1, 1)
    pool._new(("x2",), B, (False,), ("leaf", ("x2",)), 1, 1)
    pool._new(("x3",), B, (C.ERR,), ("leaf", ("x3",)), 1, 1)
    assert len(pool.classes) == 3
    R1 = C.Rel(["a"], [I], [(1,), (1,)])
    R2 = C.Rel(["a"], [I], [(1,)])
    assert S.Search._fp([R1]) != S.Search._fp([R2])                               # multiplicity is part of the fingerprint


def test_anti_unification_binding_matching_and_classes():
    a = ("branch", ("isnull", col("p")), col("q"), col("p"))
    b = ("branch", ("isnull", col("m")), const(0, I), col("m"))
    g = A.LGG()
    body, kinds = A.canonical(g.gen(a, b), g.kinds)
    assert body == ("branch", ("isnull", ("col", ("param", 0))), ("param", 1), ("col", ("param", 0))) and [k[0] for k in kinds] == ["name", "scalar"]
    bind = {}
    assert A.match(body, ("branch", ("isnull", col("z")), col("y"), col("z")), bind, kinds) and bind == {0: "z", 1: col("y")}
    assert not A.match(body, ("branch", ("isnull", col("z")), col("y"), col("w")), {}, kinds)          # inconsistent binding
    progs = [("P1", ("map", ("rel", "r"), (("o", a),))), ("P1#2", ("map", ("rel", "r"), (("o", a),))), ("P2", ("map", ("rel", "r"), (("o", b),)))]
    inst = A.instances(body, kinds, progs)
    assert sorted({p.split("#")[0] for p in inst}) == ["P1", "P2"]                    # a repeated project counts once
    assert A.op_count(("rank", ("param", 0), (("param", 1),), ((("col", ("param", 2)), True),), 1)) == 1
    lib = {"F0": dict(kind="scalar", params=kinds, body=body, ops=A.op_count(body))}
    rw = A.rewrite(("map", ("rel", "r"), (("o", a),)), lib)
    assert rw == ("map", ("rel", "r"), (("o", ("call", "F0", ("p", col("q")))),)) and C.expand(rw, lib) == ("map", ("rel", "r"), (("o", a),))
    assert C.size(C.expand(rw, lib)) == C.size(("map", ("rel", "r"), (("o", a),)))  # a call never changes the expanded size


def test_learner_task_hides_reference_and_family():
    learner, admin, hidden = T.build("preagg", 110930)
    assert set(learner) == {"id", "inputs", "expected", "out_schema"} and learner["id"].startswith("T") and "preagg" not in json.dumps(learner["id"])
    assert set(learner["inputs"]) == {"vis_a", "vis_b"} and "ref" in hidden and set(admin) == {"valid", "evidence"}


def test_numeric_seeds_only():
    for f in (ROOT / "src/nexus/de_phase11").glob("*.py"):
        s = f.read_text()
        assert not re.search(r"Random\(\s*f?[\"']", s), f
        assert not re.search(r"(rng|rng10c|seed_of|Random)\([^)]*name", s), f


def test_ledgers_verify_and_suite3_not_ready():
    sys.path.insert(0, str(ROOT / "scripts"))
    import agi11_ledger as L11
    assert L11.verify() == 0
    d = json.loads((ROOT / "artifacts/agi11_suite3_provenance.json").read_text())
    assert d["status"] == "NOT READY" and "email" in d["blocker"].lower()
