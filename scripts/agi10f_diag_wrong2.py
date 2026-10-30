"""Phase 10F audit, part 2 (NOT LOCKED; training project 101524 only): why the stg_orders partition survives Occam pruning, and
what it changes on the visible and hidden batches.  python scripts/agi10f_diag_wrong2.py OUT.json"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import world10d as W, ir10d as IR  # noqa: E402
from nexus.de_phase10e import dag10e as D, manifest10e as ME  # noqa: E402


def main(out):
    p = W.make_project10d(ME.train_spec(1, 24), 101524, ROOT / "var/agi10f_ws/diag")
    inv = D.Inv10e(p)
    res = {}
    for part in ("legacy_id", "shipping_cents", "margin_bp"):
        for pos in ("pre", "post"):
            full = [(0, "json_coalesce_before", "stg_customers|customer_id"), (0, "add_partition", f"stg_orders|{part}"), (0, "add_filter", f"stg_orders|{pos}|notnull|order_total|")]
            pruned = [full[0], full[2]]
            evf, evp = inv.run(D.replay(inv, full), True), inv.run(D.replay(inv, pruned), True)
            sp = D.replay(inv, full)
            t = sp[0]["stg_orders"]
            vis = []
            for bid, (T, S, _, _) in enumerate(inv.batches):
                rows = [r for r in D._proj_rows(t, T)]
                groups = {}
                for r in rows:
                    groups.setdefault(IR.ev(t["dedup"]["key"], r), []).append(r)
                vis.append(dict(batch=bid, rows=len(rows), dup_groups=sum(len(g) > 1 for g in groups.values()), dedup_ties=D.dedup_ties(t, rows)))
            res[f"{part}/{pos}"] = dict(full_ok=evf["ok"], full_failed=evf["failed"], pruned_ok=evp["ok"], pruned_failed=evp["failed"], visible=vis,
                                        hidden=D.verify_hidden(p, sp))
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    for k, v in res.items():
        print(k, v)


if __name__ == "__main__":
    main(*sys.argv[1:])
