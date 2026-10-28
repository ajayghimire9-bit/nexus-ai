"""LPL - a small procedural language for REGISTER-HYPOTHESIS PROCEDURES (NOT LOCKED; mi track). Human-written infrastructure
(disclosed): the statement set, the interpreter, the generic random generator and the generic mutation / crossover operators.
A procedure is a PROGRAM: it constructs, from primitives and from the evidence of one register-learning problem, the ordered
hypothesis space of register updates that the (unchanged) assignment engine searches. Programs are generated and rewritten by
the discovery search; no program is written by hand except SEED_BASELINE, a transcription of the existing learner's hard-wired
procedure (closure of {acc, x, 0, 1} under {+, -} to size 5, deduplicated, smallest first) used as one starting point.

Program = dict(main=[stmt], helpers={name: [stmt]}). Pools are named lists of update expressions (oop_synthesizer nodes).
Statements (pools P0..P5; all bounded):
  ('terms', d, names)              d := [acc | x]                       names subset of ('acc', 'x')
  ('lits', d, ks)                  d := constants ks                    ks subset of LIT (0..10)
  ('dconsts', d, mode)             d := constants derived from the problem's evidence:  'small_obs' small integers that occur
                                   as observed values; 'int_ratios' near-integer ratios of observed values; 'int_diffs'
                                   near-integer differences of observed values (all <= 10 in magnitude, <= 6 kept)
  ('combine', d, a, b, op)         d := [(p op q) for p in a for q in b]   op in + - * /  (/ guarded by the evaluator)
  ('cond', d, a, b, c, e)          d := [(r if p < q else s) for p in a, q in b, r in c, s in e]
  ('union', d, a, b) | ('dedupe', d, a) | ('take', d, a, n) | ('sort', d, a, key) | ('filter', d, a, pred)
  ('repeat', n, body)              body run n times (n <= 3)
  ('if_feat', feat, cmp, t, then, else)   feat in FEATS (n_occ, n_obs_int_frac, max_abs_obs, n_trans), cmp in < >=
  ('call', name)                   run helper `name` (no recursion; depth <= 2)
  ('ret', a)                       the hypothesis space = pool a (the engine always puts the identity `acc` first)
Caps: every pool <= POOL_CAP expressions (truncation is recorded), <= STEP_CAP executed statements."""
from __future__ import annotations

import copy
import math
import random

from nexus import oop_synthesizer as S

POOLS = tuple(f"P{i}" for i in range(6))
LIT = tuple(range(11))
OPS = ("+", "-", "*", "/")
SORT_KEYS = ("size", "acc_first", "x_first", "few_consts")
PREDS = ("uses_acc", "uses_x", "not_const", "size_le_5", "size_le_3")
FEATS = ("n_occ", "n_obs_int_frac", "max_abs_obs", "n_trans")
DMODES = ("small_obs", "int_ratios", "int_diffs")
POOL_CAP, STEP_CAP = 3000, 400
ACC, X = ("var", "acc"), ("var", "x")

SEED_BASELINE = dict(main=[("terms", "P0", ("acc", "x")), ("lits", "P1", (0, 1)), ("union", "P0", "P0", "P1"),
                           ("combine", "P2", "P0", "P0", "+"), ("combine", "P3", "P0", "P0", "-"), ("union", "P2", "P2", "P3"),
                           ("combine", "P3", "P2", "P0", "+"), ("combine", "P4", "P2", "P0", "-"), ("union", "P3", "P3", "P4"),
                           ("combine", "P4", "P0", "P2", "+"), ("combine", "P5", "P0", "P2", "-"), ("union", "P4", "P4", "P5"),
                           ("union", "P3", "P3", "P4"), ("union", "P0", "P0", "P2"), ("union", "P0", "P0", "P3"),
                           ("dedupe", "P0", "P0"), ("sort", "P0", "P0", "size"), ("ret", "P0")], helpers={})


# ------------------------------------------------------------------------------------------------ interpreter
_PROBES = [(a, x) for a, x in ((3.7, 5.1), (-2.3, 7.9), (11.4, 0.6), (0.0, 4.2), (6.6, -3.3), (1.0, 1.0), (25.5, 2.0), (-7.1, -9.4))]


def _sig(n):
    out = []
    for a, x in _PROBES:
        v = S.ev(n, {"acc": a, "x": x})
        out.append(None if not isinstance(v, (int, float)) or isinstance(v, bool) or (isinstance(v, float) and not math.isfinite(v))
                   else round(v, 7))
    return tuple(out)


def _uses(n, v):
    return v in S._vars(n)


def _consts(n):
    if n[0] == "const":
        return 1
    return sum(_consts(c) for c in n[1:] if isinstance(c, tuple))


def _derive(mode, obs):
    vals = [v for v in obs if isinstance(v, (int, float)) and not isinstance(v, bool)]
    out = []
    if mode == "small_obs":
        out = [v for v in vals if abs(v) <= 10 and abs(v - round(v)) < 1e-6]
    elif mode == "int_ratios":
        for a, b in zip(vals, vals[1:]):
            if b and abs(a / b) <= 10 and abs(a / b - round(a / b)) < 1e-4:
                out.append(round(a / b))
    elif mode == "int_diffs":
        for a, b in zip(vals, vals[1:]):
            d = a - b
            if abs(d) <= 10 and abs(d - round(d)) < 1e-6:
                out.append(round(d))
    seen = []
    for v in out:
        v = int(round(v))
        if v not in seen:
            seen.append(v)
    return [("const", v) for v in seen[:6]]


def features(ctx):
    obs = [v for v in ctx.get("obs", []) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return dict(n_occ=len(obs), n_obs_int_frac=(sum(abs(v - round(v)) < 1e-6 for v in obs) / len(obs)) if obs else 0.0,
                max_abs_obs=max((abs(v) for v in obs), default=0.0), n_trans=ctx.get("n_trans", 0))


class Run:
    def __init__(self, prog, ctx):
        self.prog, self.ctx = prog, ctx
        self.pools = {p: [] for p in POOLS}
        self.steps, self.truncated, self.ret = 0, 0, None
        self.feats = features(ctx)

    def _set(self, d, lst):
        if len(lst) > POOL_CAP:
            self.truncated += 1
            lst = lst[:POOL_CAP]
        self.pools[d] = lst

    def exec(self, body, depth=0):
        for st in body:
            if self.steps >= STEP_CAP or self.ret is not None:
                return
            self.steps += 1
            k = st[0]
            P = self.pools
            if k == "terms":
                self._set(st[1], [ACC if n == "acc" else X for n in st[2]])
            elif k == "lits":
                self._set(st[1], [("const", c) for c in st[2]])
            elif k == "dconsts":
                self._set(st[1], _derive(st[2], self.ctx.get("obs", [])))
            elif k == "combine":
                a, b = P[st[2]], P[st[3]]
                if len(a) * len(b) > 4 * POOL_CAP:
                    self.truncated += 1
                self._set(st[1], [("b", st[4], p, q) for p in a for q in b][:4 * POOL_CAP])
            elif k == "cond":
                a, b, c, e = (P[x][:8] for x in st[2:6])
                self._set(st[1], [("if", ("b", "<", p, q), r, s) for p in a for q in b for r in c for s in e if p != q and r != s])
            elif k == "union":
                self._set(st[1], P[st[2]] + [n for n in P[st[3]]])
            elif k == "dedupe":
                seen, out = set(), []
                for n in P[st[2]]:
                    s = _sig(n)
                    if s not in seen:
                        seen.add(s)
                        out.append(n)
                self._set(st[1], out)
            elif k == "take":
                self._set(st[1], P[st[2]][:st[3]])
            elif k == "sort":
                key = {"size": lambda n: S.size(n), "acc_first": lambda n: (not _uses(n, "acc"), S.size(n)),
                       "x_first": lambda n: (not _uses(n, "x"), S.size(n)), "few_consts": lambda n: (_consts(n), S.size(n))}[st[3]]
                self._set(st[1], sorted(P[st[2]], key=key))
            elif k == "filter":
                pr = {"uses_acc": lambda n: _uses(n, "acc"), "uses_x": lambda n: _uses(n, "x"), "not_const": lambda n: bool(S._vars(n)),
                      "size_le_5": lambda n: S.size(n) <= 5, "size_le_3": lambda n: S.size(n) <= 3}[st[3]]
                self._set(st[1], [n for n in P[st[2]] if pr(n)])
            elif k == "repeat":
                for _ in range(min(3, st[1])):
                    self.exec(st[2], depth)
            elif k == "if_feat":
                v = self.feats[st[1]]
                ok = v < st[3] if st[2] == "<" else v >= st[3]
                self.exec(st[4] if ok else st[5], depth)
            elif k == "call":
                if depth < 2 and st[1] in self.prog.get("helpers", {}):
                    self.exec(self.prog["helpers"][st[1]], depth + 1)
            elif k == "ret":
                self.ret = st[1]


def hypothesis_space(prog, ctx):
    """Execute the procedure; returns (ordered update list with the identity first, run stats)."""
    r = Run(prog, ctx)
    r.exec(prog["main"])
    pool = r.pools.get(r.ret or "P0", [])
    out, seen = [ACC], {_sig(ACC)}
    for n in pool:
        s = _sig(n)
        if s in seen or all(v is None for v in s):
            continue
        seen.add(s)
        out.append(n)
    return out, dict(steps=r.steps, truncated=r.truncated, size=len(out))


# ------------------------------------------------------------------------------------------------ generic generation / mutation
def _rand_stmt(rnd, depth=0, helpers=()):
    p = lambda: rnd.choice(POOLS)                                    # noqa: E731
    k = rnd.choices(["terms", "lits", "dconsts", "combine", "cond", "union", "dedupe", "take", "sort", "filter", "repeat", "if_feat", "call"],
                    weights=[3, 3, 2, 6, 1, 4, 3, 1, 2, 1, 1 if depth < 1 else 0, 1 if depth < 1 else 0, 1 if helpers else 0])[0]
    if k == "terms":
        return ("terms", p(), tuple(rnd.sample(["acc", "x"], rnd.randint(1, 2))))
    if k == "lits":
        return ("lits", p(), tuple(sorted(rnd.sample(LIT, rnd.randint(1, 3)))))
    if k == "dconsts":
        return ("dconsts", p(), rnd.choice(DMODES))
    if k == "combine":
        return ("combine", p(), p(), p(), rnd.choice(OPS))
    if k == "cond":
        return ("cond", p(), p(), p(), p(), p())
    if k == "union":
        return ("union", p(), p(), p())
    if k == "dedupe":
        return ("dedupe", p(), p())
    if k == "take":
        return ("take", p(), p(), rnd.choice([20, 50, 100, 300, 1000]))
    if k == "sort":
        return ("sort", p(), p(), rnd.choice(SORT_KEYS))
    if k == "filter":
        return ("filter", p(), p(), rnd.choice(PREDS))
    if k == "repeat":
        return ("repeat", rnd.randint(2, 3), [_rand_stmt(rnd, depth + 1, helpers) for _ in range(rnd.randint(1, 3))])
    if k == "if_feat":
        f = rnd.choice(FEATS)
        t = {"n_occ": rnd.choice([5, 10, 20, 40]), "n_obs_int_frac": rnd.choice([0.3, 0.5, 0.8]),
             "max_abs_obs": rnd.choice([10, 100, 1000]), "n_trans": rnd.choice([5, 10, 15])}[f]
        return ("if_feat", f, rnd.choice(["<", ">="]), t, [_rand_stmt(rnd, depth + 1, helpers) for _ in range(rnd.randint(1, 3))],
                [_rand_stmt(rnd, depth + 1, helpers) for _ in range(rnd.randint(0, 2))])
    return ("call", rnd.choice(list(helpers)))


def random_program(rnd, n=None):
    helpers = {}
    if rnd.random() < 0.3:
        helpers["h0"] = [_rand_stmt(rnd, 1) for _ in range(rnd.randint(1, 4))]
    body = [_rand_stmt(rnd, 0, tuple(helpers)) for _ in range(n or rnd.randint(4, 14))]
    return dict(main=body + [("dedupe", "P0", "P0"), ("ret", "P0")] if rnd.random() < 0.5 else body + [("ret", rnd.choice(POOLS))],
                helpers=helpers)


def _bodies(prog):
    """Every statement list in the program (main, helpers, nested bodies) - mutation sites."""
    out = [prog["main"]] + list(prog.get("helpers", {}).values())
    i = 0
    while i < len(out):
        for st in out[i]:
            if st[0] == "repeat":
                out.append(st[2])
            elif st[0] == "if_feat":
                out += [st[4], st[5]]
        i += 1
    return out


def mutate(prog, rnd):
    """One generic structural edit (insert / delete / replace / perturb a statement, wrap a block in a loop or a feature test,
    extract a block into a helper). Returns (new program, edit description)."""
    p = copy.deepcopy(prog)
    p.setdefault("helpers", {})
    bodies = [b for b in _bodies(p)]
    b = rnd.choice(bodies)
    kind = rnd.choice(["insert", "insert", "delete", "replace", "perturb", "wrap_repeat", "wrap_if", "extract_helper"])
    if kind == "insert" or not b:
        i = rnd.randint(0, len(b))
        b.insert(i, _rand_stmt(rnd, 0, tuple(p["helpers"])))
        return p, f"insert@{i}"
    i = rnd.randrange(len(b))
    if kind == "delete" and b[i][0] != "ret":
        del b[i]
        return p, f"delete@{i}"
    if kind == "replace" and b[i][0] != "ret":
        b[i] = _rand_stmt(rnd, 0, tuple(p["helpers"]))
        return p, f"replace@{i}"
    if kind == "wrap_repeat" and b[i][0] != "ret":
        j = min(len(b), i + rnd.randint(1, 3))
        blk = [s for s in b[i:j] if s[0] != "ret"]
        b[i:j] = [("repeat", rnd.randint(2, 3), blk)] + [s for s in b[i:j] if s[0] == "ret"]
        return p, f"wrap_repeat@{i}"
    if kind == "wrap_if" and b[i][0] != "ret":
        f = rnd.choice(FEATS)
        t = {"n_occ": 10, "n_obs_int_frac": 0.5, "max_abs_obs": 100, "n_trans": 10}[f]
        b[i] = ("if_feat", f, rnd.choice(["<", ">="]), t, [b[i]], [])
        return p, f"wrap_if@{i}"
    if kind == "extract_helper" and b[i][0] != "ret":
        j = min(len(b), i + rnd.randint(1, 3))
        blk = [s for s in b[i:j] if s[0] != "ret"]
        if blk:
            name = f"h{len(p['helpers'])}"
            p["helpers"][name] = blk
            b[i:j] = [("call", name)] + [s for s in b[i:j] if s[0] == "ret"]
            return p, f"extract_helper {name}"
    st = list(b[i])                                                  # perturb one argument
    if st[0] in ("combine",):
        st[4] = rnd.choice(OPS)
    elif st[0] == "lits":
        st[2] = tuple(sorted(set(st[2]) ^ {rnd.choice(LIT)})) or (1,)
    elif st[0] in ("terms", "dconsts", "union", "dedupe", "sort", "filter", "take", "cond"):
        j = rnd.randrange(1, len(st))
        if isinstance(st[j], str) and st[j] in POOLS:
            st[j] = rnd.choice(POOLS)
    b[i] = tuple(st)
    return p, f"perturb@{i}"


def crossover(a, b, rnd):
    """Splice: a prefix of a's main + a suffix of b's main (helpers merged; b's renamed on clash)."""
    a, b = copy.deepcopy(a), copy.deepcopy(b)
    i, j = rnd.randint(0, len(a["main"])), rnd.randint(0, len(b["main"]))
    helpers = dict(a.get("helpers", {}))
    for k, v in b.get("helpers", {}).items():
        helpers[k if k not in helpers else k + "b"] = v
    main = [s for s in a["main"][:i] if s[0] != "ret"] + b["main"][j:]
    if not any(s[0] == "ret" for s in main):
        main.append(("ret", "P0"))
    return dict(main=main, helpers=helpers), f"crossover a[:{i}] + b[{j}:]"


def source(prog):
    """Readable listing of a procedure (the complete executable program is the JSON itself)."""
    def lines(body, ind):
        out = []
        for st in body:
            if st[0] == "repeat":
                out.append(" " * ind + f"repeat {st[1]}:")
                out += lines(st[2], ind + 2)
            elif st[0] == "if_feat":
                out.append(" " * ind + f"if {st[1]} {st[2]} {st[3]}:")
                out += lines(st[4], ind + 2)
                if st[5]:
                    out.append(" " * ind + "else:")
                    out += lines(st[5], ind + 2)
            else:
                out.append(" " * ind + " ".join(map(str, st)))
        return out
    txt = []
    for name, body in prog.get("helpers", {}).items():
        txt.append(f"def {name}:")
        txt += lines(body, 2)
    txt.append("main:")
    txt += lines(prog["main"], 2)
    return "\n".join(txt)
