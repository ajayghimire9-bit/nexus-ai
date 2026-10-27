"""Wave 31 under Checker v3 (NOT LOCKED): the owner's 4-way comparison on the increment-3 suite (depth-4 matched G_P scope,
3-op cores, LODO over 4 domains). Every arm in one comparison is graded by the same pinned checker, and all costs are on the
OS retired-instruction meter (`evaluator_work`: sandboxed-child instructions + evaluator checker instructions + priced
oracle calls).
Configs: Fresh-v2 (all v2 lemmas; the increment-3 Fresh-L baseline), Fresh-v3 (no proofs), Fresh-v3-allP (every axiom;
generic, non-learned), Experienced-v3 (learned macros + source-learned axiom selection), Placebo-v3 (size-matched macros
+ the same number of randomly chosen axioms).
Source learning (charged to Experienced and Placebo): Fresh, depth 4, under v3; source task i cites only axiom i mod 4,
and the per-axiom application rate comes from the checker's verdicts."""
import argparse, hashlib, json, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DEPTH = 4
CONFIGS = {"Fresh-v2": ("Fresh", 2, {"lemmas": "all"}), "Fresh-v3": ("Fresh", 3, {"proofs": "none"}),
           "Fresh-v3-allP": ("Fresh", 3, {"proofs": "all"}), "Experienced-v3": ("Useful", 3, {"proofs": "learned"}),
           "Placebo-v3": ("Placebo", 3, {"proofs": "placebo"})}
NOISY = ("ext", "solver_reported")


def digest(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def run_seed(seed, hashseed, folds):
    from nexus import wave31_evaluator as E
    from nexus import wave31_tasks as T
    evs = {2: E.Evaluator(depth=DEPTH, checker=2), 3: E.Evaluator(depth=DEPTH, checker=3)}
    out = dict(seed=seed, pins={2: evs[2].pin, 3: evs[3].pin}, folds={})
    for h in folds:
        f = {}
        src = T.source_stream3(seed, h)
        ch = E.Child(hashseed)
        rows, progs = [], []
        for i, t in enumerate(src):
            r = evs[3].solve(ch, t, "Fresh", "matched", [], f"{seed}:{h}:src{i}",
                             {"matched_depth": DEPTH, "checker": 3, "proofs": f"rotate:{i}"})
            rows.append(r)
            if r["label"] == "exhaustive_UNIQUE":
                progs.append(r["candidate"])
        c0 = E.instructions(ch.p.pid)
        lib = evs[3].library(ch, progs, f"{seed}:{h}", (), max_holes=1, depth=DEPTH)
        build = E.instructions(ch.p.pid) - c0
        ch.close()
        f["source"] = dict(n=len(src), certified=len(progs), wrong=sum(r["wrong"] is not None for r in rows),
                           labels=dict(Counter(r["label"] for r in rows)),
                           evaluator_work=sum(r["ext"]["evaluator_work"] for r in rows) + build)
        f["library"] = dict(useful=len(lib["useful"]), placebo=len(lib["placebo"]), learned_axioms=lib["learned_axioms"],
                            placebo_axioms=lib["placebo_axioms"], axiom_stats=lib["axiom_stats"],
                            digest=digest([lib["useful"], lib["placebo"], lib["learned_axioms"], lib["placebo_axioms"]]))
        tgt = T.target_stream3(seed, h)
        f["configs"] = {}
        for name, (arm, ck, pol) in CONFIGS.items():
            L = lib["useful"] if arm == "Useful" else lib["placebo"] if arm == "Placebo" else []
            axs = lib["learned_axioms"] if arm == "Useful" else lib["placebo_axioms"]
            p = dict(pol, matched_depth=DEPTH, checker=ck, proof_axioms=axs)
            ch = E.Child(hashseed)
            f["configs"][name] = [evs[ck].solve(ch, t, arm, "matched", L, f"{seed}:{h}:{k}", p) for k, t in enumerate(tgt)]
            ch.close()
        out["folds"][h] = f
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int); ap.add_argument("--split", default="dev"); ap.add_argument("--hashseed", default="0")
    ap.add_argument("--folds", default="records,strings,grids,graphs"); ap.add_argument("--out")
    ap.add_argument("--claim-only", action="store_true")
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    if a.claim_only:
        R.claim("wave31", a.split, list(R.REGISTRY[("wave31", a.split)]), run_id="wave31v3-" + a.split)
        print("claimed", a.split); return
    if a.split == "dev":
        R.claim("wave31", "dev", [a.seed], run_id="wave31v3-dev", record=False)
    else:
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "wave31v3-" + a.split and a.seed in r.get("seeds", []) for r in spent):
            raise SystemExit("one-use split must be claimed first")
        if a.hashseed == "0" and Path(a.out).exists():
            raise SystemExit("one-use split: run once")
    t0 = time.perf_counter()
    res = run_seed(a.seed, a.hashseed, a.folds.split(","))
    wall = time.perf_counter() - t0
    view = {h: {c: [{k: v for k, v in r.items() if k not in NOISY} for r in rs] for c, rs in f["configs"].items()}
            for h, f in res["folds"].items()}
    res["digest"] = digest([view, {h: f["library"]["digest"] for h, f in res["folds"].items()}])
    E.ledger_append(dict(run=f"wave31v3-{a.split}-{a.seed}-hs{a.hashseed}", wall_s=wall, status="COMPLETE", digest=res["digest"]))
    Path(a.out).write_text(json.dumps(res, default=repr, sort_keys=True))
    print(json.dumps(dict(seed=a.seed, wall_s=round(wall, 1), digest=res["digest"])))


if __name__ == "__main__":
    main()
