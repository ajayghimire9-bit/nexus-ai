"""Pillar 5 - the editable BASE learner L (NOT LOCKED).

L is data, not code paths: everything the u5 synthesis learner does differently from the uniform enumerator is in L
  op_cost     construction cost of every primitive operator (search heuristic / credit prior)
  leaf_cost   cost of variables, dictionary keys and numeric constants
  P, adapt    execution-guided delay scale; online failure memory on/off
  score       the affinity scoring program: an AST over the 11 execution features (residual, correlation, mutual
              information, ...) - the credit-assignment rule that decides which partial programs combine first
  lib         admitted library functions (abstraction admission result) and lib_cost
  per_task_s  the search budget split per task
Variation operators (AST edits) are below; the improver (meta_improver.py) chooses and accepts them. The evaluator, the
checker kernels and the budget meter are outside L and outside every improver's reach: an improver receives only a
`score(L, tasks)` callable that returns numbers."""
from __future__ import annotations

import copy
import random

from nexus import u5_construct as K
from nexus.oop_synthesizer import BINARY, UNARY

OPS = UNARY + BINARY
EDITS = ("const", "feat", "insert", "delete", "opcost", "leafcost", "P", "adapt", "lib_drop")
SCALAR_EDITS = ("const", "opcost", "leafcost", "P")


def from_config(cfg, lib=(), per_task_s=2.0):
    return dict(op_cost=dict(cfg["op_cost"]), leaf_cost=dict(cfg["leaf_cost"]), P=cfg["P"], adapt=cfg["adapt"],
                score=cfg.get("score_ast") or K.linear_ast(cfg["weights"], cfg["bias"]), lib=[tuple(x) for x in lib],
                lib_cost=dict(cfg.get("lib_cost", {})), per_task_s=per_task_s)


def to_config(L):
    cfg = K.default_config("exec")
    cfg.update(op_cost=dict(L["op_cost"]), leaf_cost=dict(L["leaf_cost"]), P=L["P"], adapt=L["adapt"], score_ast=L["score"],
               lib_cost=dict(L["lib_cost"]))
    return cfg, list(L["lib"])


# ------------------------------------------------------------------------------------------------ AST helpers
def _paths(n, path=()):
    out = [(path, n)]
    if n[0] in ("+", "*", "max"):
        out += _paths(n[1], path + (1,)) + _paths(n[2], path + (2,))
    elif n[0] == "neg":
        out += _paths(n[1], path + (1,))
    return out


def _replace(n, path, new):
    if not path:
        return new
    i = path[0]
    lst = list(n)
    lst[i] = _replace(n[i], path[1:], new)
    return tuple(lst)


def ast_size(n):
    return len(_paths(n))


# ------------------------------------------------------------------------------------------------ variation operators
def mutate(L, kind, rnd, sigma=0.3):
    """Apply one edit of the given kind; returns (L', description) or (None, why) if not applicable."""
    L = copy.deepcopy(L)
    if kind == "const":
        cs = [(p, n) for p, n in _paths(L["score"]) if n[0] == "c"]
        if not cs:
            return None, "no constant"
        p, n = rnd.choice(cs)
        v = n[1] * (1 + rnd.gauss(0, sigma)) + rnd.gauss(0, sigma * 0.5)
        L["score"] = _replace(L["score"], p, ("c", round(v, 4)))
        return L, f"const {n[1]:.3f}->{v:.3f}"
    if kind == "feat":
        fs = [(p, n) for p, n in _paths(L["score"]) if n[0] == "f"]
        if not fs:
            return None, "no feature"
        p, n = rnd.choice(fs)
        j = rnd.randrange(K.N_FEAT)
        L["score"] = _replace(L["score"], p, ("f", j))
        return L, f"feat {n[1]}->{j}"
    if kind == "insert":
        j = rnd.randrange(K.N_FEAT)
        op = rnd.choice(["+", "+", "max"])
        term = ("*", ("c", round(rnd.gauss(0, 1.5), 4)), ("f", j)) if op == "+" else ("f", j)
        L["score"] = (op, L["score"], term)
        return L, f"insert {op} f{j}"
    if kind == "delete":
        plus = [(p, n) for p, n in _paths(L["score"]) if n[0] in ("+", "max")]
        if not plus:
            return None, "nothing to delete"
        p, n = rnd.choice(plus)
        L["score"] = _replace(L["score"], p, n[rnd.choice([1, 2])])
        return L, "delete term"
    if kind == "opcost":
        op = rnd.choice(OPS)
        L["op_cost"][op] = max(1, min(4, L["op_cost"][op] + rnd.choice([-1, 1])))
        return L, f"opcost {op}={L['op_cost'][op]}"
    if kind == "leafcost":
        lf = rnd.choice(sorted(L["leaf_cost"]))
        L["leaf_cost"][lf] = max(1, min(3, L["leaf_cost"][lf] + rnd.choice([-1, 1])))
        return L, f"leafcost {lf}={L['leaf_cost'][lf]}"
    if kind == "P":
        L["P"] = max(0, min(6, L["P"] + rnd.choice([-1, 1])))
        return L, f"P={L['P']}"
    if kind == "adapt":
        L["adapt"] = not L["adapt"]
        return L, f"adapt={L['adapt']}"
    if kind == "lib_drop":
        if not L["lib"]:
            return None, "empty library"
        i = rnd.randrange(len(L["lib"]))
        fid = L["lib"][i][0]
        del L["lib"][i]
        return L, f"drop {fid}"
    raise KeyError(kind)


def score(L, tasks, per_task_s=None):
    """Improvement objective on a task sample (computed by the caller-provided evaluator path): solved tasks minus a CPU
    term. Returns (score, solved, cpu_s)."""
    cfg, lib = to_config(L)
    b = per_task_s or L["per_task_s"]
    solved, cpu = 0, 0.0
    for t in tasks:
        node, st, _ = K.solve(t.train, t.y_train, cfg, lib, b)
        solved += node is not None
        cpu += st["cpu_s"]
    return solved - 0.1 * cpu / max(1, len(tasks)) / b, solved, cpu
