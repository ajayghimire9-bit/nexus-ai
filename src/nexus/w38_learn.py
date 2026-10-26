"""Wave 38 learned knowledge (SOLVER SIDE; NOT LOCKED). Everything here is fitted only on CHECKER-CERTIFIED solutions.

Abstraction key: a tool with its field names -> F, delimiters -> D, colours -> C (op and lambda shape kept), so experience can
cross domains. A prior is a function cost(prev_key, key) used by w38_search's lazy best-first proposal:
  learned  : p = lam * p_key(bigram over abstract keys) + (1 - lam) * p_op(bigram over ops) / |keys with that op|  (smoothed)
  repr     : learned statistics ONLY for the encoder (first) and decoder (last) positions; uniform elsewhere (experiment 1)
  placebo  : the learned tables with abstract-key identities permuted (size- and shape-matched)
  fixed    : a hand-designed, non-learned 'encode -> transform -> aggregate' preference (category (d), the richer fixed DSL)
  uniform  : Fresh
Neural ranker (experiment 7): a small MLP over (prev op, candidate op, candidate lambda-shape) features trained on certified
traces; used as a prior; CPU (Stage 1: MPS only wins at batch >= 1024)."""
from __future__ import annotations

import json
import math
import random

ENCODERS = {"split", "words", "chars", "objs", "tjoin", "countby", "groupby", "indeg", "outdeg", "reach", "topo", "enum", "pairs", "fill"}
AGGREGATES = {"fold", "len", "join", "best", "get", "paint", "take"}


def _abs(e):
    if isinstance(e, list):
        if e and e[0] == "f":
            return ["f", "F"]
        if e and e[0] in ("bef", "aft"):
            return [e[0], _abs(e[1]), "D"]
        return [_abs(x) for x in e]
    return e


def akey(t):
    a = {}
    for k, v in t.items():
        if k in ("d",):
            a[k] = "D"
        elif k in ("k", "ks"):
            a[k] = "F"
        elif k in ("color",):
            a[k] = "C"
        elif k in ("h", "w"):
            a[k] = "N"
        else:
            a[k] = _abs(v)
    return json.dumps(a, sort_keys=True)


START = "<START>"


def fit(programs, alpha=1.0, lam=0.8, weights=None):
    kb, ob, keys_by_op = {}, {}, {}
    for i, p in enumerate(programs):
        w = 1.0 if weights is None else weights[i]
        prev_k, prev_o = START, START
        for t in p:
            k, o = akey(t), t["op"]
            kb.setdefault(prev_k, {}); kb[prev_k][k] = kb[prev_k].get(k, 0.0) + w
            ob.setdefault(prev_o, {}); ob[prev_o][o] = ob[prev_o].get(o, 0.0) + w
            keys_by_op.setdefault(o, set()).add(k)
            prev_k, prev_o = k, o
    return {"kind": "learned", "kb": kb, "ob": ob, "kbo": {o: sorted(v) for o, v in keys_by_op.items()}, "alpha": alpha,
            "lam": lam, "n": len(programs)}


def fit_repr(programs, alpha=1.0):
    first, last = {}, {}
    for p in programs:
        first[akey(p[0])] = first.get(akey(p[0]), 0) + 1
        last[akey(p[-1])] = last.get(akey(p[-1]), 0) + 1
    return {"kind": "repr", "first": first, "last": last, "alpha": alpha, "n": len(programs)}


def placebo(prior, seed):
    """Permute abstract-key identities (and op identities) consistently inside the learned tables."""
    keys = sorted({k for r in prior["kb"].values() for k in r} | {k for k in prior["kb"] if k != START})
    perm = keys[:]
    random.Random(f"w38-placebo:{seed}").shuffle(perm)
    m = dict(zip(keys, perm)); m[START] = START
    ops = sorted({o for r in prior["ob"].values() for o in r} | {o for o in prior["ob"] if o != START})
    po = ops[:]
    random.Random(f"w38-placebo-op:{seed}").shuffle(po)
    mo = dict(zip(ops, po)); mo[START] = START
    kb = {m.get(a, a): {m.get(b, b): c for b, c in r.items()} for a, r in prior["kb"].items()}
    ob = {mo.get(a, a): {mo.get(b, b): c for b, c in r.items()} for a, r in prior["ob"].items()}
    return dict(prior, kind="learned", kb=kb, ob=ob, placebo=True)


class Lazy:
    """Row-lazy cost table: row r (= predecessor r-1; row 0 = START) is computed on first access only (Stage 2 efficiency fix:
    the eager (T+1) x T matrix cost more than the search it saved)."""

    def __init__(self, n, fn):
        self.fn, self.rows = fn, [None] * n

    def __getitem__(self, r):
        if self.rows[r] is None:
            self.rows[r] = self.fn(r)
        return self.rows[r]


def cost_matrix(prior, tools):
    """cost[prev_index + 1][t] for prev in START..T-1 (abstract keys looked up per task); rows are computed lazily."""
    T = len(tools)
    if prior is None or prior.get("kind") == "uniform":
        return {"cost": [[1.0] * T for _ in range(T + 1)]}
    ks = [akey(t) for t in tools]
    ops = [t["op"] for t in tools]
    if prior["kind"] == "fixed":
        def c1(prev_op, op, pos):
            if prev_op == START:
                return 0.5 if op in ENCODERS else 2.0
            if op in AGGREGATES:
                return 0.8
            return 1.0 if op not in ENCODERS else 1.6
        return {"cost": Lazy(T + 1, lambda r: [c1(START if r == 0 else ops[r - 1], o, r) for o in ops])}
    if prior["kind"] == "repr":
        a = prior["alpha"]
        nf, nl = sum(prior["first"].values()), sum(prior["last"].values())
        rf = [-math.log((prior["first"].get(k, 0) + a) / (nf + a * T)) for k in ks]
        rl = [-math.log((prior["last"].get(k, 0) + a) / (nl + a * T)) for k in ks]
        base = math.log(T)
        rest = [0.5 * (base + rl[j]) for j in range(T)]
        return {"cost": Lazy(T + 1, lambda r: rf if r == 0 else rest)}
    a, lam = prior["alpha"], prior["lam"]
    kbo = prior["kbo"]
    n_ops = max(1, len({o for o in ops}))

    def row(prev_k, prev_o):
        kr = prior["kb"].get(prev_k, {})
        orow = prior["ob"].get(prev_o, {})
        nk, no = sum(kr.values()), sum(orow.values())
        out = []
        for k, o in zip(ks, ops):
            pk = (kr.get(k, 0.0) + a) / (nk + a * T)
            members = max(1, sum(1 for o2 in ops if o2 == o))
            po = (orow.get(o, 0.0) + a) / (no + a * n_ops) / members
            out.append(-math.log(lam * pk + (1 - lam) * po))
        return out
    return {"cost": Lazy(T + 1, lambda r: row(START, START) if r == 0 else row(ks[r - 1], ops[r - 1]))}


# --------------------------------------------------------------------------- experiment 7: neural ranker
def _feat(prev_op, op, shape_len, ops_vocab):
    v = [0.0] * (2 * len(ops_vocab) + 2)
    if prev_op in ops_vocab:
        v[ops_vocab.index(prev_op)] = 1.0
    if op in ops_vocab:
        v[len(ops_vocab) + ops_vocab.index(op)] = 1.0
    v[-2] = shape_len / 10.0
    v[-1] = 1.0
    return v


OPS = ["<START>", "map", "filter", "sortby", "groupby", "countby", "fold", "scan", "take", "drop", "rev", "uniq", "flat", "enum",
       "pairs", "len", "best", "split", "join", "chars", "words", "strip", "get", "proj", "tjoin", "fill", "objs", "paint",
       "recolor_if", "reach", "topo", "indeg", "outdeg"]


def train_ranker(programs, epochs=60, seed=0):
    """MLP (feat -> 32 -> 1) trained to score observed (prev op -> op, lambda size) transitions above sampled negatives.
    Returns (state_dict as lists, counters). CPU (Stage 1 measurement: batches here are < 1024)."""
    import torch
    torch.manual_seed(seed)
    rng = random.Random(seed)
    pos, neg = [], []
    for p in programs:
        prev = "<START>"
        for t in p:
            pos.append(_feat(prev, t["op"], len(akey(t)) // 20, OPS))
            for _ in range(3):
                neg.append(_feat(prev, rng.choice(OPS[1:]), rng.randint(1, 6), OPS))
            prev = t["op"]
    if not pos:
        return None, {"forward": 0, "backward": 0}
    X = torch.tensor(pos + neg); Y = torch.tensor([1.0] * len(pos) + [0.0] * len(neg))
    net = torch.nn.Sequential(torch.nn.Linear(X.shape[1], 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))
    opt = torch.optim.Adam(net.parameters(), 1e-2)
    for _ in range(epochs):
        loss = torch.nn.functional.binary_cross_entropy_with_logits(net(X).squeeze(-1), Y)
        opt.zero_grad(); loss.backward(); opt.step()
    sd = {k: v.tolist() for k, v in net.state_dict().items()}
    return sd, {"forward": epochs, "backward": epochs, "examples": len(X)}


def neural_cost_matrix(sd, tools):
    import torch
    T = len(tools)
    net = torch.nn.Sequential(torch.nn.Linear(2 * len(OPS) + 2, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))
    net.load_state_dict({k: torch.tensor(v) for k, v in sd.items()})
    ops = [t["op"] for t in tools]
    sl = [len(akey(t)) // 20 for t in tools]
    cnt = {"forward_rows": 0}

    def row(r):
        po = "<START>" if r == 0 else ops[r - 1]
        cnt["forward_rows"] += 1
        with torch.no_grad():
            logits = net(torch.tensor([_feat(po, o, s, OPS) for o, s in zip(ops, sl)])).squeeze(-1)
            return (-torch.log_softmax(logits, dim=-1)).tolist()
    return {"cost": Lazy(T + 1, row)}, cnt
