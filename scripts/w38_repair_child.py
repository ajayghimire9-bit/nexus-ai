"""Sandboxed repair processes (launched under sandbox-exec by the evaluator; JSON lines on stdin/stdout).
mode "search": receives buggy source + PUBLIC tests + a mutation-kind prior; returns the first patch passing every public test
                (and the number of candidate evaluations). It never sees held-out tests.
mode "oracle": receives a patch + held-out tests; returns pass counts. Candidates run with restricted builtins and a per-call
               time limit (setitimer)."""
import json
import signal
import sys

from nexus import w38_repair as RP

SAFE = {"max": max, "min": min, "len": len, "range": range, "abs": abs, "None": None}


class TO(Exception):
    pass


def _alarm(*_):
    raise TO()


def run_tests(src, tests):
    signal.signal(signal.SIGALRM, _alarm)
    ns = {"__builtins__": SAFE}
    try:
        exec(compile(src, "cand", "exec"), ns)
    except Exception:
        return 0
    ok = 0
    for x, y in tests:
        signal.setitimer(signal.ITIMER_REAL, 0.05)
        try:
            out = ns["f"](list(x))
            ok += (out == y) if y != "<EXC>" else 0
        except TO:
            pass
        except Exception:
            ok += y == "<EXC>"
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    return ok


def main():
    for line in sys.stdin:
        job = json.loads(line)
        if job["cmd"] == "exit":
            break
        if job["cmd"] == "search":
            evals, found = 0, None
            for muts in RP.candidates(job["buggy"], job["prior"], job.get("max_edits", 2)):
                evals += 1
                if evals > job["max_evals"]:
                    break
                try:
                    src = RP._apply(job["buggy"], muts)
                except Exception:
                    continue
                if run_tests(src, job["public"]) == len(job["public"]):
                    found = dict(patch=src, kinds=[m[0] for m in muts])
                    break
            out = {"done": True, "found": found, "evals": evals}
        else:
            out = {"done": True, "passed": run_tests(job["patch"], job["tests"]), "n": len(job["tests"])}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
