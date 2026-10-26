"""Differential generator: random evidence checked by Checker v2 and Checker v3 (verdict fields compared)."""
import random

from nexus import checker_kernel_v2 as V2
from nexus import checker_kernel_v3 as V3

FIELDS = ("label", "reason", "k", "k_exact", "fitting", "answers", "witnesses")
POOL = [{"op": "Sort", "path": ".", "desc": False}, {"op": "Sort", "path": ".", "desc": True}, {"op": "run_heads"},
        {"op": "rotate", "k": 1}, {"op": "rotate", "k": 2}, {"op": "prefix_sum"}, {"op": "diff"}, {"op": "running_max"},
        {"op": "map_add", "c": 1}, {"op": "map_mul", "c": 2}, {"op": "map_mod", "c": 3},
        {"op": "F", "pred": {"path": ".", "cmp": "ge", "val": 2}}, {"op": "S", "k": 2, "path": ".", "desc": True},
        {"op": "comp", "cond": "head", "cparam": 2, "transform": "id", "path": ".", "desc": False},
        {"op": "comp", "cond": "first_occ", "cparam": ".", "transform": "id", "path": "#", "desc": True},
        {"op": "group_count", "path": "."}, {"op": "repeat", "n": 2, "body": {"op": "rotate", "k": 1}},
        {"op": "enc_counter", "path": "."}, {"op": "ir_counter_top", "k": 1}, {"op": "ir_counter_top", "k": 2},
        {"op": "ir_counter_keys"}, {"op": "dec_counter"}, {"op": "enc_chars"}, {"op": "dec_chars"},
        {"op": "proj", "path": "a"}, {"op": "proj", "path": "b"},
        {"op": "enc_cells"}, {"op": "enc_objects", "conn": 4, "background": 0}, {"op": "enc_objects", "conn": 8, "background": 0},
        {"op": "dec_objects", "background": 0}, {"op": "ir_objects_sizes"}, {"op": "ir_objects_filter_size", "min": 2, "max": 144},
        {"op": "ir_objects_recolor", "color": 5}, {"op": "ir_objects_keep_color", "color": 1},
        {"op": "grid_coord", "a": -1, "b": -1, "c": 1, "d": 0}, {"op": "grid_coord", "a": 1, "b": 0, "c": -1, "d": -1},
        {"op": "grid_connect", "moves": [[1, 2], [2, 1], [-1, 2], [-2, 1], [1, -2], [2, -1], [-1, -2], [-2, -1]],
         "passable": 0, "seed": 2, "fill": 3},
        {"op": "grid_cellwise", "table": [[a, b, a ^ b] for a in range(4) for b in range(4)], "dr": 0, "dc": 1},
        {"op": "enc_graph", "moves": [[0, 1], [1, 0]], "passable": 0}, {"op": "ir_graph_reach", "seeds": [0]},
        {"op": "ir_graph_degrees"}, {"op": "seq", "body": [{"op": "Sort", "path": ".", "desc": False}, {"op": "run_heads"}]},
        {"op": "seq", "body": [{"op": "enc_counter", "path": "."}, {"op": "ir_counter_keys"}]}]


def sample(rng, dom):
    if dom == "ints":
        return [rng.randrange(5) for _ in range(rng.randint(0, 6))]
    if dom == "str":
        return "".join(rng.choice("abc") for _ in range(rng.randint(1, 6)))
    if dom == "grid":
        n, m = rng.randint(2, 4), rng.randint(2, 4)
        return [[rng.choice((0, 0, 1, 2, 3)) for _ in range(m)] for _ in range(n)]
    if dom == "rec":
        return [{"a": rng.randrange(4), "b": rng.randrange(4)} for _ in range(rng.randint(1, 5))]
    e = sorted({(rng.randrange(5), rng.randrange(5)) for _ in range(6)})
    return {"nodes": list(range(5)), "edges": [list(p) for p in e]}


def case(rng, depth=None, n_tools=None):
    dom = rng.choice(("ints", "str", "grid", "rec", "graph"))
    T = rng.sample(POOL, n_tools or rng.randint(3, 8))
    D = depth or rng.randint(1, 3)
    for _ in range(50):
        chain = [rng.choice(T) for _ in range(rng.randint(1, D))]
        xs = [sample(rng, dom) for _ in range(rng.randint(2, 4))]
        ys = [V2.run(chain, x)[0] for x in xs]
        if V2.ERROR in ys:
            continue
        pub = [[x, y] for x, y in zip(xs[:-1], ys[:-1])]
        ev = {"public": pub, "query": xs[-1], "claimed_answer": ys[-1], "candidate": chain,
              "scope": {"kind": rng.choice(("exhaustive", "exhaustive", "proposal")), "tools": T, "max_depth": D},
              "lemmas": [], "trace": {}}
        return ev
    return None


def both(ev, proofs=()):
    a = V2.check(dict(ev, checker_version=2))
    b = V3.check(dict(ev, checker_version=3, proofs=list(proofs)))
    return a, b


def same(a, b):
    return all(a.get(f) == b.get(f) for f in FIELDS)
