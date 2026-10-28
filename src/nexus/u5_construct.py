"""Pillar 2 - construction search that observes programs while they are built (NOT LOCKED).

One engine, three construction policies (the 3-way dev comparison):
  baseline  every primitive costs 1: plain bottom-up enumeration by size with observational-equivalence (OE) collapse
  count     operator / leaf costs from counts of primitives in NEXUS's OWN earlier solutions (a learned PCFG, Probe-style)
  exec      count costs + an execution-guided penalty: every partial program is executed on the examples the moment it is
            built and scored against the target (CrossBeam-style partial execution) with
              - the error residual  D = Y_expected (-) Y_actual  (is it constant / proportional / zero?)
              - continuous affinity: |corr|, |corr| of logs, binned mutual information I(V; Y) / H(Y)
              - exception rate, exact-match rate, type agreement
            a logistic model over these features (fit on NEXUS's own solved src searches) gives an affinity a in [0, 1];
            a partial program is made available to later constructions after a delay of round(P * (1 - a)) cost levels
            (low-affinity values wait, high-affinity values combine first). Online failure memory: an operator whose
            recent constructions were mostly exceptions / OE duplicates costs one more level; the penalty scale P grows
            as the remaining budget shrinks.
All scoring CPU is inside the search's own CPU (charged). Library abstractions (Pillar 3) enter as k-ary operators."""
from __future__ import annotations

import math
import time
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict

import numpy as np

from nexus.oop_synthesizer import BINARY, ERR, UNARY, Bank, Solver, _b_raw, _canon, _isnum, _u, ev, size

N_FEAT = 11
FEAT_NAMES = ("ok_rate", "exact", "corr", "logcorr", "resid_add", "resid_mul", "mi", "is_num", "is_bool", "is_str", "const")


def _consts(envs):
    """String keys of the example dicts (and of dicts nested one level inside them)."""
    ks = []
    for e in envs:
        for top in e.values():
            if isinstance(top, dict):
                ks += [k for k in top if isinstance(k, str)]
                for v in top.values():
                    if isinstance(v, dict) and len(v) <= 6:
                        ks += [k for k in v if isinstance(k, str)]
    return list(dict.fromkeys(ks))


def _num(v):
    return _isnum(v) and math.isfinite(v)


def _bins(x, k=6):
    q = np.quantile(x, np.linspace(0, 1, k + 1)[1:-1])
    return np.searchsorted(q, x, side="right")


def _mi(a, b):
    """I(a; b) / H(b) for small integer-coded vectors."""
    n = len(a)
    ca, cb, cab = Counter(a), Counter(b), Counter(zip(a, b))
    hb = -sum(c / n * math.log(c / n) for c in cb.values())
    if hb <= 0:
        return 0.0
    i = sum(c / n * math.log((c / n) / (ca[x] / n * cb[y] / n)) for (x, y), c in cab.items())
    return max(0.0, min(1.0, i / hb))


class Target:
    def __init__(self, ys):
        self.ys = ys
        self.kind = "bool" if all(isinstance(y, bool) for y in ys) else "num" if all(_num(y) for y in ys) else "other"
        if self.kind == "num":
            self.arr = np.array(ys, dtype=float)
            self.code = _bins(self.arr)
            self.tol = np.maximum(1.0, np.abs(self.arr)) * 1e-6
            la = np.log(np.abs(self.arr) + 1e-12)
            self.log = la
        else:
            m = {}
            self.code = np.array([m.setdefault(_canon(y), len(m)) for y in ys])

    def match(self, vec):
        if self.kind == "num":
            for v, y, t in zip(vec, self.ys, self.tol):
                if not _num(v) or isinstance(v, bool) or abs(v - y) > t:
                    return False
            return True
        if self.kind == "bool":
            return all(v is y for v, y in zip(vec, self.ys))
        return all(v is not ERR and _canon(v) == _canon(y) for v, y in zip(vec, self.ys))

    def features(self, vec):
        n = len(vec)
        ok = [v is not ERR for v in vec]
        okr = sum(ok) / n
        f = np.zeros(N_FEAT)
        f[0] = okr
        isn = all(_num(v) and not isinstance(v, bool) for v in vec)
        isb = all(isinstance(v, bool) for v in vec)
        iss = all(isinstance(v, str) for v in vec)
        f[7], f[8], f[9] = isn, isb, iss
        if okr == 0:
            return f
        sig = [_canon(v) for v in vec]
        f[10] = len(set(sig)) == 1
        if self.kind == "num" and isn:
            x = np.array(vec, dtype=float)
            f[1] = float(np.mean(np.abs(x - self.arr) <= self.tol))
            if x.std() > 0 and self.arr.std() > 0:
                f[2] = abs(float(np.corrcoef(x, self.arr)[0, 1]))
                lx = np.log(np.abs(x) + 1e-12)
                if lx.std() > 0 and self.log.std() > 0:
                    f[3] = abs(float(np.corrcoef(lx, self.log)[0, 1]))
                r = self.arr - x
                f[4] = 1.0 / (1.0 + float(r.std()) / (float(self.arr.std()) + 1e-12))
                with np.errstate(divide="ignore", invalid="ignore"):
                    q = self.arr / x
                if np.all(np.isfinite(q)):
                    f[5] = 1.0 / (1.0 + float(q.std()) / (abs(float(q.mean())) + 1e-12))
            f[6] = _mi(_bins(x), self.code) if x.std() > 0 else 0.0
        else:
            m = {}
            code = np.array([m.setdefault(s, len(m)) for s in sig])
            f[6] = _mi(code, self.code) if len(m) > 1 else 0.0
            if self.kind == "bool" and isb:
                f[1] = float(np.mean([v is y for v, y in zip(vec, self.ys)]))
        return f


def eval_score(n, f):
    """Affinity score expression (an editable AST, Pillar 5): ("f", i) feature, ("c", v) constant, ("+"|"*"|"max", a, b),
    ("neg", a)."""
    k = n[0]
    if k == "f":
        return float(f[n[1]])
    if k == "c":
        return n[1]
    if k == "neg":
        return -eval_score(n[1], f)
    a, b = eval_score(n[1], f), eval_score(n[2], f)
    return a + b if k == "+" else a * b if k == "*" else max(a, b)


def linear_ast(weights, bias):
    n = ("c", float(bias))
    for i, w in enumerate(weights):
        if w:
            n = ("+", n, ("*", ("c", float(w)), ("f", i)))
    return n


def default_config(policy="exec"):
    return dict(policy=policy, op_cost={op: 1 for op in UNARY + BINARY}, leaf_cost=dict(var=1, key=1, num=1),
                weights=[0.0] * N_FEAT, bias=0.0, P=3, adapt=True, max_level=40, cap=60000, lib_cost={})


class Search:
    """Cost-ordered bottom-up construction. Each entry: (node, vec, syn_size, level)."""

    def __init__(self, envs, ys, cfg, lib=(), budget_s=4.0):
        self.envs, self.E, self.cfg, self.lib = envs, len(envs), cfg, list(lib)
        self.tg = Target(ys)
        self.budget, self.t0 = budget_s, time.process_time()
        self.sig = {}
        self.buckets = defaultdict(list)
        self.n_built = self.n_dup = self.n_err = self.n_scored = 0
        self.fail = Counter()
        self.made = Counter()
        self.sol = None
        self.exec = cfg["policy"] == "exec"
        self.w = np.array(cfg["weights"], dtype=float)
        self.solution_level = None

    # -------------------------------------------------------------- bookkeeping
    def left(self):
        return self.budget - (time.process_time() - self.t0)

    def _cost(self, op):
        c = self.cfg["op_cost"].get(op, 1) if op in self.cfg["op_cost"] else self.cfg["lib_cost"].get(op, 2)
        if self.cfg.get("adapt") and self.exec and self.made[op] >= 50 and self.fail[op] / self.made[op] > 0.9:
            c += 1                                                    # online failure memory
        return c

    def _pen(self, vec):
        if not self.exec or self.cfg["P"] <= 0 or any(isinstance(v, (dict, list, set)) for v in vec):
            return 0
        self.n_scored += 1
        f = self.tg.features(vec)
        z = eval_score(self.cfg["score_ast"], f) if self.cfg.get("score_ast") else float(self.w @ f) + self.cfg["bias"]
        a = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
        frac_left = max(0.0, self.left() / self.budget)
        P = self.cfg["P"] * (1.0 + (1.0 - frac_left))                # greedier as the budget runs out
        return int(round(P * (1.0 - a)))

    def _add(self, node, vec, syn, level, op):
        self.n_built += 1
        self.made[op] += 1
        if all(v is ERR for v in vec):
            self.n_err += 1
            self.fail[op] += 1
            return None
        sg = tuple(_canon(v) for v in vec)
        if sg in self.sig:
            self.n_dup += 1
            self.fail[op] += 1
            return None
        e = (node, vec, syn, level)
        self.sig[sg] = e
        if self.tg.match(vec):
            self.sol = node
            self.solution_level = level
            return e
        self.buckets[level + self._pen(vec)].append(e)
        return e

    # -------------------------------------------------------------- search
    def run(self):
        lc = self.cfg["leaf_cost"]
        for v in sorted({k for e in self.envs for k in e}):
            self._add(("var", v), [e.get(v, ERR) for e in self.envs], 1, lc["var"], "var")
        for c in _consts(self.envs):
            self._add(("const", c), [c] * self.E, 1, lc["key"], "key")
        for c in (0, 1, 2, 100):
            self._add(("const", c), [c] * self.E, 1, lc["num"], "num")
        if self.sol is not None:
            return self.sol
        for level in range(2, self.cfg["max_level"] + 1):
            self._level(level)
            if self.sol is not None or self.left() <= 0 or len(self.sig) >= self.cfg["cap"]:
                break
        return self.sol

    def _stop(self):
        return self.sol is not None or len(self.sig) >= self.cfg["cap"] or (self.n_built & 255 == 0 and self.left() <= 0)

    def _level(self, c):
        B = self.buckets
        for op in UNARY:
            co = self._cost(op)
            for a in list(B.get(c - co, [])):
                if Bank._unary_ok(op, a[1]):
                    self._add(("u", op, a[0]), [_u(op, x) for x in a[1]], a[2] + 1, c, op)
                    if self._stop():
                        return
        for op in BINARY:
            co = self._cost(op)
            for i in range(1, c - co):
                L, R = B.get(i, []), B.get(c - co - i, [])
                if not L or not R:
                    continue
                for a in list(L):
                    if not Bank._left_ok(op, a[1]):
                        continue
                    for b in list(R):
                        if not Bank._pair_ok(op, a, b):
                            continue
                        if op in ("and", "or"):
                            vec = [_b_raw(op, x, y) if x is not ERR and (x if op == "or" else not x) else
                                   (ERR if x is ERR else y) for x, y in zip(a[1], b[1])]
                        else:
                            vec = [_b_raw(op, x, y) for x, y in zip(a[1], b[1])]
                        self._add(("b", op, a[0], b[0]), vec, a[2] + b[2] + 1, c, op)
                        if self._stop():
                            return
        for fid, params, body in self.lib:
            co = self._cost(fid)
            k = len(params)
            for parts in _compositions(c - co, k):
                pools = [B.get(p, []) for p in parts]
                if not all(pools):
                    continue
                for args in _product(pools):
                    vec = []
                    for j in range(self.E):
                        vals = [a[1][j] for a in args]
                        vec.append(ERR if any(v is ERR for v in vals) else _safe_ev(body, dict(zip(params, vals))))
                    self._add(("fn", fid, tuple(params), body, tuple(a[0] for a in args)), vec, sum(a[2] for a in args) + 1, c, fid)
                    if self._stop():
                        return

    def stats(self):
        return dict(cpu_s=round(time.process_time() - self.t0, 4), built=self.n_built, kept=len(self.sig), dup=self.n_dup,
                    err=self.n_err, scored=self.n_scored, solved=self.sol is not None, level=self.solution_level,
                    size=size(self.sol) if self.sol is not None else None)


def _safe_ev(body, env):
    try:
        return ev(body, env)
    except Exception:                                                  # noqa: BLE001
        return ERR


def _compositions(n, k):
    if k == 1:
        if n >= 1:
            yield (n,)
        return
    for i in range(1, n - k + 2):
        for rest in _compositions(n - i, k - 1):
            yield (i,) + rest


def _product(pools, cap=4000):
    out = [()]
    for p in pools:
        out = [o + (x,) for o in out for x in p]
        if len(out) > cap:
            out = out[:cap]
    return out


def solve(task_envs, ys, cfg, lib=(), budget_s=4.0):
    s = Search(task_envs, ys, cfg, lib, budget_s)
    node = s.run()
    return node, s.stats(), s


class _Bank(Bank):
    """Bank with RELATIVE lookup slack (e2e dev revision 1). oop_synthesizer.Bank.num_lookup pads intervals by an absolute
    1e-12; after decomposition divides by a huge left factor (timestamps x 100 ~ 1e11) the interval is ~1e-15 wide and the
    pad admits wrong programs (found on pdev 8010: (p * (p - p)) accepted as y / p). Phase 1's module is not edited."""

    def num_lookup(self, lo, hi, mask, limit=1):
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
        slo, shi = lo[idx], hi[idx]
        eps = 1e-12 * np.maximum(1e-300, np.maximum(np.abs(slo), np.abs(shi)))
        ok = np.all((sub >= slo - eps) & (sub <= shi + eps), axis=1)
        hits = [self.num[i] for i in cand[ok]]
        hits.sort(key=lambda e: e[2])
        return hits[:limit]


class _Solver(Solver):
    """oop_synthesizer.Solver with a float-precision guard (e2e dev revision 1): a decomposition whose sub-target interval
    has collapsed below float resolution (e.g. p - R with p ~ 1e11 and |R| ~ 1e-9 rounds to [p, p]) is skipped, because any
    program then 'matches' by cancellation (pdev 8010 accepted p * (p - p) == 0 for y ~ 1e2). Otherwise identical."""

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
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                if np.all(Ls[idx] != 0):
                    a, b = lo / Ls, hi / Ls
                    opts.append(("*", True, np.minimum(a, b), np.maximum(a, b)))
                    a, b = lo * Ls, hi * Ls
                    opts.append(("/", False, np.minimum(a, b), np.maximum(a, b)))
                opts.append(("+", True, lo - Ls, hi - Ls))
                opts.append(("-", True, Ls - hi, Ls - lo))
                opts.append(("-", False, lo + Ls, hi + Ls))
            for op, left, rlo, rhi in opts:
                if np.any(~np.isfinite(rlo[idx])) or np.any(~np.isfinite(rhi[idx])):
                    continue
                w, m = rhi[idx] - rlo[idx], np.maximum(np.abs(rlo[idx]), np.abs(rhi[idx]))
                if np.any(w <= 1e-12 * np.maximum(1.0, m)):
                    continue                                              # collapsed by cancellation: no evidence
                r = self._dec(rlo, rhi, mask, depth - 1, K)
                if r is None:
                    continue
                n = ("b", op, e[0], r) if left else ("b", op, r, e[0])
                if best is None or size(n) < size(best):
                    best = n
            if best is not None and size(best) <= e[2] + 4:
                break
        return best


def solve_hybrid(envs, ys, cfg, lib=(), budget_s=4.0, construct_frac=0.6):
    """Deployment solver: the construction policy runs first (direct matches); if unsolved, the Phase 1 deductive
    decomposition / decision-list solver (oop_synthesizer.Solver, unchanged) runs over the bank THIS construction built.
    The construction policy therefore decides which partial programs decomposition can use."""
    t0 = time.process_time()
    node, st, s = solve(envs, ys, cfg, lib, budget_s * construct_frac)
    st = dict(st, stage="construct")
    if node is None:
        bank = _Bank.__new__(_Bank)
        bank.inputs, bank.E, bank.sig = envs, len(envs), {}
        bank.entries = [(e[0], e[1], e[2]) for e in s.sig.values()]
        bank.levels, bank.consts = {}, []
        bank._num_index()
        tg = Target(ys)
        tol = (lambda t: 1e-6 * max(1.0, abs(t))) if tg.kind == "num" else None
        sv = _Solver(bank, ys, tol=tol, max_s=max(0.2, budget_s - (time.process_time() - t0)))
        try:
            cand = sv.solve()
        except RecursionError:
            cand = None
        if cand is not None and all(_ok(_safe_ev(cand, e), y) for e, y in zip(envs, ys)):
            node = cand
            st["stage"] = "decompose"
    st.update(cpu_s=round(time.process_time() - t0, 4), solved=node is not None, size=size(node) if node is not None else None)
    return node, st, s


def _ok(v, y):
    if v is ERR:
        return False
    if isinstance(y, bool) or isinstance(v, bool):
        return v is y
    if _num(y) and _num(v):
        return abs(v - y) <= 1e-6 * max(1.0, abs(y))
    return _canon(v) == _canon(y)


# ------------------------------------------------------------------------------------------------ learning the policies
def _subtree_sigs(node, envs):
    out = set()

    def walk(n):
        if n[0] in ("var", "const"):
            pass
        for c in n[1:]:
            if isinstance(c, tuple):
                walk(c)
        out.add(tuple(_canon(_safe_ev(n, e)) for e in envs))
    walk(node)
    return out


def op_counts(nodes):
    c = Counter()

    def walk(n):
        k = n[0]
        if k == "u" or k == "b":
            c[n[1]] += 1
        elif k == "fn":
            c[n[1]] += 1
            for a in n[4]:
                walk(a)
            return
        for ch in n[1:]:
            if isinstance(ch, tuple):
                walk(ch)
    for n in nodes:
        walk(n)
    return c


def count_costs(nodes, ops=UNARY + BINARY, alpha=1.0, max_cost=3):
    """PCFG costs from NEXUS's own solved programs: cost(op) = 1 + round(alpha * (-log2 p(op) - min))."""
    c = op_counts(nodes)
    tot = sum(c[o] + 0.5 for o in ops)
    nl = {o: -math.log2((c[o] + 0.5) / tot) for o in ops}
    m = min(nl.values())
    return {o: int(min(max_cost, 1 + round(alpha * (nl[o] - m) / 2))) for o in ops}


def affinity_samples(s, node, max_neg=1500, seed=0):
    """(features, label) rows from one of NEXUS's own solved searches: was this built partial program (OE class) a
    sub-program of the search's own solution? Negatives are subsampled (memory); no reference programs are used."""
    import random as _r
    pos = _subtree_sigs(node, s.envs)
    P, N = [], []
    for sg, e in s.sig.items():
        if any(isinstance(v, (dict, list, set)) for v in e[1]):
            continue
        (P if sg in pos else N).append(e[1])
    _r.Random(seed).shuffle(N)
    rows = [(s.tg.features(v), 1.0) for v in P] + [(s.tg.features(v), 0.0) for v in N[:max_neg]]
    return rows


def fit_affinity(searches_with_solutions, l2=1.0, iters=300, lr=0.5):
    return fit_affinity_xy([r for s, n in searches_with_solutions for r in affinity_samples(s, n)], l2, iters, lr)


def fit_affinity_xy(rows, l2=1.0, iters=300, lr=0.5):
    """Class-balanced logistic regression on affinity samples."""
    X = [f for f, _ in rows]
    y = [l for _, l in rows]
    if not X or sum(y) == 0:
        return [0.0] * N_FEAT, 0.0
    X, y = np.array(X), np.array(y)
    pw = (len(y) - y.sum()) / max(1.0, y.sum())                         # class balance
    sw = np.where(y > 0, pw, 1.0)
    w, b = np.zeros(X.shape[1]), 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w + b)))
        g = (p - y) * sw
        w -= lr * (X.T @ g / sw.sum() + l2 * w / len(y))
        b -= lr * g.sum() / sw.sum()
    return [round(float(v), 4) for v in w], round(float(b), 4)
