"""Wave 30 A2 (coder direct solver with iterative feedback) on the local Qwen2.5-1.5B-Instruct GGUF (CPU unless the
owner's Metal grant is explicitly set; the backend is recorded).

The model writes a program in the A1 DSL as a JSON list of op specs. NEXUS executes it under the kernel's declared
semantics. On a mismatch, the first failing demonstration is fed back, for up to MAX_ATTEMPTS generations. The
first program that fits every demonstration is submitted: one final submission, under the common limit of two.
Its certificate is proposal-relative. The kernel checks it against the proposal set {candidate}, so it can only
be AGREEMENT_AMONG_PROPOSALS, never exhaustive. Cost = 1 unit per prompt token + 4 per generated token
(the Wave 24 meter) + execution."""
from __future__ import annotations

import json
import re

from nexus import checker_kernel as K

MAX_ATTEMPTS = 4
SYSTEM = ("You write tiny list programs. Reply with ONLY a JSON list (1 or 2 steps) of operations applied left to "
          "right. Operations:\n"
          '{"op":"F","pred":{"path":P,"cmp":"ge|le|eq","val":V}} keep items whose field P (or "." for the item) passes\n'
          '{"op":"S","k":K,"path":P,"desc":B} first K items after ordering by P ("#" = position)\n'
          '{"op":"Sort","path":P,"desc":B}\n'
          '{"op":"proj","path":P} replace each record by its field P\n'
          '{"op":"map_add","c":C} {"op":"map_mul","c":C} {"op":"map_mod","c":C} on numbers\n'
          '{"op":"prefix_sum"} {"op":"running_max"} {"op":"diff"} {"op":"run_heads"} {"op":"rotate","k":K}\n'
          '{"op":"group_count","path":P} counts per distinct value in first-appearance order\n'
          '{"op":"repeat","n":N,"body":OP}')


def _user(public, feedback):
    ex = "\n".join(f"input: {json.dumps(x)}\noutput: {json.dumps(y)}" for x, y in public)
    return ex + ("\n" + feedback if feedback else "") + "\nProgram:"


def parse(text):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        prog = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(prog, list) or not 1 <= len(prog) <= 2 or not all(isinstance(s, dict) and K.known(s) for s in prog):
        return None
    return prog


def solve_a2(engine, public, query, *, seed=0):
    public = [(x, y) for x, y in public]
    feedback, work, rows = "", 0, []
    for attempt in range(MAX_ATTEMPTS):
        text, row = engine.complete(SYSTEM, _user(public, feedback), temperature=0.0 if attempt == 0 else 0.7,
                                    seed=seed * 10 + attempt, purpose="w30-A2")
        work += engine.work_units(row)
        rows.append(row)
        prog = parse(text)
        if prog is None:
            feedback = "Your reply was not a valid program. Reply with only the JSON list."
            continue
        bad = None
        for x, y in public:
            work += 1
            try:
                o = K.run(prog, x)
            except Exception as exc:
                bad = (x, y, f"error {type(exc).__name__}")
                break
            if K.key(o) != K.key(y):
                bad = (x, y, json.dumps(o))
                break
        if bad is None:
            ev = {"version": 1, "public": [[x, y] for x, y in public], "query": query,
                  "claimed_answer": K.run(prog, query), "candidate": prog,
                  "scope": {"kind": "proposal", "tools": prog, "max_depth": len(prog)}, "lemmas": [], "trace": {}}
            v = K.check(ev)
            return dict(label=v["label"], answer=ev["claimed_answer"], attempts=attempt + 1, work=work,
                        tokens=sum(r["input_tokens"] + r["generated_tokens"] for r in rows), program=prog)
        feedback = (f"Your program {json.dumps(prog)} gave {bad[2]} on input {json.dumps(bad[0])}; expected "
                    f"{json.dumps(bad[1])}. Write a corrected program.")
    return dict(label="ABSTAIN", answer=None, attempts=MAX_ATTEMPTS, work=work,
                tokens=sum(r["input_tokens"] + r["generated_tokens"] for r in rows), program=None)
