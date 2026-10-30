"""Phase 10E Stage 1B: why Phase 10D training verified 0 replay repairs (NOT LOCKED; training-stream data only, no target).
  python scripts/agi10e_diag_replay.py OUT.json
Rebuilds every Phase 10D training task whose family contains `replay` (rep0 + rep1 wake logs), and measures on each, with the
frozen Phase 10D code and the fixed operator order:
  n_root           L0 candidates at the root (all nodes)
  dedup_cands      set_dedup candidates on the replayed relation (stg_order_items)
  truth_pos        position of the generator's replay repair (set_dedup item key x ingest-seq order x desc) in the fixed
                   interleaved root order (search10d.candidates; the search evaluates at most `widen` = 40 children per expansion)
  role_twins       dedup candidates on that relation whose role-form edit (dag10d.abstract_edit) is IDENTICAL to the truth's:
                   a role-form macro or a role-token ranker cannot tell them apart
  visible_ok       the truth repair (plus the dirty repair on T_dirty+replay) alone passes every visible check and contract
  visible_twins    role twins that ALSO pass every visible check (an over-permissive verifier would accept them)
  hidden_ok        the truth repair verifies on the declared engine and both hidden batches"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import dag10d as D, manifest10d as MD, search10d as SD, world10d as W  # noqa: E402


def main(out):
    res = []
    for rep in (0, 1):
        for l in open(ROOT / f"artifacts/agi10d_train/rep{rep}.wake.jsonl"):
            w = json.loads(l)
            if "replay" not in w["faults"]:
                continue
            p = W.make_project10d(MD.train_spec(rep, w["i"]), w["seed"], ROOT / "var/agi10e_ws/diag")
            inv = D.Inv10d(p)
            truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
            nm = p["names"]
            start = [dict(s) for s in inv.legacy]
            pre_path = []
            if "dirty" in w["faults"]:                                  # apply the generator's dirty repair first
                start[0] = dict(start[0], stg_orders=dict(start[0]["stg_orders"], pre=truth["stg"]["stg_orders"]["pre"]))
            rel = "stg_order_items"
            want = truth["stg"][rel]["dedup"]
            dom = inv.dom(0, start)
            cands = D.candidates("set_dedup", start[0], dom)
            dc = [(s, prm) for s, prm in cands if prm.startswith(rel + "|")]
            t_prm = next(prm for s, prm in dc if s[rel]["dedup"] == want)
            t_abs = D.abstract_edit("set_dedup", t_prm, dom)
            twins = [(s, prm) for s, prm in dc if D.abstract_edit("set_dedup", prm, dom) == t_abs and prm != t_prm]
            node = dict(specs=start, ev=inv.run(start, True))
            order = SD.candidates(inv, {}, node, "whole")
            pos = next(i for i, c in enumerate(order) if c["op"] == "set_dedup" and c["prm"] == t_prm)
            fixed = list(start)
            fixed[0] = dict(start[0], **{rel: dict(start[0][rel], dedup=want)})
            vis = inv.run(fixed, True)["ok"]
            vtw = 0
            for s, prm in twins:
                sp = list(start)
                sp[0] = s
                vtw += inv.run(sp, True)["ok"]
            hid = D.verify_hidden(p, fixed)["ok"]
            ints = [c for c, _ in start[0][rel]["cols"] if "int" in dom.roles(rel, c)]
            res.append(dict(rep=rep, i=w["i"], seed=w["seed"], family=w["family"], n_cols=p["n_cols"], n_root=len(order), dedup_cands=len(dc),
                            int_cols_in_rel=len(ints), truth_pos=pos, truth_role_form=json.loads(json.dumps(t_abs, default=list)),
                            role_twins=len(twins), visible_ok=vis, visible_twins=vtw, hidden_ok=hid, logged_work=w["work"], logged_outcome=w["outcome"],
                            root_symptoms=sorted(node["ev"]["features"]), root_stage_fail=node["ev"]["stage_fail"]))
            print(json.dumps({k: res[-1][k] for k in ("rep", "seed", "family", "n_cols", "n_root", "dedup_cands", "truth_pos", "role_twins",
                                                      "visible_ok", "visible_twins", "hidden_ok")}), flush=True)
    summ = dict(n=len(res), truth_pos_min=min(r["truth_pos"] for r in res), truth_pos_median=sorted(r["truth_pos"] for r in res)[len(res) // 2],
                beyond_600=sum(r["truth_pos"] >= 600 for r in res), visible_ok=sum(r["visible_ok"] for r in res), hidden_ok=sum(r["hidden_ok"] for r in res),
                role_twins_median=sorted(r["role_twins"] for r in res)[len(res) // 2], with_visible_twins=sum(r["visible_twins"] > 0 for r in res),
                dedup_cands_median=sorted(r["dedup_cands"] for r in res)[len(res) // 2])
    Path(out).write_text(json.dumps(dict(summary=summ, tasks=res), indent=1, default=str))
    print("SUMMARY", json.dumps(summ))


if __name__ == "__main__":
    main(*sys.argv[1:])
