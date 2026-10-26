"""Wave 38 domain 5: planning (NOT LOCKED). Evidence class: VALIDATED_PLAN (an independent simulator checks every
precondition and the goal; plan length vs the published optimum where known). Never a uniqueness certificate.

* Minimal STRIPS PDDL parser (untyped :strips: blocksworld from planning.domains) and an internal STRIPS domain
  (logistics-lite with truck capacity and fuel; a dynamics-shift variant changes an action's preconditions mid-stream).
* Planner: greedy best-first search, h(s) = sum_w w[pred] * (#goal atoms of predicate `pred` not yet true), with expansion
  budget; w = 1 is the generic goal-count heuristic. Learned weights come from solved plans (experience).
* validate(): an INDEPENDENT simulator (no planner code) applying the plan to the initial state."""
from __future__ import annotations

import heapq
import itertools
import re


# --------------------------------------------------------------------------- PDDL (untyped STRIPS)
def _tok(s):
    s = re.sub(r";[^\n]*", "", s.lower())
    return re.findall(r"\(|\)|[^\s()]+", s)


def _parse(tokens):
    stack, cur = [], []
    for t in tokens:
        if t == "(":
            stack.append(cur); cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t)
    return cur[0]


def _find(tree, head):
    for e in tree:
        if isinstance(e, list) and e and e[0] == head:
            return e
    return None


def _atoms(e):
    if not e:
        return []
    if e[0] == "and":
        return [tuple(a) for a in e[1:]]
    return [tuple(e)]


def parse_domain(text):
    tree = _parse(_tok(text))
    acts = {}
    for e in tree:
        if isinstance(e, list) and e and e[0] == ":action":
            name = e[1]
            d = dict(zip(e[2::2], e[3::2]))
            eff = _atoms(d.get(":effect", []))
            acts[name] = dict(params=d.get(":parameters", []), pre=_atoms(d.get(":precondition", [])),
                              add=[a for a in eff if a[0] != "not"], dele=[tuple(a[1]) for a in eff if a[0] == "not"])
    return acts


def parse_problem(text):
    tree = _parse(_tok(text))
    objs = [o for o in _find(tree, ":objects")[1:] if o != "-"]
    init = frozenset(tuple(a) for a in _find(tree, ":init")[1:])
    goal = frozenset(_atoms(_find(tree, ":goal")[1]))
    return objs, init, goal


def ground(acts, objs):
    out = []
    for name, a in acts.items():
        ps = a["params"]
        for combo in itertools.product(objs, repeat=len(ps)):
            if len(set(combo)) < len(combo):
                continue
            m = dict(zip(ps, combo))
            sub = lambda at: tuple(m.get(x, x) for x in at)
            out.append((name, combo, frozenset(map(sub, a["pre"])), frozenset(map(sub, a["add"])), frozenset(map(sub, a["dele"]))))
    return out


# --------------------------------------------------------------------------- internal STRIPS domain (logistics-lite)
def logistics(r, n_loc=4, n_pkg=3, capacity=2, shifted=False):
    """Trucks move between adjacent locations (a ring) spending fuel units; load/unload respects capacity. `shifted`: unloading
    additionally requires the location to be a depot (a dynamics change)."""
    locs = [f"l{i}" for i in range(n_loc)]
    pk = [f"p{i}" for i in range(n_pkg)]
    fuel = [f"f{i}" for i in range(6)]
    slots = [f"s{i}" for i in range(capacity + 1)]
    init = {("at", "t0", "l0"), ("fuel", "t0", "f5"), ("load", "t0", "s0")}
    for i in range(5):
        init.add(("dec", fuel[i + 1], fuel[i]))
    for i in range(capacity):
        init.add(("inc", slots[i], slots[i + 1]))
    for i in range(n_loc):
        init.add(("adj", locs[i], locs[(i + 1) % n_loc])); init.add(("adj", locs[(i + 1) % n_loc], locs[i]))
    depots = set(r.sample(locs, 2))
    for d in depots:
        init.add(("depot", d))
    goal = set()
    for p in pk:
        a, b = r.sample(locs, 2)
        init.add(("pat", p, a)); goal.add(("pat", p, b))
        if shifted and b not in depots:
            goal.discard(("pat", p, b)); goal.add(("pat", p, sorted(depots)[0]))
    acts = []
    for a in locs:
        for b in locs:
            if a != b:
                for i in range(5):
                    acts.append(("drive", ("t0", a, b, fuel[i + 1]), frozenset({("at", "t0", a), ("adj", a, b), ("fuel", "t0", fuel[i + 1])}),
                                 frozenset({("at", "t0", b), ("fuel", "t0", fuel[i])}), frozenset({("at", "t0", a), ("fuel", "t0", fuel[i + 1])})))
    for p in pk:
        for l in locs:
            for i in range(capacity):
                acts.append(("loadp", (p, l, slots[i]), frozenset({("at", "t0", l), ("pat", p, l), ("load", "t0", slots[i])}),
                             frozenset({("in", p), ("load", "t0", slots[i + 1])}), frozenset({("pat", p, l), ("load", "t0", slots[i])})))
                pre = {("at", "t0", l), ("in", p), ("load", "t0", slots[i + 1])} | ({("depot", l)} if shifted else set())
                acts.append(("unload", (p, l, slots[i + 1]), frozenset(pre),
                             frozenset({("pat", p, l), ("load", "t0", slots[i])}), frozenset({("in", p), ("load", "t0", slots[i + 1])})))
    for l in locs:                                                     # refuel at depots
        for i in range(5):
            acts.append(("refuel", ("t0", l, fuel[i]), frozenset({("at", "t0", l), ("depot", l), ("fuel", "t0", fuel[i])}),
                         frozenset({("fuel", "t0", "f5")}), frozenset({("fuel", "t0", fuel[i])})))
    return frozenset(init), frozenset(goal), acts


# --------------------------------------------------------------------------- planner + validator
def plan(init, goal, acts, weights=None, budget=20000):
    """Greedy best-first with a weighted goal-count heuristic. Returns (plan or None, expansions)."""
    w = weights or {}

    def h(s):
        return sum(w.get(g[0], 1.0) for g in goal if g not in s)
    start = frozenset(init)
    heap = [(h(start), 0, 0, start, ())]
    seen = {start}
    tick = exp = 0
    while heap:
        _hv, g, _t, s, pl = heapq.heappop(heap)
        if goal <= s:
            return list(pl), exp
        exp += 1
        if exp > budget:
            return None, exp
        for name, args, pre, add, dele in acts:
            if pre <= s:
                s2 = (s - dele) | add
                if s2 not in seen:
                    seen.add(s2); tick += 1
                    heapq.heappush(heap, (h(s2) + 0.01 * (g + 1), g + 1, tick, s2, pl + ((name, args),)))
    return None, exp


def validate(init, goal, acts, pl):
    """Independent simulator: every action must exist with satisfied preconditions; the goal must hold at the end."""
    table = {(n, tuple(a)): (pre, add, dele) for n, a, pre, add, dele in acts}
    s = set(init)
    for n, a in pl:
        k = (n, tuple(a))
        if k not in table:
            return False
        pre, add, dele = table[k]
        if not pre <= s:
            return False
        s = (s - dele) | add
    return goal <= s


def learn_weights(solved):
    """Experience: weight of predicate p = mean (plan length / #unsatisfied goal atoms of p) over solved tasks (>= 0.5)."""
    acc = {}
    for init, goal, pl in solved:
        by = {}
        for g in goal:
            if g not in init:
                by[g[0]] = by.get(g[0], 0) + 1
        for p, n in by.items():
            acc.setdefault(p, []).append(len(pl) / max(1, n))
    return {p: max(0.5, sum(v) / len(v)) for p, v in acc.items()}
