"""Wave 38 online-learning solver child (sandboxed; JSON lines). Holds one empty-library online learner per stream."""
import json
import sys

import w38_child as C                     # same directory: the TaskView solve loop (scope, search, probing)
from nexus import w38_online as O

LEARNER = {"l": None}


def main():
    chan = C.Chan()
    for line in sys.stdin:
        job = json.loads(line)
        if job["cmd"] == "exit":
            break
        if job["cmd"] == "o_reset":
            g = job.get("genome")
            LEARNER["l"] = (O.RegimeLearner(g) if g.get("gate") == "regime" else O.Learner(g)) if g else None
            out = {"done": True}
        elif job["cmd"] == "solve":
            l = LEARNER["l"]
            job["prior"] = (l.current_prior({"public": job["public"]}) if isinstance(l, O.RegimeLearner) else l.current_prior()) if l else None
            ev, meter, info = C.solve(chan, job)
            out = {"done": True, "evidence": ev, "meter": meter, "info": info}
        elif job["cmd"] == "o_update":
            l = LEARNER["l"]
            refit = (l.update(job["candidate"], {"public": job["public"]}) if isinstance(l, O.RegimeLearner) else l.update(job["candidate"])) if l else False
            out = {"done": True, "refit": refit, "declared": l.declared if l else 0}
        sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()


if __name__ == "__main__":
    main()
