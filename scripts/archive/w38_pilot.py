"""Wave 38 Stage 1 pilot (NOT LOCKED): per-domain timing / memory / semantics. For each program-domain task: is the teacher
in the declared scope; prover proposal (uniform lazy best-first over the scope, own interpreter); Checker v4 verdict and its
instructions / wall / RSS. Development data only."""
import json, os, resource, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    from nexus import w38_domains as D, w38_scope as S, w38_lang as L, w38_search as Q, checker_kernel_v4 as V4
    from nexus.wave31_evaluator import instructions, ledger_append
    pid = os.getpid(); t0 = time.perf_counter()
    rows = []
    for t in D.stream("pilot", n_per=int(sys.argv[1]) if len(sys.argv) > 1 else 1):
        depth = len(t["teacher"])
        sc = S.scope(t["public"], t["query"], depth)
        keys = {L.key(x) for x in sc["tools"]}
        inscope = all(L.key(x) in keys for x in t["teacher"])
        i0, w0 = instructions(pid), time.perf_counter()
        cand = Q.search(t["public"], t["query"], sc["tools"], depth, Q.uniform(len(sc["tools"])), budget=200000)
        i1, w1 = instructions(pid), time.perf_counter()
        v = {"label": "NO_CANDIDATE"}
        if cand is not None:
            ans = L.run(cand, t["query"])
            v = V4.check({"checker_version": 4, "public": t["public"], "query": t["query"], "claimed_answer": ans,
                          "candidate": cand, "scope": sc})
            correct = v["label"] == "exhaustive_UNIQUE" and L.key(ans) == L.key(t["answer"])
        else:
            correct = False
        i2, w2 = instructions(pid), time.perf_counter()
        rows.append(dict(domain=t["domain"], mech=t["mechanism"], depth=depth, tools=len(sc["tools"]), inscope=inscope,
                         label=v["label"], reason=v.get("reason"), k=v.get("k"), correct=correct,
                         prover_G=(i1 - i0) / 1e9, prover_s=w1 - w0, checker_G=(i2 - i1) / 1e9, checker_s=w2 - w1,
                         nodes=v.get("nodes"), edges=v.get("edge_evals")))
        r = rows[-1]
        print(f"{r['domain']:8s} {r['mech']:18s} d{depth} T{r['tools']} in{int(inscope)} {r['label'][:12]:12s} ok{int(correct)} "
              f"prover {r['prover_s']:.2f}s checker {r['checker_s']:.2f}s nodes {r['nodes']}", flush=True)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
    Path(ROOT / "artifacts/w38_pilot_programs.json").write_text(json.dumps(dict(rows=rows, peak_rss_mib=rss), sort_keys=True))
    ledger_append(dict(run="w38-pilot-programs", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    print("peak RSS MiB %.0f wall %.0fs" % (rss, time.perf_counter() - t0))


if __name__ == "__main__":
    main()
