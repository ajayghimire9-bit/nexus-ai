"""Milestone A (NOT LOCKED): learned fragment priors + learned tool knowledge for HELD-OUT mechanisms, under Checker v3
(pinned), the sandbox and the OS meter. Suite: the Wave 31 increment-3 LODO tasks (depth-4 matched G_P scope); held_out
cores never appear in source. Per fold: source tasks are solved as Fresh-v3 (BFS); the evaluator returns the candidates its
checker certified (exhaustive_UNIQUE) plus the source views; the child fits the prior (metered = MARGINAL learning
cost). Configs (all matched exhaustive strength, no proofs, no macros):
  Fresh-v3 (eager BFS first-fit), Fresh-lazy (same best-first engine, uniform prior), Experienced-frag (learned prior +
  tool knowledge), Placebo-frag (the same prior and knowledge with tool identities permuted)."""
import argparse, hashlib, json, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DEPTH, ALPHA, LAM = 4, 1.0, 0.8
NOISY = ("ext", "solver_reported")


def digest(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def run_seed(seed, hashseed):
    from nexus import wave31_evaluator as E
    from nexus import wave31_tasks as T
    ev = E.Evaluator(depth=DEPTH, checker=3)
    out = dict(seed=seed, pin=ev.pin, folds={})
    for h in ("records", "strings", "grids", "graphs"):
        f = {}
        src = T.source_stream3(seed, h)
        ch = E.Child(hashseed)
        progs, views, rows = [], [], []
        for i, t in enumerate(src):
            r = ev.solve(ch, t, "Fresh", "matched", [], f"{seed}:{h}:src{i}", {"matched_depth": DEPTH, "checker": 3})
            rows.append(r)
            if r["label"] == "exhaustive_UNIQUE":
                progs.append(r["candidate"]); views.append({"public": t["public"], "query": t["query"]})
        c0 = E.instructions(ch.p.pid)
        ch.send({"cmd": "fit_prior", "programs": progs, "views": views, "alpha": ALPHA, "lam": LAM, "seed": f"{seed}:{h}"})
        pri = ch.recv()["result"]
        fit = E.instructions(ch.p.pid) - c0
        ch.close()
        f["source"] = dict(n=len(src), certified=len(progs), wrong=sum(r["wrong"] is not None for r in rows),
                           solve_work=sum(r["ext"]["evaluator_work"] for r in rows), marginal_fit_instr=fit,
                           redundant=len(pri["learned"]["redundant"]), prior_digest=digest(pri["learned"]))
        configs = {"Fresh-v3": {}, "Fresh-lazy": {"search": "best_first", "prior": pri["uniform"]},
                   "Experienced-frag": {"search": "best_first", "prior": pri["learned"]},
                   "Placebo-frag": {"search": "best_first", "prior": pri["placebo"]}}
        tgt = T.target_stream3(seed, h)
        f["configs"] = {}
        for name, pol in configs.items():
            ch = E.Child(hashseed)
            f["configs"][name] = [ev.solve(ch, t, "Fresh", "matched", [], f"{seed}:{h}:{k}",
                                           dict(pol, matched_depth=DEPTH, checker=3)) for k, t in enumerate(tgt)]
            ch.close()
        out["folds"][h] = f
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int); ap.add_argument("--split", default="dev")
    ap.add_argument("--hashseed", default="0"); ap.add_argument("--out"); ap.add_argument("--claim-only", action="store_true")
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    if a.claim_only:
        R.claim("wave31", a.split, list(R.REGISTRY[("wave31", a.split)]), run_id="w33A-" + a.split); print("claimed"); return
    if a.split == "dev":
        R.claim("wave31", "dev", [a.seed], run_id="w33A-dev", record=False)
    else:
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "w33A-" + a.split and a.seed in r.get("seeds", []) for r in spent):
            raise SystemExit("claim first")
        if a.hashseed == "0" and Path(a.out).exists():
            raise SystemExit("run once")
    t0 = time.perf_counter()
    res = run_seed(a.seed, a.hashseed)
    view = {h: {c: [{k: v for k, v in r.items() if k not in NOISY} for r in rs] for c, rs in f["configs"].items()}
            for h, f in res["folds"].items()}
    res["digest"] = digest([view, {h: f["source"]["prior_digest"] for h, f in res["folds"].items()}])
    wall = time.perf_counter() - t0
    E.ledger_append(dict(run=f"w33A-{a.split}-{a.seed}-hs{a.hashseed}", wall_s=wall, status="COMPLETE", digest=res["digest"]))
    Path(a.out).write_text(json.dumps(res, sort_keys=True, default=repr))
    print(json.dumps(dict(seed=a.seed, wall_s=round(wall, 1), digest=res["digest"])))


if __name__ == "__main__":
    main()
