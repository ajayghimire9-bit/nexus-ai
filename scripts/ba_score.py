"""ba validation gate / sealed scorecard (NOT LOCKED).  python scripts/ba_score.py val|val_b|test
Reads artifacts/ba_<split>/p<k>_<arm>.json for every (project, arm); val / val_b: writes gate.json (PASSED iff NEXUS_Confirmed
is independently correct on every project with 0 silent, all projects evaluated); test: writes scorecard.json
(primary criterion: 16/16 independently correct, 0 silent)."""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARMS = ("NEXUS_Confirmed", "NEXUS_U5", "Fixed_Policy", "Conventional")


def main():
    split = sys.argv[1]
    d = ROOT / f"artifacts/ba_{split}"
    n = {"val": 8, "val_b": 8, "test": 16}[split]
    R = {}
    for k in range(n):
        for a in ARMS:
            p = d / f"p{k}_{a}.json"
            R[(k, a)] = json.loads(p.read_text())["result"] if p.exists() else None
    tab = {}
    for a in ARMS:
        rs = [R[(k, a)] for k in range(n)]
        ev = [r for r in rs if r is not None]
        tab[a] = dict(evaluated=len(ev), independently_correct=sum(r["independently_correct"] for r in ev),
                      data_ok=sum(r["data_ok"] for r in ev), silent=sum(r["silent"] for r in ev),
                      completed=sum(r.get("completed", False) for r in ev), human_repairs=sum(r.get("human_repairs", 0) for r in ev),
                      timed_out=sum(r.get("outcome") == "TIMED_OUT" for r in ev), crashed=sum(r.get("outcome") == "CRASHED" for r in ev),
                      abstained=sum(r.get("outcome") == "ABSTAIN" for r in ev),
                      by_fault={f: f"{sum(r['independently_correct'] for r in ev if r['fault'] == f)}/{sum(r['fault'] == f for r in ev)}"
                                for f in sorted({r["fault"] for r in ev})},
                      by_domain={dm: f"{sum(r['independently_correct'] for r in ev if r['domain'] == dm)}/{sum(r['domain'] == dm for r in ev)}"
                                 for dm in sorted({r["domain"] for r in ev})},
                      crash_identical=f"{sum(r.get('crash_ok') is True for r in ev)}/{sum(r.get('crash_ok') is not None for r in ev)}")
    per = [dict(index=k, seed=(R[(k, ARMS[0])] or {}).get("project"), domain=(R[(k, ARMS[0])] or {}).get("domain"),
                fault=(R[(k, ARMS[0])] or {}).get("fault"),
                **{a: (None if R[(k, a)] is None else ("CORRECT" if R[(k, a)]["independently_correct"] else
                       "SILENT" if R[(k, a)]["silent"] else R[(k, a)]["outcome"] + ("/data_ok" if R[(k, a)]["data_ok"] else "/bad")
                       + (f"/human{R[(k, a)]['human_repairs']}" if R[(k, a)].get("human_repairs") else ""))) for a in ARMS})
           for k in range(n)]
    c = tab["NEXUS_Confirmed"]
    ok = c["evaluated"] == n and c["independently_correct"] == n and c["silent"] == 0
    out = dict(split=split, n=n, arms=tab, projects=per, passed=ok)
    (d / ("scorecard.json" if split == "test" else "gate.json")).write_text(json.dumps(out, indent=1))
    print("| arm | evaluated | independently correct | silent | data correct | human repairs | timed out | crashed | by fault | by domain |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for a, t in tab.items():
        print(f"| {a} | {t['evaluated']}/{n} | {t['independently_correct']}/{t['evaluated']} | {t['silent']} | {t['data_ok']} | {t['human_repairs']} | "
              f"{t['timed_out']} | {t['crashed']} | {t['by_fault']} | {t['by_domain']} |")
    print()
    for p in per:
        print(p)
    print("criterion" if split == "test" else "gate", "PASSED" if ok else "NOT MET")


if __name__ == "__main__":
    main()
