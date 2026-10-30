"""Phase 10G Stage 1: mechanism of the Phase 10F training wrong submission (NOT LOCKED; agi10fde/train project only).
  python scripts/agi10g_diag_104529.py OUT.json
rep1 task 29: P10F.S_dirty.duckdb.postgres.104529, submitted path add_partition -> add_filter -> set_dedup (operator names only
in the wake log). Rebuilt on the frozen Phase 10F generator and acceptance (dag10f.Inv10f); enumerates add_partition(stg_orders|K)
-> add_filter(stg_orders, post NOT NULL on any nullable column) -> set_dedup(stg_orders|K|O|dir) (the minimal-change reorder
keeps the key) and records, for every accepted path, the hidden verdict and what the partition does on the visible batches."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import ir10d as IR  # noqa: E402
from nexus.de_phase10e import dag10e as D  # noqa: E402
from nexus.de_phase10f import dag10f as DF, manifest10f as MF, world10f as W  # noqa: E402


def main(out):
    t0 = time.time()
    spec = MF.train_spec(1, 29)
    p = W.make_project10d(spec, 104529, ROOT / "var/agi10g_ws/diag")
    inv = DF.Inv10f(p)
    truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
    rows = []
    for s1, p1 in D.candidates("add_partition", inv.legacy[0], inv.dom(0, inv.legacy)):
        if not p1.startswith("stg_orders|"):
            continue
        K = p1.split("|")[1]
        sp1 = [s1] + inv.legacy[1:]
        for s2, p2 in D.candidates("add_filter", s1, inv.dom(0, sp1)):
            if not p2.startswith("stg_orders|post|notnull"):
                continue
            sp2 = [s2] + sp1[1:]
            for s3, p3 in D.candidates("set_dedup", s2, inv.dom(0, sp2)):
                if not p3.startswith(f"stg_orders|{K}|"):
                    continue
                sp3 = [s3] + sp2[1:]
                if not inv.run(sp3, True)["ok"]:
                    continue
                t = s3["stg_orders"]
                vis = []
                for bid, (T, S, _, _) in enumerate(inv.batches):
                    rs = D._proj_rows(t, T)
                    keys = [IR.ev(t["dedup"]["key"], r) for r in rs]
                    dups = {k for k in keys if k not in (None, "") and keys.count(k) > 1}
                    kept = IR.run_stg(dict(t, post=[]), T, {})
                    dropped = [r for r in rs if r not in kept and r.get(p["names"]["total"]) not in (None, "") and IR.ev(["try_int", ["col", p["names"]["total"]]], r) is not None]
                    vis.append(dict(batch=bid, nonnull_dup_keys=len(dups), clean_rows_dropped_by_dedup=len(dropped),
                                    dropped_examples=[{c: r.get(c) for c in (p["names"]["oid"], p["names"]["fk"], p["names"]["total"], K)} for r in dropped[:3]]))
                rows.append(dict(path=[p1, p2, p3], hidden=D.verify_hidden(p, sp3), visible=vis))
    wrong = [r for r in rows if not r["hidden"]["ok"]]
    res = dict(project=p["pid"], truth_stg_orders=truth["stg"]["stg_orders"], accepted=len(rows), wrong=len(wrong), wrong_paths=wrong[:10],
               correct_paths=[r["path"] for r in rows if r["hidden"]["ok"]][:10], wall=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(dict(accepted=len(rows), wrong=len(wrong), wall=res["wall"])))
    for r in wrong[:5]:
        print("WRONG", r["path"], r["hidden"]["fails"], [(v["nonnull_dup_keys"], v["clean_rows_dropped_by_dedup"], v["dropped_examples"]) for v in r["visible"]])


if __name__ == "__main__":
    main(*sys.argv[1:])
