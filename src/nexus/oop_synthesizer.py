"""Primitive-to-OOP program synthesis (NOT LOCKED). NEXUS writes Python functions and classes from foundational primitives
against input/output examples; nothing in this module names a data-engineering concept.

Primitives (the whole grammar; author-written, domain-free):
  terminals   the hole's argument variables; constants 0, 1, 2, 100 and the string / small-int values that occur in the
              examples (dict keys, categorical values, output labels)
  unary       float(x)  int(x)  str(x)  not x  isinstance-number(x)  isinstance-str(x)  x is None
  binary      x + y  x - y  x * y  x / y  x == y  x < y  x <= y  x in y  x and y  x or y  x.get(y)  round(x, k)
  control     if / else (conditional unification), bounded for-loops with an accumulator (folds; class methods)
  abstraction def fn_<id>(...) by anti-unification of repeated sub-programs; class StreamOrganelle_<id> with __init__ /
              ingest / retract / flush over dict / set / list state, synthesised ONLY when a Markov state violation shows
              that no pure function of a record reproduces the examples
Search: bottom-up enumeration by size with observational-equivalence collapse (one representative - the smallest - per
output vector on the examples, exceptions included), deductive decomposition of numeric targets through + - * / with
interval targets (tolerance-aware inverse semantics), conditional unification with greedy conjunctive predicate
learning, CEGIS rounds over the full example set. Every caller supplies only examples; the oracle is a black box."""
from __future__ import annotations

import hashlib
import json
import math
import time
from bisect import bisect_left, bisect_right

import numpy as np


class _Err:
    __slots__ = ()

    def __repr__(self):
        return "ERR"


ERR = _Err()
NUMT = (int, float)


def _isnum(x):
    return isinstance(x, NUMT) and not isinstance(x, bool)


def _canon(v):
    if v is ERR:
        return ("!",)
    if isinstance(v, bool):
        return ("b", v)
    if isinstance(v, int):
        return ("i", v)
    if isinstance(v, float):
        return ("f", round(v, 9)) if math.isfinite(v) else ("f", repr(v))
    if isinstance(v, (str, type(None))):
        return ("s", v)
    try:
        return ("j", json.dumps(v, sort_keys=True, default=str))
    except (TypeError, ValueError):
        return ("o", id(v))


# ------------------------------------------------------------------------------------------------ primitive semantics
def _u(op, x):
    if x is ERR:
        return ERR
    try:
        if op == "float":
            return float(x) if not isinstance(x, (dict, list, set, bool)) else ERR
        if op == "int":
            return int(x) if not isinstance(x, (dict, list, set, bool)) else ERR
        if op == "str":
            return str(x) if not isinstance(x, (dict, list, set)) else ERR
        if op == "not":
            return not x
        if op == "isnum":
            return _isnum(x)
        if op == "isstr":
            return isinstance(x, str)
        if op == "isnone":
            return x is None
    except (TypeError, ValueError, OverflowError):
        return ERR
    raise KeyError(op)


def _b(op, x, y):
    if op == "and":                                   # Python short-circuit semantics
        if x is ERR:
            return ERR
        return x if not x else y
    if op == "or":
        if x is ERR:
            return ERR
        return x if x else y
    if x is ERR or y is ERR:
        return ERR
    try:
        if op in ("+", "-", "*", "/"):
            if not (_isnum(x) and _isnum(y)):
                return ERR
            if op == "+":
                return x + y
            if op == "-":
                return x - y
            if op == "*":
                return x * y
            return x / y
        if op == "==":
            return x == y
        if op == "<":
            return x < y
        if op == "<=":
            return x <= y
        if op == "in":
            return x in y if isinstance(y, (dict, list, set, str, tuple)) else ERR
        if op == "get":
            return x.get(y) if isinstance(x, dict) else ERR
        if op == "round":
            return round(x, y) if _isnum(x) and isinstance(y, int) else ERR
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return ERR
    raise KeyError(op)


UNARY = ("float", "int", "str", "not", "isnum", "isstr", "isnone")
BINARY = ("get", "==", "in", "+", "-", "*", "/", "<", "<=", "and", "or")


def size(n):
    if n[0] in ("var", "const"):
        return 1
    return 1 + sum(size(c) for c in n[1:] if isinstance(c, tuple))


def ev(n, env):
    """Evaluate a node on one example environment (used for verification and for class simulation)."""
    k = n[0]
    if k == "var":
        return env.get(n[1], ERR)
    if k == "const":
        return n[1]
    if k == "u":
        return _u(n[1], ev(n[2], env))
    if k == "b":
        return _b(n[1], ev(n[2], env), ev(n[3], env) if n[1] not in ("and", "or") else _Lazy(n[3], env))
    if k == "if":
        p = ev(n[1], env)
        if p is ERR:
            return ERR
        return ev(n[2], env) if p else ev(n[3], env)
    if k == "fn":
        return ev(n[3], dict(zip(n[2], [ev(a, env) for a in n[4]])))
    raise KeyError(k)


class _Lazy:                                          # the right operand of and / or is evaluated only when needed
    __slots__ = ("n", "env")

    def __init__(self, n, env):
        self.n, self.env = n, env


def _force(v):
    return ev(v.n, v.env) if isinstance(v, _Lazy) else v


_b_raw = _b


def _b(op, x, y):                                     # noqa: F811  (wrap: force lazy operands)
    if op in ("and", "or"):
        if x is ERR:
            return ERR
        if op == "and":
            return x if not x else _force(y)
        return x if x else _force(y)
    return _b_raw(op, x, _force(y))


# ------------------------------------------------------------------------------------------------ source generation
def src(n, top=True):
    k = n[0]
    if k == "var":
        return n[1]
    if k == "const":
        return repr(n[1])
    if k == "u":
        a = src(n[2], False)
        return {"float": f"float({a})", "int": f"int({a})", "str": f"str({a})", "not": f"(not {a})",
                "isnum": f"(isinstance({a}, (int, float)) and not isinstance({a}, bool))", "isstr": f"isinstance({a}, str)",
                "isnone": f"({a} is None)"}[n[1]]
    if k == "b":
        a, b = src(n[2], False), src(n[3], False)
        if n[1] == "get":
            return f"{a}.get({b})"
        if n[1] == "round":
            return f"round({a}, {b})"
        return f"({a} {n[1]} {b})"
    if k == "if":
        return f"({src(n[2], False)} if {src(n[1], False)} else {src(n[3], False)})"
    if k == "fn":
        return f"{n[1]}({', '.join(src(a, False) for a in n[4])})"
    raise KeyError(k)


# ------------------------------------------------------------------------------------------------ the bank
class Bank:
    """Bottom-up enumeration by size; observational-equivalence collapse on the example inputs."""

    def __init__(self, inputs, consts=(), max_size=7, cap=6000, max_s=20.0):
        self.inputs, self.E = inputs, len(inputs)
        self.sig, self.entries = {}, []
        self.levels = {}
        t0 = time.process_time()
        vars_ = sorted({k for e in inputs for k in e})
        lv1 = [(("var", v), [e.get(v, ERR) for e in inputs]) for v in vars_]
        cs = list(dict.fromkeys(list(consts) + [0, 1, 2, 100]))
        lv1 += [(("const", c), [c] * self.E) for c in cs]
        self.levels[1] = [x for x in (self._add(n, vec) for n, vec in lv1) if x is not None]
        self.consts = cs
        for s in range(2, max_size + 1):
            out = []
            for a in self.levels.get(s - 1, []):
                for op in UNARY:
                    if self._unary_ok(op, a[1]):
                        r = self._add(("u", op, a[0]), [_u(op, x) for x in a[1]])
                        if r is not None:
                            out.append(r)
            for i in range(1, s - 1):
                L, R = self.levels.get(i, []), self.levels.get(s - 1 - i, [])
                for op in BINARY:
                    for a in L:
                        if not self._left_ok(op, a[1]):
                            continue
                        for b in R:
                            if len(out) >= cap or time.process_time() - t0 > max_s:
                                break
                            if not self._pair_ok(op, a, b):
                                continue
                            if op in ("and", "or"):
                                vec = [_b_raw(op, x, y) if x is not ERR and (x if op == "or" else not x) else
                                       (ERR if x is ERR else y) for x, y in zip(a[1], b[1])]
                            else:
                                vec = [_b_raw(op, x, y) for x, y in zip(a[1], b[1])]
                            r = self._add(("b", op, a[0], b[0]), vec)
                            if r is not None:
                                out.append(r)
            self.levels[s] = out
        self._num_index()

    def _add(self, n, vec):
        if all(v is ERR for v in vec):
            return None
        sg = tuple(_canon(v) for v in vec)
        if sg in self.sig:
            return None
        e = (n, vec, size(n))
        self.sig[sg] = e
        self.entries.append(e)
        return e

    @staticmethod
    def _unary_ok(op, vec):
        if op in ("float", "int"):
            return any(_isnum(v) or isinstance(v, str) for v in vec)
        if op == "not":
            return any(isinstance(v, bool) for v in vec)
        if op == "str":
            return any(_isnum(v) for v in vec)
        return True

    @staticmethod
    def _left_ok(op, vec):
        if op == "get":
            return any(isinstance(v, dict) for v in vec)
        if op in ("+", "-", "*", "/"):
            return any(_isnum(v) for v in vec)
        if op in ("and", "or"):
            return any(isinstance(v, bool) for v in vec)
        if op == "in":
            return all(not isinstance(v, (dict, list, set)) for v in vec if v is not ERR)
        return True

    @staticmethod
    def _pair_ok(op, a, b):
        av, bv = a[1], b[1]
        if op == "get":
            return a[0][0] != "const" and any(isinstance(v, (str, int)) and not isinstance(v, bool) for v in bv)
        if op in ("+", "-", "*", "/"):
            return any(_isnum(v) for v in bv) and not (a[0][0] == "const" and b[0][0] == "const")
        if op in ("and", "or"):
            return any(isinstance(v, bool) for v in bv)
        if op == "in":
            return any(isinstance(v, (dict, list, set)) for v in bv)
        if op in ("==", "<", "<="):
            if a[0][0] == "const":
                return False
            return op == "==" or b[0][0] == "const"
        return True

    def _num_index(self):
        num = [e for e in self.entries if all(_isnum(v) or v is ERR for v in e[1]) and any(_isnum(v) for v in e[1])]
        num.sort(key=lambda e: e[2])
        self.num = num
        self.M = np.array([[float(v) if _isnum(v) else np.nan for v in e[1]] for e in num]) if num else np.zeros((0, self.E))
        self._sorted = {}

    def _col(self, j):
        if j not in self._sorted:
            col = self.M[:, j]
            order = np.argsort(np.where(np.isnan(col), np.inf, col), kind="stable")
            self._sorted[j] = (order, col[order])
        return self._sorted[j]

    def num_lookup(self, lo, hi, mask, limit=1):
        """Numeric bank entries whose value lies in [lo, hi] on every masked example (smallest first)."""
        idx = np.flatnonzero(mask)
        if len(idx) == 0 or len(self.num) == 0:
            return []
        j = int(idx[0])
        order, vals = self._col(j)
        a, b = bisect_left(vals, lo[j]), bisect_right(vals, hi[j])
        if b <= a:
            return []
        cand = order[a:b]
        sub = self.M[np.ix_(cand, idx)]
        ok = np.all((sub >= lo[idx] - 1e-12) & (sub <= hi[idx] + 1e-12), axis=1)
        hits = [self.num[i] for i in cand[ok]]
        hits.sort(key=lambda e: e[2])
        return hits[:limit]


# ------------------------------------------------------------------------------------------------ solving
def _match(vec, target, mask, tol):
    for j in np.flatnonzero(mask):
        v, t = vec[j], target[j]
        if v is ERR:
            return False
        if _isnum(t) and _isnum(v) and not isinstance(t, bool):
            if abs(v - t) > tol(t):
                return False
        elif _canon(v) != _canon(t):
            return False
    return True


class Solver:
    def __init__(self, bank, target, tol=None, max_s=30.0):
        self.bank, self.target = bank, target
        self.tol = tol or (lambda t: 1e-9 * max(1.0, abs(t)))
        self.t0, self.max_s = time.process_time(), max_s
        self.numeric = all(_isnum(t) for t in target)

    def out_of_time(self):
        return time.process_time() - self.t0 > self.max_s

    def direct(self, mask):
        if self.numeric:
            lo, hi = self._interval(mask)
            h = self.bank.num_lookup(lo, hi, mask)
            if h:
                return h[0][0]
        best = None
        for n, vec, s in self.bank.entries:
            if (best is None or s < size(best)) and _match(vec, self.target, mask, self.tol):
                best = n
        return best

    def _interval(self, mask):
        t = np.array([float(x) if _isnum(x) else np.nan for x in self.target])
        w = np.array([self.tol(x) if _isnum(x) else 0.0 for x in self.target])
        return t - w, t + w

    def decompose(self, mask, depth=2, K=(160, 50)):
        """Deductive decomposition y = L op R with L from the bank and R solved recursively on interval targets."""
        lo, hi = self._interval(mask)
        return self._dec(lo, hi, mask, depth, K)

    def _dec(self, lo, hi, mask, depth, K):
        h = self.bank.num_lookup(lo, hi, mask)
        if h:
            return h[0][0]
        if depth == 0 or self.out_of_time():
            return None
        best = None
        idx = np.flatnonzero(mask)
        for e in self.bank.num[:K[0] if depth == 2 else K[1]]:
            if self.out_of_time():
                break
            Ls = np.array([float(v) if _isnum(v) else np.nan for v in e[1]])
            if np.any(np.isnan(Ls[idx])):
                continue
            opts = []
            with np.errstate(divide="ignore", invalid="ignore"):
                if np.all(Ls[idx] != 0):
                    a, b = lo / Ls, hi / Ls                       # y = L * R
                    opts.append(("*", True, np.minimum(a, b), np.maximum(a, b)))
                    a, b = lo * Ls, hi * Ls                       # y = R / L
                    opts.append(("/", False, np.minimum(a, b), np.maximum(a, b)))
                opts.append(("+", True, lo - Ls, hi - Ls))      # y = L + R
                opts.append(("-", True, Ls - hi, Ls - lo))      # y = L - R
                opts.append(("-", False, lo + Ls, hi + Ls))     # y = R - L
            for op, left, rlo, rhi in opts:
                if np.any(~np.isfinite(rlo[idx])) or np.any(~np.isfinite(rhi[idx])):
                    continue
                r = self._dec(rlo, rhi, mask, depth - 1, K)
                if r is None:
                    continue
                n = ("b", op, e[0], r) if left else ("b", op, r, e[0])
                if best is None or size(n) < size(best):
                    best = n
            if best is not None and size(best) <= e[2] + 4:
                break
        return best

    def solve(self, mask=None, depth_if=2):
        mask = np.ones(self.bank.E, bool) if mask is None else mask
        if not mask.any():
            return ("const", None)
        n = self.direct(mask)
        if n is None and self.numeric:
            n = self.decompose(mask)
        if n is not None or depth_if == 0 or self.out_of_time():
            return n
        if not self.numeric:
            d = self.decision_list(mask)
            if d is not None:
                return d
        best = None
        for e1, vec in self._cover_candidates(mask):
            cov = np.array([bool(mask[j]) and _match([vec[j]], [self.target[j]], np.ones(1, bool), self.tol)
                            for j in range(self.bank.E)])
            rest = mask & ~cov
            if not rest.any() or not cov.any():
                continue
            p = learn_predicate(self.bank, pos=rest, neg=cov)
            if p is None:
                continue
            e2 = self.solve(rest, depth_if - 1)
            if e2 is None:
                continue
            cand = ("if", p, e2, e1)
            if best is None or size(cand) < size(best):
                best = cand
            if self.out_of_time():
                break
        return best

    def decision_list(self, mask, max_labels=8):
        """Categorical targets: peel labels off rarest first, each with a predicate separating it from the examples still
        undecided; the most frequent label is the default (if / elif / else)."""
        labs = {}
        for j in np.flatnonzero(mask):
            labs.setdefault(_canon(self.target[j]), []).append(j)
        if len(labs) < 2 or len(labs) > max_labels:
            return None
        order = sorted(labs, key=lambda k: len(labs[k]))
        branches, left = [], mask.copy()
        for k in order[:-1]:
            pos = np.zeros(self.bank.E, bool)
            pos[labs[k]] = True
            p = learn_predicate(self.bank, pos=pos, neg=left & ~pos)
            if p is None:
                return None
            branches.append((p, ("const", self.target[labs[k][0]])))
            left = left & ~pos
        n = ("const", self.target[labs[order[-1]][0]])
        for p, e in reversed(branches):
            n = ("if", p, e, n)
        return n

    def _cover_candidates(self, mask, n_top=4):
        scored = []
        for n, vec, s in self.bank.entries:
            c = sum(1 for j in np.flatnonzero(mask) if vec[j] is not ERR and _match([vec[j]], [self.target[j]], np.ones(1, bool),
                                                                                       self.tol))
            if c:
                scored.append((-c, s, n, vec))
        if self.numeric:                                   # numeric targets: decomposed expressions also cover subsets
            for sub in _subsets_by_shape(self.bank, mask):
                d = self.decompose(sub)
                if d is not None:
                    vec = [ev(d, e) for e in self.bank.inputs]
                    c = sum(1 for j in np.flatnonzero(mask) if _match([vec[j]], [self.target[j]], np.ones(1, bool), self.tol))
                    scored.append((-c, size(d), d, vec))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [(n, vec) for _, _, n, vec in scored[:n_top]]


def _shape(x, depth=0):
    if isinstance(x, dict):
        if depth > 1:
            return ("d",)
        return ("d",) + tuple(sorted((k, _shape(v, depth + 1) if not isinstance(v, str) or len(x) > 6 else ("s", v))
                                     for k, v in x.items()))
    return (type(x).__name__,)


def _subsets_by_shape(bank, mask):
    groups = {}
    for j in np.flatnonzero(mask):
        groups.setdefault(json.dumps(_shape(bank.inputs[j]), default=str), []).append(j)
    out = []
    for js in sorted(groups.values(), key=len, reverse=True)[:4]:
        m = np.zeros(bank.E, bool)
        m[js] = True
        out.append(m)
    return out


def _cheapest_pair(P, alive, V, Er, C, okP, cand, n_first=120):
    """The cheapest a and b with a safe and true on P, b defined where a holds, (a and b) false on every alive negative."""
    best = None
    first = np.flatnonzero(cand)
    first = first[np.argsort(C[first])][:n_first]
    for i in first:
        al = alive & V[i]
        if not al.any():
            continue
        ok = okP & ~np.any(Er[:, al], axis=1) & ~np.any(V[:, al], axis=1)
        if ok.any():
            j = int(np.flatnonzero(ok)[np.argmin(C[ok])])
            c = C[i] + C[j]
            if best is None or c < best[2]:
                best = (int(i), j, c)
    return best


def learn_predicate(bank, pos, neg, max_conj=3):
    """Conjunctive predicate true on every pos example and false on every neg example, Python short-circuit safe (a later
    conjunct needs a defined value only where the earlier ones are true). Occam-first greedy: at each step the cheapest
    literal that rejects every remaining negative wins; otherwise the one rejecting most (cheaper on ties). The complement
    form not(conjunction) and guarded two-literal or / and combinations are tried as well. Vectorised over literals."""
    rows, nodes, cost = [], [], []
    for n, vec, s in bank.entries:
        if any(isinstance(v, bool) for v in vec):
            rows.append(vec)
            nodes.append(n)
            cost.append(s + 2 * _literal_compares(n))
    if not rows:
        return None
    err = np.array([[v is ERR for v in r] for r in rows])
    val = np.array([[bool(v) if v is not ERR else False for v in r] for r in rows])
    # negations
    nodes += [("u", "not", n) for n in nodes]
    cost = np.array(cost + [c + 1 for c in cost], float)
    err = np.vstack([err, err])
    val = np.vstack([val, ~val & ~err[: len(rows)]])

    def conj(P, N, V, Er, C, Nd):
        alive = N.copy()
        chosen = []
        okP = np.all(V[:, P], axis=1) if P.any() else np.ones(len(V), bool)
        for _ in range(max_conj):
            safe = okP & ~np.any(Er[:, alive], axis=1)
            kill = np.sum(~V[:, alive], axis=1)
            cand = safe & (kill > 0)
            if not cand.any():
                return None
            total = cand & (kill == alive.sum())
            if total.any():
                i = int(np.flatnonzero(total)[np.argmin(C[total])])
            elif len(chosen) + 2 <= max_conj and (pr := _cheapest_pair(P, alive, V, Er, C, okP, cand)) is not None:
                chosen += [Nd[pr[0]], Nd[pr[1]]]
                p = chosen[0]
                for c in chosen[1:]:
                    p = ("b", "and", p, c)
                return p
            else:
                ks = np.where(cand, kill - 1e-3 * C, -np.inf)
                i = int(np.argmax(ks))
            chosen.append(Nd[i])
            alive = alive & V[i]
            if not alive.any():
                p = chosen[0]
                for c in chosen[1:]:
                    p = ("b", "and", p, c)
                return p
        return None

    def best(V, Er, C, Nd):
        p = conj(pos, neg, V, Er, C, Nd)
        q = conj(neg, pos, V, Er, C, Nd)
        if q is not None and (p is None or size(q) + 1 < size(p)):
            return ("u", "not", q)
        return p

    r = best(val, err, cost, nodes)
    if r is not None:
        return r
    allm = pos | neg
    safe = np.flatnonzero(~np.any(err[:, allm], axis=1))
    safe = safe[np.argsort(cost[safe])][:K_PAIR]
    top = np.argsort(np.sum(err[:, allm], axis=1) + 1e-3 * cost)[:K_PAIR]
    V2, E2, C2, N2 = [val], [err], [cost], list(nodes)
    for op in ("or", "and"):
        for i in safe:
            vi, ei = val[i], err[i]
            gate = vi if op == "or" else ~vi                 # where the left operand decides
            V2.append(np.where(gate[None, :], vi[None, :], val[top]))
            E2.append(np.where(gate[None, :], False, err[top]))
            C2.append(cost[i] + cost[top] + 1)
            N2 += [("b", op, nodes[i], nodes[j]) for j in top]
    return best(np.vstack(V2), np.vstack(E2), np.concatenate(C2), N2)


K_PAIR = 40


def _literal_compares(n):
    if n[0] in ("var", "const"):
        return 0
    c = 1 if n[0] == "b" and n[1] in ("==", "<", "<=") and n[3][0] == "const" and isinstance(n[3][1], str) else 0
    return c + sum(_literal_compares(x) for x in n[1:] if isinstance(x, tuple))


def simplify(n):
    """not not x -> x; not (a and b) stays (it is the learnt complement form)."""
    if n[0] in ("var", "const"):
        return n
    if n[0] == "u" and n[1] == "not" and n[2][0] == "u" and n[2][1] == "not":
        return simplify(n[2][2])
    if n[0] == "if":
        return ("if",) + tuple(simplify(c) for c in n[1:])
    if n[0] == "fn":
        return n[:4] + (tuple(simplify(a) for a in n[4]),)
    return (n[0], n[1]) + tuple(simplify(c) if isinstance(c, tuple) else c for c in n[2:])


# ------------------------------------------------------------------------------------------------ holes
def _consts_from(examples, outputs):
    cs = []
    for e in examples:
        for v in e.values():
            if isinstance(v, dict):
                for k, x in v.items():
                    cs.append(k)
                    if isinstance(x, str) and len(x) <= 24:
                        cs.append(x)
    for y in outputs:
        if isinstance(y, str):
            cs.append(y)
    cnt = {}
    for c in cs:
        cnt[c] = cnt.get(c, 0) + 1
    return [c for c, _ in sorted(cnt.items(), key=lambda x: -x[1])][:60]


def stratified(examples, n, key=lambda e: e, labels=None):
    """Up to n examples covering every input shape (generic: dict keys, small categorical values, value types) and, for
    categorical outputs, every output value."""
    groups = {}
    cat = labels is not None and not all(_isnum(y) for y in labels)
    for i, e in enumerate(examples):
        g = [_shape(key(e))] + ([_canon(labels[i])] if cat else [])
        groups.setdefault(json.dumps(g, default=str), []).append(i)
    pick, r = [], 0
    while len(pick) < min(n, len(examples)):
        added = False
        for g in groups.values():
            if r < len(g) and len(pick) < n:
                pick.append(g[r])
                added = True
        if not added:
            break
        r += 1
    return sorted(pick)


def synthesize_scalar(examples, outputs, tol=None, sample=150, rounds=5, max_s=60.0, max_size=7):
    """A single expression (possibly with if/else) mapping each example env to its output. CEGIS over all examples."""
    t0 = time.process_time()
    pick = stratified(examples, sample, labels=outputs)
    stats = dict(rounds=0, bank=0, examples=len(examples))
    while True:
        stats["rounds"] += 1
        ins = [examples[i] for i in pick]
        outs = [outputs[i] for i in pick]
        bank = Bank(ins, _consts_from(ins, outs), max_size=max_size, max_s=max(1.0, (max_s - (time.process_time() - t0)) / 3))
        stats["bank"] = len(bank.entries)
        tl = tol
        if tl is None and all(_isnum(y) for y in outs):
            dec = max((len(repr(float(y)).split(".")[1]) if "." in repr(float(y)) else 0) for y in outs)
            tl = (lambda t: 0.005 + 1e-9) if dec <= 2 and any(isinstance(y, float) for y in outs) else None
        s = Solver(bank, outs, tol=tl, max_s=max(1.0, max_s - (time.process_time() - t0)))
        n = s.solve()
        if n is None:
            return None, stats
        n = simplify(_wrap_round(n, ins, outs))
        bad = [i for i in range(len(examples)) if not _eq(ev(n, examples[i]), outputs[i], tol)]
        if not bad:
            stats["cpu_s"] = round(time.process_time() - t0, 3)
            return n, stats
        if stats["rounds"] >= rounds or time.process_time() - t0 > max_s:
            stats["unsolved_examples"] = len(bad)
            return None, stats
        pick = sorted(set(pick) | set(bad[:40]))


def _eq(v, t, tol=None):
    if v is ERR:
        return False
    if _isnum(t) and _isnum(v):
        return abs(v - t) <= (tol(t) if tol else 1e-9 * max(1.0, abs(t)))
    return _canon(v) == _canon(t)


def _wrap_round(n, ins, outs):
    if not all(_isnum(y) for y in outs) or not any(isinstance(y, float) for y in outs):
        return n
    vals = [ev(n, e) for e in ins]
    if all(_eq(v, y) for v, y in zip(vals, outs)):
        return n
    for k in range(0, 6):
        r = ("b", "round", n, ("const", k))
        if all(_eq(ev(r, e), y) for e, y in zip(ins, outs)):
            return r
    return n


# ------------------------------------------------------------------------------------------------ anti-unification -> def
def _skeleton(n, params):
    if n[0] == "const" and isinstance(n[1], str):
        params.append(n)
        return ("hole",)
    if n[0] in ("var", "const"):
        return n
    return (n[0], n[1]) + tuple(_skeleton(c, params) if isinstance(c, tuple) else c for c in n[2:])


def _subtrees(n):
    yield n
    if n[0] in ("u", "b"):
        for c in n[2:]:
            yield from _subtrees(c)
    elif n[0] == "if":
        for c in n[1:]:
            yield from _subtrees(c)


def _vars(n):
    if n[0] == "var":
        return {n[1]}
    if n[0] == "const":
        return set()
    out = set()
    for c in n[1:]:
        if isinstance(c, tuple):
            out |= _vars(c)
    return out


def anti_unify(programs, min_size=4):
    """programs: {name: node}. Repeated sub-programs that differ only in string constants become one def fn_<id>(vars,
    c0..ck) (least general generalisation); every occurrence is rewritten to a call. Admitted only when the rewrite saves
    nodes. Returns (rewritten programs, [(def name, params, body)])."""
    occ = {}
    for name, n in programs.items():
        for t in _subtrees(n):
            if size(t) < min_size or t[0] == "if":
                continue
            ps = []
            sk = _skeleton(t, ps)
            if not ps:
                continue
            occ.setdefault(json.dumps(sk, default=str), []).append(t)
    defs, rewrite = [], {}
    for sk, ts in sorted(occ.items(), key=lambda x: (-len(x[1]), x[0])):
        uniq = {json.dumps(t, default=str): t for t in ts}
        if len(ts) < 2 or len(uniq) < 2:
            continue
        t0 = ts[0]
        vs = sorted(_vars(t0))
        ps = []
        _skeleton(t0, ps)
        params = vs + [f"c{i}" for i in range(len(ps))]
        it = iter(range(len(ps)))

        def body_of(n):
            if n[0] == "const" and isinstance(n[1], str):
                return ("var", f"c{next(it)}")
            if n[0] in ("var", "const"):
                return n
            return (n[0], n[1]) + tuple(body_of(c) if isinstance(c, tuple) else c for c in n[2:])
        body = body_of(t0)
        saved = sum(size(t) for t in ts) - (size(body) + sum(1 + len(params) for _ in ts))
        if saved <= 0:
            continue
        fid = "fn_" + hashlib.sha256(sk.encode()).hexdigest()[:8]
        defs.append((fid, params, body))
        for t in ts:
            cps = []
            _skeleton(t, cps)
            rewrite[json.dumps(t, default=str)] = ("fn", fid, tuple(params), body, tuple([("var", v) for v in vs] + cps))
    if not defs:
        return programs, []

    def rw(n):
        key = json.dumps(n, default=str)
        if key in rewrite:
            return rewrite[key]
        if n[0] in ("var", "const", "fn"):
            return n
        if n[0] == "if":
            return ("if",) + tuple(rw(c) for c in n[1:])
        return (n[0], n[1]) + tuple(rw(c) if isinstance(c, tuple) else c for c in n[2:])
    used = {}
    out = {name: rw(n) for name, n in programs.items()}

    def calls(n):
        if n[0] == "fn":
            used[n[1]] = True
            for a in n[4]:
                calls(a)
            return
        if n[0] in ("var", "const"):
            return
        for c in n[1:]:
            if isinstance(c, tuple):
                calls(c)
    for n in out.values():
        calls(n)
    return out, [d for d in defs if d[0] in used]


def def_source(fid, params, body):
    return f"def {fid}({', '.join(params)}):\n    return {src(body)}\n"


def function_source(fid, args, node, record_fields=None):
    """A hole program as a def. Record holes return a dict of per-field expressions; a top-level if/else of a scalar hole is
    emitted as statements."""
    head = f"def {fid}({', '.join(args)}):\n"
    if record_fields is not None:
        body = ",\n".join(f"        {f!r}: {src(node[f])}" for f in record_fields)
        return head + "    return {\n" + body + "\n    }\n"
    lines, n = [], node
    while n[0] == "if":
        lines.append(f"    {'if' if not lines else 'elif'} {src(n[1])}:\n        return {src(n[2])}\n")
        n = n[3]
    if lines:
        return head + "".join(lines) + f"    return {src(n)}\n"
    return head + f"    return {src(n)}\n"


def node_id(node):
    return hashlib.sha256(json.dumps(node, sort_keys=True, default=str).encode()).hexdigest()[:8]


# ------------------------------------------------------------------------------------------------ folds (bounded loops)
def synthesize_fold(examples, outputs, list_var, elem="x", acc="acc", max_size=5, bound=10 ** 6, max_s=20.0):
    """acc = init; for x in xs[:bound]: acc = step(acc, x). init from the constants, step from a bank over (acc, x) built on
    probe states drawn from the examples; verified by running the loop on every example."""
    t0 = time.process_time()
    probes = []
    for e in examples:
        for x in e[list_var][:8]:
            for a0 in (0.0, 1.0, 3.5):                   # varied accumulator states: OE must not merge acc + x with x
                probes.append({acc: a0, elem: x})
    inits = [0, 0.0, 1]
    bank = Bank(probes or [{acc: 0, elem: 0}], _consts_from(probes, []), max_size=max_size, max_s=max_s / 2)
    for init in inits:
        for n, vec, s in sorted(bank.entries, key=lambda e: e[2]):
            if time.process_time() - t0 > max_s:
                return None
            if acc not in _vars(n):
                continue
            ok = True
            for e, y in zip(examples, outputs):
                a = init
                for x in e[list_var][:bound]:
                    a = ev(n, {acc: a, elem: x})
                    if a is ERR:
                        break
                if not _eq(a, y):
                    ok = False
                    break
            if ok:
                return dict(init=init, step=n, list_var=list_var, elem=elem, acc=acc, bound=bound)
    return None


def fold_source(fid, args, f):
    return (f"def {fid}({', '.join(args)}):\n    {f['acc']} = {f['init']!r}\n"
            f"    for {f['elem']} in {f['list_var']}[:{f['bound']}]:\n        {f['acc']} = {src(f['step'])}\n    return {f['acc']}\n")


# ------------------------------------------------------------------------------------------------ classes (Markov violation)
def markov_violation(records_seqs, labels_seqs, ignore=()):
    """A witness that no pure function of a record reproduces the labels: two records with the same content (ignoring
    identity / position fields) and different labels, in the same or different histories. None when none exists."""
    seen = {}
    for rs, ls in zip(records_seqs, labels_seqs):
        for r, l in zip(rs, ls):
            k = json.dumps({a: b for a, b in r.items() if a not in ignore}, sort_keys=True, default=str)
            if k in seen and seen[k][1] != l:
                return dict(a=seen[k][0], b=r, labels=[seen[k][1], l])
            seen.setdefault(k, (r, l))
    return None


def synthesize_organelle(seqs, wanted, max_s=60.0, ignore=()):
    """seqs: list of record sequences (dicts, arrival order); wanted[i]: the set of output identities (tuples of field values
    over `identity`) the flush must produce for seqs[i]... expressed as a callable out_id(record). Tries a PURE filter first
    (no state); on a Markov violation enumerates state grammars: key field x order field x comparison x {tombstone flush
    filter, eager retract} with the delete predicate learned from the final states. Returns a spec dict or None."""
    t0 = time.process_time()
    want_sets, out_id = wanted
    flat = [r for s in seqs for r in s]
    fields = sorted({k for r in flat for k in r if not isinstance(r[k], (dict, list))})
    labels = [[out_id(r) in w for r in s] for s, w in zip(seqs, want_sets)]
    witness = markov_violation(seqs, labels, ignore=ignore)
    if witness is None:
        bank = Bank([{"r": r} for r in flat], _consts_from([{"r": r} for r in flat], []), max_size=6, max_s=10)
        lab = np.array([l for ls in labels for l in ls])
        p = learn_predicate(bank, pos=lab, neg=~lab)
        if p is not None:
            return dict(kind="pure_filter", keep=p, witness=None)
    numeric = [f for f in fields if all(_isnum(r.get(f)) for r in flat)]
    keyable = [f for f in fields if len({json.dumps(r.get(f), default=str) for r in flat}) < len(flat)]
    tried = 0
    for kf in keyable:
        for of in [None] + numeric:
            for cmp_ in ([">", ">="] if of else ["always"]):
                if time.process_time() - t0 > max_s:
                    return dict(kind="unsolved", witness=witness, tried=tried)
                base = dict(kind="organelle", key=kf, order=of, cmp=cmp_, mode="tombstone", witness=witness)
                finals = [_run_state(base, s) for s in seqs]
                st_recs = [r for f in finals for r in f.values()]
                if not st_recs:
                    continue
                lab = np.array([out_id(r) in w for f, w in zip(finals, want_sets) for r in f.values()])
                if lab.all():
                    drop = ("const", False)
                else:
                    ins = [{"r": r} for r in st_recs]
                    drop = learn_predicate(Bank(ins, _consts_from(ins, []), max_size=6, max_s=8), pos=~lab, neg=lab)
                    if drop is None:
                        continue
                for mode in ("tombstone", "eager"):
                    tried += 1
                    spec = dict(base, mode=mode, drop=drop)
                    if all(_flush_ok(spec, s, w, out_id) for s, w in zip(seqs, want_sets)):
                        spec["tried"] = tried
                        return spec
    return dict(kind="unsolved", witness=witness, tried=tried)


def _flush_ok(spec, seq, want, out_id):
    try:
        out = flush(spec, seq)
    except Exception:  # noqa: BLE001  - a candidate that raises is rejected
        return False
    ids = [json.dumps(r.get(spec["key"]), default=str) if spec.get("key") else json.dumps(out_id(r), default=str) for r in out]
    return {out_id(r) for r in out} == want and len(out) == len(set(ids))


def _gt(a, b, cmp_):
    if cmp_ == "always":
        return True
    if a is None or b is None:
        return False
    return a > b if cmp_ == ">" else a >= b


def _run_state(spec, seq):
    state = {}
    for r in seq:
        k = r.get(spec["key"])
        cur = state.get(k)
        if cur is None or _gt(r.get(spec["order"]) if spec["order"] else None, cur.get(spec["order"]) if spec["order"] else None,
                              spec["cmp"]):
            if spec["mode"] == "eager" and ev(spec["drop"], {"r": r}) is True:
                state.pop(k, None)
                continue
            state[k] = r
    return state


def flush(spec, seq):
    if spec["kind"] == "pure_filter":
        return [r for r in seq if ev(spec["keep"], {"r": r})]
    st = _run_state(spec, seq)
    if spec["mode"] == "tombstone":
        return [r for r in st.values() if ev(spec["drop"], {"r": r}) is False]
    return list(st.values())


def organelle_source(cid, spec, bound=10 ** 6):
    if spec["kind"] == "pure_filter":
        return (f"class StreamOrganelle_{cid}:\n    \"\"\"pure filter (no Markov violation found)\"\"\"\n\n"
                f"    def __init__(self):\n        self.rows = []\n\n    def ingest(self, r):\n        if {src(spec['keep'])}:\n"
                f"            self.rows.append(r)\n\n    def retract(self, k):\n        self.rows = [r for r in self.rows if r is not k]\n\n"
                f"    def flush(self):\n        return list(self.rows[:{bound}])\n")
    kf, of = spec["key"], spec["order"]
    cond = "True" if spec["cmp"] == "always" else f"r.get({of!r}) {spec['cmp']} cur.get({of!r})"
    w = spec.get("witness") or {}
    doc = (f"Markov state violation: identical record content, different required outcome "
           f"({json.dumps(w.get('labels'))}); state = dict keyed by {kf!r}, order {of!r} {spec['cmp']}, {spec['mode']}")
    ing = (f"    def ingest(self, r):\n        k = r.get({kf!r})\n        cur = self.state.get(k)\n"
           f"        if cur is None or {cond}:\n")
    if spec["mode"] == "eager":
        ing += f"            if {src(spec['drop'])}:\n                self.retract(k)\n                return\n"
    ing += "            self.state[k] = r\n"
    fl = (f"    def flush(self):\n        out = []\n        n = 0\n        for k in self.state:\n            n += 1\n"
          f"            if n > {bound}:\n                break\n            r = self.state[k]\n")
    fl += (f"            if not {src(spec['drop'])}:\n                out.append(r)\n" if spec["mode"] == "tombstone" else
           "            out.append(r)\n")
    fl += "        return out\n"
    return (f"class StreamOrganelle_{cid}:\n    \"\"\"{doc}\"\"\"\n\n    def __init__(self):\n        self.state = {{}}\n\n" + ing +
            f"\n    def retract(self, k):\n        self.state.pop(k, None)\n\n" + fl)
