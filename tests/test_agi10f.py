"""Phase 10F unit tests (committed Phase 10E checkpoints, small synthetic inputs, dev-range / Phase 10E training-range generated
workspaces; no search, no training, no evaluation target)."""
import json
import re
import sys
from pathlib import Path

from nexus.de_phase10 import memory10 as MEM
from nexus.de_phase10d import world10d as W10D
from nexus.de_phase10e import dag10e as D, manifest10e as ME
from nexus.de_phase10f import abstract10f as AB, atomic10f as AT, dag10f as DF, lineage10f as LF, manifest10f as MF, world10f as W

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/nexus/de_phase10f"
TR10E = ROOT / "artifacts/agi10e_train"


def _replay_cands(mem, rule):
    return [json.loads(json.dumps(c)) for c in AB.invent(mem["skill_src"], 2, 3, rule, len(mem["de"]["skills"])) if len(c["edits"]) >= 2 and c["edits"][0][0] == "add_partition"]


def test_subgroup_rule_recovers_the_phase10e_ckey_macro():
    L5 = next(v["canonical"] for v in json.loads((TR10E / "rep1.N120.json").read_text())["memory"]["de"]["skills"].values() if v["edits"][0][0] == "add_partition")
    for ck in ("rep0.N60", "rep0.N118", "rep1.N120"):                  # rep0 at steps 50 / 100+, rep1 at step 100 (the failure cases)
        mem = json.loads((TR10E / f"{ck}.json").read_text())["memory"]
        cur, sub = _replay_cands(mem, "current"), _replay_cands(mem, "subgroup")
        assert [c["edits"][0][2][1] for c in cur] == [["dupes", "int"]]          # whole-group intersection strips ckey
        assert [c["canonical"] for c in cur] == [c["canonical"] for c in sub if not c.get("subgroup")]  # the broad candidate is kept
        g = [c for c in sub if c.get("subgroup")]
        assert len(g) == 1 and g[0]["canonical"] == L5                          # ... and the role-consistent subgroup is proposed
        assert len(AB.verified_projects([(dict(project=p), None) for p in g[0]["support"]])) >= AB.K_MIN
        assert MEM.delta_mdl(len(g[0]["edits"]), len(g[0]["support"]), len(mem["de"]["skills"])) > 0


def test_subgroup_rule_is_generic():
    e = lambda roles, lit="a": [["op_a", ["x", roles]], ["op_b", ["y", ["r1"]], ["z", lit]]]       # noqa: E731
    src = [dict(project=f"P{i}", stage_features=["s"], edits=e(["r1", "r2"])) for i in range(3)] + \
          [dict(project="Q#dream", stage_features=["s"], edits=e(["r1", "r3"])), dict(project="P9#partial", stage_features=["s"], edits=e(["r1", "r2"]))]
    sub = [json.loads(json.dumps(c)) for c in AB.invent(src, 2, 3, "subgroup") if c.get("subgroup")]
    assert len(sub) == 1 and sub[0]["edits"][0][1] == ["x", ["r1", "r2"]] and len(sub[0]["support"]) == 4
    assert not [c for c in AB.invent(src[:2] + src[3:], 2, 3, "subgroup") if c.get("subgroup")]     # 2 verified projects + a partial < K_MIN
    same = [dict(project=f"P{i}", stage_features=["s"], edits=e(["r1", "r2"])) for i in range(4)]
    assert AB.invent(same, 2, 3, "subgroup") == AB.invent(same, 2, 3, "current")                     # nothing to split: identical to Abs_current
    assert not [c for c in AB.invent(src, 2, 3, "subgroup") if c.get("subgroup") and c["edits"][1][2][1] != "a"]   # literals stay literal


def test_rules_select_differently_on_the_phase10e_rep0_state(tmp_path):
    ck = json.loads((TR10E / "rep0.N60.json").read_text())
    L = LF.Learner(0, "t", tmp_path / "ws", 10 ** 12, tmp_path, MF.train(0))
    L.mem = ck["memory"]
    a, b = [c["canonical"] for c in L.select("current")], [c["canonical"] for c in L.select("subgroup")]
    assert a != b and any(c.get("subgroup") and c["edits"][0][0] == "add_partition" for c in L.select("subgroup"))


def test_fork_copies_state_logs_and_checkpoints(tmp_path):
    L = LF.Learner(1, "rep1.current", tmp_path / "ws", 10 ** 12, tmp_path, MF.train(1))
    L.mem["skill_src"].append(dict(project="P", stage_features=[], edits=[]))
    L.n, L.cycles = 50, 5
    L.log("wake", dict(i=0))
    L.checkpoint(50)
    T = L.fork("subgroup", "rep1.subgroup")
    assert T.abs_mode == "subgroup" and L.abs_mode == "current" and T.mem == L.mem and T.mem is not L.mem
    T.mem["skill_src"].append(dict(project="Q", stage_features=[], edits=[]))
    assert len(L.mem["skill_src"]) == 1
    assert json.loads((tmp_path / "rep1.subgroup.N50.json").read_text())["name"] == "rep1.subgroup"
    assert (tmp_path / "rep1.subgroup.wake.jsonl").read_text() == (tmp_path / "rep1.current.wake.jsonl").read_text()


def test_generator_breaks_the_quantity_shortcut(tmp_path):
    spec = dict(family="S_replay", faults=["replay"], engine="duckdb", legacy="snowflake", names="heldout")
    p = W.make_project10d(spec, 103950, tmp_path)
    nm = p["names"]
    items = [W.read_csv(Path(p["ws"]) / "data" / f"{b}order_items.csv") for b in ("", "b/")]
    assert sum(W.decreases(rows, nm) for rows in items) >= 1                   # a later sequence with a LOWER quantity is visible
    inv = DF.Inv10f(p)
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    alias = W.quantity_alias(truth, nm)
    assert not inv.run([alias[n] for n in D.NODES], True)["ok"]                # ORDER BY quantity fails visible acceptance
    assert not D.verify_hidden(p, [alias[n] for n in D.NODES])["ok"]
    assert inv.run([truth[n] for n in D.NODES], True)["ok"]
    dom = inv.dom(0, inv.legacy)
    assert "arrival" in dom.roles("stg_order_items", nm["seq"]) and "arrival" not in dom.roles("stg_order_items", nm["qty"])


def test_justified_dedup_closes_the_phase10e_training_wrong(tmp_path):
    p = W10D.make_project10d(ME.train_spec(1, 24), 101524, tmp_path)          # rep1 task 24 (agi10ede/train), Phase 10E generator
    path = [(0, "json_coalesce_before", "stg_customers|customer_id"), (0, "add_partition", "stg_orders|legacy_id"), (0, "add_filter", "stg_orders|post|notnull|order_total|")]
    i10e, i10f = D.Inv10e(p), DF.Inv10f(p)
    sp = D.replay(i10e, path)
    assert i10e.run(sp, True)["ok"] and not D.verify_hidden(p, sp)["ok"]         # the Phase 10E verifier gap: accepted, hidden-wrong
    ev = i10f.run(sp, True)
    assert not ev["ok"] and "justified_dedup:stg_orders" in ev["failed"]
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    assert i10f.run([truth[n] for n in D.NODES], True)["ok"]


def test_null_keys_do_not_justify_a_dedup():
    t = dict(src="o", cols=[], pre=[], dedup=dict(key=["try_int", ["col", "tot"]], order=["try_int", ["col", "id"]], desc=True), post=[])
    rows = [dict(tot="", id="1"), dict(tot="12x", id="2"), dict(tot="50", id="3"), dict(tot="70", id="4")]
    assert DF.dup_groups(t, rows) == 0                                   # dirty totals -> NULL keys: not a duplicate entity
    assert DF.dup_groups(t, rows + [dict(tot="50", id="5")]) == 1


def test_atomic_substrate_is_scoped_and_one_step(tmp_path):
    spec = dict(family="S_replay", faults=["replay"], engine="duckdb", legacy="snowflake", names="base")
    p = W.make_project10d(spec, 103951, tmp_path)
    inv = DF.Inv10f(p)
    want = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())["stg"]["stg_order_items"]["dedup"]
    dom = inv.dom(0, inv.legacy)
    split_ops = D.OPS
    with AT.atomic():
        assert "add_partition" not in D.OPS and not D.candidates("add_partition", inv.legacy[0], dom)
        assert any(s["stg_order_items"].get("dedup") == want for s, _ in D.candidates("set_dedup", inv.legacy[0], dom))
    assert D.OPS == split_ops and "add_partition" in D.OPS
    assert not any(s["stg_order_items"].get("dedup") == want for s, _ in D.candidates("set_dedup", inv.legacy[0], dom))


def test_atomic_rewrite_merges_the_two_dedup_steps():
    ctx = ["pos:first", "fail:unique"]
    ap = dict(stage=0, ctx=ctx, sym=[], pos=["op:add_partition"], negs=[["op:add_partition", "x"], ["op:add_filter", "y"]],
              abs=["add_partition", ["rel", ["nodedup", "plain"]], ["key", ["ckey", "int"]]])
    sd = dict(stage=0, ctx=["pos:first"], sym=[], pos=["op:set_dedup"], negs=[["op:set_dedup", "z"]],
              abs=["set_dedup", ["rel", ["dedup", "plain"]], ["key", ["ckey", "int"]], ["order", ["arrival", "int"]], ["dir", "desc"]])
    other = dict(stage=1, ctx=ctx, sym=[], pos=["op:cast_keys"], negs=[["op:pre_aggregate"]], abs=["cast_keys"])
    pairs, merged = AT.rewrite_atomic([("P", [ap, sd, other]), ("Q", [ap])])
    assert merged == 1 and len(pairs) == 2 + 1               # (add_filter y, set_dedup z) + cast_keys; unpaired partition dropped
    pos = pairs[0][1]
    assert pos[0] == "op:set_dedup" and "op:set_dedup|rel:nodedup" in pos and "op:set_dedup|order:arrival" in pos and "op:set_dedup|ev:fail:unique" in pos
    assert all(ng[0] != "op:add_partition" for _, _, ng in pairs)


def test_manifest_and_leakage():
    man = MF.eval_manifest()
    assert len(man) == 48 and sum(t["group"] == "heldout" for t in man) == 24
    assert all(t["seed"] in MF.RANGES[("agi10fde", "eval")] for t in man)
    assert {t["family"] for t in man if t["group"] == "heldout"} == set(MF.HELD) and MF.leakage()["violations"] == []
    assert not set(MF.RANGES[("agi10fde", "eval")]) & set(ME.RANGES[("agi10ede", "eval")])
    assert MF.CHECKPOINTS == (50, 100) and MF.N_MAX == 100


def test_numeric_seeds_only():
    for f in SRC.glob("*.py"):
        s = f.read_text()
        assert not re.search(r"Random\(\s*f?[\"']", s), f
        assert not re.search(r"(rng|seed_of|Random)\([^)]*name", s), f


def test_tracked_ledger_verifies():
    sys.path.insert(0, str(ROOT / "scripts"))
    import agi10f_ledger as LG
    assert LG.verify() == 0
