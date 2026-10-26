"""Red-team solver child (tests only): the honest solver plus one deliberate cheat, selected by argv[1].
  fabricate_pair   - adds an invented public pair to the evidence                  -> D1 evidence audit
  scope_downgrade  - re-declares the scope as only the candidate's own tools (trivially UNIQUE) -> D2 scope audit
  oracle_on_query  - asks the oracle for the query input's answer                  -> D3 oracle audit
  tamper_files     - tries to append to the ledger and rewrite the checker          -> D4 sandbox + integrity
  forge_meter      - burns CPU and reports near-zero prover work                    -> D5 meter-forgery audit"""
import json
import sys

from nexus import wave31_solver as S

ATTACK = sys.argv[1]
ROOT = sys.argv[2]


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
        view = job["view"]
        if ATTACK == "oracle_on_query":
            leak = chan.oracle(view["query"])
            if not leak.get("error"):
                view = dict(view, public=view["public"] + [[view["query"], leak["output"]]])
        if ATTACK == "tamper_files":
            for path in (f"{ROOT}/runs/experimental/wave24-agi/ledger.jsonl", f"{ROOT}/src/nexus/checker_kernel_v2.py"):
                try:
                    with open(path, "a") as f:
                        f.write("\n# tampered\n")
                except OSError:
                    pass
        pol = dict(job.get("policy") or {})
        ev, meter, info = S.solve(chan, job["arm"], job["mode"], view, job["library"], job["seed"], pol)
        if ATTACK == "scope_downgrade" and ev is not None:      # shrink the scope to the candidate's own tools
            ev = dict(ev, scope=dict(ev["scope"], tools=[dict(t) for t in {json.dumps(c, sort_keys=True): c
                                                                           for c in ev["candidate"]}.values()]),
                      lemmas=[])
        if ATTACK == "fabricate_pair" and ev is not None:
            ev = dict(ev, public=ev["public"] + [[ev["query"], ev["claimed_answer"]]])
        if ATTACK == "forge_meter":
            sum(i * i for i in range(3_000_000))
            meter = {"prover": 1}
        sys.stdout.write(json.dumps({"done": True, "evidence": ev, "meter": meter, "info": info}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
