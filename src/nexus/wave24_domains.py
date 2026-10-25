"""Wave 24 multi-domain suite: seen source families and structurally disjoint targets.

Every tool is a plain unary Python callable with a docstring (its public API
text). Tools are NOT wrapped: a domain fault is a real exception that the
solver must handle or route around. Teachers are seeded random programs; the
solver only ever sees public input/output pairs (and, for grounded tasks, a
natural-language description generated from the teacher's tool docstrings).
"""
from __future__ import annotations

import base64
import binascii
import inspect
import math
import random
import zlib
from dataclasses import dataclass, field


def vkey(value):
    """Canonical, hashable key for any suite value (NaN == NaN by repr)."""
    if isinstance(value, dict):
        return ("dict", tuple(sorted((vkey(k), vkey(v)) for k, v in value.items())))
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(vkey(v) for v in value))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted(vkey(v) for v in value)))
    if isinstance(value, float):
        return ("float", repr(round(value, 9)) if math.isfinite(value) else repr(value))
    return (type(value).__name__, repr(value))


@dataclass(frozen=True)
class Tool:
    name: str
    fn: object = field(compare=False, repr=False)
    doc: str = field(default="", compare=False)
    cost: int = 1
    layer: int = 0          # 0 = primitive; macros/recovery tools are >= 1
    parts: tuple = ()       # primitive expansion (names) for macros
    children: tuple = field(default=(), compare=False, repr=False)  # child Tool objects
    kind: str = "primitive"  # primitive | macro | recovery

    def __call__(self, value):
        return self.fn(value)


@dataclass
class Domain:
    name: str
    family: str             # "source" or "target"
    tools: tuple
    sampler: object = field(repr=False)
    messy_sampler: object = field(default=None, repr=False)

    def inputs(self, rng, n, *, messy=False):
        sample = self.messy_sampler if messy and self.messy_sampler else self.sampler
        return [sample(rng) for _ in range(n)]


def _tool(name, fn, doc):
    return Tool(name, fn, doc)


# --------------------------------------------------------------------------- source
def int_domain():
    t = [
        _tool("inc", lambda x: x + 1, "increment add one to the integer"),
        _tool("dec", lambda x: x - 1, "decrement subtract one from the integer"),
        _tool("double", lambda x: 2 * x, "double multiply the integer by two"),
        _tool("halve", lambda x: x // 2, "halve integer divide by two floor"),
        _tool("negate", lambda x: -x, "negate flip the sign of the integer"),
        _tool("absval", lambda x: abs(x), "absolute value remove the sign"),
        _tool("square", lambda x: x * x, "square multiply the integer by itself"),
        _tool("mod10", lambda x: x % 10, "last digit modulo ten remainder"),
        _tool("digits", lambda x: len(str(abs(x))), "count the number of decimal digits"),
        _tool("isqrt", lambda x: math.isqrt(x), "integer square root floor raises on negative"),
    ]
    return Domain("INT", "source", tuple(t), lambda r: r.randint(-40, 60))


def str_domain():
    t = [
        _tool("strip", str.strip, "strip remove leading and trailing whitespace"),
        _tool("lower", str.lower, "lowercase convert all letters to lower case"),
        _tool("upper", str.upper, "uppercase convert all letters to upper case"),
        _tool("reverse", lambda s: s[::-1], "reverse the order of the characters"),
        _tool("first_word", lambda s: s.split()[0], "first word before the first space raises if empty"),
        _tool("drop_digits", lambda s: "".join(c for c in s if not c.isdigit()), "remove all digit characters"),
        _tool("only_digits", lambda s: "".join(c for c in s if c.isdigit()), "keep only the digit characters"),
        _tool("length", len, "count the number of characters length"),
        _tool("title", str.title, "title case capitalize each word"),
        _tool("squash", lambda s: " ".join(s.split()), "collapse repeated whitespace into single spaces"),
    ]
    words = ["alpha", "Beta", "gamma7", "Delta", "eps 42", "zeta", "Theta9", "iota"]
    return Domain("STR", "source", tuple(t),
                  lambda r: (" " * r.randint(0, 2)) + " ".join(r.sample(words, r.randint(1, 3))) + (" " * r.randint(0, 2)))


def list_domain():
    t = [
        _tool("sort", sorted, "sort the list ascending order"),
        _tool("rev", lambda xs: list(reversed(xs)), "reverse the order of the list"),
        _tool("dedup", lambda xs: list(dict.fromkeys(xs)), "remove duplicate elements keep first"),
        _tool("evens", lambda xs: [x for x in xs if x % 2 == 0], "keep only the even elements filter"),
        _tool("pos", lambda xs: [x for x in xs if x > 0], "keep only the positive elements filter"),
        _tool("sum", sum, "sum add all the elements together total"),
        _tool("count", len, "count the number of elements length"),
        _tool("head", lambda xs: xs[0], "first element of the list raises if empty"),
        _tool("cumsum", lambda xs: [sum(xs[:i + 1]) for i in range(len(xs))], "running cumulative sum prefix totals"),
        _tool("incall", lambda xs: [x + 1 for x in xs], "increment every element by one map"),
    ]
    return Domain("LIST_INT", "source", tuple(t), lambda r: [r.randint(-5, 9) for _ in range(r.randint(2, 6))])


# --------------------------------------------------------------------------- targets
def _rule(bits, table):
    n = len(bits)
    return tuple(table[(bits[(i - 1) % n] << 2) | (bits[i] << 1) | bits[(i + 1) % n]] for i in range(n))


def cell_domain():
    r30 = {i: (30 >> i) & 1 for i in range(8)}
    r90 = {i: (90 >> i) & 1 for i in range(8)}
    t = [
        _tool("step30", lambda b: _rule(b, r30), "advance one generation of elementary cellular automaton rule 30"),
        _tool("step90", lambda b: _rule(b, r90), "advance one generation of elementary cellular automaton rule 90"),
        _tool("shl", lambda b: b[1:] + b[:1], "rotate the cells left by one position"),
        _tool("shr", lambda b: b[-1:] + b[:-1], "rotate the cells right by one position"),
        _tool("invert", lambda b: tuple(1 - x for x in b), "invert flip every cell bit"),
        _tool("live", lambda b: sum(b), "count the live cells population"),
        _tool("mirror", lambda b: tuple(reversed(b)), "mirror reverse the cell row"),
        _tool("trim", lambda b: tuple(b[1:-1]), "drop the first and last cell"),
        _tool("andshift", lambda b: tuple(b[i] & b[(i + 1) % len(b)] for i in range(len(b))), "keep cells alive only if right neighbour alive"),
    ]
    return Domain("CELL_AUTOMATA", "target", tuple(t), lambda r: tuple(r.randint(0, 1) for _ in range(r.randint(5, 9))))


def nested_domain():
    def flatten(d):
        out = {}
        for k, v in d.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    out[f"{k}.{k2}"] = v2
            else:
                out[k] = v
        return out
    t = [
        _tool("flatten", flatten, "flatten nested dictionaries into dotted keys"),
        _tool("drop_none", lambda d: {k: v for k, v in d.items() if v is not None}, "drop keys whose value is missing none"),
        _tool("keys", lambda d: sorted(d), "sorted list of the keys"),
        _tool("size", len, "count the number of keys"),
        _tool("get_id", lambda d: d["id"], "value stored under the id key raises if absent"),
        _tool("numeric", lambda d: {k: v for k, v in d.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}, "keep only numeric valued entries"),
        _tool("invert", lambda d: {v: k for k, v in d.items()}, "invert swap keys and values raises if unhashable"),
        _tool("total", lambda d: sum(d.values()), "sum of all values total raises if non numeric"),
        _tool("meta", lambda d: d["meta"], "nested sub dictionary under the meta key raises if absent"),
    ]
    def sample(r):
        d = {"id": r.randint(1, 9), "a": r.randint(0, 5)}
        if r.random() < 0.7:
            d["meta"] = {"x": r.randint(0, 3), "y": r.choice([None, 2, 5])}
        if r.random() < 0.5:
            d["b"] = r.choice([None, 1, 4])
        return d
    def messy(r):
        d = sample(r)
        if r.random() < 0.5:
            d.pop("id")
        if r.random() < 0.5:
            d["a"] = r.choice(["?", None, "n/a"])
        return d
    return Domain("NESTED_DICT", "target", tuple(t), sample, messy)


def series_domain():
    t = [
        _tool("diff", lambda xs: [xs[i] - xs[i - 1] for i in range(1, len(xs))], "first differences between consecutive samples"),
        _tool("cumsum", lambda xs: [sum(xs[:i + 1]) for i in range(len(xs))], "running cumulative integral of the samples"),
        _tool("mean", lambda xs: sum(xs) / len(xs), "arithmetic mean average raises if empty"),
        _tool("peak", lambda xs: max(xs), "maximum peak value raises if empty"),
        _tool("drop_nan", lambda xs: [x for x in xs if isinstance(x, float) and math.isfinite(x)], "remove missing nan samples"),
        _tool("normalize", lambda xs: [x / max(abs(v) for v in xs) for x in xs], "scale by the largest magnitude raises on all zero"),
        _tool("round1", lambda xs: [round(x, 1) for x in xs], "round each sample to one decimal"),
        _tool("square", lambda xs: [x * x for x in xs], "square every sample energy"),
        _tool("tail", lambda xs: xs[1:], "drop the first sample"),
        _tool("check", lambda xs: [_finite(x) for x in xs], "validate samples raise on nan or missing"),
    ]
    return Domain("NUM_SERIES", "target", tuple(t),
                  lambda r: [float(r.randint(-4, 9)) for _ in range(r.randint(3, 6))],
                  lambda r: [r.choice([float(r.randint(-4, 9)), float(r.randint(0, 9)), float("nan")]) for _ in range(r.randint(3, 6))])


def _finite(x):
    if not (isinstance(x, float) and math.isfinite(x)):
        raise ValueError("non-finite sample")
    return x


def graph_domain():
    t = [
        _tool("transpose", lambda g: {n: tuple(sorted(m for m in g if n in g[m])) for n in g}, "reverse every edge direction transpose"),
        _tool("degrees", lambda g: {n: len(v) for n, v in g.items()}, "out degree of every node"),
        _tool("sources", lambda g: sorted(n for n in g if not any(n in v for v in g.values())), "nodes with no incoming edges"),
        _tool("noloops", lambda g: {n: tuple(m for m in v if m != n) for n, v in g.items()}, "remove self loop edges"),
        _tool("symmetric", lambda g: {n: tuple(sorted(set(v) | {m for m in g if n in g[m]})) for n, v in g.items()}, "add reverse edges make undirected"),
        _tool("edges", lambda g: sum(len(v) for v in g.values()), "count the edges"),
        _tool("nodes", lambda g: sorted(g), "sorted list of nodes"),
        _tool("leaves", lambda g: {n: v for n, v in g.items() if v}, "drop nodes with no outgoing edges"),
    ]
    def sample(r):
        n = r.randint(3, 5)
        names = "abcdefg"[:n]
        return {a: tuple(sorted(r.sample(names, r.randint(0, 2)))) for a in names}
    return Domain("GRAPH", "target", tuple(t), sample)


def ingest_stdlib(modules=(base64, binascii, zlib), carrier=bytes, probe=b"Nexus 01", max_tools=12):
    """Raw stdlib ingestion: introspect callables, keep those accepting one positional arg.

    No per-function wrappers: a fault inside the stdlib call is propagated.
    """
    tools, seen = [], set()
    candidates = [(f"bytes.{n}", getattr(carrier, n)) for n in dir(carrier) if not n.startswith("_")]
    for module in modules:
        candidates += [(f"{module.__name__}.{n}", f) for n, f in inspect.getmembers(module, callable) if not n.startswith("_")]
    for name, fn in candidates:
        try:
            out = fn(probe)
        except Exception:
            continue
        if out is None or isinstance(out, type) or callable(out) or hasattr(out, "__next__"):
            continue
        try:
            sig = vkey(out)
        except Exception:
            continue
        if sig in seen or sig == vkey(probe):
            continue
        seen.add(sig)
        doc = (inspect.getdoc(fn) or name).split("\n")[0]
        tools.append(Tool(name.replace(".", "_"), fn, doc.lower()))
        if len(tools) >= max_tools:
            break
    return tuple(tools)


def stdlib_domain():
    words = [b"Nexus", b"data", b"OK", b"zz", b"Rule30", b"abc"]
    return Domain("STDLIB_BYTES", "target", ingest_stdlib(),
                  lambda r: b" ".join(r.sample(words, r.randint(1, 3))))


def source_domains():
    return (int_domain(), str_domain(), list_domain())


def target_domains():
    return (cell_domain(), nested_domain(), series_domain(), graph_domain(), stdlib_domain())


# --------------------------------------------------------------------------- tasks
@dataclass(frozen=True)
class Task:
    domain: str
    public: tuple            # ((x, y), ...)
    query: object
    answer: object = field(compare=False)   # grading only; never shown to the solver
    teacher: tuple = field(compare=False)   # tool names (grading/diagnostics only)
    description: str = field(compare=False, default="")
    messy: bool = field(compare=False, default=False)


def _run(chain, x, tools):
    for name in chain:
        x = tools[name](x)
    return x


def generate_task(domain, rng, depth, *, n_public=3, messy=False, recovery=False, attempts=400):
    """Seeded random teacher of exactly `depth` steps, defined on all its inputs.

    With recovery=True a step is a try/except of two tools: the teacher itself
    handles faults that fire on some public inputs (messy open-world data).
    """
    tools = {t.name: t for t in domain.tools}
    names = sorted(tools)
    for _ in range(attempts):
        chain = [rng.choice(names) for _ in range(depth)]
        if any(a == b for a, b in zip(chain, chain[1:])):
            continue
        xs = domain.inputs(rng, n_public + 1, messy=messy)
        steps = [(c,) for c in chain]
        if recovery:
            i = rng.randrange(depth)
            alt = rng.choice([n for n in names if n != chain[i]])
            steps[i] = (chain[i], alt)
        def teach(x):
            for step in steps:
                if len(step) == 1:
                    x = tools[step[0]](x)
                else:
                    try:
                        x = tools[step[0]](x)
                    except Exception:
                        x = tools[step[1]](x)
            return x
        try:
            ys = [teach(x) for x in xs]
        except Exception:
            continue
        if len({vkey(y) for y in ys[:-1]}) < 2 or len({vkey(x) for x in xs}) < len(xs):
            continue
        if all(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue  # identity on every input: not a task
        if recovery:
            # the recovery must actually fire on at least one public input
            i = next(j for j, s in enumerate(steps) if len(s) == 2)
            fired = False
            for x in xs[:-1]:
                v = x
                try:
                    for s in steps[:i]:
                        v = teach_step(s, v, tools)
                    tools[steps[i][0]](v)
                except Exception:
                    fired = True
            if not fired:
                continue
        desc = " then ".join(_describe(s, tools) for s in steps)
        teacher = tuple("|".join(s) for s in steps)
        return Task(domain.name, tuple(zip(xs[:-1], ys[:-1])), xs[-1], ys[-1], teacher, desc, messy)
    return None


def teach_step(step, x, tools):
    if len(step) == 1:
        return tools[step[0]](x)
    try:
        return tools[step[0]](x)
    except Exception:
        return tools[step[1]](x)


def _describe(step, tools):
    if len(step) == 1:
        return tools[step[0]].doc
    return f"{tools[step[0]].doc} otherwise if that fails {tools[step[1]].doc}"


def task_bank(domain, seed, depths, per_depth, **kw):
    rng = random.Random(seed)
    out = []
    for d in depths:
        made = 0
        for _ in range(per_depth * 20):
            t = generate_task(domain, rng, d, **kw)
            if t is not None:
                out.append(t)
                made += 1
            if made == per_depth:
                break
    return out
