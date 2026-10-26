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

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from nexus import checker_kernel_v2 as V
from nexus import checker_kernel_v3 as V3
from nexus import wave31_grammar as G

ROOT = Path(__file__).resolve().parents[2]
V2_PIN_COMMIT = "01d84f6"
V3_PIN_COMMIT = "1642721"
ORACLE_PRICE_INSTR = 50_000_000      # declared price of one oracle query in evaluator_work (retired instructions)
LEDGER = ROOT / "runs/experimental/wave24-agi/ledger.jsonl"
VAULT = os.environ.get("NEXUS_SEALED_VAULT_DIR", str(Path.home() / ".gemini/antigravity/sealed_nexus_vault"))


def verify_v2():
    pin = subprocess.run(["git", "-C", str(ROOT), "show", f"{V2_PIN_COMMIT}:src/nexus/checker_kernel_v2.sha256"],
                         capture_output=True, text=True, check=True).stdout.split()[0]
    disk = hashlib.sha256((ROOT / "src/nexus/checker_kernel_v2.py").read_bytes()).hexdigest()
    if disk != pin or Path(V.__file__).resolve() != (ROOT / "src/nexus/checker_kernel_v2.py").resolve():
        raise SystemExit("checker v2 does not match its pin; refusing to run")
    return pin


class _RU(ctypes.Structure):
    _fields_ = [("ri_uuid", ctypes.c_uint8 * 16)] + [(f"f{i}", ctypes.c_uint64) for i in range(29)] + \
               [("ri_instructions", ctypes.c_uint64), ("ri_cycles", ctypes.c_uint64)] + \
               [(f"g{i}", ctypes.c_uint64) for i in range(4)]


_LIBPROC = ctypes.CDLL("/usr/lib/libproc.dylib") if sys.platform == "darwin" else None


def instructions(pid):
    """Retired instructions of process `pid`, read by the OS kernel (proc_pid_rusage, RUSAGE_INFO_V4). The measured
    process cannot alter this counter."""
    r = _RU()
    if _LIBPROC is None or _LIBPROC.proc_pid_rusage(int(pid), 4, ctypes.byref(r)) != 0:
        raise RuntimeError("instruction counter unavailable")
    return int(r.ri_instructions)


def verify_v3():
    pin = subprocess.run(["git", "-C", str(ROOT), "show", f"{V3_PIN_COMMIT}:src/nexus/checker_kernel_v3.sha256"],
                         capture_output=True, text=True, check=True).stdout.split()[0]
    disk = hashlib.sha256((ROOT / "src/nexus/checker_kernel_v3.py").read_bytes()).hexdigest()
    if disk != pin or Path(V3.__file__).resolve() != (ROOT / "src/nexus/checker_kernel_v3.py").resolve():
        raise SystemExit("checker v3 does not match its pin; refusing to run")
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
    def __init__(self, hashseed="0", script="scripts/wave31_solver_child.py", args=()):
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "src"), "PYTHONHASHSEED": str(hashseed),
               "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/var/empty"}
        self.t0 = time.perf_counter()
        self.p = subprocess.Popen(["/usr/bin/sandbox-exec", "-p", sandbox_profile(), sys.executable, "-B",
                                   str(ROOT / script), *map(str, args)], stdin=subprocess.PIPE,
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
    ORACLE_CAP = G.MAX_PROBES

    def __init__(self, depth=G.MATCHED_DEPTH, checker=2):
        """`checker`: the one pinned checker every arm of this evaluator is graded by (2 or 3)."""
        self.checker = checker
        self.pin = verify_v2() if checker == 2 else verify_v3()
        self.kernel_work = 0
        self.oracle_calls = 0
        self.depth = depth
        self._cache = {}

    def _check(self, ev, meter):
        """Evaluator-side kernel call, metered in kernel steps and in the evaluator's own retired instructions."""
        d = hashlib.sha256(json.dumps(ev, sort_keys=True).encode()).hexdigest()
        if d in self._cache:
            return self._cache[d]
        i0 = instructions(os.getpid())
        v = (V.check if self.checker == 2 else V3.check)(ev)
        meter["eval_instr"] = meter.get("eval_instr", 0) + instructions(os.getpid()) - i0
        w = v.get("steps", 0) + (v.get("chains_checked", 0) if self.checker == 2 else v.get("point_evals", 0))
        meter["kernel"] = meter.get("kernel", 0) + w
        self.kernel_work += w
        self._cache = {d: v}
        return v

    def _serve(self, child, task, meter):
        """Serve requests until the child's `done` line. `task` (evaluator-side) is used only for the oracle.
        Oracle requests on the task's query input, or beyond ORACLE_CAP, are refused and flagged."""
        while True:
            msg = child.recv()
            if msg.get("done"):
                return msg
            if msg.get("req") == "check":
                child.send(self._check(msg["evidence"], meter))
            elif msg.get("req") == "oracle":
                x = msg["input"]
                if V.key(x) == V.key(task["query"]):
                    meter["flag_oracle_on_query"] = meter.get("flag_oracle_on_query", 0) + 1
                    child.send({"error": True, "refused": "query_input"})
                    continue
                if meter.get("oracle_calls", 0) >= self.ORACLE_CAP:
                    meter["flag_oracle_over_cap"] = meter.get("flag_oracle_over_cap", 0) + 1
                    child.send({"error": True, "refused": "cap"})
                    continue
                meter["oracle_calls"] = meter.get("oracle_calls", 0) + 1
                self.oracle_calls += 1
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

    def library(self, child, programs, seed, views=(), **kw):
        """Source-only feedback: the child receives the candidates of source tasks that the evaluator's own checker
        labelled exhaustive_UNIQUE (labels only; no answers or correctness) and builds both libraries."""
        child.send(dict({"cmd": "library", "programs": programs, "seed": seed, "views": list(views)}, **kw))
        return child.recv()["result"]

    def lsolve(self, child, task, program, seed, cmd="l_solve"):
        """Milestone B: the child's learner program decides how to solve; graded and metered exactly like solve()."""
        meter = {}
        task.pop("_oracle_log", None)
        c0, t0 = instructions(child.p.pid), time.perf_counter()
        child.send({"cmd": cmd, "view": {"public": task["public"], "query": task["query"]}, "program": program,
                    "seed": seed})
        msg = self._serve(child, task, meter)
        meter["child_instr"] = instructions(child.p.pid) - c0
        meter["wall_s"] = time.perf_counter() - t0
        row = self.grade(task, msg, meter)
        ev = msg.get("evidence")
        row["flag_scope_mismatch"] = bool(ev is not None and not G.is_matched(ev["scope"], self.depth))
        row["used"] = [msg["info"].get("used_macros"), msg["info"].get("used_prior")]
        row["rec"] = msg["info"].get("rec")
        return row

    def solve(self, child, task, arm, mode, library, seed, policy=None):
        meter = {}
        task.pop("_oracle_log", None)
        c0, t0 = instructions(child.p.pid), time.perf_counter()
        child.send({"cmd": "solve", "arm": arm, "mode": mode, "view": {"public": task["public"], "query": task["query"]},
                    "library": library, "seed": seed, "policy": policy or {}})
        msg = self._serve(child, task, meter)
        meter["child_instr"] = instructions(child.p.pid) - c0
        meter["wall_s"] = time.perf_counter() - t0
        row = self.grade(task, msg, meter)
        ev = msg.get("evidence")
        row["flag_scope_mismatch"] = bool(mode == "matched" and ev is not None and not G.is_matched(ev["scope"], self.depth))
        return row

    def grade(self, task, msg, meter):
        ev, info = msg["evidence"], msg["info"]
        ext = {k: meter.get(k, 0) for k in ("child_instr", "eval_instr", "oracle_calls", "wall_s",
                                            "flag_oracle_on_query", "flag_oracle_over_cap")}
        ext["evaluator_work"] = ext["child_instr"] + ext["eval_instr"] + ext["oracle_calls"] * ORACLE_PRICE_INSTR
        row = dict(category=task["category"], domain=task["domain"], core=task["core"], probes=info["probes"], ext=ext,
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
        k0 = meter.get("kernel", 0)
        v = self._check(ev, meter)
        row["kernel"] += meter.get("kernel", 0) - k0
        lab = G.report_label(v, ev["scope"], self.depth)
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
