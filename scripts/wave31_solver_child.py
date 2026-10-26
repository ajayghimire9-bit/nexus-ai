"""Solver child process (runs under sandbox-exec, launched only by nexus.wave31_evaluator). It speaks JSON lines
on stdin/stdout and has no file access to the repository's runs/ or artifacts/, or to the sealed vault."""
import json
import sys

from nexus import wave31_solver as S
from nexus import wave33_prior as P          # loaded at start-up for every arm (code loading is not a learning cost)
from nexus import wave31_grammar as G
from nexus import wave33_metalearner as M
from nexus import wave34_learner as L
from nexus import wave36_e1 as _E1  # noqa: F401  (loaded at start-up like every other solver module)
from nexus import wave37_cd as _CD  # noqa: F401
L.install_counter()       # deterministic op-unit counter for the learner's own accounting; identical for every arm


class Chan:
    def _ask(self, msg):
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()
        return json.loads(sys.stdin.readline())

    def check(self, evidence):
        return self._ask({"req": "check", "evidence": evidence})

    def oracle(self, x):
        return self._ask({"req": "oracle", "input": x})


def main():
    chan = Chan()
    for line in sys.stdin:
        job = json.loads(line)
        if job["cmd"] == "exit":
            break
        if job["cmd"] == "library":
            out = S.build(job["programs"], job["seed"], job.get("views", ()), job.get("max_holes", 1),
                          job.get("depth", 3), job.get("min_support", 1), job.get("cap"))
            sys.stdout.write(json.dumps({"done": True, "result": out}) + "\n")
        elif job["cmd"] == "fit_prior":
            pr = P.fit_prior(job["programs"], G.G_P, job["views"], job["alpha"], job["lam"])
            out = {"learned": pr, "placebo": P.permuted_prior(pr, job["seed"]), "uniform": P.uniform_prior(len(G.G_P))}
            if job.get("frags"):
                from nexus import wave36_search as F36
                fr = F36.fragments_from(job["programs"])
                out.update(frags=fr, frags_placebo=F36.placebo_fragments(fr, job["seed"]),
                           frags_fixed=F36.fixed_dsl_fragments())
            sys.stdout.write(json.dumps({"done": True, "result": out}) + "\n")
        elif job["cmd"] == "cd_reset":
            from nexus import wave37_cd as CD
            S.online_reset(); CD.reset(job["mode"])
            sys.stdout.write(json.dumps({"done": True}) + "\n")
        elif job["cmd"] == "cd_solve":
            from nexus import wave37_cd as CD
            ev, meter, info = CD.solve(chan, job["view"], job["seed"])
            sys.stdout.write(json.dumps({"done": True, "evidence": ev, "meter": meter, "info": info}) + "\n")
        elif job["cmd"] == "cd_update":
            from nexus import wave37_cd as CD
            out = CD.update(job["candidate"], job["view"], job["certified"], job["rec"])
            sys.stdout.write(json.dumps({"done": True, "result": out}) + "\n")
        elif job["cmd"] == "e1_reset":
            from nexus import wave36_e1 as E1
            S.online_reset(); E1.reset()
            sys.stdout.write(json.dumps({"done": True}) + "\n")
        elif job["cmd"] == "e1_solve":
            from nexus import wave36_e1 as E1
            ev, meter, info = E1.solve(chan, job["view"], job["seed"])
            sys.stdout.write(json.dumps({"done": True, "evidence": ev, "meter": meter, "info": info}) + "\n")
        elif job["cmd"] == "e1_update":
            from nexus import wave36_e1 as E1
            out = E1.update(job["candidate"], job["view"], job["certified"], job["rec"])
            sys.stdout.write(json.dumps({"done": True, "result": out}) + "\n")
        elif job["cmd"] == "l2_reset":
            S.online_reset(); L.reset(bool(job.get("placebo")))
            sys.stdout.write(json.dumps({"done": True}) + "\n")
        elif job["cmd"] == "l2_solve":
            L.validate(job["program"])
            ev, meter, info = L.solve(chan, job["view"], job["program"], job["seed"])
            sys.stdout.write(json.dumps({"done": True, "evidence": ev, "meter": meter, "info": info}) + "\n")
        elif job["cmd"] == "l2_update":
            out = L.update(job["program"], job["candidate"], job["view"], job["certified"], job["rec"])
            sys.stdout.write(json.dumps({"done": True, "result": out}) + "\n")
        elif job["cmd"] == "l_reset":
            S.online_reset(); M.reset()
            sys.stdout.write(json.dumps({"done": True}) + "\n")
        elif job["cmd"] == "l_solve":
            M.validate(job["program"])
            ev, meter, info = M.solve(chan, job["view"], job["program"], job["seed"])
            sys.stdout.write(json.dumps({"done": True, "evidence": ev, "meter": meter, "info": info}) + "\n")
        elif job["cmd"] == "l_update":
            out = M.update(job["program"], job["candidate"], job["view"], job["certified"])
            sys.stdout.write(json.dumps({"done": True, "result": out}) + "\n")
        elif job["cmd"] == "online_reset":
            S.online_reset()
            sys.stdout.write(json.dumps({"done": True}) + "\n")
        elif job["cmd"] == "online_update":
            sys.stdout.write(json.dumps({"done": True, "result": S.online_update(job["candidate"], job["genome"])}) + "\n")
        elif job["cmd"] == "solve":
            ev, meter, info = S.solve(chan, job["arm"], job["mode"], job["view"], job["library"], job["seed"],
                                     job.get("policy"))
            sys.stdout.write(json.dumps({"done": True, "evidence": ev, "meter": meter, "info": info}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
