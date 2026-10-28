"""OOP-track reconciliation = the operator-side spec monitor (NOT LOCKED). r2_reconcile (unchanged) loaded as a SEPARATE module
from its source and rebound to the de5 rules every de5 spec declares, on top of the R2 rules:
  registry amount unit   a registry version declaring types.amount_unit = minor: amount = value / 100
  warehouse rule         an order record whose warehouse_id is not in spec.warehouses is quarantined (unknown_warehouse)
A quarantine ledger status may be the class label itself ("q:<reason>"); STATUS maps the legacy names as before.
decode_full adds promised_ts (the field the s4 silver derivation reads) for the synthesis oracle (oop_examples).
Expected values never come from the pipeline or from the evaluator's truth."""
from __future__ import annotations

import importlib.util

from nexus import r2_reconcile as _R2R
from nexus import s4_checks as C

_spec = importlib.util.spec_from_loader("nexus._oop_reconcile_core", loader=None)
R = importlib.util.module_from_spec(_spec)
R.__file__ = _R2R.__file__
_SRC = open(_R2R.__file__).read()
_P = [("""(pay is None or all((abs(float(pay[c]) - float(want_row[c])) <= 1e-6) if c in ("amount", "discount")""",
       """(pay is None or all(_numeq(pay[c], want_row[c]) if c in ("amount", "discount")""")]
for _a, _b in _P:
    if _SRC.count(_a) != 1:
        raise RuntimeError("oop_reconcile patch anchor not found exactly once")
    _SRC = _SRC.replace(_a, _b)
exec(compile(_SRC, _R2R.__file__ + "[oop]", "exec"), R.__dict__)


def _numeq(x, y):
    """A malformed pipeline value (None, text) is a content mismatch, never a monitor crash."""
    try:
        return abs(float(x) - float(y)) <= 1e-6
    except (TypeError, ValueError):
        return False


R._numeq = _numeq
R.STATUS = dict(R.STATUS, unknown_warehouse="q:unknown_warehouse")
_decode_r2, _classify_r2 = R.decode, R.classify


def _rg(spec, r, reg):
    return reg.get(("orders", r.get("schema_version", 1)), {"fields": spec["physical_names_v1"], "types": {"discount": "int"}})


def decode(spec, r, reg):
    row = _decode_r2(spec, r, reg)
    if row is not None and _rg(spec, r, reg)["types"].get("amount_unit") == "minor":
        row["amount"] = row["amount"] / 100.0
    return row


def decode_full(spec, r, reg):
    row = decode(spec, r, reg)
    if row is not None:
        row["promised_ts"] = r["after"].get(_rg(spec, r, reg)["fields"]["promised_ts"])
    return row


def classify(spec, pre, registry=None):
    out = _classify_r2(spec, pre, registry)
    reg = R._reg(registry if registry is not None else pre)
    whs = set(spec.get("warehouses", []))
    rec = {(tp, p, o): r for tp, p, o, r in pre}
    for k, (c, eid) in list(out.items()):
        r = rec.get(k)
        if c == "accepted" and r and k[0] in ("orders_cdc", "backfill_orders") and r.get("after") and "control" not in r:
            if whs and (decode(spec, r, reg) or {}).get("warehouse_id") not in whs:
                out[k] = ("q:unknown_warehouse", eid)
    return out


def derive_silver(spec, keep):
    """The R2 derivation with the de5 rules: unknown-warehouse records never enter silver; registry amount units."""
    reg = {}
    for tp, p, r in keep:
        if tp == "_schemas":
            reg[(r.get("subject", "orders"), r["version"])] = r
    whs = set(spec.get("warehouses", []))
    out = []
    for tp, p, r in keep:
        if tp in ("orders_cdc", "backfill_orders") and "control" not in r and r.get("after"):
            row = decode(spec, r, reg)
            if whs and row["warehouse_id"] not in whs:
                continue
            rg = reg.get(("orders", r.get("schema_version", 1)))
            if rg and rg["types"].get("amount_unit") == "minor":
                f = rg["fields"]
                r = dict(r, after=dict(r["after"], **{f["amount"]: float(r["after"][f["amount"]]) / 100.0}))
        out.append((tp, p, r))
    return _R2R.derive_silver(spec, out)


def silver_provenance(spec, keep):
    """{key: source_version of the record the derivation's silver row comes from} (the s4 precedence rule: the highest
    source_version, first seen on ties) for every key derive_silver keeps."""
    reg = {}
    for tp, p, r in keep:
        if tp == "_schemas":
            reg[(r.get("subject", "orders"), r["version"])] = r
    fx, whs = spec["fx_to_usd"], set(spec.get("warehouses", []))
    best = {}
    for tp, p, r in keep:
        if tp not in ("orders_cdc", "backfill_orders") or "control" in r or "_undecodable" in r:
            continue
        if r.get("after"):
            row = decode(spec, r, reg)
            if row["currency"] not in fx or (whs and row["warehouse_id"] not in whs):
                continue
        cur = best.get(r["key"])
        if cur is None or r["source_version"] > cur["source_version"]:
            best[r["key"]] = r
    sil = derive_silver(spec, keep)
    return {k: best[k]["source_version"] for k in sil if k in best}, sil


R.decode, R.classify, R.derive_silver = decode, classify, derive_silver
STATUS = R.STATUS
_reconcile = R.reconcile


def reconcile(env, spec):
    """The monitor never crashes on what the pipeline wrote: an exception while reading pipeline output is a failed
    reconciliation with the exception recorded (monitor_exception), never a harness crash."""
    try:
        return _reconcile(env, spec)
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        return False, dict(silver_mismatch=[], late_mismatch=0, coverage=[], accounting=[], sla_mismatch=0, volume_mismatch=0,
                           event_class=[], quarantine_rows=[], content=[], multiplicity=[],
                           monitor_exception=f"{type(e).__name__}: {e}"[:300])


R.reconcile = reconcile
_reg = R._reg
utc = C.utc
