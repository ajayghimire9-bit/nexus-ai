"""Wave 33 task streams (EVALUATOR SIDE ONLY; the solver never imports this).
Milestone B evolution / selection streams use the Wave 31 increment-3 family. The TEST family F2 (IR-routed mechanisms:
mode, distinct counter keys, object sizes, degree statistics, `proj b` leaf) appears in no earlier wave."""
from __future__ import annotations

import random

from nexus import wave31_tasks as T

C = {"topc": {"op": "ir_counter_top", "k": 1}, "keys": {"op": "ir_counter_keys"}, "cnt": {"op": "enc_counter", "path": "."},
     "sizes": {"op": "ir_objects_sizes"}, "objs": {"op": "enc_objects", "conn": 4, "background": 0},
     "deg": {"op": "ir_graph_degrees"}, "reach": {"op": "ir_graph_reach", "seeds": [0]}, "cells": {"op": "enc_cells"},
     "chars": {"op": "enc_chars"}, "pa": {"op": "proj", "path": "a"}, "pb": {"op": "proj", "path": "b"},
     "Sort": {"op": "Sort", "path": ".", "desc": False}, "RUNH": {"op": "run_heads"}, "rot": {"op": "rotate", "k": 1},
     "psum": {"op": "prefix_sum"}, "diff": {"op": "diff"}, "rmax": {"op": "running_max"}}
F2 = {"records": (("pa", "cnt", "topc", "keys"), ("pb", "cnt", "keys", "diff"), ("pb", "rmax", "rot", "Sort")),
      "strings": (("chars", "cnt", "topc", "keys"), ("chars", "cnt", "keys", "rot")),
      "grids": (("objs", "sizes", "Sort", "RUNH"), ("cells", "cnt", "topc", "keys"), ("objs", "sizes", "psum")),
      "graphs": (("deg", "topc", "keys"), ("deg", "keys", "rot"), ("reach", "diff", "rmax"))}


def f2_stream(seed, rep):
    rng = random.Random(f"w33-f2:{seed}:{rep}")
    out = []
    for d, progs in F2.items():
        for names in progs:
            for _ in range(rep):
                t = T._task(d, [dict(C[n]) for n in names], rng, 4, core=list(names), category="F2")
                if t:
                    out.append(t)
    random.Random(f"w33-f2-order:{seed}:{rep}").shuffle(out)
    return out


def evo_streams(seed):
    """Three regimes per seed on two seeded domains of the increment-3 family: 2 reps, 3 reps, mixed (2 then 3)."""
    rng = random.Random(f"w33-evo:{seed}")
    doms = rng.sample(("records", "strings", "grids", "graphs"), 2)

    def seg(sub, rep):
        ts = [t for d in doms for t in T.target_stream3(f"{seed}{sub}", d, rep)]
        random.Random(f"w33-evo-order:{seed}:{sub}").shuffle(ts)
        return ts
    return {"2rep": seg("a", 2), "3rep": seg("b", 3), "mixed": seg("c", 2) + seg("d", 3)}
