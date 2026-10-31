"""NEXUS Phase 14: out-of-sandbox multi-engine full-DAG repair (Capabilities 3, 7). NOT LOCKED; engineering machinery.

Modules
  multi_engine14  bidirectional core11 AST <-> engine compiler (SQLite, DuckDB, Polars, PySpark/SQL) and a semantic conformance
                  verifier (NULL 3-valued logic, window ranking, group folds, anti-join upserts).
  dag_repair14    multi-node DAG fault localizer (stg_ -> int_ -> fct_): isolates the faulty node with Phase 13 program-aware
                  probes, lifts only that node, repairs it and verifies the downstream invariants.
  runner14        metered runner (--grant-seconds, --execute): matched Fixed / Random / Untrained / Trained arms on held-out
                  multi-stage DAG pipelines across engines, with 0 cap overruns required.

Optional engines (duckdb, polars, pyspark) are detected WITHOUT importing them (importlib.util.find_spec). An engine that is not
installed is reported unavailable and skipped. It is never simulated, and it is never counted as agreeing.

ATTRIBUTION  everything in this package is general machinery written by the engineering team (human / Claude / Codex / Gemini edits
are external engineering). What NEXUS learns is only the state it produces during source training (selector weights, tag prior,
guide counts). Those are recorded separately by the runner."""
from __future__ import annotations

import importlib.util

PHASE = 14
WORK_CAPS = dict(full_checks=5000, rel_evals=4000, micro_evals=400000, constructed_asts=400000)
ENGINES = ("core11", "sqlite", "duckdb", "polars", "pyspark")
BUILTIN_ENGINES = ("core11", "sqlite")                 # always available (core11 is in-repo, sqlite3 is in the standard library)
OPTIONAL_ENGINES = ("duckdb", "polars", "pyspark")
DAG_LAYERS = ("stg_", "int_", "fct_")
ARMS = ("fixed", "random", "untrained", "trained")


def engine_available(name):
    """True when the engine can be used in this environment. Optional engines are probed with find_spec only (no import)."""
    if name in BUILTIN_ENGINES:
        return True
    if name not in OPTIONAL_ENGINES:
        return False
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def engine_availability():
    """{engine: bool} for every engine in ENGINES (recorded in results; unavailable engines are skipped, never simulated)."""
    return {e: engine_available(e) for e in ENGINES}


def layer_of(stage_name):
    """DAG layer prefix of a stage name ('stg_' / 'int_' / 'fct_'), or None for a stage outside the layered convention."""
    for p in DAG_LAYERS:
        if str(stage_name).startswith(p):
            return p
    return None


__all__ = ["PHASE", "WORK_CAPS", "ENGINES", "BUILTIN_ENGINES", "OPTIONAL_ENGINES", "DAG_LAYERS", "ARMS", "engine_available",
           "engine_availability", "layer_of"]
