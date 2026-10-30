"""Phase 10F Stage 1 design check (NOT LOCKED; agi10fde/dev projects only): the 2 wrong submissions of the forced-fork dev
rehearsal (P10F.T_cdc_key+dirty.polars.hive.103310, P10F.S_dirty.polars.snowflake.103313; paths [json_coalesce_before ->]
add_partition -> add_filter -> set_dedup). Enumerates that path shape restricted to stg_orders (the relation without a truth
dedup) and reports, for every path accepted under dag10f, whether it is hidden-wrong and what its partition key is.
  python scripts/agi10f_diag_dev_wrong.py OUT.json"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import ir10d as IR  # noqa: E402
from nexus.de_phase10e import dag10e as D  # noqa: E402
from nexus.de_phase10f import dag10f as DF, manifest10f as MF, world10f as W  # noqa: E402


def main(out):
    t0 = time.time()
    b = MF.RANGES[("agi10fde", "dev")].start + 300
    res = {}
    for i in (10, 13):
        spec = MF.train_spec(1, i)
        p = W.make_project10d(spec, b + i, ROOT / "var/agi10f_ws/diagdev")
        inv = DF.Inv10f(p)
        starts = [inv.legacy]
        if "cdc_key" in spec["faults"]:
            starts = [[s] + inv.legacy[1:] for s, _ in D.candidates("json_coalesce_before", inv.legacy[0], inv.dom(0, inv.legacy))]
        rows = []
        for sp0 in starts:
            for s1, p1 in D.candidates("add_partition", sp0[0], inv.dom(0, sp0)):
                if not p1.startswith("stg_orders|"):
                    continue
                sp1 = [s1] + sp0[1:]
                for s2, p2 in D.candidates("add_filter", s1, inv.dom(0, sp1)):
                    if not p2.startswith("stg_orders|post|notnull"):
                        continue
                    sp2 = [s2] + sp1[1:]
                    for s3, p3 in D.candidates("set_dedup", s2, inv.dom(0, sp2)):
                        if not p3.startswith("stg_orders|"):
                            continue
                        sp3 = [s3] + sp2[1:]
                        if inv.run(sp3, True)["ok"]:
                            t = s3["stg_orders"]
                            vis = [r for r in D._proj_rows(t, inv.tables)]
                            keys = [IR.ev(t["dedup"]["key"], r) for r in vis]
                            nn = {k for k in keys if k is not None and keys.count(k) > 1}
                            rows.append(dict(path=[p1, p2, p3], hidden_ok=D.verify_hidden(p, sp3)["ok"], null_key_rows=keys.count(None), nonnull_dup_keys=len(nn)))
        res[p["pid"]] = dict(ok_paths=len(rows), wrong=sum(not r["hidden_ok"] for r in rows),
                             wrong_with_only_null_dups=sum(not r["hidden_ok"] and r["nonnull_dup_keys"] == 0 for r in rows), examples=[r for r in rows if not r["hidden_ok"]][:8])
    res["wall"] = round(time.time() - t0, 1)
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    for k, v in res.items():
        print(k, v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "examples"})
        if isinstance(v, dict):
            for e in v["examples"][:4]:
                print("   ", e)


if __name__ == "__main__":
    main(*sys.argv[1:])
