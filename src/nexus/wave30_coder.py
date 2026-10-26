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


# --------------------------------------------------------------------------- increment 3: diagnosis variants
FEWSHOT = ('Example.\ninput: [{"a": 3, "b": "x"}, {"a": 1, "b": "y"}, {"a": 5, "b": "z"}]\n'
           'output: ["z", "x"]\nProgram: [{"op":"S","k":2,"path":"a","desc":true},{"op":"proj","path":"b"}]\n\n'
           'Example.\ninput: [4, 1, 3]\noutput: [4, 5, 8]\nProgram: [{"op":"prefix_sum"}]\n\n')


def classify(prog, public, query, answer):
    """Bucket one attempt: unparsable | runtime_error | fails_public | fits_public_wrong_heldout | correct."""
    if prog is None:
        return "unparsable"
    for x, y in public:
        try:
            o = K.run(prog, x)
        except Exception:
            return "runtime_error"
        if K.key(o) != K.key(y):
            return "fails_public"
    try:
        a = K.run(prog, query)
    except Exception:
        return "fits_public_wrong_heldout"
    return "correct" if K.key(a) == K.key(answer) else "fits_public_wrong_heldout"


def solve_a2_diag(engine, public, query, answer, *, seed=0, variant="orig"):
    """Same loop as solve_a2, recording the bucket and raw text of every attempt. variant: orig | fewshot
    (worked examples + the assistant turn pre-filled with '[' so the reply starts as a JSON list)."""
    public = [(x, y) for x, y in public]
    feedback, attempts = "", []
    for attempt in range(MAX_ATTEMPTS):
        user = _user(public, feedback)
        prefix = ""
        if variant == "fewshot":
            user = FEWSHOT + "Now this task.\n" + user
            prefix = "["
        text, row = engine.complete(SYSTEM, user, temperature=0.0 if attempt == 0 else 0.7,
                                    seed=seed * 10 + attempt, purpose=f"w30-A2-{variant}", prefix=prefix,
                                    stop=("<|im_end|>", "\n\n"))
        prog = parse(text)
        b = classify(prog, public, query, answer)
        attempts.append(dict(bucket=b, text=text[:400], tokens_in=row["input_tokens"], tokens_out=row["generated_tokens"],
                             wall_s=row["wall_s"]))
        if b in ("correct", "fits_public_wrong_heldout"):
            break
        if prog is None:
            feedback = "Your reply was not a valid program. Reply with only the JSON list."
        else:
            bad = next(((x, y) for x, y in public if b != "runtime_error" and _safe(prog, x) != K.key(y)), public[0])
            feedback = (f"Your program {json.dumps(prog)} is wrong on input {json.dumps(bad[0])}; expected "
                        f"{json.dumps(bad[1])}. Write a corrected program.")
    return attempts


def _safe(prog, x):
    try:
        return K.key(K.run(prog, x))
    except Exception:
        return "<error>"


# --------------------------------------------------------------------------- increment 3: fixed prompt (v3)
SYSTEM_V3 = ("You write tiny list programs. Reply with ONLY a JSON list of AT MOST 2 operations, applied left to "
             "right. Replace every <...> with a concrete value; <field> must be one of the task's field names, '.' "
             "for a plain item, or '#' for position.\n"
             '{"op":"F","pred":{"path":<field>,"cmp":"ge"|"le"|"eq","val":<value>}}\n'
             '{"op":"S","k":<int>,"path":<field>,"desc":true|false}   (first k after ordering)\n'
             '{"op":"Sort","path":<field>,"desc":true|false}\n'
             '{"op":"proj","path":<field>}\n'
             '{"op":"map_add","c":<int>}  {"op":"map_mul","c":<int>}  {"op":"map_mod","c":<int>}\n'
             '{"op":"prefix_sum"} {"op":"running_max"} {"op":"diff"} {"op":"run_heads"} {"op":"rotate","k":<int>}\n'
             '{"op":"group_count","path":<field>}\n'
             "desc=true needs a numeric field.")


def _fields(public):
    fs = sorted({k for x, _ in public if isinstance(x, list) for it in x if isinstance(it, dict) for k in it})
    return "Field names: " + (", ".join(fs) if fs else "(items are plain values: use '.')")


def parse_v3(text):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None, "unparsable"
    try:
        prog = json.loads(m.group(0))
    except Exception:
        return None, "unparsable"
    if not isinstance(prog, list) or not all(isinstance(s, dict) and K.known(s) for s in prog):
        return None, "invalid_spec"
    if not 1 <= len(prog) <= 2:
        return None, "too_long"
    return prog, None


def solve_a2_v3(engine, public, query, answer, *, seed=0):
    public = [(x, y) for x, y in public]
    feedback, attempts = "", []
    for attempt in range(MAX_ATTEMPTS):
        user = _fields(public) + "\n" + _user(public, feedback)
        text, row = engine.complete(SYSTEM_V3, user, temperature=0.0 if attempt == 0 else 0.7, seed=seed * 10 + attempt,
                                    purpose="w30-A2-v3", prefix="[", stop=("<|im_end|>", "\n\n"))
        prog, err = parse_v3(text)
        b = err or classify(prog, public, query, answer)
        attempts.append(dict(bucket=b, text=text[:400], tokens_in=row["input_tokens"],
                             tokens_out=row["generated_tokens"], wall_s=row["wall_s"]))
        if b in ("correct", "fits_public_wrong_heldout"):
            break
        if prog is None:
            feedback = {"too_long": "Use at most 2 operations.", "invalid_spec": "Use only the listed operations.",
                        "unparsable": "Reply with only the JSON list."}[b]
        else:
            bad = next(((x, y) for x, y in public if _safe(prog, x) != K.key(y)), public[0])
            feedback = (f"Your program {json.dumps(prog)} gave {_safe(prog, bad[0])} on input {json.dumps(bad[0])}; "
                        f"expected {json.dumps(bad[1])}. Write a corrected program.")
    return attempts


def normalize_scalar_paths(prog, public):
    """Declared input adapter (charged 1 unit per rewrite, equally available to every arm): when the task's items
    are plain values (no records), any field path is rewritten to '.'. Returns (program, rewrites)."""
    scalar = all(isinstance(x, list) and all(not isinstance(it, dict) for it in x) for x, _ in public)
    if not scalar or prog is None:
        return prog, 0
    n = 0

    def fix(s):
        nonlocal n
        s = dict(s)
        for k in ("path", "tparam"):
            if isinstance(s.get(k), str) and s[k] not in (".", "#"):
                s[k], n = ".", n + 1
        if isinstance(s.get("pred"), dict) and s["pred"].get("path") not in (".", None):
            s["pred"], n = dict(s["pred"], path="."), n + 1
        return s
    return [fix(s) for s in prog], n


def solve_a2_v4(engine, public, query, answer, *, seed=0):
    public = [(x, y) for x, y in public]
    feedback, attempts = "", []
    for attempt in range(MAX_ATTEMPTS):
        user = _fields(public) + "\n" + _user(public, feedback)
        text, row = engine.complete(SYSTEM_V3, user, temperature=0.0 if attempt == 0 else 0.7, seed=seed * 10 + attempt,
                                    purpose="w30-A2-v4", prefix="[", stop=("<|im_end|>", "\n\n"))
        prog, err = parse_v3(text)
        prog, rewrites = normalize_scalar_paths(prog, public)
        b = err or classify(prog, public, query, answer)
        attempts.append(dict(bucket=b, text=text[:400], rewrites=rewrites, tokens_in=row["input_tokens"],
                             tokens_out=row["generated_tokens"], wall_s=row["wall_s"]))
        if b in ("correct", "fits_public_wrong_heldout"):
            break
        if prog is None:
            feedback = {"too_long": "Use at most 2 operations.", "invalid_spec": "Use only the listed operations.",
                        "unparsable": "Reply with only the JSON list."}[b]
        else:
            bad = next(((x, y) for x, y in public if _safe(prog, x) != K.key(y)), public[0])
            feedback = (f"Your program {json.dumps(prog)} gave {_safe(prog, bad[0])} on input {json.dumps(bad[0])}; "
                        f"expected {json.dumps(bad[1])}. Write a corrected program.")
    return attempts
