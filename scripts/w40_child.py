"""Wave 40 sandboxed solver child (v5 language / scope, REPAIRED search w40_search, Wave 40 cost matrices; Checker v5 and the
oracle only through the evaluator). Same loop as w39_child plus:
  * `tick` messages after the search and after the witness search, so the evaluator meters search work and certification
    work separately on the child's own instruction counter;
  * optional sound ambiguity short-circuit (job["witness"]): after a candidate is found, continue in the SAME prior order for a
    fitting chain with a different query answer (w40_search.disagreeing_witness). The checker is still called (the evaluator
    decides which accounting a row uses, and verifies that every witness-found task gets the kernel label AMBIGUOUS)."""
import json
import random
import sys

from nexus import w38_learn as K
from nexus import w39_lang as L
from nexus import w39_scope as S
from nexus import w40_learn as W
from nexus import w40_search as Q


class Chan:
    def ask(self, m):
        sys.stdout.write(json.dumps(m) + "\n"); sys.stdout.flush()
        return json.loads(sys.stdin.readline())


def rows_computed(cm):
    c = cm["cost"]
    return sum(len(r) for r in c.rows if r is not None) if isinstance(c, K.Lazy) else 0


def solve(chan, job):
    pub = [list(p) for p in job["public"]]
    q, depth = job["query"], job["depth"]
    sc = S.scope(job["public"], q, depth)
    cm = W.cost_matrix_fast(job.get("prior"), sc["tools"])
    rng = random.Random(f"w38-probe:{job['seed']}")
    meter, probes, ev = {}, 0, None
    while True:
        e0 = meter.get("execs", 0)
        cand = Q.search(pub, q, sc["tools"], depth, cm, budget=job.get("budget", 300000), meter=meter)
        meter.setdefault("iters", []).append([meter["execs"] - e0, cand is not None])
        meter["row_entries"] = rows_computed(cm)
        chan.ask({"req": "tick", "what": "search"})
        if cand is None:
            return None, meter, {"probes": probes, "status": "no_candidate"}
        claimed = L.run(cand, q)
        if job.get("witness") and probes == 0:
            wm = {}
            w = Q.disagreeing_witness(pub, q, sc["tools"], depth, cm, claimed, budget=job.get("witness_budget", 10**7), meter=wm)
            meter["witness"] = dict(found=w is not None, execs=wm.get("execs", 0), chain=w)
            meter["row_entries"] = rows_computed(cm)
            chan.ask({"req": "tick", "what": "witness"})
        ev = {"checker_version": 5, "public": pub, "query": q, "claimed_answer": claimed, "candidate": cand, "scope": sc,
              "extra_queries": job.get("extra") or []}
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
            elif job["kind"] == "fixed_repr":
                pr = {"kind": "fixed_repr", "repr": K.fit_repr(progs, job.get("alpha", 1.0))}
            else:
                pr = K.fit(progs, job.get("alpha", 1.0), job.get("lam", 0.8), job.get("weights"))
                if job["kind"] == "placebo":
                    pr = K.placebo(pr, job["seed"])
            out = {"done": True, "prior": pr}
        sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()


if __name__ == "__main__":
    main()
