"""Wave 31 independent evaluator / meter boundary (development, NOT LOCKED; a prerequisite for Wave 32).

The evaluator process owns the tasks (teachers, answers, category labels), Checker v2, the oracle, the meters and
the ledger. Solver code runs in a separate child process:
  * Launched under macOS `sandbox-exec`, with a profile that denies writes to the repository (so it cannot touch
    runs/, artifacts/ or the ledger), denies reads of the sealed vault, and denies network access. The child gets
    a clean environment and no file paths.
  * It sees TaskViews only (public pairs + query). It reaches the checker and the oracle only through request
    lines on its stdout, which the evaluator serves and meters.
Meters the solver cannot alter:
  * kernel work (steps + chains, summed over every check request, computed in the evaluator process);
  * oracle calls;
  * the child's CPU seconds (os.wait4 rusage of the child pid) and its wall-clock time.
The solver's own prover counts are kept but marked `solver_reported`. They are audited by a fresh-process replay
(identical digest required), and the unforgeable CPU seconds are reported next to them.
Evidence audit: the final evidence's public pairs must be the original passive pairs plus exactly the pairs the
oracle answered for this task. Anything else is INVALID_EVIDENCE.
Labels come from the evaluator's own Checker v2 call on the final evidence, then the reporting rule
(wave31_grammar.report_label). Only the evaluator appends to the ledger, with a sha256 hash chain.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from nexus import checker_kernel_v2 as V
from nexus import wave31_grammar as G

ROOT = Path(__file__).resolve().parents[2]
V2_PIN_COMMIT = "01d84f6"
LEDGER = ROOT / "runs/experimental/wave24-agi/ledger.jsonl"
VAULT = os.environ.get("NEXUS_SEALED_VAULT_DIR", str(Path.home() / ".gemini/antigravity/sealed_nexus_vault"))


def verify_v2():
    pin = subprocess.run(["git", "-C", str(ROOT), "show", f"{V2_PIN_COMMIT}:src/nexus/checker_kernel_v2.sha256"],
                         capture_output=True, text=True, check=True).stdout.split()[0]
    disk = hashlib.sha256((ROOT / "src/nexus/checker_kernel_v2.py").read_bytes()).hexdigest()
    if disk != pin or Path(V.__file__).resolve() != (ROOT / "src/nexus/checker_kernel_v2.py").resolve():
        raise SystemExit("checker v2 does not match its pin; refusing to run")
    return pin


def sandbox_profile():
    return ("(version 1)(allow default)"
            f'(deny file-write* (subpath "{ROOT}"))'
            f'(deny file-read* (subpath "{Path(VAULT).resolve()}"))'
            "(deny network*)")


def ledger_append(row):
    """Hash-chained append; only the evaluator calls this."""
    prev = ""
    if LEDGER.exists():
        lines = LEDGER.read_text().splitlines()
        prev = hashlib.sha256(lines[-1].encode()).hexdigest() if lines else ""
    row = dict(row, prev_sha256=prev)
    with open(LEDGER, "a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


class Child:
    def __init__(self, hashseed="0"):
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "src"), "PYTHONHASHSEED": str(hashseed),
               "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/var/empty"}
        self.t0 = time.perf_counter()
        self.p = subprocess.Popen(["/usr/bin/sandbox-exec", "-p", sandbox_profile(), sys.executable, "-B",
                                   str(ROOT / "scripts/wave31_solver_child.py")], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, env=env, cwd="/")
        self.cpu_s = self.wall_s = None

    def send(self, msg):
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def recv(self):
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError("solver child exited")
        return json.loads(line)

    def close(self):
        try:
            self.send({"cmd": "exit"})
            self.p.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        _pid, status, ru = os.wait4(self.p.pid, 0)
        self.p.returncode = os.waitstatus_to_exitcode(status)
        self.cpu_s = ru.ru_utime + ru.ru_stime
        self.wall_s = time.perf_counter() - self.t0
        return self.cpu_s


class Evaluator:
    def __init__(self):
        self.pin = verify_v2()
        self.kernel_work = 0
        self.oracle_calls = 0

    def _serve(self, child, task, meter):
        """Serve requests until the child's `done` line. `task` (evaluator-side) is used only for the oracle."""
        while True:
            msg = child.recv()
            if msg.get("done"):
                return msg
            if msg.get("req") == "check":
                v = V.check(msg["evidence"])
                w = v.get("steps", 0) + v.get("chains_checked", 0)
                meter["kernel"] = meter.get("kernel", 0) + w
                self.kernel_work += w
                child.send(v)
            elif msg.get("req") == "oracle":
                meter["oracle_calls"] = meter.get("oracle_calls", 0) + 1
                self.oracle_calls += 1
                x = msg["input"]
                try:
                    V.check_value(x)
                    y = V.run(task["teacher"], x)[0] if task else V.ERROR
                except Exception:
                    y = V.ERROR
                if y == V.ERROR:
                    child.send({"error": True})
                else:
                    task.setdefault("_oracle_log", []).append([x, y])
                    child.send({"output": y})
            else:
                raise RuntimeError("protocol violation")

    def library(self, child, programs, seed):
        """Source-only feedback: the child receives the candidates of source tasks that the evaluator's own checker
        labelled exhaustive_UNIQUE (labels only; no answers or correctness) and builds both libraries."""
        child.send({"cmd": "library", "programs": programs, "seed": seed})
        return child.recv()["result"]

    def solve(self, child, task, arm, mode, library, seed):
        meter = {}
        task.pop("_oracle_log", None)
        child.send({"cmd": "solve", "arm": arm, "mode": mode, "view": {"public": task["public"], "query": task["query"]},
                    "library": library, "seed": seed})
        msg = self._serve(child, task, meter)
        return self.grade(task, msg, meter)

    def grade(self, task, msg, meter):
        ev, info = msg["evidence"], msg["info"]
        row = dict(category=task["category"], domain=task["domain"], core=task["core"], probes=info["probes"],
                   fallback=info["fallback"], checks=info["checks"], solver_status=info["status"],
                   solver_reported=msg["meter"], kernel=meter.get("kernel", 0),
                   oracle_calls=meter.get("oracle_calls", 0))
        if ev is None:
            return dict(row, label="ABSTAIN", reason="no_program_in_scope", correct=False, wrong=None)
        allowed = {V.key(p) for p in task["public"]} | {V.key(p) for p in task.get("_oracle_log", [])}
        got = [V.key(p) for p in ev["public"]]
        if not set(V.key(p) for p in task["public"]) <= set(got) or not set(got) <= allowed or \
                V.key(ev["query"]) != V.key(task["query"]):
            return dict(row, label="INVALID_EVIDENCE", correct=False, wrong=None)
        v = V.check(ev)
        w = v.get("steps", 0) + v.get("chains_checked", 0)
        row["kernel"] += w
        self.kernel_work += w
        lab = G.report_label(v, ev["scope"])
        uniq = lab.endswith("UNIQUE")
        correct = uniq and V.key(ev["claimed_answer"]) == V.key(task["answer"])
        tk = [V.key(s) for s in task["teacher"]]
        scope_keys = {V.key(t) for t in ev["scope"]["tools"]}
        inside = len(tk) <= ev["scope"]["max_depth"] and set(tk) <= scope_keys
        return dict(row, label=lab, kernel_label=v["label"], reason=v.get("reason"), k=v.get("k"), correct=correct,
                    answer_digest=hashlib.sha256(json.dumps(ev["claimed_answer"]).encode()).hexdigest()[:12],
                    candidate=ev["candidate"],
                    wrong=(None if not uniq or correct else
                           "wrong_teacher_inside_scope" if inside else "wrong_teacher_outside_scope"))
