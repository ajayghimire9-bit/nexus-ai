"""Phase 11 evaluator-side verification (NOT LOCKED; the evaluator process alone holds hidden batches).
verify(program, lib, hidden, engine): expand, compile to the engine (DuckDB primary), run NATIVELY on each hidden batch and compare
the bag with the expected output (computed by the reference interpreter from the generator's reference program). The reference
interpreter's own result is recorded too: a reference / native disagreement is a CONFORMANCE failure (logged), and only the native
result decides `verified`. Unsupported compilation = not verified (coverage failure), never counted as native execution."""
from __future__ import annotations

from nexus.de_phase11 import core11 as C, sql11 as Q


def _match(got, exp):
    if got is C.ERR:
        return False
    if set(got.cols) != set(exp.cols) or len(got.cols) != len(exp.cols):
        return False
    return C.same_bag(C.project_like(got, list(exp.cols)), exp)


def verify(program, lib, hidden, engine="duckdb"):
    out = dict(engine=engine, batches=[], native_executions=0)
    try:
        Q.compile_sql(program, {k: v.schema() for k, v in hidden["hid"][0][0].items()}, engine, lib)
    except (C.Unsupported, C.TypeErr) as e:
        out.update(ok=False, unsupported=str(e)[:120])
        return out
    ok = True
    for env, exp in hidden["hid"]:
        nat = Q.execute(program, env, engine, lib)
        out["native_executions"] += 1
        ref = C.evaluate(program, env, lib)
        nm, rm = _match(nat, exp), _match(ref, exp)
        out["batches"].append(dict(native=nm, reference=rm, conformance=nm == rm))
        ok = ok and nm
    out["ok"] = ok
    out["conformance_mismatch"] = sum(not b["conformance"] for b in out["batches"])
    return out
