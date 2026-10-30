"""Phase 12B unit tests (synthetic fixtures, Phase 11 dev seeds and non-manifest seeds; no Fresh_Phase12B_24 task is built)."""
import json
import re
import sys
from pathlib import Path

from nexus.de_phase11 import abstr11 as A, core11 as C, tasks11 as T11
from nexus.de_phase12 import synth12 as S12, tasks12 as T12
from nexus.de_phase12b import disamb12b as D, manifest12b as M, synth12b as S, tasks12b as T

ROOT = Path(__file__).resolve().parents[1]
I, ST = C.INT, C.STR
LIB0 = A.load_library(json.loads((ROOT / "artifacts/agi11_stageA/rep0.final.json").read_text())["library"])


def _budget():
    return S.Budget(rel_cap=300, sc_cap=120000, fc_cap=4000, ast_cap=300000, wall=60)


def test_default_flags_reproduce_phase12_candidates():
    learner, _, _ = T11.build("flag", 120992)
    a = S12.collect(learner, LIB0, S12.Costs(), S12.Budget(rel_cap=300, sc_cap=120000, fc_cap=4000, ast_cap=300000, wall=60))
    b = S.collect(learner, LIB0, S.Costs(), _budget(), reopen=False)
    assert [c["expanded"] for c in a["candidates"]] == [c["expanded"] for c in b["candidates"]]


def _null_default_task():
    rows_a = [(i, 3 * i + 1, "p") for i in range(1, 9)]
    rows_b = [(i, 2 * i + 5, "q") for i in range(10, 18)]
    sch = (("k", I), ("x", I), ("g", ST))
    ref = ("map", ("rel", "r"), (("k", ("col", "k")), ("o", ("branch", ("isnull", ("col", "x")), ("const", 0, I), ("col", "x")))))
    envs = {b: {"r": C.Rel([n for n, _ in sch], [t for _, t in sch], rows)} for b, rows in (("vis_a", rows_a), ("vis_b", rows_b))}
    return dict(id="Tn", inputs=envs, expected={b: C.evaluate(ref, envs[b]) for b in envs}, out_schema=(("k", I), ("o", I)),
                contracts={"r": dict(unique=["k"], not_null=["k", "g"])}), ref


def test_reopened_projection_keeps_a_null_replacement_alternative():
    task, _ = _null_default_task()
    closed = S.collect(task, {}, S.Costs(), _budget(), reopen=False)
    opened = S.collect(task, {}, S.Costs(), _budget(), reopen=True)
    has_isnull = lambda res: any("isnull" in json.dumps(c["expanded"]) for c in res["candidates"])    # noqa: E731
    assert not has_isnull(closed) and has_isnull(opened)
    assert opened["candidates"][0]["expanded"][2][1] == ("o", ("col", "x"))   # passthrough stays the first priority


def test_reopened_count_star_keeps_count_column_alternative():
    rows = [(i, "abc"[i % 3], i) for i in range(1, 10)]
    sch = (("k", I), ("g", ST), ("v", I))
    ref = ("map", ("fold", ("rel", "r"), ("g",), (("n", "count", ("col", "v")),)), (("g", ("col", "g")), ("n", ("col", "n"))))
    envs = {b: {"r": C.Rel([n for n, _ in sch], [t for _, t in sch], rows)} for b in ("vis_a", "vis_b")}
    task = dict(id="Tc", inputs=envs, expected={b: C.evaluate(ref, envs[b]) for b in envs}, out_schema=(("g", ST), ("n", I)), contracts={})
    closed = S.collect(task, {}, S.Costs(), _budget(), reopen=False)
    opened = S.collect(task, {}, S.Costs(), _budget(), reopen=True)
    count_col = lambda res: any('"count",' in json.dumps(c["expanded"]) for c in res["candidates"])  # noqa: E731
    assert not count_col(closed) and count_col(opened)


def test_challenge_flag_queries_a_singleton_set():
    task, ref = _null_default_task()
    col = S.collect(task, {}, S.Costs(), _budget(), reopen=False)
    single = dict(col, candidates=col["candidates"][:1])
    admin = dict(static=[], oracle=lambda env: C.evaluate(ref, env))
    off = D.resolve(task, admin, {}, S.Costs(), single, "nexus", 2, _budget(), seed=5, challenge=False)
    on = D.resolve(task, admin, {}, S.Costs(), single, "nexus", 2, _budget(), seed=5, challenge=True)
    assert off["queries"] == [] and on["queries"] and on["queries"][0]["qtype"] == "challenge" and on["queries"][0]["unanimous"]


def test_fresh_manifest_frozen_and_separate():
    f = M.fresh()
    assert len(f) == 24 and sorted({t["mech"] for t in f}) == sorted(T.MECHS) and all(t["seed"] in M.RANGES[("agi12b", "fresh")] for t in f)
    assert not set(T.MECHS) & set(T12.MECHS) and len(M.p12()) == 24 and len(M.p11()) == 24
    for i, m in enumerate(T.MECHS):                                       # every mechanism builds (non-manifest seeds)
        for inst in (0, 2):
            learner, admin, hidden = T.build(m, inst, 129000 + 10 * i + inst)
            assert set(learner) == {"id", "inputs", "expected", "out_schema", "contracts"} and len(admin["static"]) == 2


def test_numeric_seeds_only():
    for f in (ROOT / "src/nexus/de_phase12b").glob("*.py"):
        s = f.read_text()
        assert not re.search(r"Random\(\s*f?[\"']", s), f
        assert not re.search(r"(rng|rng10c|seed_of|Random)\([^)]*name", s), f


def test_ledgers_verify():
    sys.path.insert(0, str(ROOT / "scripts"))
    import agi12b_ledger as L
    assert L.verify() == 0
