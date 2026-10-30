"""Phase 10D unit tests (small generated workspaces; no search, no training, no evaluation target)."""
import json
import re
from pathlib import Path

from nexus.de_phase10d import dag10d as D, engines10d as EN, ir10d as IR, legacy10d as LG, lineage10d as LD, manifest10d as MD, world10d as W

SRC = Path(__file__).resolve().parents[1] / "src/nexus/de_phase10d"


def _spec():
    return dict(stg={"stg_c": dict(src="c", cols=[["k", ["coalesce", ["json", "p", "after.k"], ["json", "p", "before.k"]]], ["op", ["json", "p", "op"]], ["ts", ["json", "p", "ts"]]],
                                   pre=[], dedup=dict(key=["try_int", ["col", "k"]], order=["try_int", ["col", "ts"]], desc=True), post=[["ne", ["col", "op"], ["lit", "d"]]],
                                   latest_as="stg_c_latest"),
                     "stg_o": dict(src="o", cols=[["oid", ["col", "oid"]], ["fk", ["col", "fk"]], ["amt", ["try_int", ["col", "amt"]]]], pre=[["notnull", ["col", "amt"]]], dedup=None, post=[])},
                int=dict(base="stg_o", base_cols=["oid", "fk", "amt"], joins=[dict(rel="stg_c", how="left", lkey=["try_int", ["col", "fk"]], rkey=["try_int", ["col", "k"]], agg=None,
                                                                                   take=[["op2", "op"]])], out=[["oid", ["col", "oid"]], ["fk", ["col", "fk"]], ["amt", ["col", "amt"]]]),
                fct=dict(src="int_orders", group=[["key", ["try_int", ["col", "fk"]]]], measures=[["n", "count", ["col", "oid"]], ["tot", "sum", ["col", "amt"]]],
                         merge=dict(key="key", update=True, delete=True, deletes=dict(rel="stg_c_latest", key=["try_int", ["col", "k"]], minus="stg_c"))))


def _tables():
    ev = lambda op, k, ts: json.dumps({"op": op, "before": {"k": k} if op != "c" else None, "after": None if op == "d" else {"k": k}, "ts": ts})  # noqa: E731
    c = [dict(p=ev("c", 1, 1)), dict(p=ev("c", 2, 2)), dict(p=ev("d", 2, 5)), dict(p=ev("c", 3, 3))]
    o = [dict(oid="10", fk="001", amt="5"), dict(oid="11", fk="1", amt="x"), dict(oid="12", fk="3", amt="7"), dict(oid="13", fk="9", amt="2")]
    return dict(c=c, o=o), dict(fct_target=[dict(key=2, n=9, tot=9), dict(key=3, n=1, tot=1), dict(key=8, n=4, tot=4)])


def test_reference_merge_and_cdc_semantics():
    T, S = _tables()
    R = IR.interpret(_spec(), T, S)
    assert sorted(r["k"] for r in R["stg_c"]) == ["1", "3"] and sorted(r["k"] for r in R["stg_c_latest"]) == ["1", "2", "3"]
    out = {r["key"]: (r["n"], r["tot"]) for r in R["fct_out"]}
    assert out == {1: (1, 5), 3: (1, 7), 8: (4, 4), 9: (1, 2)}               # key 2 deleted (soft-delete detection), 3 updated, 8 kept, 9 inserted
    s = _spec()
    s["fct"]["merge"]["delete"] = False
    assert {r["key"]: r["n"] for r in IR.interpret(s, T, S)["fct_out"]}[2] is None


def test_engines_agree_with_reference():
    T, S = _tables()
    ref = IR.interpret(_spec(), T, S)
    for eng in ("duckdb", "sqlite", "polars"):
        got = EN.run(_spec(), T, S, eng, ["stg_c", "stg_c_latest", "int_orders", "fct_out"])
        for rel in got:
            cols = list(ref[rel][0].keys())
            assert IR.table_key(got[rel], cols) == IR.table_key(ref[rel], cols), (eng, rel)


def test_every_legacy_language_lifts_back_exactly(tmp_path):
    for i, lang in enumerate(MD.LEGACY):
        p = W.make_project10d(dict(family="t", faults=["fanout", "merge_update"], engine="duckdb", legacy=lang, names="base"), 97500 + i, tmp_path)
        c = json.loads((Path(p["ws"]) / "contract.json").read_text())
        truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
        assert json.loads(json.dumps(LG.read_and_lift(p["ws"], c))) == json.loads(json.dumps(W.inject(truth, ["fanout", "merge_update"], p["names"]))), lang
        assert 60 <= p["n_cols"] <= 120 and p["n_tables"] >= 3


def test_wide_schemas_multiply_operator_branching(tmp_path):
    p = W.make_project10d(dict(family="t", faults=["replay"], engine="duckdb", legacy="snowflake", names="base", width=110, n_tables=5), 97510, tmp_path)
    inv = D.Inv10d(p)
    n = sum(len(D.candidates(op, inv.legacy[D.OP_NODE[op]], inv.dom(D.OP_NODE[op], inv.legacy))) for op in D.OPS)
    assert n > 300


def test_held_out_compositions_never_reach_training():
    leak = MD.leakage()
    assert leak["violations"] == [] and leak["specs_checked"] == 1000
    man = MD.eval_manifest()
    assert len(man) == 48 and sum(t["group"] == "heldout" for t in man) == 24
    assert all(len({W.MECH_NODE[f] for f in t["faults"]}) >= 2 for t in man if t["group"] == "heldout")
    assert {t["engine"] for t in man if t["group"] == "heldout"} == set(MD.ENGINES) and {t["legacy"] for t in man} == set(MD.LEGACY)
    assert all(t["seed"] in MD.RANGES[("agi10dde", "eval")] for t in man)


def test_numeric_seeds_only():
    for f in SRC.glob("*.py"):
        s = f.read_text()
        assert not re.search(r"Random\(\s*f?[\"']", s), f
        assert not re.search(r"(rng|seed_of|Random)\([^)]*name", s), f


def test_renamed_learners_train_identical_rankers(tmp_path):
    from tests.test_agi10c import _steps
    outs = []
    for name in ("rep0", "rep0.clone.renamed"):
        L = LD.Learner(0, name, tmp_path / name, 1e18, tmp_path / name / "out", MD.train(0))
        L.mem["steps"] = _steps()
        L.train_rankers()
        outs.append(json.dumps(L.mem["guides"], sort_keys=True))
    assert outs[0] == outs[1]
