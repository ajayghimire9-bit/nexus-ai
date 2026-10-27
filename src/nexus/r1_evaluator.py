"""R1 evaluator (NOT LOCKED; evaluator side). The protected Stage 4 reference (s4_evaluator, unchanged) applies: X1 aborted
records are not in the truth timeline and X2 delays change only WHEN records become visible, so silver / gold / telemetry
expectations are the Stage 4 ones. Only record_accounting gains the declared statuses: each transaction marker is an applied
orders_cdc record and each aborted-transaction record is accounted 'aborted'. Imports nothing from NEXUS agents, checks or
templates."""
from __future__ import annotations

import os
from pathlib import Path

from nexus import s4_evaluator as V

OUT = V.OUT
_S4_EXPECTED = V.expected


def expected(truth, T, flags=frozenset()):
    res = _S4_EXPECTED(truth, T, flags)
    acc = {(t, s): n for t, s, n in res["record_accounting"]}
    for c in truth.get("txn_controls", []):
        if c["tick"] <= T:
            acc[("orders_cdc", "applied")] = acc.get(("orders_cdc", "applied"), 0) + 1
    for a in truth.get("aborted", []):
        if a["tick"] <= T:
            acc[("orders_cdc", "aborted")] = acc.get(("orders_cdc", "aborted"), 0) + 1
    res["record_accounting"] = [(t, s, n) for (t, s), n in acc.items()]
    return res


def evaluate(truth, proto, ticks=12):
    """s4_evaluator.evaluate with the R1 accounting (V.expected is rebound only for the duration of the call)."""
    orig = V.expected
    V.expected = lambda tr, T, flags=frozenset(): expected(tr, T, flags)
    try:
        return V.evaluate(truth, proto, ticks)
    finally:
        V.expected = orig


def evaluate_ops(truth, env, service, ticks=14):
    """Final outputs vs the truth reference (record_accounting by conservation, since re-snapshots legitimately add
    records), service at the end, per-tick freshness, duplicate keys, secret leakage."""
    st = V.read_state(env.rt["state"])
    want = expected(truth, ticks)
    tables = {t: V.table_equal(t, st[t], want[t]) for t in V.OUT if t != "record_accounting"}
    acc = {(t, s): n for t, s, n in (st["record_accounting"] or [])}
    conserv = not any(s == "dropped" for _, s in acc)
    dup = sum(len(v) - len(set(map(tuple, v))) for v in st.values() if isinstance(v, list))
    secret = env.secret.read_text()
    leaks = sum(secret in x for v in env.logs.values() for x in v)
    onset = {i["name"]: i["tick"] for i in truth["incidents"]}
    restore = {}
    for n, t0 in onset.items():
        ok_after = [s["tick"] for s in service if s["tick"] >= t0 and s["ok"]]
        restore[n] = (ok_after[0] - t0) if ok_after else None
    data_ok = all(ok for ok, _ in tables.values())
    return dict(clarifications=len(getattr(env, "clarifications", [])), data_ok=data_ok, service_restored=service[-1]["ok"],
                correct=data_ok and service[-1]["ok"] and conserv and not dup,
                tables={t: v[1] for t, v in tables.items() if not v[0]}, freshness_violations=sum(1 for s in service if not s["ok"]),
                restore_ticks=restore, duplicate_rows=dup, secret_leaks=leaks, conservation_ok=conserv,
                quarantined=sum(n for (t, s), n in acc.items() if s == "quarantined"), late=acc.get(("telemetry", "late"), 0))
