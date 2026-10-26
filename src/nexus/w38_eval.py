"""Wave 38 evaluator / meter boundary (NOT LOCKED). Reuses the Wave 31 sandboxed Child (sandbox-exec, OS instruction
counter) with the Wave 38 solver child. Checker v4 (pinned, verified from its git object) runs here; the oracle is the
evaluator-side teacher; detectors: D1 evidence audit, D2 declared-scope match, D3 oracle refusal (query input / cap)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from nexus import checker_kernel_v4 as V4
from nexus import w38_lang as L
from nexus import w38_scope as S
from nexus.wave31_evaluator import Child, instructions, ledger_append  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
V4_PIN_COMMIT = "51c12f9"
CHILD = "scripts/w38_child.py"


def verify_v4():
    pin = subprocess.run(["git", "-C", str(ROOT), "show", f"{V4_PIN_COMMIT}:src/nexus/checker_kernel_v4.sha256"],
                         capture_output=True, text=True, check=True).stdout.split()[0]
    disk = hashlib.sha256((ROOT / "src/nexus/checker_kernel_v4.py").read_bytes()).hexdigest()
    if disk != pin:
        raise SystemExit("checker v4 does not match its pin")
    return pin


class Eval:
    def __init__(self):
        self.pin = verify_v4()

    def child(self, hashseed="0", script=CHILD):
        return Child(hashseed, script)

    def stream(self, tasks, genome, tag, hashseed="0"):
        """One online stream from an EMPTY library (genome None = Fresh). Every update is metered on the child's counter."""
        ch = self.child(hashseed, "scripts/w38_online_child.py")
        self.call(ch, {"cmd": "o_reset", "genome": genome})
        rows, learn, declared = [], 0, 0
        for k, t in enumerate(tasks):
            r = self.solve(ch, t, len(t["teacher"]), f"{tag}:{k}")
            rows.append(r)
            if r.get("candidate"):
                u = self.call(ch, {"cmd": "o_update", "candidate": r["candidate"], "public": t["public"]})
                learn += u["_instr"]; declared = u["declared"]
        ch.close()
        return rows, learn, declared

    def _check(self, ev, meter):
        i0 = instructions(os.getpid())
        v = V4.check(ev)
        meter["checker_instr"] = meter.get("checker_instr", 0) + instructions(os.getpid()) - i0
        return v

    def solve(self, ch, task, depth, seed, prior=None, neural=None, budget=300000):
        meter, oracle_log = {}, []
        c0, t0 = instructions(ch.p.pid), time.perf_counter()
        ch.send({"cmd": "solve", "public": task["public"], "query": task["query"], "depth": depth, "seed": seed,
                 "prior": prior, "neural": neural, "budget": budget})
        while True:
            msg = ch.recv()
            if msg.get("done"):
                break
            if msg.get("req") == "check":
                ch.send(self._check(msg["evidence"], meter))
            else:
                x = msg["input"]
                if L.key(x) == L.key(task["query"]) or len(oracle_log) >= 3:
                    meter["flag_oracle"] = meter.get("flag_oracle", 0) + 1
                    ch.send({"error": True}); continue
                y = L.run(task["teacher"], x)
                if y == L.ERROR:
                    ch.send({"error": True}); continue
                oracle_log.append([x, y]); ch.send({"output": y})
        meter["child_instr"] = instructions(ch.p.pid) - c0
        meter["wall_s"] = time.perf_counter() - t0
        ev = msg["evidence"]
        row = dict(domain=task.get("domain"), mechanism=task.get("mechanism"), source=task.get("source"),
                   probes=msg["info"]["probes"], status=msg["info"]["status"], execs=msg["meter"].get("execs", 0))
        flags = {"D1": 0, "D2": 0, "D3": meter.get("flag_oracle", 0)}
        if ev is None:
            row.update(label="ABSTAIN", correct=False, wrong=False)
        else:
            allowed = {L.key(p) for p in task["public"]} | {L.key(p) for p in oracle_log}
            got = [L.key(p) for p in ev["public"]]
            if not {L.key(p) for p in task["public"]} <= set(got) or not set(got) <= allowed or L.key(ev["query"]) != L.key(task["query"]):
                flags["D1"] = 1
            if L.key(ev["scope"]) != L.key(S.scope(task["public"], task["query"], depth)):
                flags["D2"] = 1
            v = self._check(ev, meter)
            uniq = v["label"] == "exhaustive_UNIQUE" and not flags["D1"] and not flags["D2"]
            correct = uniq and L.key(ev["claimed_answer"]) == L.key(task["answer"])
            row.update(label=v["label"] if not (flags["D1"] or flags["D2"]) else "INVALID_EVIDENCE", k=v.get("k"),
                       correct=correct, wrong=uniq and not correct, candidate=ev["candidate"] if uniq else None)
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
