"""World D - graphs and planning (NOT LOCKED).
Inputs: adjacency lists (row i = successors of node i), prerequisite tables, route cost lists, corridor descriptions.
Verification: D1-D3 finite hidden-test agreement with the reference simulator's answer; D4 formal plan validity: the
simulator executes the plan and requires every move legal, every subgoal achieved in order and the minimal length
(the 'valid' protocol: training labels are demonstration plans; consistency is simulator success, not plan equality).
  D1 directed reachability (k-step closure)          D2 prerequisite/dependency DAG unlocking
  D3 resource-constrained routing (fuel budgets)     D4 multi-stage subgoal planning (keys/switches/doors, irreversible)"""
from .base import Mech, Post

WORLD = "D"
FAMILIES = ("D1", "D2", "D3", "D4")
Q_BUDGET = 4


def _graph(r, nmin, nmax, deg):
    n = r.randint(nmin, nmax)
    return tuple(tuple(sorted(r.sample(range(n), r.randint(0, min(deg, n))))) for _ in range(n))


def _reach(G, s, k):
    S = {s}
    for _ in range(k):
        S |= {v for u in S if 0 <= u < len(G) for v in G[u]}
    return tuple(sorted(S))


def _dag(r, nmin, nmax):
    n = r.randint(nmin, nmax)
    order = list(range(n))
    r.shuffle(order)
    pre = [()] * n
    for idx, v in enumerate(order):
        pre[v] = tuple(sorted(r.sample(order[:idx], r.randint(0, min(2, idx)))))
    owned = tuple(sorted(r.sample(range(n), r.randint(0, n // 2))))
    return tuple(pre), owned


def _unlock(pre, owned, mode):
    o = set(owned)
    new = [i for i in range(len(pre)) if i not in o and set(pre[i]) <= o]
    return tuple(sorted(new)) if mode == "new" else tuple(sorted(o | set(new)))


def _route(r, nmin, nmax, cmax):
    return tuple(r.randint(1, cmax) for _ in range(r.randint(nmin, nmax)))


def _fuel(costs, B, mode):
    t, s = 0, 0
    for c in costs:
        if s + c > B:
            break
        s += c
        t += 1
    return t if mode == "steps" else B - s


MOVE = {1: +1, 2: -1}


def _corridor(r, n_lo, n_hi, stages):
    n = r.randint(n_lo, n_hi)
    pts = r.sample(range(n), stages + 2)
    return (n,) + tuple(pts)            # (length, agent, subgoal_1, ..., goal)


def _plan(x):
    pos, out = x[1], []
    for tgt in x[2:]:
        while pos != tgt:
            step = 1 if tgt > pos else 2
            out.append(step)
            pos += MOVE[step]
    return tuple(out)


def _valid_plan(x, y):
    if not isinstance(y, tuple) or len(y) != len(_plan(x)):
        return False
    n, pos, targets = x[0], x[1], list(x[2:])
    for a in y:
        if a not in MOVE:
            return False
        pos += MOVE[a]
        if not 0 <= pos < n:
            return False
        if targets and pos == targets[0]:
            targets.pop(0)
    return not targets


def gen(family, rng, level):
    if family == "D1":
        k = rng.randint(1, 3)
        return Mech(fn=lambda x: _reach(x[0], x[1], k), sig=("L", "i"), out="l", descr=f"reach[k={k}]",
                    train=lambda r: (lambda G: (G, r.randrange(len(G))))(_graph(r, 4, 6, 2)),
                    iface=lambda r: (lambda G: (G, r.randrange(len(G))))(_graph(r, 3, 8, 3)))
    if family == "D2":
        mode = rng.choice(("new", "all"))
        return Mech(fn=lambda x: _unlock(x[0], x[1], mode), sig=("L", "l"), out="l", descr=f"unlock[{mode}]",
                    train=lambda r: _dag(r, 4, 6), iface=lambda r: _dag(r, 3, 8))
    if family == "D3":
        mode = rng.choice(("steps", "left"))
        B = rng.randint(5, 12)
        return Mech(fn=lambda x: _fuel(x[0], B, mode), sig=("l",), out="i", descr=f"fuel[{mode},B={B}]",
                    train=lambda r: (_route(r, 3, 6, 4),), iface=lambda r: (_route(r, 0, 9, 6),))
    if family == "D4":
        stages = {1: 0, 2: 1, 3: 1, 4: 2}[level]
        lo, hi = (4, 7) if level < 3 else (6, 10)
        return Mech(fn=lambda x: _plan(x[0]), sig=("l",), out="l", descr=f"plan[stages={stages}]", protocol="valid",
                    valid=lambda x, y: _valid_plan(x[0], y),
                    train=lambda r: (_corridor(r, lo, hi, stages),), iface=lambda r: (_corridor(r, lo, hi + 2, stages),),
                    verify_kind="plan_validity", own_levels=True)
    raise KeyError(family)


def posts(family, rng):
    if family == "D3":
        mode = rng.choice(("steps", "left"))
        B = rng.randint(5, 12)
        return [Post(lambda l: _fuel(tuple(max(1, c) for c in l), B, mode), "l", "i", f"fuel[{mode},B={B}]")]
    return []
