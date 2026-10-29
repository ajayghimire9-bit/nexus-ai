"""Phase 4 Stage 1 development runs (NOT LOCKED; agi4de/dev projects only, never Stage 4 targets).
  python scripts/agi4_dev.py smoke   [first seed]   Init solve, gate on vs off, 12 SQLite + 4 Spark dev projects
  python scripts/agi4_dev.py calib   [first seed]   Init solve rate per (k, runtime) at the source budgets (curriculum calibration)
Writes artifacts/agi4_dev/<mode>_<seed>.json."""
import json, sys, time
from collections import Counter
from pathlib import Path
from nexus.de_phase4 import world as W, learner as L, seeds as SD  # noqa: F401
ROOT = Path(__file__).resolve().parents[1]
WS = ROOT / "var/agi4_ws/dev"
BUDGET = {"sqlite": 2.5, "spark": 10.0}


def episode(p, de, rt, budget, gate=True, M=None, explore=False):
    rec = L.solve(p, de, rt, budget_s=budget, gate=gate, M=M, explore=explore)
    ev = W.evaluate(p, rec["code"], rt) if rec["outcome"] == "submitted" else None
    return rec, ev


def row(p, rec, ev, **kw):
    return dict(pid=p["pid"], faults=p["faults"], shape=p["shape"], outcome=rec["outcome"], status=rec.get("status"),
                verified=bool(ev and ev["ok"]), silent=rec["outcome"] == "submitted" and not (ev and ev["ok"]), runs=rec["runs"],
                runs_by=rec["runs_by"], wall=rec["wall"], edits=rec["edits"], hidden=ev and ev["fails"],
                gate=[{k: g[k] for k in g if k != "edits"} for g in rec["gate"]][-3:], **kw)


def main(mode, seed0="53600"):
    s0 = int(seed0)
    rts = {"sqlite": W.SQLiteCode(), "spark": W.SparkCode()}
    t = time.time()
    W.SparkCode.warm()
    out = dict(spark_warm_s=round(time.time() - t, 2), rows=[])
    if mode == "smoke":
        plan = [(f, k, "sqlite") for f in W.SOURCE_FAMS for k in (1, 2)] + [("F1", 2, "spark"), ("F2", 1, "spark"),
                                                                            ("F4", 2, "spark"), ("F6", 1, "spark")]
        for i, (f, k, rt) in enumerate(plan):
            p = W.make_project(f, k, s0 + i, rt, WS)
            for gate in (True, False):
                rec, ev = episode(p, L.empty_de(), rts[rt], BUDGET[rt], gate=gate)
                out["rows"].append(row(p, rec, ev, gate_on=gate, runtime=rt))
                r = out["rows"][-1]
                print(p["pid"], "gate" if gate else "nogate", r["outcome"], r["status"], "verified" if r["verified"] else
                      ("SILENT" if r["silent"] else "-"), r["runs_by"], r["wall"], flush=True)
    elif mode == "calib":
        bud = {"sqlite": float(sys.argv[3]) if len(sys.argv) > 3 else 0.5, "spark": float(sys.argv[4]) if len(sys.argv) > 4 else 2.0}
        out["budget"] = bud
        i = 0
        for k in (1, 2, 3, 4):
            for f in W.SOURCE_FAMS:
                for rt in ("sqlite", "spark") if k <= 2 else ("sqlite",):
                    p = W.make_project(f, k, s0 + i, rt, WS)
                    i += 1
                    rec, ev = episode(p, L.empty_de(), rts[rt], bud[rt], explore=True)
                    out["rows"].append(row(p, rec, ev, runtime=rt, k=k))
                    r = out["rows"][-1]
                    print(p["pid"], r["outcome"], r["status"], "V" if r["verified"] else ("S" if r["silent"] else "-"), r["runs"], r["wall"], flush=True)
        agg = {}
        for r in out["rows"]:
            a = agg.setdefault(f"k{r['k']}_{r['runtime']}", Counter())
            a["n"] += 1
            a["verified"] += r["verified"]
            a["silent"] += r["silent"]
        out["agg"] = {k: dict(v) for k, v in agg.items()}
        print(out["agg"])
    for g in (True, False):
        rs = [r for r in out["rows"] if r.get("gate_on", True) == g]
        print("gate" if g else "nogate", dict(n=len(rs), verified=sum(r["verified"] for r in rs), silent=sum(r["silent"] for r in rs),
                                              runs=sum(r["runs"] for r in rs), wall=round(sum(r["wall"] for r in rs), 1)))
    d = ROOT / "artifacts/agi4_dev"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{mode}_{s0}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:3])
