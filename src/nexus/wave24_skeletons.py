"""Higher-order program skeletons with typed slots and data-fitted parameters.

A skeleton is a reusable control-flow template (MAP, FILTER, FOLD, GUARD,
ITERATE_UNTIL_STABLE, WINDOW) whose slots are bound to *generic* Python element
operations (no domain bridges). Parameters (thresholds, window sizes) are
fitted from the PUBLIC inputs of the task at hand. Instantiations are ordinary
Tools: every element operation they perform is charged as primitive work.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from nexus.wave24_domains import Tool, vkey

SKELETON_TYPES = ("MAP", "FILTER", "FOLD", "GUARD", "ITERATE", "WINDOW")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# Generic element vocabulary: plain Python operations, applicable to any family.
ELEM_FUNCS = {
    "neg": lambda v: -v, "abs": abs, "inc": lambda v: v + 1, "dec": lambda v: v - 1,
    "double": lambda v: v * 2, "half": lambda v: v / 2, "square": lambda v: v * v,
    "round0": lambda v: round(v), "not1": lambda v: 1 - v,
}
ELEM_PREDS = {
    "gt": lambda v, c: v > c, "lt": lambda v, c: v < c, "eq": lambda v, c: v == c,
}
TYPE_PREDS = {
    "is_none": lambda v: v is None,
    "is_finite_num": lambda v: _num(v) and math.isfinite(v),
}
FOLDS = {
    "sum": sum, "max": max, "min": min, "count": len,
    "prod": lambda xs: math.prod(xs), "mean": lambda xs: sum(xs) / len(xs),
}


def _elements(x):
    if isinstance(x, dict):
        return list(x.values())
    if isinstance(x, (list, tuple, bytes)):
        return list(x)
    raise TypeError("not a container")


def _rebuild(x, elems):
    if isinstance(x, dict):
        return dict(zip(x.keys(), elems))
    if isinstance(x, tuple):
        return tuple(elems)
    if isinstance(x, bytes):
        return bytes(elems)
    return list(elems)


@dataclass(frozen=True)
class SkeletonSpec:
    type: str
    slots: tuple      # names bound into the slots
    params: tuple     # fitted constants

    @property
    def name(self):
        return f"{self.type}({','.join(map(str, self.slots))}{';' if self.params else ''}{','.join(map(repr, self.params))})"


def instantiate(spec, tools_by_name=None):
    """Executable Tool for a skeleton spec. Raises on domain faults (never swallows)."""
    t, s, p = spec.type, spec.slots, spec.params
    if t == "MAP":
        f = ELEM_FUNCS[s[0]]
        fn = lambda x: _rebuild(x, [f(v) for v in _elements(x)])
        cost = 1
    elif t == "FILTER":
        if s[0] in TYPE_PREDS:
            pred = TYPE_PREDS[s[0]]
            keep = (lambda v: not pred(v)) if p and p[0] == "drop" else pred
        else:
            pr, c = ELEM_PREDS[s[0]], p[0]
            keep = lambda v: _num(v) and pr(v, c)
        def fn(x):
            if isinstance(x, dict):
                return {k: v for k, v in x.items() if keep(v)}
            return _rebuild(x, [v for v in _elements(x) if keep(v)])
        cost = 1
    elif t == "FOLD":
        f = FOLDS[s[0]]
        fn = lambda x: f(_elements(x))
        cost = 1
    elif t == "ITERATE":
        step = tools_by_name[s[0]]
        def fn(x, step=step):
            seen = vkey(x)
            fn.last_cost = 0
            for _ in range(8):
                fn.last_cost += step.cost      # exact: every step application is charged, even one that raises
                y = step(x)
                ky = vkey(y)
                if ky == seen:
                    return y
                x, seen = y, ky
            raise ValueError("did not stabilise within 8 iterations")
        fn.last_cost = 0
        cost = step.cost
    elif t == "WINDOW":
        k, f = p[0], FOLDS[s[0]]
        fn = lambda x: [f(_elements(x)[i:i + k]) for i in range(len(_elements(x)) - k + 1)]
        cost = 2
    elif t == "GUARD":
        a, b = tools_by_name[s[1]], tools_by_name[s[2]]
        if s[0] in TYPE_PREDS:
            g = TYPE_PREDS[s[0]]
        else:
            pr, c = ELEM_PREDS[s[0]], p[0]
            g = lambda v: _num(v) and pr(v, c)
        def fn(x, a=a, b=b, g=g):
            key = len(x) if isinstance(x, (list, tuple, dict, bytes, str)) else x
            return a(x) if g(key) else b(x)
        cost = 1 + max(a.cost, b.cost)
    else:
        raise ValueError(t)
    return Tool(spec.name, fn, f"{t.lower()} skeleton", cost, layer=1, parts=(spec.name,),
                kind="skeleton")


def fitted_constants(public_inputs, k=4):
    """Data-fitted thresholds: distinct numeric element values / sizes seen in PUBLIC inputs."""
    vals = set()
    for x in public_inputs:
        try:
            vals |= {v for v in _elements(x) if _num(v) and math.isfinite(v)}
        except TypeError:
            if _num(x):
                vals.add(x)
        if isinstance(x, (list, tuple, dict, bytes, str)):
            vals.add(len(x))
    vals = sorted(vals)
    if len(vals) <= k:
        return vals
    return [vals[int(i * (len(vals) - 1) / (k - 1))] for i in range(k)]


def skeleton_library(public_inputs, domain_tools, types=SKELETON_TYPES, *, guards=False):
    """All instantiations of the allowed skeleton types for this task's public data."""
    consts = fitted_constants(public_inputs)
    container = all(isinstance(x, (list, tuple, dict, bytes)) for x in public_inputs)
    specs = []
    if container:
        if "MAP" in types:
            specs += [SkeletonSpec("MAP", (f,), ()) for f in ELEM_FUNCS]
        if "FILTER" in types:
            specs += [SkeletonSpec("FILTER", (p,), (c,)) for p in ELEM_PREDS for c in consts[:3]]
            specs += [SkeletonSpec("FILTER", (p,), ("drop",)) for p in TYPE_PREDS]
        if "FOLD" in types:
            specs += [SkeletonSpec("FOLD", (f,), ()) for f in FOLDS]
        if "WINDOW" in types:
            specs += [SkeletonSpec("WINDOW", (f,), (2,)) for f in ("sum", "max")]
    if "ITERATE" in types:
        specs += [SkeletonSpec("ITERATE", (t.name,), ()) for t in domain_tools if t.layer == 0]
    by_name = {t.name: t for t in domain_tools}
    return [instantiate(s, by_name) for s in specs]


def guard_candidates(public_inputs, domain_tools, consts=None):
    """Parameterized piecewise schemas GUARD(pred, c, A, B) over primitive tools (used at the last step)."""
    consts = consts if consts is not None else fitted_constants(public_inputs)
    by_name = {t.name: t for t in domain_tools if t.layer == 0}
    out = []
    for p in ELEM_PREDS:
        for c in consts:
            for a in by_name:
                for b in by_name:
                    if a != b:
                        out.append(SkeletonSpec("GUARD", (p, a, b), (c,)))
    return out, by_name


def spec_key(tool):
    """Domain-agnostic schema key of a skeleton tool name, e.g. ('MAP', 'abs') or ('ITERATE', '*')."""
    name = tool.name if hasattr(tool, "name") else tool
    t, rest = name.split("(", 1)
    slot = rest.split(";")[0].split(",")[0].rstrip(")")
    return (t, "*" if t in ("ITERATE", "GUARD") else slot)


def skeletons_in(chain):
    out = []
    for tool in chain:
        if tool.kind == "skeleton":
            out.append(spec_key(tool))
        out += skeletons_in(tool.children) if tool.children else []
    return out
