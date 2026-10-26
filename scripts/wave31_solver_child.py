"""Solver child process (runs under sandbox-exec, launched only by nexus.wave31_evaluator). It speaks JSON lines
on stdin/stdout and has no file access to the repository's runs/ or artifacts/, or to the sealed vault."""
import json
import sys

from nexus import wave31_solver as S


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
