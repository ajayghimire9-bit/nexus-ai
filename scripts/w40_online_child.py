"""Wave 40 online-learning solver child (sandboxed; JSON lines): one empty-library online learner per stream, v5 language,
repaired search. Learners: none (Fresh), no-gate (w38 Learner), regime (w38 RegimeLearner = hard-gated), hier (w39
HierLearner), hier-payoff (w40 PayoffGated(HierLearner))."""
import json
import sys

import w40_child as C                     # same directory: the TaskView solve loop
from nexus import w38_online as O
from nexus import w39_online as H
from nexus import w40_online as P

LEARNER = {"l": None}


def _prior(l, view):
    if l is None:
        return None
    if isinstance(l, P.PayoffGated):
        return l.current_prior(view)
    return l.current_prior(view) if isinstance(l, O.RegimeLearner) else l.current_prior()


def main():
    chan = C.Chan()
    for line in sys.stdin:
        job = json.loads(line)
        if job["cmd"] == "exit":
            break
        if job["cmd"] == "o_reset":
            g = job.get("genome")
            if not g:
                LEARNER["l"] = None
            elif g.get("gate") in ("hier", "hier-payoff"):
                l = H.HierLearner(dict(g, gate="regime"), job.get("shrink", 4.0))
                LEARNER["l"] = P.PayoffGated(l) if g["gate"] == "hier-payoff" else l
            elif g.get("gate") == "regime":
                LEARNER["l"] = O.RegimeLearner(g)
            else:
                LEARNER["l"] = O.Learner(g)
            out = {"done": True}
        elif job["cmd"] == "solve":
            l = LEARNER["l"]
            job["prior"] = _prior(l, {"public": job["public"]})
            ev, meter, info = C.solve(chan, job)
            if isinstance(l, P.PayoffGated):
                l.observe(meter.get("execs", 0), meter.get("row_entries", 0))
                meter["gate"] = dict(used=l.used, off=l.off, net=l.net())
            out = {"done": True, "evidence": ev, "meter": meter, "info": info}
        elif job["cmd"] == "o_update":
            l = LEARNER["l"]
            view = {"public": job["public"]}
            if l is None:
                refit = False
            elif isinstance(l, (P.PayoffGated, O.RegimeLearner)):
                refit = l.update(job["candidate"], view)
            else:
                refit = l.update(job["candidate"])
            out = {"done": True, "refit": refit, "declared": l.declared if l else 0,
                   "gate_log": l.log if isinstance(l, P.PayoffGated) else None}
        sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()


if __name__ == "__main__":
    main()
