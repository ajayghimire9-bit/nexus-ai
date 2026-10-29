"""MI-2 additions to LPL (NOT LOCKED; mi_lpl stays frozen with MI-1).

Milestone B call site. The MI-1/MI-2 discovery engine (the "improver": propose -> evaluate -> select) never invokes a learned
procedure: candidates are only ever scored, and proposals come from mi_lpl's generic operators. This module adds the ONE
connection through which an accepted, machine-generated procedure can influence later discovery:

    mutate_lib(prog, rnd, library, p_lib)  ->  (new program, edit description)

Contract. Input: a candidate program, an RNG, a LIBRARY (list of accepted procedures, each an LPL program as produced by an
earlier discovery and accepted by its validation gate; empty for the original improver) and p_lib. Output: a program in the
same language. With probability p_lib (and a non-empty library) the edit is LIBRARY INSERTION: a contiguous block of 1-4
non-`ret` statements is copied from a library procedure (helper calls inlined) and inserted at a random site of a random
body; otherwise the edit is exactly mi_lpl.mutate. With an empty library, mutate_lib == mi_lpl.mutate for every RNG state
(tested). Nothing else in the improver changes."""
from __future__ import annotations

import copy

from nexus import mi_lpl as LP


def _inline(body, helpers, depth=0):
    out = []
    for st in body:
        if st[0] == "call":
            if depth < 2 and st[1] in helpers:
                out += _inline(helpers[st[1]], helpers, depth + 1)
        elif st[0] == "repeat":
            out.append(("repeat", st[1], _inline(st[2], helpers, depth)))
        elif st[0] == "if_feat":
            out.append(st[:4] + (_inline(st[4], helpers, depth), _inline(st[5], helpers, depth)))
        elif st[0] != "ret":
            out.append(st)
    return out


def library_blocks(library):
    """Every contiguous block (1-4 statements) of every library procedure's main body, helpers inlined."""
    out = []
    for prog in library:
        body = _inline(prog["main"], prog.get("helpers", {}))
        for i in range(len(body)):
            for n in range(1, 5):
                if i + n <= len(body):
                    out.append(body[i:i + n])
    return out


def mutate_lib(prog, rnd, library=(), p_lib=0.0):
    if not library or p_lib <= 0:
        return LP.mutate(prog, rnd)
    if rnd.random() >= p_lib:
        return LP.mutate(prog, rnd)
    p = copy.deepcopy(prog)
    p.setdefault("helpers", {})
    blocks = library_blocks(library)
    blk = copy.deepcopy(rnd.choice(blocks))
    b = rnd.choice(LP._bodies(p))
    i = rnd.randint(0, max(0, len([s for s in b if s[0] != "ret"])))
    b[i:i] = blk
    return p, f"library_insert@{i} len {len(blk)}"
