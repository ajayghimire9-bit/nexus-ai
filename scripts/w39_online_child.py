"""Wave 39 online-learning solver child (sandboxed; JSON lines): one empty-library online learner per stream, v5 language."""
import json
import sys

import w39_child as C                     # same directory: the TaskView solve loop (v5 scope, search, probing)
from nexus import w38_online as O
from nexus import w39_online as H

LEARNER = {"l": None}


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
            elif g.get("gate") == "hier":
                LEARNER["l"] = H.HierLearner(dict(g, gate="regime"), job.get("shrink", 4.0))
            elif g.get("gate") == "regime":
                LEARNER["l"] = O.RegimeLearner(g)
            else:
                LEARNER["l"] = O.Learner(g)
            out = {"done": True}
        elif job["cmd"] == "solve":
            l = LEARNER["l"]
            view = {"public": job["public"]}
            job["prior"] = (l.current_prior(view) if isinstance(l, O.RegimeLearner) else l.current_prior()) if l else None
            ev, meter, info = C.solve(chan, job)
            out = {"done": True, "evidence": ev, "meter": meter, "info": info}
        elif job["cmd"] == "o_update":
            l = LEARNER["l"]
            view = {"public": job["public"]}
            refit = (l.update(job["candidate"], view) if isinstance(l, O.RegimeLearner) else l.update(job["candidate"])) if l else False
            out = {"done": True, "refit": refit, "declared": l.declared if l else 0}
        sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()


if __name__ == "__main__":
    main()
