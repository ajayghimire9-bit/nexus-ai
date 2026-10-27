"""Wave 41 epistemic guards (CONTRACT LAYER; NOT LOCKED). Applied identically to every arm, per future input, from PUBLIC data
plus the system's own candidate and verdict only (never held-out outputs). Calibrated only on PROSE-dev, Split-dev and the 4
BURNED Wave 40 cases (artifacts/w40_step6_heldout_audit.json); those stay excluded from every confirmation.

Per-input tiers (first match wins):
  ABSTAIN_ERROR           the candidate's answer is ERROR (Wave 40 UserAgent: an ERROR answer was reported as unique)
  ABSTAIN_OUT_OF_SUPPORT  the input breaks a structural invariant shared by ALL public inputs: a delimiter / bracket /
                          punctuation character present in every public input is missing (UserAgent ';', FilePath '.')
  ABSTAIN_PROVENANCE      (a) the program writes a digit-bearing literal that occurs in EVERY public output (a memorised number:
                          PROSE-dev DateTime ':15'), or (b) it contains a string literal (len >= 2) and the input lacks a span
                          (len >= 4) shared verbatim by every public input (EmergencyCall: '2015-12-11' -> '12 Nov 2015')
  UNIQUE / NOT_UNIQUE     Checker v5's per-input answer count (query: the SCOPE_UNIQUE label; extras: answers == 1)
Structural characters = every non-alphanumeric character (incl. space), so the envelope adds no task-specific knowledge.
Frozen variant V2 (scripts/w41_calibrate_guards.py on dev + burned: guarded silent failures 11 -> 1). V0 also abstained on any
structural character absent from every public input; that cost more correct answers and caught nothing extra on dev."""
from __future__ import annotations

from nexus import w39_lang as L


def _text(x):
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        return "\x00".join(_text(e) for e in x)
    return ""


def envelope(public):
    xs = [_text(x) for x, _ in public]
    if not xs or not all(xs):
        return None
    struct = {c for s in xs for c in s if not c.isalnum()}
    present = {c for c in struct if all(c in s for s in xs)}
    # absent-in-all: structural characters seen in no public input but present in a candidate future input are detected at
    # check time (any non-alphanumeric character outside `struct`)
    return dict(present=present, struct=struct)


def out_of_support(x, env):
    if env is None:
        return False
    s = _text(x)
    if any(c not in s for c in env["present"]):
        return True
    return any((not c.isalnum()) and c not in env["struct"] for c in s)


def shared_spans(public, minlen=4):
    xs = [_text(x) for x, _ in public]
    if len(xs) < 2 or not all(xs):
        return []
    base = min(xs, key=len)
    found = set()
    for i in range(len(base)):
        for j in range(len(base), i + minlen - 1, -1):
            sub = base[i:j]
            if all(sub in s for s in xs):
                found.add(sub)
                break
    keep = [s for s in found if not any(s != o and s in o for o in found)]
    return sorted(keep)


def has_literal(prog):
    def walk(e):
        if isinstance(e, list) and e:
            if e[0] == "c" and len(e) > 1 and isinstance(e[1], str) and len(e[1]) >= 2:
                return True
            return any(walk(y) for y in e[1:])
        return False
    for t in prog:
        for k in ("f", "p"):
            if k in t and walk(t[k]):
                return True
        for k in ("v", "init"):
            if isinstance(t.get(k), str) and len(t[k]) >= 2:
                return True
    return False


def digit_literals_in_all_outputs(public, prog):
    """String literals of the program that contain a digit and occur in EVERY public output: a number the program writes as a
    constant (DateTime ':15' = minutes floored to a quarter in all three examples) instead of computing it from the input."""
    lits = []

    def walk(e):
        if isinstance(e, list) and e:
            if e[0] == "c" and len(e) > 1 and isinstance(e[1], str):
                lits.append(e[1])
            for y in e[1:]:
                walk(y)
    for t in prog or []:
        for k in ("f", "p"):
            if k in t:
                walk(t[k])
    outs = [_text(y) for _, y in public]
    return [s for s in lits if any(c.isdigit() for c in s) and all(s in o for o in outs)]


VARIANT = "V2"     # chosen on PROSE-dev + Split-dev + the 4 BURNED cases (scripts/w41_calibrate_guards.py); frozen


def label_inputs(public, prog, inputs, unique_flags, variant=None):
    """inputs: future inputs (query first); unique_flags: Checker v5's per-input uniqueness for each. Returns tiers.
    V0: ERROR + envelope (present and absent structural characters) + shared-span provenance; V1: V0 + digit-literal
    provenance; V2: V1 without the absent-character check; V3: ERROR only."""
    variant = variant or VARIANT
    env, spans, lit = envelope(public), shared_spans(public), has_literal(prog or [])
    dlit = variant in ("V1", "V2") and bool(digit_literals_in_all_outputs(public, prog))
    out = []
    for x, u in zip(inputs, unique_flags):
        a = L.run(prog, x) if prog else L.ERROR
        if a == L.ERROR:
            out.append("ABSTAIN_ERROR")
        elif variant != "V3" and _oos(x, env, variant):
            out.append("ABSTAIN_OUT_OF_SUPPORT")
        elif variant != "V3" and (dlit or (lit and any(sp not in _text(x) for sp in spans))):
            out.append("ABSTAIN_PROVENANCE")
        else:
            out.append("UNIQUE" if u else "NOT_UNIQUE")
    return out


def _oos(x, env, variant):
    if env is None:
        return False
    s = _text(x)
    if any(c not in s for c in env["present"]):
        return True
    if variant == "V2" or env.get("struct") is None:
        return False
    return any((not c.isalnum()) and c not in env["struct"] for c in s)
