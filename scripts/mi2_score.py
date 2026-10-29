"""MI-2 scoring with the pre-registered decision rules (NOT LOCKED).  python scripts/mi2_score.py val | test | btest
Exact = the evaluator's held-out stream check; silent = a learner accepted a machine that is not exact (wrong accepted output).
val  (gate, artifacts/mi2_val/gate.json). Primary arm A2 (the evolve representative); decisive controls C = A0 A1 A3 A4 A5 A6.
     On the 90 dev-unfamiliar episodes: G1 exact(A2) - exact(c) >= 6 for every c; G2 exact one-sided sign test on discordant
     episodes p <= 0.05 / 6 (Bonferroni over the six primary comparisons) for every c; G3 silent(A2) <= silent(A0) (all 110);
     G4 K exact(A2) >= K exact(A0) - 1. All four required; no revision.
test (confirmation, artifacts/mi2_test/result.json). The same G1 (>= 8) and G2 on the 120 WITHHELD-family episodes; G3 on all
     210; G4 K >= A0 - 2 (30 K episodes). Dev-unfamiliar fresh is reported. A pass writes artifacts/mi2_accepted.json (A2's
     procedure = the accepted machine-generated procedure for Milestone B).
btest (Milestone B, artifacts/mi2_btest/result.json). Paired lineages L1, L2: positive iff for BOTH pairs exact(B1_Lx) -
     exact(B0_Lx) >= 5 on the 90 SCL / AVG / MAX episodes; pooled sign test (B1-only vs B0-only over both pairs) p <= 0.05; the
     better B1 descendant beats BA (the accepted procedure unchanged) by >= 5 (an actual further improvement); silent(B1_Lx) <=
     silent(B0_Lx); K exact(B1_Lx) >= exact(A0) - 1."""
import json, sys
from math import comb
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
UNF, WH = ("MUL", "ADDC", "SUBH"), ("SCL", "AVG", "MAX")


def rows(split, arm):
    p = ROOT / f"artifacts/mi2_{split}/{arm}.jsonl"
    return {r["i"]: r for r in (json.loads(l) for l in p.read_text().splitlines() if l.strip())}


def sign_p(a, b):
    n = a + b
    return sum(comb(n, k) for k in range(a, n + 1)) / 2 ** n if n else 1.0


def table(split, arms, n_total):
    out = {}
    for a in arms:
        r = rows(split, a)
        if len(r) != n_total:
            raise SystemExit(f"{split}/{a}: {len(r)} of {n_total} episodes recorded")
        fams = sorted({x["family"] for x in r.values()})
        out[a] = dict(rows=r, exact={f: sum(x["exact"] for x in r.values() if x["family"] == f) for f in fams},
                      silent=sum(x["silent"] for x in r.values()), cpu_s=round(sum(x["cpu_s"] for x in r.values()), 1),
                      full_cpu_s=round(sum(x.get("full_cpu_s", 0.0) for x in r.values()), 1),
                      queries=sum(x["queries"] for x in r.values()),
                      exact_3s={f: sum(x["exact"] and x.get("full_cpu_s", 0.0) <= 3.0 for x in r.values() if x["family"] == f) for f in fams})
    return out


def compare(T, a, c, fams):
    ra, rc = T[a]["rows"], T[c]["rows"]
    ids = [i for i in ra if ra[i]["family"] in fams]
    ea, ec = sum(ra[i]["exact"] for i in ids), sum(rc[i]["exact"] for i in ids)
    ao = sum(ra[i]["exact"] and not rc[i]["exact"] for i in ids)
    co = sum(rc[i]["exact"] and not ra[i]["exact"] for i in ids)
    return dict(primary=ea, control=ec, diff=ea - ec, primary_only=ao, control_only=co, p=sign_p(ao, co))


def ab(split):
    fr = json.loads((ROOT / "artifacts/mi2_freeze.json").read_text())
    arms = list(fr["arms"][split])
    n = 110 if split == "val" else 210
    T = table(split, arms, n)
    C = ["A0", "A1", "A3", "A4", "A5", "A6"]
    fams, thr = (UNF, 6) if split == "val" else (WH, 8)
    cmp = {c: compare(T, "A2", c, fams) for c in C}
    g1 = all(v["diff"] >= thr for v in cmp.values())
    g2 = all(v["p"] <= 0.05 / len(C) for v in cmp.values())
    g3 = T["A2"]["silent"] <= T["A0"]["silent"]
    g4 = T["A2"]["exact"]["K"] >= T["A0"]["exact"]["K"] - (1 if split == "val" else 2)
    res = dict(split=split, passed=g1 and g2 and g3 and g4, G1=g1, G2=g2, G3=g3, G4=g4, threshold=thr, primary_families=fams,
               comparisons=cmp, dev_unfamiliar={c: compare(T, "A2", c, UNF) for c in C},
               table={a: {k: v for k, v in t.items() if k != "rows"} for a, t in T.items()})
    d = ROOT / f"artifacts/mi2_{split}"
    (d / ("gate.json" if split == "val" else "result.json")).write_text(json.dumps(res, indent=1))
    if split == "test" and res["passed"]:
        (ROOT / "artifacts/mi2_accepted.json").write_text(json.dumps(dict(accepted=[fr["arms"]["test"]["A2"]["file"]],
                                                                          by="mi2_score.py test (confirmation passed)"), indent=1))
    return res


def btest():
    fr = json.loads((ROOT / "artifacts/mi2_bfreeze.json").read_text())
    T = table("btest", list(fr["arms"]["btest"]), 140)
    pairs = {L: compare(T, f"B1_L{L}", f"B0_L{L}", WH) for L in (1, 2)}
    pooled_a = sum(v["primary_only"] for v in pairs.values())
    pooled_c = sum(v["control_only"] for v in pairs.values())
    best = max((1, 2), key=lambda L: pairs[L]["primary"])
    vs_ba = compare(T, f"B1_L{best}", "BA", WH)
    ok = (all(v["diff"] >= 5 for v in pairs.values()) and sign_p(pooled_a, pooled_c) <= 0.05 and vs_ba["diff"] >= 5
          and all(T[f"B1_L{L}"]["silent"] <= T[f"B0_L{L}"]["silent"] for L in (1, 2))
          and all(T[f"B1_L{L}"]["exact"]["K"] >= T["A0"]["exact"]["K"] - 1 for L in (1, 2)))
    res = dict(passed=ok, pairs=pairs, pooled=dict(b1_only=pooled_a, b0_only=pooled_c, p=sign_p(pooled_a, pooled_c)), b1_vs_ba=vs_ba,
               table={a: {k: v for k, v in t.items() if k != "rows"} for a, t in T.items()})
    (ROOT / "artifacts/mi2_btest/result.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    r = btest() if sys.argv[1] == "btest" else ab(sys.argv[1])
    print(json.dumps({k: v for k, v in r.items() if k != "table"}, indent=1))
    for a, t in r["table"].items():
        print(a, t["exact"], "silent", t["silent"], "cpu", t["cpu_s"])
