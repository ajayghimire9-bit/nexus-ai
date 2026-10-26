"""Wave 30 counterfactual ("alien") grid-world generator. FROZEN before any final_sealed instance is drawn.

Fresh instances generated after freezing the generator and model reduce exact-instance contamination. They do not
establish that the underlying concepts were absent from pretraining.

Families (each with an executable reference mechanism and an enumerable parameter space):
  * connectivity: cells of a passable colour reachable from the seed cell under a counterfactual move set
    (knight, camel, zebra, king) are recoloured;
  * coord: out[i][j] = in[(a*i + b) % H][(c*j + d) % W] (wrapped, permuted coordinates);
  * algebra: out[i][j] = in[i][j] (+) in[i][(j + 1) % W] under a randomly relabelled group of order 4
    (Z4 or Z2 x Z2).
Observation interface: 3 demonstration pairs plus a test input, and a charged oracle for active probes.
Unavoidable ambiguity is explicit. Every parameter setting of the family is enumerated, and the record states
how many fit the demonstrations and how many distinct test outputs they give.
Splits: dev seeds (any), admission_val, final_sealed (registry `wave30/final_sealed`, drawn only by a locked
runner after freezing).
"""
from __future__ import annotations

import itertools
import random

MOVES = {"knight": [(1, 2), (2, 1)], "camel": [(1, 3), (3, 1)], "zebra": [(2, 3), (3, 2)], "king": [(0, 1), (1, 1), (1, 0)]}


def _moves(name):
    out = set()
    for a, b in MOVES[name]:
        for sa in (1, -1):
            for sb in (1, -1):
                out.add((sa * a, sb * b))
    return sorted(out)


def connectivity(grid, move, passable, seed_c, fill):
    H, W = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    seeds = [(i, j) for i in range(H) for j in range(W) if grid[i][j] == seed_c]
    seen, todo = set(seeds), list(seeds)
    while todo:
        i, j = todo.pop()
        for di, dj in _moves(move):
            a, b = i + di, j + dj
            if 0 <= a < H and 0 <= b < W and (a, b) not in seen and grid[a][b] == passable:
                seen.add((a, b))
                todo.append((a, b))
                out[a][b] = fill
    return out


def coord(grid, a, b, c, d):
    H, W = len(grid), len(grid[0])
    return [[grid[(a * i + b) % H][(c * j + d) % W] for j in range(W)] for i in range(H)]


def group_table(kind, perm):
    """Order-4 group op on colours 0..3 relabelled by `perm` (colour -> group element)."""
    inv = {g: c for c, g in enumerate(perm)}
    if kind == "Z4":
        op = lambda x, y: (x + y) % 4
    else:
        op = lambda x, y: x ^ y
    return {(c1, c2): inv[op(perm[c1], perm[c2])] for c1 in range(4) for c2 in range(4)}


def algebra(grid, kind, perm):
    t = group_table(kind, perm)
    W = len(grid[0])
    return [[t[(row[j], row[(j + 1) % W])] for j in range(W)] for row in grid]


def params(fam, H, W):
    if fam == "connectivity":
        return [("connectivity", m, 1, 2, 3) for m in MOVES]
    if fam == "coord":
        from math import gcd
        return [("coord", a, b, c, d) for a in range(1, H) if gcd(a, H) == 1 for b in range(H)
                for c in range(1, W) if gcd(c, W) == 1 for d in range(W)]
    return [("algebra", k, tuple(p)) for k in ("Z4", "Z2xZ2") for p in itertools.permutations(range(4))]


def apply(p, grid):
    if p[0] == "connectivity":
        return connectivity(grid, *p[1:])
    if p[0] == "coord":
        return coord(grid, *p[1:])
    return algebra(grid, p[1], list(p[2]))


def _grid(rng, fam, H, W):
    if fam == "connectivity":
        g = [[1 if rng.random() < 0.45 else 0 for _ in range(W)] for _ in range(H)]
        g[rng.randrange(H)][rng.randrange(W)] = 2
        return g
    if fam == "coord":
        return [[rng.randrange(4) for _ in range(W)] for _ in range(H)]
    return [[rng.randrange(4) for _ in range(W)] for _ in range(H)]


def draw(seed, fam=None, n_train=3):
    rng = random.Random(f"w30-alien:{seed}")
    fam = fam or rng.choice(("connectivity", "coord", "algebra"))
    H, W = (7, 7) if fam == "connectivity" else (rng.choice((4, 5)), rng.choice((4, 5, 6)))
    space = params(fam, H, W)
    for _ in range(200):
        p = rng.choice(space)
        xs = [_grid(rng, fam, H, W) for _ in range(n_train + 1)]
        ys = [apply(p, x) for x in xs]
        if any(x == y for x, y in zip(xs, ys)):
            continue
        fit = [q for q in space if all(apply(q, x) == y for x, y in zip(xs[:n_train], ys[:n_train]))]
        outs = {repr(apply(q, xs[-1])) for q in fit}
        return dict(family=fam, train=list(zip(xs[:n_train], ys[:n_train])), test_input=xs[-1], answer=ys[-1],
                    reference=p, fitting_params=len(fit), distinct_test_outputs=len(outs),
                    ambiguity="none" if len(outs) == 1 else f"unavoidable_within_family(k={len(outs)})",
                    oracle=lambda x, p=p: apply(p, x))
    return None
