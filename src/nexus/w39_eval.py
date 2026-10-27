"""Wave 39 evaluator / meter boundary (NOT LOCKED). Same boundary as w38_eval (sandboxed child, OS instruction counter, D1-D3
detectors, oracle 50M instructions per call) with Checker v5 (pinned, verified from its git object) and the Wave 39 language,
scope and child. Adds: extra (held-out INPUT) queries for per-input scope uniqueness, the v5 output contract, and per-iteration
search executions (anytime cost-vs-coverage curves are read from one deterministic run at the largest cap)."""
from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path

from nexus import checker_kernel_v5 as V5
from nexus import w39_lang as L
from nexus import w39_scope as S
from nexus.wave31_evaluator import Child, instructions, ledger_append  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
V5_PIN_COMMIT = None          # set at the pin commit (see verify_v5)
CHILD = "scripts/w39_child.py"


def verify_v5():
    pin = (ROOT / "src/nexus/checker_kernel_v5.sha256").read_text().split()[0]
    if V5_PIN_COMMIT:
        pin = subprocess.run(["git", "-C", str(ROOT), "show", f"{V5_PIN_COMMIT}:src/nexus/checker_kernel_v5.sha256"],
                             capture_output=True, text=True, check=True).stdout.split()[0]
    disk = hashlib.sha256((ROOT / "src/nexus/checker_kernel_v5.py").read_bytes()).hexdigest()
    if disk != pin:
        raise SystemExit("checker v5 does not match its pin")
    return pin


class Eval:
    def __init__(self):
        self.pin = verify_v5()

    def child(self, hashseed="0", script=CHILD):
        return Child(hashseed, script)

    def _check(self, ev, meter):
        i0 = instructions(os.getpid())
        v = V5.check(ev)
        meter["checker_instr"] = meter.get("checker_instr", 0) + instructions(os.getpid()) - i0
        return v

    def solve(self, ch, task, depth, seed, prior=None, budget=2_000_000, extra=None, oracle=True):
        meter, oracle_log, verdict = {}, [], None
        c0, t0 = instructions(ch.p.pid), time.perf_counter()
        ch.send({"cmd": "solve", "public": task["public"], "query": task["query"], "depth": depth, "seed": seed,
                 "prior": prior, "budget": budget, "extra": extra or []})
        while True:
            msg = ch.recv()
            if msg.get("done"):
                break
            if msg.get("req") == "check":
                verdict = self._check(msg["evidence"], meter)
                ch.send(verdict)
            else:
                x = msg["input"]
                if not oracle or L.key(x) == L.key(task["query"]) or len(oracle_log) >= 3:
                    meter["flag_oracle"] = meter.get("flag_oracle", 0) + (1 if oracle else 0)
                    ch.send({"error": True}); continue
                y = L.run(task["teacher"], x)
                if y == L.ERROR:
                    ch.send({"error": True}); continue
                oracle_log.append([x, y]); ch.send({"output": y})
        meter["child_instr"] = instructions(ch.p.pid) - c0
        meter["wall_s"] = time.perf_counter() - t0
        ev = msg["evidence"]
        row = dict(domain=task.get("domain"), mechanism=task.get("mechanism"), source=task.get("source"),
                   probes=msg["info"]["probes"], status=msg["info"]["status"], execs=msg["meter"].get("execs", 0),
                   iters=msg["meter"].get("iters", []))
        flags = {"D1": 0, "D2": 0, "D3": meter.get("flag_oracle", 0)}
        if ev is None:
            row.update(label="ABSTAIN", correct=False, wrong=False, warnings=[], extra=[])
        else:
            allowed = {L.key(p) for p in task["public"]} | {L.key(p) for p in oracle_log}
            got = [L.key(p) for p in ev["public"]]
            if not {L.key(p) for p in task["public"]} <= set(got) or not set(got) <= allowed or L.key(ev["query"]) != L.key(task["query"]):
                flags["D1"] = 1
            if L.key(ev["scope"]) != L.key(S.scope(task["public"], task["query"], depth)) or \
                    L.key(ev.get("extra_queries") or []) != L.key(extra or []):
                flags["D2"] = 1
            v = self._check(ev, meter)
            uniq = v["label"] == "SCOPE_UNIQUE" and not flags["D1"] and not flags["D2"]
            correct = uniq and L.key(ev["claimed_answer"]) == L.key(task["answer"])
            row.update(label=v["label"] if not (flags["D1"] or flags["D2"]) else "INVALID_EVIDENCE", k=v.get("k"),
                       correct=correct, wrong=uniq and not correct, candidate=ev["candidate"],
                       certified=uniq, warnings=v.get("warnings", []), warning_reasons=v.get("warning_reasons"),
                       extra=v.get("extra", []))
        work = meter["child_instr"] + meter.get("checker_instr", 0) + len(oracle_log) * 50_000_000
        row.update(work=work, child_instr=meter["child_instr"], checker_instr=meter.get("checker_instr", 0),
                   oracle=len(oracle_log), wall_s=meter["wall_s"], flags=flags)
        return row

    def call(self, ch, job):
        c0 = instructions(ch.p.pid)
        ch.send(job)
        out = ch.recv()
        out["_instr"] = instructions(ch.p.pid) - c0
        return out


def at_cap(row, cap):
    """Anytime reading of a row produced at a larger cap: the search is deterministic best-first, so a run at a smaller per-
    iteration budget explores the same prefix. Solved at `cap` iff every search iteration found its candidate within `cap`
    executions. Work: exact (identical run) if solved; otherwise a LINEAR estimate = child work x (executions spent before the
    first over-cap iteration stops at cap) / (executions in the full run) + checker work of the completed iterations."""
    it = row.get("iters") or []
    if row["label"] == "ABSTAIN" and not it:
        return dict(solved=False, correct=False, work=row["work"], exact=True)
    over = [i for i, (e, found) in enumerate(it) if found and e > cap or (not found and e > cap)]
    if not over:
        return dict(solved=row.get("certified", False), correct=row["correct"], work=row["work"], exact=True)
    i = over[0]
    spent = sum(e for e, _ in it[:i]) + cap
    total = max(1, sum(e for e, _ in it))
    frac = min(1.0, spent / total)
    chk = row["checker_instr"] * (i / max(1, len(it)))
    return dict(solved=False, correct=False, work=int(row["child_instr"] * frac + chk + row["oracle"] * 50_000_000 * (i / max(1, len(it)))),
                exact=False)
