"""Wave 39 Step 1 (NOT LOCKED): 4-way failure taxonomy on PROSE-dev (the 40 PROSE tasks run/inspected in Waves 38; now
quarantined as development data). Reruns the Stage 4 search locally (same declared v4 scope, depth 3, budget 2M executions,
Fresh and Repr) and records WHY each task failed:
  1 missing expressiveness : the declared depth-3 scope was enumerated to exhaustion with no chain fitting the public pairs
                             (also: input format the v4 harness cannot express, e.g. multi-column inputs)
  2 search-budget exhaustion: the budget ran out before exhaustion AND a 10x budget / depth-4 search finds a chain that
                             passes every held-out pair
  3 misleading prior       : Fresh certifies a held-out-correct answer within budget, Repr does not
  4 insufficient examples  : a chain fits all public pairs (certified UNIQUE in scope) but fails held-out pairs
Tasks with < 4 examples cannot be split 3 public + held-out and are reported as NOT EVALUABLE (outside the taxonomy)."""
import argparse, glob, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus import w38_domains as Dm, w38_lang as L, w38_learn as K, w38_scope as S, w38_search as Q
from nexus.wave31_evaluator import ledger_append


def load(f):
    ex = json.load(open(f))["Examples"]
    if len(ex) < 4:
        return None, "NOT_EVALUABLE_TOO_FEW_EXAMPLES"
    if any(len(e["Input"]) != 1 for e in ex):
        return None, "FORMAT_MULTI_COLUMN"
    return {"public": [[e["Input"][0], e["Output"]] for e in ex[:3]], "query": ex[3]["Input"][0],
            "heldout": [[e["Input"][0], e["Output"]] for e in ex[3:]]}, None


def held(c, t):
    return sum(L.key(L.run(c, x)) == L.key(y) for x, y in t["heldout"]) / len(t["heldout"])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    p = Path(a.out); res = json.loads(p.read_text()) if p.exists() else {}
    t0 = time.perf_counter()
    progs = [t["teacher"] for t in Dm.stream("stage4-prose-src", ("strings", "tables"), "source", 2)]
    rep = K.fit_repr(progs)
    for f in sorted(glob.glob(str(ROOT / "artifacts/external/prose/*.json"))):
        name = Path(f).stem
        if name in res:
            continue
        t, fmt = load(f)
        if t is None:
            res[name] = {"bucket": "1_missing_expressiveness" if fmt == "FORMAT_MULTI_COLUMN" else "not_evaluable", "why": fmt}
            continue
        sc = S.scope(t["public"], t["query"], 3)
        row = {"T": len(sc["tools"])}
        for arm, pr in (("Fresh", None), ("Repr", rep)):
            m = {}
            c = Q.search(t["public"], t["query"], sc["tools"], 3, K.cost_matrix(pr, sc["tools"]), budget=2_000_000, meter=m)
            row[arm] = {"found": c is not None, "execs": m["execs"], "exhausted": c is None and m["execs"] <= 2_000_000,
                        "heldout": held(c, t) if c else None, "chain": c}
        if not row["Fresh"]["found"]:
            m = {}
            c = Q.search(t["public"], t["query"], S.scope(t["public"], t["query"], 4)["tools"], 4,
                         K.cost_matrix(None, S.scope(t["public"], t["query"], 4)["tools"]), budget=20_000_000, meter=m)
            row["depth4_10x"] = {"found": c is not None, "execs": m["execs"], "heldout": held(c, t) if c else None, "chain": c}
        F, R = row["Fresh"], row["Repr"]
        if F["found"] and F["heldout"] < 1:
            b = "4_insufficient_examples"
        elif F["found"] and (not R["found"] or R["heldout"] < 1):
            b = "3_misleading_prior"
        elif F["found"]:
            b = "solved"
        elif not F["exhausted"] and row["depth4_10x"]["found"] and row["depth4_10x"]["heldout"] == 1:
            b = "2_search_budget"
        elif row.get("depth4_10x", {}).get("found") and row["depth4_10x"]["heldout"] < 1:
            b = "4_insufficient_examples"          # only reachable at depth 4, and wrong on held-out
        else:
            b = "1_missing_expressiveness"
        row["bucket"] = b
        res[name] = row
        p.write_text(json.dumps(res, sort_keys=True))
        print(name, b, F["execs"], F["exhausted"], row.get("depth4_10x", {}).get("execs"), flush=True)
        if time.perf_counter() - t0 > 840:
            break
    ledger_append(dict(run="w39-step1-audit", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
