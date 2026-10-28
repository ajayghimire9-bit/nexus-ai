"""OOP-track evaluator (NOT LOCKED; evaluator side). r1_evaluator (unchanged) plus the quarantine rules of de5 truth: every
version of an unknown-currency (X3) or unknown-warehouse (D2) order is quarantined with that reason and never enters
silver / gold; its retry copies are duplicates. X4 / D1 change only the encoding (truth values stay in their declared units).
Imports nothing from NEXUS agents, checks, templates or the synthesiser."""
from __future__ import annotations

from nexus import r1_evaluator as RV1
from nexus import s4_evaluator as V

OUT = V.OUT
_R1_EXPECTED = RV1.expected
RULES = (("unknown_currency_keys", "unknown_currency"), ("unknown_warehouse_keys", "unknown_warehouse"))


def _split(truth):
    q = []
    for field, reason in RULES:
        keys = set(truth.get(field, []))
        q += [(v, reason) for v in truth["versions"] if v["topic"] == "orders_cdc" and v["key"] in keys and v["row"] is not None]
    if not q:
        return truth, []
    drop = [v for v, _ in q]
    return dict(truth, versions=[v for v in truth["versions"] if v not in drop]), q


def expected(truth, T, flags=frozenset()):
    t, q = _split(truth)
    res = _R1_EXPECTED(t, T, flags)
    acc = {(tp, s): n for tp, s, n in res["record_accounting"]}
    for v, reason in q:
        cps = [c for c in v["copies"] if c[0] <= T]
        if cps:
            res["quarantine"] = list(res["quarantine"]) + [("orders_cdc", v["msg_id"], reason)]
            acc[("orders_cdc", "quarantined")] = acc.get(("orders_cdc", "quarantined"), 0) + 1
            if len(cps) > 1:
                acc[("orders_cdc", "duplicate")] = acc.get(("orders_cdc", "duplicate"), 0) + len(cps) - 1
    res["record_accounting"] = [(tp, s, n) for (tp, s), n in acc.items()]
    return res


def evaluate(truth, proto, ticks=12):
    orig = V.expected
    V.expected = lambda tr, T, flags=frozenset(): expected(tr, T, flags)
    try:
        return V.evaluate(truth, proto, ticks)
    finally:
        V.expected = orig


def evaluate_ops(truth, env, service, ticks=14):
    orig = RV1.expected
    RV1.expected = expected
    try:
        return RV1.evaluate_ops(truth, env, service, ticks)
    finally:
        RV1.expected = orig
