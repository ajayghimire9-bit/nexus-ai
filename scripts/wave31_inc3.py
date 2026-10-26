"""Wave 31 increment 3 (NOT LOCKED): depth-4 matched scope + checker-verified pruning proofs, via the evaluator boundary
with the external meter (retired instructions; never solver-reported numbers).
Per fold (held-out domain h): source = 3-op cores on the other 3 domains, solved as Fresh/matched depth 4 with all
v2 lemmas; the child records which lemma kinds fired; the evaluator returns certified candidates and the source
views; the child builds Useful / Placebo libraries, learned lemma kinds and (projection only) learned identities.
Configs (all matched, depth 4, exhaustive_UNIQUE strength):
  Fresh-noL (no proofs), Fresh-L (all v2-verifiable lemmas: a generic, non-learned strong baseline),
  Useful-L (macros + all lemmas), Useful-learnedL (macros + only source-learned lemma kinds), Placebo-L."""
import argparse, hashlib, json, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CONFIGS = {"Fresh-noL": ("Fresh", {"lemmas": "none"}), "Fresh-L": ("Fresh", {"lemmas": "all"}),
           "Useful-L": ("Useful", {"lemmas": "all"}), "Useful-learnedL": ("Useful", {"lemmas": "learned"}),
           "Placebo-L": ("Placebo", {"lemmas": "all"})}
DEPTH = 4
NOISY = ("ext", "solver_reported")


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def run_seed(seed, hashseed, folds):
    from nexus import wave31_evaluator as E
    from nexus import wave31_tasks as T
    from nexus import wave31_grammar as G
    ev = E.Evaluator(depth=DEPTH)
    out = dict(seed=seed, checker_v2=ev.pin, folds={})
    for h in folds:
        f = {}
        src = T.source_stream3(seed, h)
        ch = E.Child(hashseed)
        rows, progs, views = [], [], []
        for i, t in enumerate(src):
            r = ev.solve(ch, t, "Fresh", "matched", [], f"{seed}:{h}:src{i}",
                         {"matched_depth": DEPTH, "lemmas": "all", "record_lemmas": True})
            rows.append(r)
            if r["label"] == "exhaustive_UNIQUE":
                progs.append(r["candidate"]); views.append({"public": t["public"], "query": t["query"]})
        c0 = E.instructions(ch.p.pid)
        lib = ev.library(ch, progs, f"{seed}:{h}", views, max_holes=1, depth=DEPTH)
        build_instr = E.instructions(ch.p.pid) - c0
        ch.close()
        f["source"] = dict(n=len(src), certified=len(progs), labels=dict(Counter(r["label"] for r in rows)),
                           wrong=sum(r["wrong"] is not None for r in rows),
                           kernel=sum(r["kernel"] for r in rows),
                           evaluator_work=sum(r["ext"]["evaluator_work"] for r in rows) + build_instr,
                           oracle_calls=sum(r["oracle_calls"] for r in rows))
        f["library"] = dict(useful=len(lib["useful"]), placebo=len(lib["placebo"]), skeletons=lib["skeletons"],
                            lemma_kinds=lib["lemma_kinds"], identities=len(lib["identities"]),
                            identity_list=[[a["op"], b["op"], [s["op"] for s in sh]] for a, b, sh in lib["identities"]],
                            projected_skip=lib["projected_skip"], digest=digest([lib["useful"], lib["placebo"]]))
        tgt = T.target_stream3(seed, h)
        f["configs"] = {}
        for name, (arm, pol) in CONFIGS.items():
            L = lib["useful"] if arm == "Useful" else lib["placebo"] if arm == "Placebo" else []
            pol = dict(pol, matched_depth=DEPTH, lemma_kinds=lib["lemma_kinds"])
            ch = E.Child(hashseed)
            rs = [ev.solve(ch, t, arm, "matched", L, f"{seed}:{h}:{k}", pol) for k, t in enumerate(tgt)]
            ch.close()
            f["configs"][name] = rs
        # soundness spot-check of the learned identities on this fold's TARGET public inputs (evaluator side)
        bad = 0
        for a, b, sh in lib["identities"]:
            for t in tgt:
                for x, _ in t["public"]:
                    y = V_run_leaf(t["domain"], x)
                    if y is None:
                        continue
                    from nexus import checker_kernel_v2 as V
                    y1, y2 = V.run([a, b], y)[0], (y if not sh else V.run(sh, y)[0])
                    if V.ERROR not in (y1, y2) and V.key(y1) != V.key(y2):
                        bad += 1
                        break
                else:
                    continue
                break
        f["identities_violated_on_target"] = bad
        out["folds"][h] = f
    return out


def V_run_leaf(domain, x):
    from nexus import checker_kernel_v2 as V
    from nexus import wave31_grammar as G
    y, _ = V.run(G.LEAF[domain], x)
    return None if y == V.ERROR else y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int); ap.add_argument("--split", default="dev")
    ap.add_argument("--hashseed", default="0"); ap.add_argument("--folds", default="records,strings,grids,graphs")
    ap.add_argument("--out"); ap.add_argument("--claim-only", action="store_true")
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    if a.claim_only:
        R.claim("wave31", a.split, list(R.REGISTRY[("wave31", a.split)]), run_id="wave31c-" + a.split)
        print("claimed", a.split); return
    if a.split == "dev":
        R.claim("wave31", "dev", [a.seed], run_id="wave31c-dev", record=False)
    else:
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "wave31c-" + a.split and a.seed in r.get("seeds", []) for r in spent):
            raise SystemExit("one-use split must be claimed first (--claim-only)")
        if a.hashseed == "0" and Path(a.out).exists():
            raise SystemExit("one-use split: artifact exists; run once")
    t0 = time.perf_counter()
    res = run_seed(a.seed, a.hashseed, a.folds.split(","))
    wall = time.perf_counter() - t0
    view = {h: {c: [{k: v for k, v in r.items() if k not in NOISY} for r in rs] for c, rs in f["configs"].items()}
            for h, f in res["folds"].items()}
    res["digest"] = digest([view, {h: f["library"]["digest"] for h, f in res["folds"].items()}])
    E.ledger_append(dict(run=f"wave31c-{a.split}-{a.seed}-hs{a.hashseed}", wall_s=wall, status="COMPLETE", digest=res["digest"]))
    Path(a.out).write_text(json.dumps(res, default=repr, sort_keys=True))
    print(json.dumps(dict(seed=a.seed, wall_s=round(wall, 1), digest=res["digest"])))


if __name__ == "__main__":
    main()
