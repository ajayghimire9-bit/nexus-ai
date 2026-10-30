"""Phase 10E unit tests (small synthetic inputs + dev-range generated workspaces; no search, no training, no evaluation target)."""
import copy
import json
import re
from pathlib import Path

from nexus.de_phase10d import ir10d as IR, world10d as W
from nexus.de_phase10e import dag10e as D, extload10e as X, fixes10e as FX, manifest10e as ME

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/nexus/de_phase10e"


def _rel(pre=(), post=()):
    return dict(src="c", cols=[["k", ["col", "k"]], ["op", ["col", "op"]], ["ts", ["col", "ts"]], ["evt", ["col", "evt"]]],
                pre=list(pre), dedup=dict(key=["try_int", ["col", "k"]], order=["try_int", ["col", "ts"]], desc=True), post=list(post))


ROWS = [dict(k="1", op="c", ts="1", evt="100"), dict(k="1", op="u", ts="2", evt="300"), dict(k="2", op="c", ts="3", evt="150"), dict(k="2", op="d", ts="4", evt="160")]
TOMB = ["ne", ["col", "op"], ["lit", "d"]]
BUSINESS = ["notnull", ["col", "evt"]]                             # a non-tombstone predicate (10D grammar: ne / eq / notnull)


def test_shadow_sequence_witness_rejects_filter_before_dedup():
    for cond in (TOMB, BUSINESS):
        assert D.stale_witness(_rel(pre=[cond]), ROWS) == [cond]          # r_old resurrected -> rejected
        assert D.stale_witness(_rel(post=[cond]), ROWS) == []             # filter after dedup -> passes
    # the resurrection is real on data: filter-first keeps key 2's stale 'c' version, dedup-first drops the deleted key
    pre = IR.run_stg(_rel(pre=[TOMB]), {"c": ROWS}, {})
    post = IR.run_stg(_rel(post=[TOMB]), {"c": ROWS}, {})
    assert sorted(r["k"] for r in pre) == ["1", "2"] and sorted(r["k"] for r in post) == ["1"]


def test_witness_passes_predicates_that_commute_with_the_dedup():
    on_key = ["ne", ["col", "k"], ["lit", "9"]]
    assert D.stale_witness(_rel(pre=[on_key]), ROWS) == []


def test_ties_at_the_top_of_a_dedup_are_nondeterministic():
    t = _rel()
    t["dedup"] = dict(key=["try_int", ["col", "k"]], order=["try_int", ["col", "k"]], desc=True)    # add_partition interim
    assert D.dedup_ties(t, ROWS) == 2
    assert D.dedup_ties(_rel(), ROWS) == 0


def test_target_96088_state_guard_and_stage_witness():
    d = json.loads((ROOT / "artifacts/agi10c_dev/diag_96088.json").read_text())
    sub, truth = [s["submitted"] for s in d["stages"]], [s["truth"] for s in d["stages"]]
    state = {"batch.json": {"start": 126, "end": 207}}
    assert FX.unreferenced_state(state, sub) == [("batch.json", "start")]           # the wrong submission is blocked
    plus = copy.deepcopy(sub)
    plus[1]["filter"] = truth[1]["filter"][1]
    assert FX.unreferenced_state(state, plus) == [] and FX.unreferenced_state(state, truth) == []
    hdr = [n for n, _ in sub[0]["outputs"]]
    assert FX.stale_witness(sub, hdr, state) == []          # P4 IR: the stage's dedup runs BEFORE its filter (V0 = V1)
    ident = [[c, ["col", c]] for c in hdr]
    chain = [dict(outputs=ident, filter=sub[0]["filter"]), dict(outputs=ident, dedup=sub[0]["dedup"])]
    assert FX.stale_witness(chain, hdr, state) == [(0, 1)]  # a filter in an EARLIER stage than the dedup resurrects r_old
    fixed = [dict(outputs=ident), dict(outputs=ident, dedup=sub[0]["dedup"], filter=sub[0]["filter"])]
    assert FX.stale_witness(fixed, hdr, state) == []


def test_discriminative_roles():
    rels = {"r": [dict(id="1", seq="3", junk="9", qty="1"), dict(id="1", seq="7", junk="2", qty="4"), dict(id="2", seq="5", junk="4", qty="2"),
                  dict(id="3", seq="1", junk="8", qty="1"), dict(id="3", seq="9", junk="1", qty="1")]}
    dom = D.Dom10e(0, rels, {}, {("r", "id")})
    assert "ckey" in dom.roles("r", "id") and "ckey" not in dom.roles("r", "seq")
    assert "arrival" in dom.roles("r", "seq") and "arrival" not in dom.roles("r", "junk") and "arrival" not in dom.roles("r", "qty")


def test_replay_repair_is_a_two_step_path_and_the_interim_is_never_acceptable(tmp_path):
    p = W.make_project10d(dict(family="S_replay", faults=["replay"], engine="duckdb", legacy="snowflake", names="base"), 100700, tmp_path)
    inv = D.Inv10e(p)
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    want = truth["stg"]["stg_order_items"]["dedup"]
    assert not any(prm.startswith("stg_order_items|") for _, prm in D.candidates("set_dedup", inv.legacy[0], inv.dom(0, inv.legacy)))
    mid = D.replay(inv, [(0, "add_partition", f"stg_order_items|{want['key'][1][1]}")])
    assert mid[0]["stg_order_items"]["dedup"]["key"] == want["key"] and "deterministic_dedup:stg_order_items" in inv.rules(mid)
    assert not inv.run(mid, True)["ok"]
    prm = next(p2 for s, p2 in D.candidates("set_dedup", mid[0], inv.dom(0, mid)) if s["stg_order_items"]["dedup"] == want)
    fin = D.replay(inv, [(0, "set_dedup", prm)], mid)
    assert inv.run(fin, True)["ok"] and inv.run([truth[n] for n in D.NODES], True)["ok"]


def test_replay_never_reaches_training_in_a_composition():
    leak = ME.leakage()
    assert leak["violations"] == [] and leak["specs_checked"] == 1000
    man = ME.eval_manifest()
    assert len(man) == 48 and sum(t["group"] == "heldout" for t in man) == 24
    assert all("replay" in t["faults"] and len({W.MECH_NODE[f] for f in t["faults"]}) >= 2 for t in man if t["group"] == "heldout")
    assert all(t["seed"] in ME.RANGES[("agi10ede", "eval")] for t in man) and "T_dirty+replay" not in ME.TRAIN_FAMILIES
    assert {t["engine"] for t in man if t["group"] == "heldout"} == set(ME.ENGINES)


def test_numeric_seeds_only():
    for f in SRC.glob("*.py"):
        s = f.read_text()
        assert not re.search(r"Random\(\s*f?[\"']", s), f
        assert not re.search(r"(rng|seed_of|Random)\([^)]*name", s), f


def test_general_loader_on_synthetic_texts():
    T = dict(ev=[dict(k="1", s="a", ts="10"), dict(k="1", s="b", ts="20"), dict(k="2", s="a", ts="15")])
    L = X.load("select k, s from {{ source('crm', 'ev') }}", "j2", T)                      # dbt source + bare SELECT + unaliased
    assert L.ok and L.inputs == ["ev"] and L.stages[0]["outputs"] == [["k", ["col", "k"]], ["s", ["col", "s"]]]
    L = X.load("select k, s from ev qualify row_number() over (partition by k order by ts desc) = 1", "snowflake", T)
    assert L.ok and L.stages[0]["dedup"]["key"] == "k"
    L = X.load("out = ev.filter(pl.col('s') != 'b').unique(subset=['k'], keep='last')", "polars", T)
    assert L.ok and len(L.stages) == 2 and L.stages[0]["filter"] == ["ne", ["col", "s"], ["lit", "b"]]
    L = X.load("clean = ev.dropDuplicates(['k']).select('k', 's')", "py", T)
    assert L.ok and L.stages[0]["dedup"] == {"key": "k"}
    assert X.load("select k from missing_table", "postgres", T).stage == "bind"
    M = dict(a=[dict(id="1", u="x")], b=[dict(aid="1", q="3"), dict(aid="1", q="4")])
    L = X.load("select a.u, sum(b.q) as q from a join b on a.id = b.aid group by a.u", "postgres", M)            # multi-table binder
    assert L.ok and sorted(L.inputs) == ["a", "b"] and len(L.input_rows) == 2 and "R4 multi-table binder" in L.notes
