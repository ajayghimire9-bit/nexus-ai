"""Wave 31 increment 2 (development, NOT LOCKED): declarations shared by the evaluator and the solver.

Only declarations live here (domains, leaf adapters, the primitive grammar G_P, scope depths, the label rule).
There is no task generation, teacher or answer here, and no solver logic.

Four surface domains map into the middle IR Sequence through a thin leaf adapter phi_d (checker v2 ops):
  records: proj a|b   strings: enc_chars   grids: enc_cells   graphs: ir_graph_reach{seeds:[0]}
Other IR ops (ObjectSet, Counter, RelationGraph) are in G_P too, so every arm can route through them.

Scopes:
  * MATCHED: G_P (fixed, data-independent), depth <= MATCHED_DEPTH. Only an exhaustive verdict over exactly this
    scope is reported as exhaustive_UNIQUE. Every arm's matched certificate has identical strength by construction.
  * MACRO: G_P + an arm's library macros (seq ops), depth <= MACRO_DEPTH. Its UNIQUE verdict is reported as
    MACRO_SCOPE_UNIQUE and never pooled with exhaustive_UNIQUE.
"""
from __future__ import annotations

from nexus import checker_kernel_v2 as V

DOMAINS = ("records", "strings", "grids", "graphs")
LEAF = {"records": [{"op": "proj", "path": "a"}], "strings": [{"op": "enc_chars"}], "grids": [{"op": "enc_cells"}],
        "graphs": [{"op": "ir_graph_reach", "seeds": [0]}]}
MATCHED_DEPTH = 3
MACRO_DEPTH = 2
MAX_PROBES = 3

SORT = {"op": "Sort", "path": ".", "desc": False}
RUNH = {"op": "run_heads"}
ROT = {"op": "rotate", "k": 1}
PSUM = {"op": "prefix_sum"}
DIFF = {"op": "diff"}
RMAX = {"op": "running_max"}
CORE_OPS = {"Sort": SORT, "RUNH": RUNH, "rotate": ROT, "prefix_sum": PSUM, "diff": DIFF, "running_max": RMAX}

G_P = ([{"op": "proj", "path": "a"}, {"op": "proj", "path": "b"}, {"op": "enc_chars"}, {"op": "dec_chars"},
        {"op": "enc_cells"}, {"op": "ir_graph_reach", "seeds": [0]}, {"op": "ir_graph_degrees"},
        {"op": "enc_objects", "conn": 4, "background": 0}, {"op": "ir_objects_sizes"},
        {"op": "enc_counter", "path": "."}, {"op": "ir_counter_top", "k": 1}, {"op": "ir_counter_keys"}]
       + list(CORE_OPS.values()))
ADAPTER_OPS = {"proj", "enc_chars", "dec_chars", "enc_cells", "ir_graph_reach", "enc_objects"}


def matched_scope():
    return {"kind": "exhaustive", "tools": [dict(t) for t in G_P], "max_depth": MATCHED_DEPTH}


def is_matched(scope):
    """True iff `scope` is exactly the matched scope (tool set by canonical key, depth, kind)."""
    try:
        return (scope["kind"] == "exhaustive" and int(scope["max_depth"]) == MATCHED_DEPTH
                and sorted(V.key(t) for t in scope["tools"]) == sorted(V.key(t) for t in G_P))
    except (KeyError, TypeError, ValueError):
        return False


def report_label(verdict, scope):
    """Evaluator-side reporting rule around the unchanged kernel verdict."""
    lab = verdict["label"]
    if lab != "exhaustive_UNIQUE":
        return lab
    if is_matched(scope):
        return "exhaustive_UNIQUE"
    if any(t.get("op") == "seq" for t in scope["tools"]):
        return "MACRO_SCOPE_UNIQUE"
    return "SCOPE_RELATIVE_UNIQUE"
