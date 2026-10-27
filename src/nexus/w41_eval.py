"""Wave 41 evaluator / meter boundary (NOT LOCKED): the Wave 40 boundary (sandboxed child, OS instruction counter, D1-D3
detectors, Checker v5 pinned at 622a29a and verified from its git object, identical-evidence verdict cache, split search /
witness / certification meter) with the Wave 41 child and:
  * external user oracle: answers ONLY inputs from the task's future-input pool (held-out inputs offered as extra queries),
    from held-out outputs held by the evaluator; 50M instructions per answer (the Wave 38 oracle charge); queried inputs are
    reported so scoring excludes them;
  * D2 accepts evidence whose extra queries are the task's extras minus oracle-answered inputs (same order);
  * the certificate tier (w41_hier.global_label: GLOBAL_SCOPE_UNIQUE only from Checker v5 on the original declared scope);
  * per-round snapshots (k = 0, 1, 2), the Middle-IR record, child peak RSS."""
from __future__ import annotations

import time

from nexus import w39_eval as E39
from nexus import w39_lang as L
from nexus import w39_scope as S
from nexus import w40_eval as E40
from nexus import w41_hier as H
from nexus.w39_eval import at_cap, instructions, ledger_append, verify_v5  # noqa: F401

CHILD = "scripts/w41_child.py"


class Eval(E40.Eval):
    def child(self, hashseed="0", script=CHILD):
        return E39.Child(hashseed, script)

    def solve(self, ch, task, depth, seed, budget=2_000_000, extra=None, mode="internal", k=0):
        meter, oracle_log, last, ticks = {}, [], (None, None), {}
        pool = {L.key(x): y for x, y in task.get("heldout", [])[1:]} if mode == "external" else {}
        extra = list(extra or [])
        c0, t0 = instructions(ch.p.pid), time.perf_counter()
        ch.send({"cmd": "solve", "public": task["public"], "query": task["query"], "depth": depth, "seed": seed, "budget": budget,
                 "extra": extra, "mode": mode, "k": k})
        while True:
            msg = ch.recv()
            if msg.get("done"):
                break
            if msg.get("req") == "tick":
                ticks.setdefault(msg["what"], instructions(ch.p.pid) - c0)
                ch.send({}); continue
            if msg.get("req") == "check":
                e = msg["evidence"]
                askd = {L.key(x) for x, _ in oracle_log}
                okp = {L.key(p) for p in task["public"]} | {L.key(p) for p in oracle_log}
                gp = {L.key(p) for p in e["public"]}
                we = [z for z in extra if L.key(z) not in askd] if mode == "external" else extra
                clean = ({L.key(p) for p in task["public"]} <= gp <= okp and L.key(e["query"]) == L.key(task["query"]) and
                         L.key(e["scope"]) == L.key(S.scope(task["public"], task["query"], depth)) and
                         L.key(e.get("extra_queries") or []) == L.key(we))
                verdict = self._check(e, meter)
                meter.setdefault("checks", []).append([verdict["label"], clean])
                last = (L.key(msg["evidence"]), verdict)
                meter.setdefault("first_label", verdict["label"])
                meter["kernel_calls"] = meter.get("kernel_calls", 0) + 1
                ch.send(verdict)
                continue
            x = msg["input"]
            if L.key(x) == L.key(task["query"]) or len(oracle_log) >= 3:
                meter["flag_oracle"] = meter.get("flag_oracle", 0) + 1
                ch.send({"error": True}); continue
            if mode == "external":
                if L.key(x) not in pool:
                    meter["flag_oracle"] = meter.get("flag_oracle", 0) + 1
                    ch.send({"error": True}); continue
                y = pool[L.key(x)]
            else:
                y = L.run(task["teacher"], x)
                if y == L.ERROR:
                    ch.send({"error": True}); continue
            oracle_log.append([x, y]); ch.send({"output": y})
        meter["child_instr"] = instructions(ch.p.pid) - c0
        meter["wall_s"] = time.perf_counter() - t0
        ev, mm, info = msg["evidence"], msg["meter"], msg["info"]
        asked = {L.key(x) for x, _ in oracle_log}
        row = dict(domain=task.get("domain"), mechanism=task.get("mechanism"), source=task.get("source"),
                   probes=info.get("probes", 0), status=info["status"], execs=mm.get("execs", 0), iters=mm.get("iters", []),
                   search_instr=ticks.get("search", meter["child_instr"]),
                   witness_instr=(ticks["witness"] - ticks["search"]) if "witness" in ticks else 0,
                   witness_execs=mm.get("witness_execs", 0), witness_found=mm.get("witness_found", 0),
                   lemma_skips=mm.get("lemma_skips", 0), skill_execs=mm.get("skill_execs", 0), skill_won=mm.get("skill_won"),
                   skill_excluded_summary=mm.get("skill_excluded_summary", 0), kernel_calls=meter.get("kernel_calls", 0),
                   first_label=meter.get("first_label"), rss=mm.get("rss"), snaps=info.get("snaps", []),
                   queries=[x for x, _ in oracle_log] if mode == "external" else [], record=info.get("record"),
                   checks=meter.get("checks", []))
        flags = {"D1": 0, "D2": 0, "D3": meter.get("flag_oracle", 0)}
        if ev is None:
            row.update(label="ABSTAIN" if info["status"] == "no_candidate" else "AMBIGUOUS_WITNESS", tier="ABSTAIN"
                       if info["status"] == "no_candidate" else "AMBIGUOUS", correct=False, wrong=False, warnings=[], extra=[])
        else:
            allowed = {L.key(p) for p in task["public"]} | {L.key(p) for p in oracle_log}
            got = [L.key(p) for p in ev["public"]]
            if not {L.key(p) for p in task["public"]} <= set(got) or not set(got) <= allowed or L.key(ev["query"]) != L.key(task["query"]):
                flags["D1"] = 1
            want_extra = [e for e in extra if L.key(e) not in asked] if mode == "external" else extra
            if L.key(ev["scope"]) != L.key(S.scope(task["public"], task["query"], depth)) or \
                    L.key(ev.get("extra_queries") or []) != L.key(want_extra):
                flags["D2"] = 1
            v = last[1] if last[0] == L.key(ev) else self._check(ev, meter)
            clean = not flags["D1"] and not flags["D2"]
            tier = H.global_label(kernel_full=v, flags_clean=clean)
            uniq = tier == "GLOBAL_SCOPE_UNIQUE"
            correct = uniq and L.key(ev["claimed_answer"]) == L.key(task["answer"])
            row.update(label=v["label"] if clean else "INVALID_EVIDENCE", tier=tier, k=v.get("k"), correct=correct,
                       wrong=uniq and not correct, candidate=ev["candidate"], certified=uniq, warnings=v.get("warnings", []),
                       extra=v.get("extra", []), final_public=ev["public"])
        work = meter["child_instr"] + meter.get("checker_instr", 0) + len(oracle_log) * 50_000_000
        row.update(work=work, child_instr=meter["child_instr"], checker_instr=meter.get("checker_instr", 0),
                   oracle=len(oracle_log), wall_s=meter["wall_s"], flags=flags)
        return row
