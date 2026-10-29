"""World C - spatial objects on grids [WHOLLY HELD-OUT TARGET WORLD] (NOT LOCKED).
Inputs: grids (tuples of rows), background 0, colours 1..4; training boards 3x3..5x5, test boards 2x2..6x7 (varying
dimensions and object topologies). Occluded cells are -1. Verification: exact multi-grid agreement on 30 hidden boards.
  C1 connected-component grouping & occupancy/bounding statistics
  C2 relational transformations (reflection, rotation, transposition, recolouring, scaling)
  C3 occluded observation reconstruction (symmetry completion / background fill)
  C4 object actions under boundary & collision constraints (gravity, clipped translation)"""
from .base import Mech, Post

WORLD = "C"
FAMILIES = ("C1", "C2", "C3", "C4")
Q_BUDGET = 2


def _grid(rng, hmin, hmax, wmin, wmax, density=0.4, colours=(1, 2, 3, 4)):
    h, w = rng.randint(hmin, hmax), rng.randint(wmin, wmax)
    return tuple(tuple(rng.choice(colours) if rng.random() < density else 0 for _ in range(w)) for _ in range(h))


def _tr(r):
    return (_grid(r, 3, 5, 3, 5),)


def _if(r):
    return (_grid(r, 2, 6, 2, 7, density=r.choice((0.2, 0.4, 0.6))),)


def _components(g):
    h = len(g)
    seen, comps = set(), []
    for i in range(h):
        for j in range(len(g[i])):
            if g[i][j] > 0 and (i, j) not in seen:
                stack, n = [(i, j)], 0
                seen.add((i, j))
                while stack:
                    a, b = stack.pop()
                    n += 1
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        u, v = a + da, b + db
                        if 0 <= u < h and 0 <= v < len(g[u]) and g[u][v] > 0 and (u, v) not in seen:
                            seen.add((u, v))
                            stack.append((u, v))
                comps.append(n)
    return comps


def _stats(rng):
    v = rng.choice(("occupied_rows", "row_counts", "n_components", "largest"))
    f = {"occupied_rows": lambda g: sum(1 for r in g if any(x > 0 for x in r)),
         "row_counts": lambda g: tuple(sum(1 for x in r if x > 0) for r in g),
         "n_components": lambda g: len(_components(g)),
         "largest": lambda g: max(_components(g), default=0)}[v]
    return f, ("l" if v == "row_counts" else "i"), f"stats[{v}]"


def _T(g):
    if not g:
        return ()
    w = max(len(r) for r in g)
    return tuple(tuple(r[j] if j < len(r) else 0 for r in g) for j in range(w))


def _transform(rng):
    v = rng.choice(("reflect_lr", "reflect_ud", "transpose", "rot90", "recolour", "scale2"))
    a, b = rng.sample((1, 2, 3, 4), 2)
    f = {"reflect_lr": lambda g: tuple(r[::-1] for r in g), "reflect_ud": lambda g: g[::-1], "transpose": _T,
         "rot90": lambda g: tuple(r[::-1] for r in _T(g)),
         "recolour": lambda g: tuple(tuple(b if x == a else x for x in r) for r in g),
         "scale2": lambda g: tuple(tuple(x for x in r for _ in range(2)) for r in g for _ in range(2))}[v]
    return f, f"transform[{v}{f',{a}->{b}' if v == 'recolour' else ''}]"


def _occluded(rng, hmin, hmax, wmin, wmax, mode):
    def s(r):
        h, w = r.randint(hmin, hmax), r.randint(wmin, wmax)
        if mode == "lr":
            half = [[r.choice((1, 2, 3, 4)) if r.random() < 0.5 else 0 for _ in range((w + 1) // 2)] for _ in range(h)]
            g = [row + row[:w // 2][::-1] for row in half]
        elif mode == "ud":
            top = [[r.choice((1, 2, 3, 4)) if r.random() < 0.5 else 0 for _ in range(w)] for _ in range((h + 1) // 2)]
            g = top + top[:h // 2][::-1]
        else:
            g = [[r.choice((1, 2, 3, 4)) if r.random() < 0.5 else 0 for _ in range(w)] for _ in range(h)]
        cells = [(i, j) for i in range(len(g)) for j in range(len(g[i]))]
        for (i, j) in r.sample(cells, max(1, len(cells) // 6)):
            g[i][j] = -1
        return (tuple(tuple(row) for row in g),)
    return s


def _restore(mode):
    if mode == "lr":
        return lambda g: tuple(tuple(x if x >= 0 else max(y, 0) for x, y in zip(r, r[::-1])) for r in g)
    if mode == "ud":
        return lambda g: tuple(tuple(x if x >= 0 else max(y, 0) for x, y in zip(r, q)) for r, q in zip(g, g[::-1]))
    return lambda g: tuple(tuple(max(x, 0) for x in r) for r in g)


def _act(rng):
    v = rng.choice(("gravity_down", "gravity_left", "shift_right", "shift_down"))

    def push(seq):
        nz = [x for x in seq if x > 0]
        return (0,) * (len(seq) - len(nz)) + tuple(nz)

    def gl(g):
        return tuple(tuple([x for x in r if x > 0] + [0] * sum(1 for x in r if x <= 0)) for r in g)

    f = {"gravity_down": lambda g: _T(tuple(push(c) for c in _T(g))) if g else g,
         "gravity_left": gl,
         "shift_right": lambda g: tuple(((0,) + r[:-1]) if r else r for r in g),
         "shift_down": lambda g: (((0,) * len(g[0]),) + g[:-1]) if g else g}[v]
    return f, f"act[{v}]"


def gen(family, rng, level):
    if family == "C1":
        f, out, d = _stats(rng)
        return Mech(fn=lambda x: f(x[0]), sig=("L",), out=out, descr=d, train=_tr, iface=_if)
    if family == "C2":
        f, d = _transform(rng)
        return Mech(fn=lambda x: f(x[0]), sig=("L",), out="L", descr=d, train=_tr, iface=_if)
    if family == "C3":
        mode = rng.choice(("lr", "ud", "fill"))
        f = _restore(mode)
        return Mech(fn=lambda x: f(x[0]), sig=("L",), out="L", descr=f"restore[{mode}]",
                    train=_occluded(rng, 3, 5, 3, 5, mode), iface=_occluded(rng, 2, 6, 2, 7, mode))
    if family == "C4":
        f, d = _act(rng)
        return Mech(fn=lambda x: f(x[0]), sig=("L",), out="L", descr=d, train=_tr, iface=_if)
    raise KeyError(family)


def posts(family, rng):
    if family == "C2":
        f, d = _transform(rng)
        return [Post(f, "L", "L", d)]
    if family == "C4":
        f, d = _act(rng)
        return [Post(f, "L", "L", d)]
    if family == "C1":
        f, out, d = _stats(rng)
        return [Post(f, "L", out, d)]
    return []
