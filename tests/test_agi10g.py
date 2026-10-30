"""Phase 10G unit tests (dev-range / Phase 10F training-range generated workspaces, committed artifacts, synthetic records; no search,
no training, no evaluation target)."""
import json
import re
import sys
from pathlib import Path

from nexus.de_phase10e import dag10e as D, manifest10e as ME
from nexus.de_phase10f import atomic10f as AT, dag10f as DF, manifest10f as MF, world10f as W10F
from nexus.de_phase10g import dag10g as DG, ev10g as EV, lineage10g as LG, manifest10g as MG

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/nexus/de_phase10g"


def test_necessary_dedup_closes_task_104529(tmp_path):
    p = W10F.make_project10d(MF.train_spec(1, 29), 104529, tmp_path)          # Phase 10F rep1 task 29 (agi10fde/train)
    path = [(0, "add_partition", "stg_orders|tax_amount"), (0, "add_filter", "stg_orders|post|notnull|order_total|"),
            (0, "set_dedup", "stg_orders|tax_amount|created_at|desc")]
    i10f, i10g = DF.Inv10f(p), DG.Inv10g(p)
    sp = D.replay(i10f, path)
    assert i10f.run(sp, True)["ok"] and not D.verify_hidden(p, sp)["ok"]        # the Phase 10F false accept
    ev = i10g.run(sp, True)
    assert not ev["ok"] and "necessary_dedup:stg_orders" in ev["failed"]
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    assert i10g.run([truth[n] for n in D.NODES], True)["ok"]                    # 0 false abstains on the valid repair
    runs = dict(i10g.runs)
    i10g.rules(sp)
    assert i10g.runs == runs                                                    # the rule is uncharged


def _tie(tmp_path, fam, amb, seed):
    faults = list(MG.TRAIN_FAMILIES[fam])
    p = LG.build(dict(family=fam, faults=faults, amb=amb, engine="duckdb", legacy="snowflake", names="base"), seed, tmp_path)
    inv = LG.inv_for(p)
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    path, found = LG.witness(inv, truth)
    assert found
    return p, inv, EV.tie_set(inv, path)


def test_designed_ties_need_the_right_channel(tmp_path):
    with AT.atomic():
        for fam, amb, seed in (("S_replay", "seq", 106950), ("S_qualify_order", "time", 106951), ("S_fanout", "grain", 106952)):
            p, inv, (C, sigs) = _tie(tmp_path, fam, amb, seed)
            assert len(C) >= 2
            right = {"seq": 1, "time": 2, "grain": 3}[amb]
            for e in range(1, 6):
                r = EV.resolve(inv, C, [e], 1)
                assert (r["outcome"] == "resolved") == (e == right), (amb, e, r)
            r = EV.resolve(inv, C, [right], 1)
            assert LG.verify_hidden(p, r["chosen"][1])["ok"] and r["ev_execs"] == EV.C_REQ + len(C)
            assert EV.resolve(inv, C, [4, right], 2)["outcome"] == "resolved"                     # B_ev = 2 recovers after a decoy
            assert EV.resolve(inv, C, [], 0)["outcome"] == "abstain_no_evidence"                 # E0
            assert EV.order_E2(sigs)[0] == {"set_dedup": 1, "pre_aggregate": 3}[sigs[0]["op"]]   # the fixed rule maps dedup ties to channel 1
        p, inv, (C, _) = _tie(tmp_path, "S_replay", None, 106953)
        assert len(C) == 1                                                                         # no designed ambiguity: no tie


def test_pi_ev_learns_from_gain_records_only():
    rec = [dict(features=["op:set_dedup", "rel:cdc", "n:3"], gain={"1": 0, "2": 1, "3": 0, "4": 0, "5": 0})] * 3 + \
          [dict(features=["op:set_dedup", "rel:plain", "n:3"], gain={"1": 1, "2": 0, "3": 0, "4": 0, "5": 0})] * 3 + \
          [dict(features=["op:pre_aggregate", "rel:node", "n:2"], gain={"1": 0, "2": 0, "3": 1, "4": 0, "5": 0})] * 3
    w, info = EV.train_pi(rec, 0)
    assert info["pairs"] == 36
    assert EV.order_E3(w, ["op:set_dedup", "rel:cdc", "n:3"])[0] == 2
    assert EV.order_E3(w, ["op:set_dedup", "rel:plain", "n:3"])[0] == 1
    assert EV.order_E3(w, ["op:pre_aggregate", "rel:node", "n:2"])[0] == 3
    assert EV.order_E3({}, []) == [1, 2, 3, 4, 5]


def test_random_policy_is_numeric_seeded():
    assert EV.order_E1(0, 108000) == EV.order_E1(0, 108000) and sorted(EV.order_E1(1, 108001)) == [1, 2, 3, 4, 5]


def test_manifest_and_leakage():
    man = MG.eval_manifest()
    assert len(man) == 48 and sum(t["group"] == "heldout" for t in man) == 24
    for grp in ("heldout", "ordinary"):
        assert sorted(str(t["amb"]) for t in man if t["group"] == grp) == sorted(["seq"] * 6 + ["time"] * 6 + ["grain"] * 6 + ["None"] * 6)
    assert all(t["seed"] in MG.RANGES[("agi10gde", "eval")] for t in man)
    assert not set(MG.RANGES[("agi10gde", "eval")]) & (set(MF.RANGES[("agi10fde", "eval")]) | set(ME.RANGES[("agi10ede", "eval")]))
    lk = MG.leakage()
    assert lk["violations"] == [] and lk["base"] == []
    assert all((t["amb"] is None) or (dict(seq="replay", time="qualify_order", grain="fanout")[t["amb"]] in t["faults"]) for t in man)


def test_step50_support_below_threshold():
    d = json.loads((ROOT / "artifacts/agi10g_step50_counts.json").read_text())
    assert all(v["verified_projects_with_ckey"] < v["k_min"] == 3 for v in d.values())


def test_numeric_seeds_only():
    for f in SRC.glob("*.py"):
        s = f.read_text()
        assert not re.search(r"Random\(\s*f?[\"']", s), f
        assert not re.search(r"(rng|seed_of|Random)\([^)]*name", s), f


def test_tracked_ledger_verifies():
    sys.path.insert(0, str(ROOT / "scripts"))
    import agi10f_ledger as LGR
    assert LGR.verify() == 0
