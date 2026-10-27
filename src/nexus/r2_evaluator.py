"""R2 evaluator (NOT LOCKED; evaluator side). r1_evaluator (unchanged) plus the X3 rule: every version of an unknown-currency
order is quarantined (reason unknown_currency) and never enters silver / gold; its retry copies are duplicates. X4 changes
only the encoding (truth discounts stay percent). Telemetry truth already follows the first-copy identity rule
(r2_env._first_copy_truth). Imports nothing from NEXUS agents, checks or templates."""
from __future__ import annotations

from nexus import r1_evaluator as RV1
from nexus import s4_evaluator as V

OUT = V.OUT
_R1_EXPECTED = RV1.expected


def _split(truth):
    keys = set(truth.get("unknown_currency_keys", []))
    if not keys:
        return truth, []
    q = [v for v in truth["versions"] if v["topic"] == "orders_cdc" and v["key"] in keys and v["row"] is not None]
    t = dict(truth, versions=[v for v in truth["versions"] if v not in q])
    return t, q


def expected(truth, T, flags=frozenset()):
    t, q = _split(truth)
    res = _R1_EXPECTED(t, T, flags)
    acc = {(tp, s): n for tp, s, n in res["record_accounting"]}
    for v in q:
        cps = [c for c in v["copies"] if c[0] <= T]
        if cps:
            res["quarantine"] = list(res["quarantine"]) + [("orders_cdc", v["msg_id"], "unknown_currency")]
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
