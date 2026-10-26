"""Wave 38 task domains (EVALUATOR SIDE ONLY; the solver never imports this). Program domains 1-4: tasks = teacher programs
in the Wave 38 language over randomly generated inputs. Each domain lists SOURCE mechanisms and WITHHELD mechanisms
(withheld = never used in any source training for transfer experiments). Domains 5 (planning) and 6 (Python repairs) have
their own engines (w38_planning, w38_repair)."""
from __future__ import annotations

import random

from nexus import w38_lang as L

X = ["x"]


def _name(r):
    return r.choice(["ana", "bo", "cy", "dee", "eli", "fay", "gus", "hal"])


def gen_input(domain, r, variant):
    if domain == "strings":
        if variant == "kv":
            n = r.randint(2, 4)
            return ";".join(f"{_name(r)}={r.randint(0, 99)}" for _ in range(n))
        if variant == "csv":
            return ",".join(r.choice([_name(r), str(r.randint(0, 99))]) for _ in range(r.randint(3, 5)))
        if variant == "nested":
            return ",".join(f"{_name(r)}|{r.randint(0, 9)}" for _ in range(r.randint(2, 4)))
        return " ".join(_name(r) for _ in range(r.randint(2, 4)))
    if domain == "tables":
        depts = ["ops", "dev", "hr"]
        if variant == "join":
            ids = r.sample(range(1, 9), r.randint(3, 5))
            return {"L": [{"id": i, "x": r.randint(0, 9)} for i in ids],
                    "R": [{"id": i, "y": r.randint(0, 9)} for i in r.sample(ids, max(2, len(ids) - 1))]}
        return [{"name": _name(r), "dept": r.choice(depts), "x": r.choice([None, r.randint(0, 9), r.randint(0, 9)])}
                for _ in range(r.randint(3, 6))]
    if domain == "grids":
        n = r.choice((4, 5))
        return [[r.choice((0, 0, 0, 1, 1, 2, 3)) for _ in range(n)] for _ in range(n)]
    nodes = list(range(r.randint(4, 6)))
    edges = sorted({(a, b) for a in nodes for b in nodes if a < b and r.random() < 0.35})
    return {"nodes": nodes, "edges": [list(e) for e in edges]}


# (domain, mechanism) -> (input variant, teacher program, source?)
MECH = {
    ("strings", "kv_sum"): ("kv", [{"op": "split", "d": ";"}, {"op": "map", "f": ["int", ["aft", X, "="]]},
                                   {"op": "fold", "o": "add", "init": 0}], True),
    ("strings", "kv_keys"): ("kv", [{"op": "split", "d": ";"}, {"op": "map", "f": ["bef", X, "="]}, {"op": "join", "d": ","}], True),
    ("strings", "csv_count_digits"): ("csv", [{"op": "split", "d": ","}, {"op": "filter", "p": ["isdig", X]}, {"op": "len"}], True),
    ("strings", "initials"): ("words", [{"op": "words"}, {"op": "map", "f": ["up", ["fst", X]]}, {"op": "join", "d": ""}], False),
    ("strings", "nested_max"): ("nested", [{"op": "split", "d": ","}, {"op": "map", "f": ["int", ["aft", X, "|"]]},
                                           {"op": "fold", "o": "max", "init": -10**6}], False),
    ("tables", "join_y"): ("join", [{"op": "tjoin", "k": "id"}, {"op": "map", "f": ["f", "y"]}], True),
    ("tables", "dept_counts"): ("rows", [{"op": "countby", "f": ["f", "dept"]}, {"op": "map", "f": ["f", "count"]}], True),
    ("tables", "fill_sum"): ("rows", [{"op": "fill", "k": "x", "v": 0}, {"op": "map", "f": ["f", "x"]},
                                      {"op": "fold", "o": "add", "init": 0}], True),
    ("tables", "present_names"): ("rows", [{"op": "filter", "p": ["not", ["eq", ["f", "x"], ["c", None]]]},
                                           {"op": "map", "f": ["f", "name"]}, {"op": "join", "d": ","}], False),
    ("tables", "join_sorted_x"): ("join", [{"op": "tjoin", "k": "id"}, {"op": "sortby", "f": ["f", "y"], "desc": False},
                                           {"op": "map", "f": ["f", "x"]}], False),
    ("grids", "obj_sizes"): ("g", [{"op": "objs", "conn": 4, "bg": 0}, {"op": "map", "f": ["f", "size"]},
                                   {"op": "sortby", "f": X, "desc": True}], True),
    ("grids", "count_big"): ("g", [{"op": "objs", "conn": 4, "bg": 0}, {"op": "filter", "p": ["gt", ["f", "size"], ["c", 1]]},
                                   {"op": "len"}], True),
    ("grids", "recolor_big"): ("g", [{"op": "objs", "conn": 4, "bg": 0},
                                     {"op": "recolor_if", "p": ["gt", ["f", "size"], ["c", 1]], "color": 3},
                                     {"op": "paint", "bg": 0, "h": None, "w": None}], False),
    ("grids", "largest_color"): ("g", [{"op": "objs", "conn": 8, "bg": 0}, {"op": "best", "f": ["f", "size"]},
                                       {"op": "get", "k": "color"}], False),
    ("graphs", "topo"): ("graph", [{"op": "topo"}], True),
    ("graphs", "reach_count"): ("graph", [{"op": "reach", "s": 0}, {"op": "len"}], True),
    ("graphs", "max_indeg_node"): ("graph", [{"op": "indeg"}, {"op": "best", "f": ["f", "deg"]}, {"op": "get", "k": "node"}], True),
    ("graphs", "sinks"): ("graph", [{"op": "outdeg"}, {"op": "filter", "p": ["eq", ["f", "deg"], ["c", 0]]},
                                    {"op": "map", "f": ["f", "node"]}], False),
    ("graphs", "topo_last2"): ("graph", [{"op": "topo"}, {"op": "rev"}, {"op": "take", "n": 2}], False),
    # ---- widened (Stage 1 -> 2): scans, conditionals inside lambdas, counting, sorting, degree folds
    ("strings", "csv_running"): ("csv", [{"op": "split", "d": ","}, {"op": "filter", "p": ["isdig", X]},
                                         {"op": "map", "f": ["int", X]}], True),
    ("strings", "word_lens"): ("words", [{"op": "words"}, {"op": "map", "f": ["len", X]}], True),
    ("strings", "kv_scan"): ("kv", [{"op": "split", "d": ";"}, {"op": "map", "f": ["int", ["aft", X, "="]]},
                                    {"op": "scan", "o": "add", "init": 0}], False),
    ("strings", "words_sorted"): ("words", [{"op": "words"}, {"op": "sortby", "f": X, "desc": False}, {"op": "join", "d": ","}], False),
    ("tables", "x_running"): ("rows", [{"op": "fill", "k": "x", "v": 0}, {"op": "map", "f": ["f", "x"]},
                                       {"op": "scan", "o": "max", "init": -10**6}], True),
    ("tables", "dept_keys"): ("rows", [{"op": "countby", "f": ["f", "dept"]}, {"op": "map", "f": ["f", "key"]}], True),
    ("tables", "names_by_x"): ("rows", [{"op": "fill", "k": "x", "v": 0}, {"op": "sortby", "f": ["f", "x"], "desc": True},
                                        {"op": "map", "f": ["f", "name"]}], False),
    ("tables", "join_count"): ("join", [{"op": "tjoin", "k": "id"}, {"op": "filter", "p": ["gt", ["f", "y"], ["c", 2]]},
                                        {"op": "len"}], False),
    ("grids", "obj_colors"): ("g", [{"op": "objs", "conn": 4, "bg": 0}, {"op": "map", "f": ["f", "color"]}], True),
    ("grids", "sizes_scan"): ("g", [{"op": "objs", "conn": 4, "bg": 0}, {"op": "map", "f": ["f", "size"]},
                                    {"op": "scan", "o": "add", "init": 0}], True),
    ("grids", "n_colors"): ("g", [{"op": "objs", "conn": 8, "bg": 0}, {"op": "countby", "f": ["f", "color"]}, {"op": "len"}], False),
    ("grids", "big_rows"): ("g", [{"op": "objs", "conn": 4, "bg": 0}, {"op": "filter", "p": ["gt", ["f", "size"], ["c", 1]]},
                                  {"op": "map", "f": ["f", "r"]}], False),
    ("graphs", "outdeg_list"): ("graph", [{"op": "outdeg"}, {"op": "map", "f": ["f", "deg"]}], True),
    ("graphs", "reach_desc"): ("graph", [{"op": "reach", "s": 0}, {"op": "sortby", "f": X, "desc": True}], True),
    ("graphs", "indeg_total"): ("graph", [{"op": "indeg"}, {"op": "map", "f": ["f", "deg"]}, {"op": "fold", "o": "add", "init": 0}], False),
    ("graphs", "topo_evens"): ("graph", [{"op": "topo"}, {"op": "filter", "p": ["even", X]}], False),
}
DOMAINS = ("strings", "tables", "grids", "graphs")


def make_task(domain, mech, r, n_public=3):
    variant, prog, src = MECH[(domain, mech)]
    for _ in range(80):
        xs = [gen_input(domain, r, variant) for _ in range(n_public + 1)]
        pr = [dict(t) for t in prog]
        for t in pr:
            if t["op"] == "paint":
                t["h"], t["w"] = len(xs[0]), len(xs[0][0])
        if t["op"] == "paint" and any(len(x) != len(xs[0]) for x in xs):
            continue
        ys = [L.run(pr, x) for x in xs]
        if L.ERROR in ys or len({L.key(y) for y in ys[:n_public]}) < 2:
            continue
        return dict(domain=domain, mechanism=mech, source=src, public=[[x, y] for x, y in zip(xs[:n_public], ys[:n_public])],
                    query=xs[-1], answer=ys[-1], teacher=pr)
    return None


def stream(seed, domains=DOMAINS, which="all", n_per=2):
    r = random.Random(f"w38:{seed}")
    out = []
    for (d, m), (_v, _p, src) in MECH.items():
        if d not in domains or (which == "source" and not src) or (which == "withheld" and src):
            continue
        for _ in range(n_per):
            t = make_task(d, m, r)
            if t:
                out.append(t)
    return out
