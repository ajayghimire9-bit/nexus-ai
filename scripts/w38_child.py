"""Wave 38 sandboxed solver child (launched under sandbox-exec by nexus.w38_eval; JSON lines). Sees TaskViews only; reaches
Checker v4 and the oracle only through the evaluator."""
import json
import random
import sys

from nexus import w38_learn as K
from nexus import w38_lang as L
from nexus import w38_scope as S
from nexus import w38_search as Q


class Chan:
    def ask(self, m):
        sys.stdout.write(json.dumps(m) + "\n"); sys.stdout.flush()
        return json.loads(sys.stdin.readline())


def solve(chan, job):
    pub = [list(p) for p in job["public"]]
    q, depth = job["query"], job["depth"]
    sc = S.scope(job["public"], q, depth)                   # declared scope: computed from the ORIGINAL public pairs
    if job.get("neural"):
        cm, _ = K.neural_cost_matrix(job["neural"], sc["tools"])
    else:
        cm = K.cost_matrix(job.get("prior"), sc["tools"])
    rng = random.Random(f"w38-probe:{job['seed']}")
    meter, probes, ev = {}, 0, None
    while True:
        cand = Q.search(pub, q, sc["tools"], depth, cm, budget=job.get("budget", 300000), meter=meter)
        if cand is None:
            return None, meter, {"probes": probes, "status": "no_candidate"}
        ev = {"checker_version": 4, "public": pub, "query": q, "claimed_answer": L.run(cand, q), "candidate": cand, "scope": sc}
        v = chan.ask({"req": "check", "evidence": ev})
        if v["label"] != "AMBIGUOUS" or probes >= 3:
            return ev, meter, {"probes": probes, "status": v["label"]}
        x = Q.design_probe(pub, q, sc["tools"], v, rng)
        if x is None:
            return ev, meter, {"probes": probes, "status": "ambiguous_no_probe"}
        y = chan.ask({"req": "oracle", "input": x})
        probes += 1
        if y.get("error"):
            return ev, meter, {"probes": probes, "status": "probe_error"}
        pub = pub + [[x, y["output"]]]


def main():
    chan = Chan()
    for line in sys.stdin:
        job = json.loads(line)
        if job["cmd"] == "exit":
            break
        if job["cmd"] == "solve":
            ev, meter, info = solve(chan, job)
            out = {"done": True, "evidence": ev, "meter": meter, "info": info}
        elif job["cmd"] == "fit":
            progs = job["programs"]
            if job["kind"] == "repr":
                pr = K.fit_repr(progs, job.get("alpha", 1.0))
            else:
                pr = K.fit(progs, job.get("alpha", 1.0), job.get("lam", 0.8), job.get("weights"))
                if job["kind"] == "placebo":
                    pr = K.placebo(pr, job["seed"])
            out = {"done": True, "prior": pr}
        elif job["cmd"] == "train_ranker":
            sd, cnt = K.train_ranker(job["programs"], seed=job.get("seed", 0))
            out = {"done": True, "sd": sd, "counters": cnt}
        sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()


if __name__ == "__main__":
    main()
