"""mi scoring (NOT LOCKED).  python scripts/mi_score.py val|test  -> artifacts/mi_<split>/gate.json | scorecard.json
val gate (pre-registered): invented exact on the dev-unfamiliar families >= baseline + 10 (of 60), invented exact on K >=
baseline - 1, invented silent <= baseline silent + 1.
test rules: R1 invented vs baseline / params / random_struct / direct on WITHHELD (exact one-sided sign tests, p <= 0.05 each);
R2 the same on dev-unfamiliar fresh; R3 K: invented >= baseline - 2; plus learning curves (exact within query / CPU budgets)."""
import json, math, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARMS = ("baseline", "invented", "random_struct", "params", "direct")
GROUPS = {"K": ("K",), "dev_unfamiliar": ("MUL", "ADDC", "SUBH"), "withheld": ("SCL", "AVG", "MAX")}
QB, CB = (500, 1000, 2000, 4000, 8000), (2, 5, 10, 20, 40)


def sign_p(a, b):
    n = a + b
    return 1.0 if n == 0 else sum(math.comb(n, i) for i in range(a, n + 1)) / 2 ** n


def main(split):
    d = ROOT / f"artifacts/mi_{split}"
    rows = {a: {r["i"]: r for r in (json.loads(l) for l in (d / f"{a}.jsonl").read_text().splitlines() if l.strip())}
            for a in ARMS if (d / f"{a}.jsonl").exists()}
    tab = {}
    for a, rs in rows.items():
        t = dict(n=len(rs))
        for g, fams in list(GROUPS.items()) + [(f, (f,)) for fams in GROUPS.values() for f in fams]:
            sub = [r for r in rs.values() if r["family"] in fams]
            if sub:
                t[g] = dict(n=len(sub), exact=sum(r["exact"] for r in sub), silent=sum(r["silent"] for r in sub),
                            cpu_s=round(sum(r["cpu_s"] for r in sub), 1), queries=sum(r["queries"] for r in sub),
                            curve_q={b: sum(r["exact"] and r["queries"] <= b for r in sub) for b in QB},
                            curve_cpu={b: sum(r["exact"] and r["cpu_s"] <= b for r in sub) for b in CB})
        tab[a] = t
    out = dict(split=split, arms=tab)
    inv = rows.get("invented", {})
    def pair(o, fams):
        common = [i for i in inv if i in rows[o] and inv[i]["family"] in fams]
        a = sum(inv[i]["exact"] and not rows[o][i]["exact"] for i in common)
        b = sum(rows[o][i]["exact"] and not inv[i]["exact"] for i in common)
        return dict(n=len(common), invented_only=a, other_only=b, p=sign_p(a, b))
    if split == "val":
        b, v = tab["baseline"], tab["invented"]
        out["passed"] = (v["dev_unfamiliar"]["exact"] >= b["dev_unfamiliar"]["exact"] + 10 and v["K"]["exact"] >= b["K"]["exact"] - 1
                         and sum(v[g]["silent"] for g in GROUPS if g in v) <= sum(b[g]["silent"] for g in GROUPS if g in b) + 1)
        out["pairs"] = {o: {g: pair(o, f) for g, f in GROUPS.items() if g in tab[o]} for o in rows if o != "invented"}
        (d / "gate.json").write_text(json.dumps(out, indent=1))
    else:
        out["rules"] = {o: {g: dict(pair(o, f), verdict=("SUPPORTED" if pair(o, f)["p"] <= 0.05 and pair(o, f)["invented_only"] > pair(o, f)["other_only"]
                                                       else "REJECTED" if pair(o, f)["invented_only"] < pair(o, f)["other_only"] else "INCONCLUSIVE"))
                            for g, f in GROUPS.items()} for o in rows if o != "invented"}
        out["R3_K_no_regression"] = tab["invented"]["K"]["exact"] >= tab["baseline"]["K"]["exact"] - 2
        (d / "scorecard.json").write_text(json.dumps(out, indent=1))
    print("| arm | " + " | ".join(f"{g} exact" for g in list(GROUPS) + [f for fs in GROUPS.values() for f in fs]) + " | silent | CPU s | queries |")
    print("|---" * (4 + len(GROUPS) + sum(len(v) for v in GROUPS.values())) + "|")
    for a, t in tab.items():
        cells = [f"{t[g]['exact']}/{t[g]['n']}" if g in t else "-" for g in list(GROUPS) + [f for fs in GROUPS.values() for f in fs]]
        print(f"| {a} | " + " | ".join(cells) + f" | {sum(t[g]['silent'] for g in GROUPS if g in t)} | {sum(t[g]['cpu_s'] for g in GROUPS if g in t):.0f} | "
              f"{sum(t[g]['queries'] for g in GROUPS if g in t)} |")
    print(json.dumps({k: v for k, v in out.items() if k in ("passed", "pairs", "rules", "R3_K_no_regression")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
