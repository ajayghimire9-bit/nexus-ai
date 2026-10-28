"""Trial 1 - Model-X knockoff gate for learned items (NOT LOCKED).

Library arm: every candidate function f (from NEXUS's own solutions) gets a matched fake twin f~ with the same size, arity
and parameter types: each operator is replaced by a random operator of the same arity and type class (+ - * / among
themselves; < <= == among themselves; float/int among themselves); a body with no swappable operator gets its parameter
order permuted instead (permuted causal alignment). Real items and twins are evaluated side by side by the same measured
utility; W_j = utility(f_j) - utility(f~_j); the knockoff+ filter (Barber & Candes) admits {j : W_j >= T} with
T = min{t > 0 : (1 + #{W_j <= -t}) / max(1, #{W_j >= t}) <= q}."""
from __future__ import annotations

import random

ARITH, CMP, CAST = ("+", "-", "*", "/"), ("<", "<=", "=="), ("float", "int")


def twin(params, body, seed):
    rnd = random.Random(seed)
    changed = [False]

    def mut(n):
        if n[0] == "b" and n[1] in ARITH + CMP:
            pool = ARITH if n[1] in ARITH else CMP
            op = rnd.choice([o for o in pool if o != n[1]])
            changed[0] = True
            return ("b", op, mut(n[2]), mut(n[3]))
        if n[0] == "u" and n[1] in CAST:
            changed[0] = True
            return ("u", [o for o in CAST if o != n[1]][0], mut(n[2]))
        if n[0] in ("u", "b"):
            return (n[0], n[1]) + tuple(mut(c) for c in n[2:])
        return n
    b2 = mut(body)
    if not changed[0]:                                  # permuted causal alignment
        perm = list(params)
        while perm == list(params) and len(params) > 1:
            rnd.shuffle(perm)
        ren = dict(zip(params, perm))

        def sub(n):
            if n[0] == "var" and n[1] in ren:
                return ("var", ren[n[1]])
            if n[0] in ("var", "const"):
                return n
            return (n[0], n[1]) + tuple(sub(c) for c in n[2:])
        b2 = sub(body)
    return b2


def knockoff_plus(W, q):
    ts = sorted({abs(w) for w in W if w != 0})
    for t in ts:
        if (1 + sum(w <= -t for w in W)) / max(1, sum(w >= t for w in W)) <= q:
            return t, [j for j, w in enumerate(W) if w >= t]
    return None, []
