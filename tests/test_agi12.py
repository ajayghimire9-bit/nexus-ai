"""Phase 12 unit tests (development fixtures only; Phase 11 dev seeds; no Suite 1 task is built)."""
import json
import re
import sys
from pathlib import Path

import pytest

from nexus.de_phase11 import abstr11 as A, core11 as C, tasks11 as T11
from nexus.de_phase12 import disamb12 as D, manifest12 as M, synth12 as S, tasks12 as T

ROOT = Path(__file__).resolve().parents[1]
I = C.INT
LIB0 = A.load_library(json.loads((ROOT / "artifacts/agi11_stageA/rep0.final.json").read_text())["library"])


def test_capped_counter_halts_at_the_exact_cap():
    b = S.Budget(rel_cap=10, sc_cap=10, fc_cap=3, ast_cap=10, wall=60)
    for _ in range(3):
        b.c["full_checks"] += 1
    with pytest.raises(S.WorkExhausted):
        b.c["full_checks"] += 1
    assert b.c["full_checks"] == 3                                          # never exceeds the cap


def test_search_never_exceeds_tiny_caps():
    learner, _, _ = T11.build("W3", 120990)
    b = S.Budget(rel_cap=40, sc_cap=4000, fc_cap=60, ast_cap=3000, wall=30)
    res = S.collect(learner, LIB0, S.Costs(), b)
    assert b.c["full_checks"] <= 60 and b.c["micro_evals"] <= 4000 and b.c["rel_evals"] <= 40 and b.c["constructed_asts"] <= 3000
    assert res["exhausted"] is not None


def test_exact_provenance_tokens_and_scalar_before_inlining():
    s = object.__new__(S.Search)
    s.pools, s.lib = {}, {"F1": dict(kind="rel", params=[("rel", None)], body=("param", 0)), "F10": dict(kind="rel", params=[("rel", None)], body=("param", 0))}
    p = S.provenance(("map", ("call", "F10", (("rel", "a"),)), (("o", ("col", "x")),)), s)
    assert p["relational"] == ["F10"]                                       # F10 is never counted as F1
    learner, _, _ = T11.build("coalesce", 120991)
    b = S.Budget(rel_cap=200, sc_cap=60000, fc_cap=3000, ast_cap=200000, wall=30)
    res = S.collect(learner, LIB0, S.Costs(), b)
    srch = res["search"]
    recorded = {f for pl in srch.pools.values() for ids in pl.prov.values() for f in ids}
    assert recorded and all(f in LIB0 and LIB0[f]["kind"] == "scalar" for f in recorded)   # scalar calls recorded before inlining
    for c in res["candidates"]:
        assert set(c["provenance"]["scalar"]) <= recorded


def test_candidate_retention_collects_several_consistent_programs():
    learner, _, _ = T11.build("flag", 120992)
    b = S.Budget(rel_cap=300, sc_cap=100000, fc_cap=4000, ast_cap=300000, wall=30)
    res = S.collect(learner, LIB0, S.Costs(), b)
    assert len(res["candidates"]) >= 2
    for c in res["candidates"]:
        for k in ("vis_a", "vis_b"):
            got = C.run(c["expanded"], learner["inputs"][k])
            assert C.same_bag(C.project_like(got, list(learner["expected"][k].cols)), learner["expected"][k])


def test_generic_distinguishing_input_and_falsification():
    R = C.Rel(["x", "y"], [I, I], [(v, v) for v in range(0, 8)])
    learner = dict(id="Tx", inputs={"vis_a": {"r": R}, "vis_b": {"r": R}}, out_schema=(("o", I),), contracts={"r": dict(unique=["x"], not_null=["x"])})
    good = ("map", ("rel", "r"), (("o", ("branch", ("cmp", "lt", ("col", "x"), ("const", 10, I)), ("col", "x"), ("const", 0, I))),))
    bad = ("map", ("rel", "r"), (("o", ("col", "x")),))
    cands = [dict(program=p, expanded=p, size=C.size(p)) for p in (bad, good)]
    gen = D.Inputs(learner, [{"r": R}], cands, 7)
    b = S.Budget(wall=60)
    env, outs, ncls = D.construct(cands, gen, {}, b, 200, 3)
    assert env is not None and ncls == 2 and gen.admissible(env)          # found generically from the candidates' own executions
    Y = C.evaluate(good, env)
    yk = D.out_key(C.project_like(Y, sorted(Y.cols)))
    assert [o == yk for o in outs] == [False, True]                         # the reference falsifies the wrong explanation


def test_admissibility_respects_contracts():
    R = C.Rel(["k", "v"], [I, I], [(1, 2), (2, None)])
    gen = D.Inputs(dict(inputs={"vis_a": {"r": R}}, contracts={"r": dict(unique=["k"], not_null=["k"])}), [{"r": R}], [], 3)
    for _ in range(30):
        env = gen.draw(1)
        if env is not None:
            ks = [r[0] for r in env["r"].rows]
            assert len(ks) == len(set(ks)) and None not in ks


def test_frozen_manifest_and_separation():
    s1 = M.suite1()
    assert len(s1) == 24 and sorted({t["mech"] for t in s1}) == list(T.MECHS) and all(t["seed"] in M.RANGES[("agi12", "suite1")] for t in s1)
    assert all(sum(1 for t in s1 if t["mech"] == m) == 4 for m in T.MECHS)
    assert set(M.DEV_KINDS) <= set(T11.SOURCE) | set(T11.WITHHELD)           # development uses only Phase 11 families
    assert len(M.suite2()) == 24


def test_numeric_seeds_only():
    for f in (ROOT / "src/nexus/de_phase12").glob("*.py"):
        s = f.read_text()
        assert not re.search(r"Random\(\s*f?[\"']", s), f
        assert not re.search(r"(rng|rng10c|seed_of|Random)\([^)]*name", s), f


def test_ledgers_verify():
    sys.path.insert(0, str(ROOT / "scripts"))
    import agi12_ledger as L12
    assert L12.verify() == 0
