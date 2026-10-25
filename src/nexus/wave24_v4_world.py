"""Wave 24 v4 procedural world: two source families, six target families, four task kinds.

Reused: `wave24_domains` (Tool, Domain, vkey and the CELL_AUTOMATA / NUM_SERIES / GRAPH /
STDLIB_BYTES target families, unchanged). New families: INT_SEQ and STR_PARSE (sources),
DICT_RECORD and STATE_TRANSITION (targets). Every tool is an unwrapped Python callable; a fault is
a real exception.

Task kinds (all generated, none hand-authored):
  passive  - public examples determine the query answer among plain chains (brute-force checked);
  trap     - public examples come from the ordinary sampler but are *selected* so that two
             minimal plain chains agree on every public example and disagree on the query
             (equal-signature collisions such as last-record vs latest-by-time arise naturally);
             passive trap: the correct verdict is AMBIGUOUS with the truth inside Y_q;
  active   - a trap task plus a charged oracle on non-query inputs (probe budget declared);
  subset   - the teacher is guard(c, P, r): an executable predicate c from the generic feature
             grammar, a plain chain P that raises on some public inputs, and a recovery r
             (constant or tool); no plain chain up to depth 3 fits the public examples.
Grading uses the teacher's answer only after an answer is locked.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import product

from nexus.wave24_domains import Domain, Tool, cell_domain, graph_domain, series_domain, stdlib_domain, vkey

PROBE_COST = 20          # one oracle observation (on top of executing the hypotheses on it)
PROBE_BUDGET = 3         # oracle calls per active task


def _t(name, fn, doc):
    return Tool(name, fn, doc)


# --------------------------------------------------------------------------- sources
def int_seq_domain():
    t = [
        _t("sort", sorted, "sort ascending"),
        _t("rev", lambda xs: list(reversed(xs)), "reverse order"),
        _t("rotl", lambda xs: list(xs[1:]) + list(xs[:1]), "rotate left by one"),
        _t("dedup", lambda xs: list(dict.fromkeys(xs)), "remove duplicates keep first"),
        _t("evens", lambda xs: [x for x in xs if x % 2 == 0], "keep even elements"),
        _t("pos", lambda xs: [x for x in xs if x > 0], "keep positive elements"),
        _t("total", sum, "sum of elements"),
        _t("count", len, "number of elements"),
        _t("head", lambda xs: xs[0], "first element raises if empty"),
        _t("last", lambda xs: xs[-1], "last element raises if empty"),
        _t("peak", max, "largest element raises if empty"),
        _t("incall", lambda xs: [x + 1 for x in xs], "add one to every element"),
        _t("mean_floor", lambda xs: sum(xs) // len(xs), "floor mean raises if empty"),
        _t("share", lambda xs: 60 // sum(xs), "sixty divided by the sum raises on zero sum"),
    ]
    def sample(r):
        return [r.randint(-3, 9) for _ in range(r.randint(0, 5))]
    def messy(r):
        xs = sample(r)
        if r.random() < 0.4:
            return []
        if r.random() < 0.5 and xs:
            xs = xs + [-sum(xs)]
        return xs
    return Domain("INT_SEQ", "source", tuple(t), sample, messy)


def _tokens(s):
    return [p.strip() for p in s.split(",")]


def str_parse_domain():
    t = [
        _t("split", _tokens, "split on commas into stripped tokens"),
        _t("to_ints", lambda ts: [int(x) for x in ts], "parse every token as an integer raises if malformed"),
        _t("strip", str.strip, "strip outer whitespace"),
        _t("lower", str.lower, "lower case"),
        _t("rev_str", lambda s: s[::-1], "reverse the characters"),
        _t("first_tok", lambda s: _tokens(s)[0], "first comma token"),
        _t("last_tok", lambda s: _tokens(s)[-1], "last comma token"),
        _t("ntok", lambda s: len(_tokens(s)), "number of comma tokens"),
        _t("as_int", lambda s: int(s), "parse the whole string as an integer raises if malformed"),
        _t("join", lambda ts: "-".join(ts), "join tokens with dashes"),
        _t("isum", sum, "sum of a list of integers"),
        _t("nonempty", lambda ts: [x for x in ts if x], "drop empty tokens"),
        _t("length", len, "length"),
    ]
    good = ["3", "12", "7", "40", "5", "0"]
    def sample(r):
        return ",".join(r.choice(good) for _ in range(r.randint(1, 4)))
    def messy(r):
        toks = [r.choice(good) for _ in range(r.randint(1, 4))]
        if r.random() < 0.6:
            toks[r.randrange(len(toks))] = r.choice(["x", "n/a", "?", "1o"])
        return ",".join(toks)
    return Domain("STR_PARSE", "source", tuple(t), sample, messy)


# --------------------------------------------------------------------------- new targets
def dict_record_domain():
    t = [
        _t("last_rec", lambda rs: rs[-1], "last record raises if empty"),
        _t("first_rec", lambda rs: rs[0], "first record raises if empty"),
        _t("latest", lambda rs: max(rs, key=lambda r: r["t"]), "record with the largest time raises if empty"),
        _t("earliest", lambda rs: min(rs, key=lambda r: r["t"]), "record with the smallest time raises if empty"),
        _t("by_time", lambda rs: sorted(rs, key=lambda r: r["t"]), "sort records by time"),
        _t("rev", lambda rs: list(reversed(rs)), "reverse record order"),
        _t("count", len, "number of records"),
        _t("vals", lambda rs: [r["v"] for r in rs], "list of values raises if a record lacks one"),
        _t("get_v", lambda r: r["v"], "value field of a record raises if absent"),
        _t("get_t", lambda r: r["t"], "time field of a record raises if absent"),
        _t("nonzero", lambda rs: [r for r in rs if r.get("v") != 0], "drop records whose value is zero"),
        _t("total", sum, "sum of numbers"),
    ]
    def sample(r):
        n = r.randint(1, 4)
        times = sorted(r.sample(range(1, 30), n))
        if r.random() < 0.5:
            r.shuffle(times)
        return [{"t": ti, "v": r.randint(0, 9)} for ti in times]
    def messy(r):
        rs = sample(r)
        if r.random() < 0.6:
            del rs[r.randrange(len(rs))]["v"]
        elif r.random() < 0.3:
            rs = []
        return rs
    return Domain("DICT_RECORD", "target", tuple(t), sample, messy)


def state_transition_domain():
    def up(s):
        if s[1] >= 3:
            raise ValueError("level at upper bound")
        return (s[0], s[1] + 1)
    def down(s):
        if s[1] <= 0:
            raise ValueError("level at lower bound")
        return (s[0], s[1] - 1)
    t = [
        _t("up", up, "raise the level by one raises at the upper bound"),
        _t("down", down, "lower the level by one raises at the lower bound"),
        _t("toggle", lambda s: ("run" if s[0] == "idle" else "idle", s[1]), "toggle idle and run"),
        _t("reset", lambda s: ("idle", 0), "reset to idle level zero"),
        _t("mirror", lambda s: (s[0], 3 - s[1]), "mirror the level"),
        _t("level", lambda s: s[1], "level of the state"),
        _t("mode", lambda s: s[0], "mode of the state"),
        _t("run", lambda s: ("run", s[1]), "set mode to run"),
    ]
    def sample(r):
        return (r.choice(["idle", "run"]), r.randint(0, 2))
    def messy(r):
        return (r.choice(["idle", "run"]), r.choice([0, 3, 3, 1]))
    return Domain("STATE_TRANSITION", "target", tuple(t), sample, messy)


def source_domains():
    return (int_seq_domain(), str_parse_domain())


def target_domains():
    return (dict_record_domain(), state_transition_domain(), cell_domain(), series_domain(), graph_domain(),
            stdlib_domain())


# --------------------------------------------------------------------------- tasks
@dataclass(frozen=True)
class V4Task:
    domain: str
    kind: str                 # passive | trap | active | subset
    public: tuple             # ((x, y), ...)
    query: object
    answer: object = field(compare=False)            # grading only
    teacher: str = field(compare=False, default="")  # grading/diagnostics only
    gold: str = field(compare=False, default="UNIQUE")   # UNIQUE | AMBIGUOUS
    oracle: object = field(compare=False, default=None, repr=False)
    probe_budget: int = 0


class Oracle:
    """Charged teacher access on non-query inputs only (active tasks)."""

    def __init__(self, fn, query):
        self._fn, self._qkey = fn, vkey(query)
        self.calls = 0

    def __call__(self, x):
        if vkey(x) == self._qkey:
            raise PermissionError("the oracle never answers the query input")
        self.calls += 1
        return self._fn(x)


def run_chain(chain, x):
    for t in chain:
        x = t(x)
    return x


def _outputs(chain, xs):
    try:
        return tuple(vkey(run_chain(chain, x)) for x in xs)
    except Exception:
        return None


def chains_upto(tools, depth):
    for d in range(1, depth + 1):
        for c in product(tools, repeat=d):
            yield c


def plain_fits(tools, public, query, depth):
    """Brute force: minimal depth d* at which some plain chain fits, and its query answers."""
    xs = [x for x, _ in public]
    ys = tuple(vkey(y) for _, y in public)
    for d in range(1, depth + 1):
        answers = set()
        for c in product(tools, repeat=d):
            if _outputs(c, xs) == ys:
                out = _outputs(c, [query])
                if out is not None:
                    answers.add(out[0])
        if answers:
            return d, answers
    return None, set()


def _inputs(domain, rng, n, messy):
    return domain.inputs(rng, n, messy=messy)


def make_chain_task(domain, rng, *, kind, depth, n_public=3, attempts=300):
    tools = list(domain.tools)
    for _ in range(attempts):
        chain = tuple(rng.choice(tools) for _ in range(depth))
        if any(a.name == b.name for a, b in zip(chain, chain[1:])):
            continue
        xs = _inputs(domain, rng, n_public + 1, messy=False)
        if len({vkey(x) for x in xs}) < len(xs):
            continue
        try:
            ys = [run_chain(chain, x) for x in xs]
        except Exception:
            continue
        if len({vkey(y) for y in ys[:-1]}) < 2 or all(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue
        public = tuple(zip(xs[:-1], ys[:-1]))
        dstar, answers = plain_fits(tools, public, xs[-1], depth)
        if dstar != depth or vkey(ys[-1]) not in answers:
            continue
        name = ">".join(t.name for t in chain)
        if kind == "passive" and len(answers) == 1:
            return V4Task(domain.name, "passive", public, xs[-1], ys[-1], name, "UNIQUE")
        if kind in ("trap", "active") and len(answers) >= 2:
            if kind == "trap":
                return V4Task(domain.name, "trap", public, xs[-1], ys[-1], name, "AMBIGUOUS")
            fn = lambda x, c=chain: run_chain(c, x)
            return V4Task(domain.name, "active", public, xs[-1], ys[-1], name, "UNIQUE",
                          oracle=("chain", chain), probe_budget=PROBE_BUDGET)
    return None


def make_subset_task(domain, rng, predicates_for, *, n_public=4, attempts=300):
    """Teacher guard(c, P, r); P raises on >= 1 public input; no plain chain <= 3 fits."""
    tools = list(domain.tools)
    for _ in range(attempts):
        depth = rng.choice((1, 1, 2))
        chain = tuple(rng.choice(tools) for _ in range(depth))
        xs = _inputs(domain, rng, n_public, messy=True) + _inputs(domain, rng, 1, messy=rng.random() < 0.5)
        if len({vkey(x) for x in xs}) < len(xs):
            continue
        ok, bad = [], []
        for i, x in enumerate(xs[:-1]):
            try:
                run_chain(chain, x)
                ok.append(i)
            except Exception:
                bad.append(i)
        if len(ok) < 2 or not bad:
            continue
        preds = [p for p in predicates_for([xs[i] for i in ok], [xs[i] for i in bad]) if p.size == 1]
        if not preds:
            continue
        pred = rng.choice(preds)
        rec_tools = [tl for tl in tools if all(_outputs((tl,), [xs[i]]) is not None for i in bad)]
        if rng.random() < 0.5 or not rec_tools:
            const = rng.choice([0, None, -1, ""])
            recovery = ("const", const)
            rfun = lambda x, c=const: c
        else:
            tl = rng.choice(rec_tools)
            recovery = ("tool", tl)
            rfun = tl
        def teach(x, pred=pred, chain=chain, rfun=rfun):
            return run_chain(chain, x) if pred(x) else rfun(x)
        try:
            ys = [teach(x) for x in xs]
        except Exception:
            continue
        if len({vkey(y) for y in ys[:-1]}) < 2:
            continue
        public = tuple(zip(xs[:-1], ys[:-1]))
        dstar, _ = plain_fits(tools, public, xs[-1], 3 if len(tools) <= 12 else 2)
        if dstar is not None:
            continue
        rname = repr(recovery[1]) if recovery[0] == "const" else recovery[1].name
        name = f"guard[{pred.name}?{'>'.join(t.name for t in chain)}:{rname}]"
        return V4Task(domain.name, "subset", public, xs[-1], ys[-1], name, "UNIQUE")
    return None


STREAM_MIX = (("passive", 6), ("trap", 3), ("active", 4), ("subset", 4))


def task_stream(domain, seed, predicates_for, mix=STREAM_MIX):
    """Seeded stream for one family; kinds interleaved in a seeded order."""
    rng = random.Random(f"v4-stream:{domain.name}:{seed}")
    out = []
    for kind, n in mix:
        made = 0
        for _ in range(n * 6):
            if made == n:
                break
            if kind == "subset":
                t = make_subset_task(domain, rng, predicates_for)
            else:
                t = make_chain_task(domain, rng, kind=kind, depth=rng.choice((1, 2, 2, 3) if kind == "passive"
                                                                             else (1, 2)))
            if t is not None:
                out.append(t)
                made += 1
    rng.shuffle(out)
    return out


def oracle_for(task, tools_by_name=None):
    """Bind an active task's oracle (kept as data so tasks stay picklable/deep-copyable)."""
    if task.oracle is None:
        return None
    _, chain = task.oracle
    return Oracle(lambda x, c=chain: run_chain(c, x), task.query)
