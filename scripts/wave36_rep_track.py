"""Wave 36 representation / mechanism track (NOT LOCKED): R1 (Stitch-style fragment abstraction, documented adaptation)
against the four controls, on the increment-3 LODO suite (familiar_exact / compositional / held_out per held-out domain),
under Checker v3 (pinned), the sandbox and the OS meter. Every arm: the same generic engineering (lazy best-first engine,
exact observational dedup, Checker v3 shared evaluation); learned items are charged in full (prior fit + fragment
extraction = marginal learning cost, measured in the child).
Configs:
  Fresh-v3     (a) generic only: eager BFS, no history
  FixedDSL     (a)+(d) richer fixed DSL without learning: uniform costs + all 36 core-op bigram fragments
  MilestoneA   (b) useful history: learned prior + tool knowledge (the frozen online baseline's mechanism)
  R1           (b)+(d) useful history: learned prior + learned compression-ranked fragments
  R1-Placebo   (b-permuted) size-matched permuted history: permuted prior + permuted fragments"""
import argparse, hashlib, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DEPTH, ALPHA, LAM = 4, 1.0, 0.8
NOISY = ("ext", "solver_reported")


def digest(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def run_seed(seed, hashseed="0"):
    from nexus import wave31_evaluator as E
    from nexus import wave31_tasks as T
    ev = E.Evaluator(depth=DEPTH, checker=3)
    out = dict(seed=seed, folds={})
    for h in ("records", "strings", "grids", "graphs"):
        src = T.source_stream3(seed, h)
        ch = E.Child(hashseed)
        progs, views, srcw = [], [], 0
        for i, t in enumerate(src):
            r = ev.solve(ch, t, "Fresh", "matched", [], f"{seed}:{h}:src{i}", {"matched_depth": DEPTH, "checker": 3})
            srcw += r["ext"]["evaluator_work"]
            if r["label"] == "exhaustive_UNIQUE":
                progs.append(r["candidate"]); views.append({"public": t["public"], "query": t["query"]})
        c0 = E.instructions(ch.p.pid)
        ch.send({"cmd": "fit_prior", "programs": progs, "views": views, "alpha": ALPHA, "lam": LAM, "seed": f"{seed}:{h}",
                 "frags": True})
        k = ch.recv()["result"]
        fit = E.instructions(ch.p.pid) - c0
        ch.close()
        configs = {"Fresh-v3": {}, "FixedDSL": {"search": "frag_best_first", "prior": k["uniform"], "frags": k["frags_fixed"]},
                   "MilestoneA": {"search": "best_first", "prior": k["learned"]},
                   "R1": {"search": "frag_best_first", "prior": k["learned"], "frags": k["frags"]},
                   "R1-Placebo": {"search": "frag_best_first", "prior": k["placebo"], "frags": k["frags_placebo"]}}
        tgt = T.target_stream3(seed, h)
        f = dict(source_work=srcw, fit_instr=fit, n_frags=len(k["frags"]), configs={})
        for name, pol in configs.items():
            ch = E.Child(hashseed)
            f["configs"][name] = [ev.solve(ch, t, "Fresh", "matched", [], f"{seed}:{h}:{j}", dict(pol, matched_depth=DEPTH, checker=3))
                                  for j, t in enumerate(tgt)]
            ch.close()
        out["folds"][h] = f
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int); ap.add_argument("--split", default="dev")
    ap.add_argument("--hashseed", default="0"); ap.add_argument("--out")
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    if a.split == "dev":
        R.claim("wave31", "dev", [a.seed], run_id="w36-rep-dev", record=False)
    else:
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "w36-" + a.split and a.seed in r.get("seeds", []) for r in spent):
            raise SystemExit("claim first")
        if a.hashseed == "0" and Path(a.out).exists():
            raise SystemExit("run once")
    t0 = time.perf_counter()
    res = run_seed(a.seed, a.hashseed)
    res["digest"] = digest({h: {c: [{k: v for k, v in r.items() if k not in NOISY} for r in rs] for c, rs in f["configs"].items()}
                            for h, f in res["folds"].items()})
    E.ledger_append(dict(run=f"w36-rep-{a.split}-{a.seed}-hs{a.hashseed}", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    Path(a.out).write_text(json.dumps(res, sort_keys=True, default=repr))
    print(json.dumps(dict(seed=a.seed, wall_s=round(time.perf_counter() - t0, 1), digest=res["digest"])))


if __name__ == "__main__":
    main()
