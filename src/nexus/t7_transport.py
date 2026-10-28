"""Trial 4 - skill transport across schemas / domains without name matching (NOT LOCKED; numpy, CPU).

Column spectrum (name-free, 4-D):  alpha = log(#distinct) / log(n)  (cardinality exponent);  tau = mean distance between
repeats of a value / n  (recurrence horizon);  Gamma = 1 - H(value histogram) / log(#bins)  (entropy collapse);
mu = fraction of increasing successive pairs  (monotonicity).  Relational geometry between columns: |Spearman rank
correlation| (scale-free; unaffected by unit shifts or epoch-ms switches).
Fused Gromov-Wasserstein (entropic, Sinkhorn projections): minimise (1-a) <C_feat, T> + a * sum (D_A(i,k) - D_B(j,l))^2
T_ij T_kl over couplings T; the column map phi = argmax_j T. Baselines: name matching (difflib), strong heuristic map
(per-column mean / std / min / max / log-scale z-distance, Hungarian), HDC map (random-projection hypervectors of
normalised quantile profiles, cosine), random map."""
from __future__ import annotations

import difflib
import math
import random

import numpy as np


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def columns(envs):
    """Numeric / categorical record columns -> value lists (the record 'r' of each env)."""
    names = sorted({k for e in envs for k in e["r"]})
    return {k: [e["r"].get(k) for e in envs] for k in names}


def spectrum(vals):
    n = len(vals)
    reps = [repr(v) for v in vals]
    d = len(set(reps))
    alpha = math.log(max(d, 1)) / math.log(max(n, 2))
    last, gaps = {}, []
    for i, r in enumerate(reps):
        if r in last:
            gaps.append(i - last[r])
        last[r] = i
    tau = (sum(gaps) / len(gaps) / n) if gaps else 1.0
    if all(_num(v) for v in vals):
        x = np.array(vals, float)
        h, _ = np.histogram(x, bins=10)
        mu = float(np.mean(np.diff(x) > 0)) if n > 1 else 0.0
    else:
        from collections import Counter
        h = np.array(list(Counter(reps).values()), float)
        mu = 0.0
    p = h[h > 0] / h.sum()
    gamma = 1 - float(-(p * np.log(p)).sum()) / math.log(max(2, len(h)))
    return np.array([alpha, tau, gamma, mu])


def _ranks(vals):
    if not all(_num(v) for v in vals):
        m = {}
        vals = [m.setdefault(repr(v), len(m)) for v in vals]
    return np.argsort(np.argsort(np.array(vals, float))).astype(float)


def relational(cols):
    ks = list(cols)
    R = np.array([_ranks(cols[k]) for k in ks])
    D = np.zeros((len(ks), len(ks)))
    for i in range(len(ks)):
        for j in range(len(ks)):
            if R[i].std() > 0 and R[j].std() > 0:
                D[i, j] = abs(np.corrcoef(R[i], R[j])[0, 1])
    return D


def fgw(Cf, DA, DB, a=0.5, eps=0.05, iters=60):
    """Entropic fused GW (square loss) by projected mirror descent with Sinkhorn projections (uniform marginals)."""
    n, m = Cf.shape
    p, q = np.ones(n) / n, np.ones(m) / m
    T = np.outer(p, q)
    constC = (DA ** 2) @ p[:, None] @ np.ones((1, m)) + np.ones((n, 1)) @ q[None, :] @ (DB ** 2).T
    for _ in range(iters):
        G = (1 - a) * Cf + a * (constC - 2 * DA @ T @ DB.T)
        K = np.exp(-(G - G.min()) / eps)
        u = np.ones(n)
        for _ in range(50):
            v = q / (K.T @ u + 1e-300)
            u = p / (K @ v + 1e-300)
        T = u[:, None] * K * v[None, :]
    return T


def _assign(C):
    """Hungarian-free greedy assignment (small matrices): repeatedly take the global minimum."""
    C = C.copy()
    out = {}
    for _ in range(min(C.shape)):
        i, j = np.unravel_index(np.argmin(C), C.shape)
        out[i] = j
        C[i, :] = np.inf
        C[:, j] = np.inf
    return out


def map_gw(colsB, colsA):
    kb, ka = list(colsB), list(colsA)
    SB = np.array([spectrum(colsB[k]) for k in kb])
    SA = np.array([spectrum(colsA[k]) for k in ka])
    Cf = ((SB[:, None, :] - SA[None, :, :]) ** 2).sum(-1)
    T = fgw(Cf, relational(colsB), relational(colsA))
    asg = _assign(-T)
    return {kb[i]: ka[j] for i, j in asg.items()}


def map_names(colsB, colsA):
    kb, ka = list(colsB), list(colsA)
    C = np.array([[1 - difflib.SequenceMatcher(None, b, a).ratio() for a in ka] for b in kb])
    return {kb[i]: ka[j] for i, j in _assign(C).items()}


def _stats(vals):
    if not all(_num(v) for v in vals):
        return np.array([0, 0, 0, 0, len(set(map(repr, vals))) / len(vals)])
    x = np.array(vals, float)
    return np.array([x.mean(), x.std(), x.min(), x.max(), len(set(vals)) / len(vals)])


def map_heuristic(colsB, colsA):
    kb, ka = list(colsB), list(colsA)
    SB, SA = np.array([_stats(colsB[k]) for k in kb]), np.array([_stats(colsA[k]) for k in ka])
    allS = np.vstack([SB, SA])
    mu, sd = allS.mean(0), allS.std(0) + 1e-9
    C = ((((SB - mu) / sd)[:, None, :] - ((SA - mu) / sd)[None, :, :]) ** 2).sum(-1)
    return {kb[i]: ka[j] for i, j in _assign(C).items()}


def _hv(vals, P):
    if all(_num(v) for v in vals):
        x = np.array(vals, float)
        q = np.quantile(x, np.linspace(0, 1, 16))
        q = (q - q.mean()) / (q.std() + 1e-9)
    else:
        q = np.zeros(16)
        q[0] = len(set(map(repr, vals))) / len(vals)
    return np.sign(P @ q)


def map_hdc(colsB, colsA, seed=0):
    P = np.random.RandomState(seed).randn(2048, 16)
    kb, ka = list(colsB), list(colsA)
    HB, HA = np.array([_hv(colsB[k], P) for k in kb]), np.array([_hv(colsA[k], P) for k in ka])
    C = -(HB @ HA.T)
    return {kb[i]: ka[j] for i, j in _assign(C).items()}


def map_random(colsB, colsA, seed=0):
    kb, ka = list(colsB), list(colsA)
    rnd = random.Random(seed)
    perm = rnd.sample(ka, len(ka)) + ka
    return {b: perm[i] for i, b in enumerate(kb)}


def transport(node, phi_inv):
    """Rename field reads r.get(A-name) -> r.get(B-name)."""
    if node[0] == "b" and node[1] == "get" and node[2] == ("var", "r") and node[3][0] == "const" and node[3][1] in phi_inv:
        return ("b", "get", ("var", "r"), ("const", phi_inv[node[3][1]]))
    if node[0] in ("var", "const"):
        return node
    return tuple(transport(c, phi_inv) if isinstance(c, tuple) else c for c in node)


def as_function(node):
    """g_A as a library function: each distinct field read r.get(k) becomes a parameter (for Delta-M invention)."""
    fields = []

    def sub(n):
        if n[0] == "b" and n[1] == "get" and n[2] == ("var", "r") and n[3][0] == "const":
            if n[3][1] not in fields:
                fields.append(n[3][1])
            return ("var", f"p{fields.index(n[3][1])}")
        if n[0] in ("var", "const"):
            return n
        return tuple(sub(c) if isinstance(c, tuple) else c for c in n)
    body = sub(node)
    params = [f"p{i}" for i in range(len(fields))] + (["t"] if "t" in _vars(body) else [])
    return ("fn_T", params, body) if 0 < len(params) <= 3 else None


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
