"""Wave 40 evaluator / meter boundary (NOT LOCKED). The Wave 39 boundary (sandboxed child, OS instruction counter, D1-D3
detectors, oracle 50M instructions per call, Checker v5 pinned at 622a29a and verified from its git object, identical-evidence
verdict cache) with the Wave 40 child (repaired search). Adds a split meter: the child sends `tick` after its search and after
its witness search, so every row carries search_instr, witness_instr and certification (checker) instructions separately, plus
the witness short-circuit soundness check (witness found => kernel label must be AMBIGUOUS)."""
from __future__ import annotations

import os
import time

from nexus import w39_eval as E39
from nexus import w39_lang as L
from nexus import w39_scope as S
from nexus.w39_eval import at_cap, instructions, ledger_append, verify_v5  # noqa: F401

CHILD = "scripts/w40_child.py"
ONLINE_CHILD = "scripts/w40_online_child.py"


class Eval(E39.Eval):
    def child(self, hashseed="0", script=CHILD):
        return E39.Child(hashseed, script)

    def stream(self, tasks, genome, tag, hashseed="0", shrink=4.0, budget=2_000_000, extras=None, oracle=True, depth=None,
               witness=False):
        ch = self.child(hashseed, ONLINE_CHILD)
        self.call(ch, {"cmd": "o_reset", "genome": genome, "shrink": shrink})
        rows, learn, declared, gate_log = [], 0, 0, None
        for k, t in enumerate(tasks):
            r = self.solve(ch, t, depth or len(t["teacher"]), f"{tag}:{k}", budget=budget,
                           extra=(extras[k] if extras else None), oracle=oracle, witness=witness)
            rows.append(r)
            if r.get("certified"):
                u = self.call(ch, {"cmd": "o_update", "candidate": r["candidate"], "public": t["public"]})
                learn += u["_instr"]; declared = u["declared"]; gate_log = u.get("gate_log")
        ch.close()
        return rows, learn, declared, gate_log

    def solve(self, ch, task, depth, seed, prior=None, budget=2_000_000, extra=None, oracle=True, witness=False, witness_budget=10**7):
        meter, oracle_log, verdict, last, ticks = {}, [], None, (None, None), {}
        c0, t0 = instructions(ch.p.pid), time.perf_counter()
        ch.send({"cmd": "solve", "public": task["public"], "query": task["query"], "depth": depth, "seed": seed,
                 "prior": prior, "budget": budget, "extra": extra or [], "witness": witness,
                 "witness_budget": witness_budget})
        while True:
            msg = ch.recv()
            if msg.get("done"):
                break
            if msg.get("req") == "tick":
                ticks.setdefault(msg["what"], instructions(ch.p.pid) - c0)
                ch.send({}); continue
            if msg.get("req") == "check":
                verdict = self._check(msg["evidence"], meter)
                last = (L.key(msg["evidence"]), verdict)
                meter.setdefault("first_label", verdict["label"])
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
        wit = msg["meter"].get("witness")
        row = dict(domain=task.get("domain"), mechanism=task.get("mechanism"), source=task.get("source"),
                   probes=msg["info"]["probes"], status=msg["info"]["status"], execs=msg["meter"].get("execs", 0),
                   iters=msg["meter"].get("iters", []), row_entries=msg["meter"].get("row_entries", 0),
                   search_instr=ticks.get("search", meter["child_instr"]),
                   witness_instr=(ticks["witness"] - ticks["search"]) if "witness" in ticks else 0,
                   witness_found=bool(wit and wit["found"]), witness_execs=(wit or {}).get("execs", 0),
                   first_label=meter.get("first_label"), gate=msg["meter"].get("gate"))
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
            v = last[1] if last[0] == L.key(ev) else self._check(ev, meter)
            uniq = v["label"] == "SCOPE_UNIQUE" and not flags["D1"] and not flags["D2"]
            correct = uniq and L.key(ev["claimed_answer"]) == L.key(task["answer"])
            row.update(label=v["label"] if not (flags["D1"] or flags["D2"]) else "INVALID_EVIDENCE", k=v.get("k"),
                       correct=correct, wrong=uniq and not correct, candidate=ev["candidate"],
                       certified=uniq, warnings=v.get("warnings", []), warning_reasons=v.get("warning_reasons"),
                       extra=v.get("extra", []))
        row["witness_unsound"] = bool(row["witness_found"] and row.get("first_label") != "AMBIGUOUS")
        work = meter["child_instr"] + meter.get("checker_instr", 0) + len(oracle_log) * 50_000_000
        row.update(work=work, child_instr=meter["child_instr"], checker_instr=meter.get("checker_instr", 0),
                   oracle=len(oracle_log), wall_s=meter["wall_s"], flags=flags)
        return row
