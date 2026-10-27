"""R2 event-level reconciliation (NOT LOCKED; operator side). Expected values come ONLY from the operator archive (every
published segment), the authoritative observations and the spec; nothing is taken from the pipeline's replay logic.

Event semantics (identity = (topic, msg_id); the first delivered copy, in partition-offset order, is the event; later copies
are duplicates):
  class per consumed offset   accepted (incl. snapshot / transaction controls) | quarantined(reason) | duplicate | aborted |
                              pending; reasons malformed_weight / future_event / poison (undecodable line) / unknown_currency
  conservation                every offset below the committed offset carries exactly one ledger row whose class equals the
                              derived class (a count-preserving substitution, a wrong quarantine reason or a duplicate
                              promoted to accepted all fail it)
  quarantine                  rows compared as a MULTISET of (topic, msg_id, reason)
  canonical contents          bronze orders (key, source_version, op, decoded row incl. registry renames / types / discount
                              unit), telemetry (UTC event time, future flag), manifests (kg after the operator's declared unit
                              overrides) equal the first copy; multiplicity: one bronze row per accepted event
  outputs                     silver row by row (source_version precedence, tombstones, soft deletes, snapshot rows, the
                              currency rule), late_events, gold_sla, supplier volume (r1_ops derivations)
Bounds: whatever the mutation tests in scripts/r2_dev_reconcile.py exercise; no claim of zero future errors."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

from nexus import r1_monitor as M
from nexus import r1_ops as R1O
from nexus import s4_checks as C

STATUS = {"applied": "accepted", "control": "accepted", "dup": "duplicate", "malformed": "q:malformed_weight",
          "future": "q:future_event", "poison": "q:poison", "unknown_currency": "q:unknown_currency", "aborted": "aborted",
          "pending": "pending", "dropped": "dropped"}


def _reg(pre):
    reg = {}
    for tp, p, o, r in pre:
        if tp == "_schemas" and r:
            reg[(r.get("subject", "orders"), r["version"])] = r
    return reg


def decode(spec, r, reg):
    """Canonical orders row of a record per the registry (renames, types, discount unit)."""
    a = r.get("after")
    if a is None:
        return None
    rg = reg.get(("orders", r.get("schema_version", 1)), {"fields": spec["physical_names_v1"], "types": {"discount": "int"}})
    f = rg["fields"]
    disc = float(a.get(f["discount"]) or 0)
    if rg["types"].get("discount_unit") == "fraction":
        disc *= 100
    return dict(order_id=int(a[f["order_id"]]), warehouse_id=a.get(f["warehouse_id"]), status=a.get(f["status"]),
                amount=float(a.get(f["amount"]) or 0), currency=a.get(f["currency"]), discount=disc,
                deleted=int(a.get(f["deleted"]) or 0))


def classify(spec, pre, registry=None):
    """{(topic, part, offset): (class, event_id)} for the consumed prefix (decoding per the PUBLISHED registry)."""
    fx = spec["fx_to_usd"]
    reg = _reg(registry if registry is not None else pre)
    fin = {r["txn_id"]: r["control"] for tp, p, o, r in pre if r and str(r.get("control", "")).startswith("txn_")}
    out, seen = {}, set()
    for tp, p, o, r in sorted(pre, key=lambda x: (x[0], x[1], x[2])):
        if tp == "_schemas":
            continue
        if r is None:
            out[(tp, p, o)] = ("q:poison", f"{tp}:{p}:{o}")
            continue
        eid = (tp, r.get("msg_id"))
        if eid in seen:
            out[(tp, p, o)] = ("duplicate", r.get("msg_id"))
            continue
        seen.add(eid)
        if "control" in r:
            c = "accepted"
        elif r.get("txn_id") and tp == "orders_cdc":
            c = {"txn_commit": "accepted", "txn_abort": "aborted"}.get(fin.get(r["txn_id"]), "pending")
        elif tp in ("orders_cdc", "backfill_orders") and r.get("after") and (decode(spec, r, reg) or {}).get("currency") not in fx:
            c = "q:unknown_currency"
        elif tp == "telemetry" and (C.utc(r["event_ts"]) - C.utc(r["ingest_ts"])).total_seconds() > 300:
            c = "q:future_event"
        elif tp == "manifests" and not isinstance(r.get("weight"), (int, float)):
            c = "q:malformed_weight"
        else:
            c = "accepted"
        out[(tp, p, o)] = (c, r.get("msg_id"))
    return out


def derive_silver(spec, keep):
    """s4 spec derivation with the de4 rules: unknown-currency records never enter silver; registry discount units."""
    reg = {}
    for tp, p, r in keep:
        if tp == "_schemas":
            reg[(r.get("subject", "orders"), r["version"])] = r
    fx = spec["fx_to_usd"]
    out = []
    for tp, p, r in keep:
        if tp in ("orders_cdc", "backfill_orders") and "control" not in r and r.get("after"):
            row = decode(spec, r, reg)
            if row["currency"] not in fx:
                continue
            rg = reg.get(("orders", r.get("schema_version", 1)))
            if rg and rg["types"].get("discount_unit") == "fraction":
                f = rg["fields"]
                r = dict(r, after=dict(r["after"], **{f["discount"]: float(r["after"][f["discount"]]) * 100}))
        out.append((tp, p, r))
    return C.derive_silver(spec, out)


def _rows(st, q):
    try:
        con = sqlite3.connect(f"file:{Path(st) / 'lake.db'}?mode=ro", uri=True)
        rows = con.execute(q).fetchall()
        con.close()
        return rows
    except sqlite3.Error:
        return None


def reconcile(env, spec):
    keep, com, arch = R1O._prefix(env)
    st = Path(env.rt["state"])
    ev = dict(silver_mismatch=[], late_mismatch=0, coverage=[], accounting=[], sla_mismatch=0, volume_mismatch=0,
              event_class=[], quarantine_rows=[], content=[], multiplicity=[])
    last_ok = (env.history[-1].get("exit") == 0) if env.history else True
    try:
        o = env.obs()
        for p in o["partitions"]:
            key = f"{p['topic']}/{p['part']}"
            c = com.get((p["topic"], p["part"]), 0)
            if p["state"] == "open" and o["offsets"].get(key, {}).get("contiguous_end", 0) > c:
                ev["coverage"].append(dict(kind="partition_not_consumed" if c == 0 and last_ok else "lag" if last_ok else
                                           "lag_after_failed_run", where=key, behind=o["offsets"][key]["contiguous_end"] - c))
        ev["coverage"] += [dict(kind=v["kind"], where=v["where"]) for v in M.check_consumer(st, o) if v["kind"] == "ack_beyond_durable"]
    except (OSError, ValueError):
        pass
    pre = [(tp, p, o_, r) for tp, p, o_, r, tk in arch if o_ < com.get((tp, p), 0)]
    # the registry is authoritative metadata: decode with every PUBLISHED registry record, not only the consumed ones
    regs = [(tp, p, o_, r) for tp, p, o_, r, tk in arch if tp == "_schemas" and r]
    keep = [(tp, p, r) for tp, p, o_, r in regs] + [x for x in keep if x[0] != "_schemas"]
    want = classify(spec, pre, regs)
    led = _rows(st, "SELECT topic, part, offset, status FROM _consumed") or []
    got = {(t, p, o_): STATUS.get(s, s) for t, p, o_, s in led}
    for k in sorted(set(want) | set(got)):
        if k[0] == "_schemas" or (k in got and k not in want and k[2] >= com.get((k[0], k[1]), 0)):
            continue
        if want.get(k, (None,))[0] != got.get(k):
            ev["event_class"].append(dict(at=list(k), want=want.get(k, (None,))[0], got=got.get(k)))
    wq = Counter((k[0], eid, c[2:]) for k, (c, eid) in want.items() if c.startswith("q:"))
    gq = Counter(map(tuple, _rows(st, "SELECT topic, msg_id, reason FROM quarantine") or []))
    ev["quarantine_rows"] = [dict(row=list(r), want=wq[r], got=gq[r]) for r in sorted(set(wq) | set(gq)) if wq[r] != gq[r]]
    # canonical contents + multiplicity of accepted events
    reg = _reg(regs)
    first = {}
    for k, (c, eid) in want.items():
        if c == "accepted":
            first[(k[0], eid)] = k
    rec = {(tp, p, o_): r for tp, p, o_, r in pre}
    ovs = env.cfg["deploy"].get("unit_overrides", [])
    bo = _rows(st, "SELECT msg_id, key, sv, op, payload, source FROM bronze_orders") or []
    bt = _rows(st, "SELECT msg_id, ets, future FROM bronze_tel") or []
    bm = _rows(st, "SELECT msg_id, kg FROM bronze_man") or []
    for name, rows, topics in (("orders", bo, ("orders_cdc", "backfill_orders")), ("telemetry", bt, ("telemetry",)),
                               ("manifests", bm, ("manifests",))):
        cnt = Counter((r[5] if name == "orders" else topics[0], r[0]) for r in rows)
        exp = {e for e in first if e[0] in topics and "control" not in rec[first[e]]}
        for e in sorted(set(cnt) | exp):
            # accepted events exactly once; non-accepted orders / manifests never (aborted, pending, unknown currency,
            # malformed); a quarantined future telemetry event may be kept once, flagged (the template's declared storage)
            hi = 1 if (e in exp or name == "telemetry") else 0
            lo = 1 if e in exp else 0
            if not lo <= cnt.get(e, 0) <= hi:
                ev["multiplicity"].append(dict(table=name, event=list(e), want=lo, got=cnt.get(e, 0)))
        for r in rows:
            e = (r[5] if name == "orders" else topics[0], r[0])
            if e not in first:
                continue
            x = rec[first[e]]
            if name == "orders":
                want_row = decode(spec, x, reg)
                pay = json.loads(r[4]) if r[4] else None
                ok = (r[1] == x["key"] and r[2] == x["source_version"] and r[3] == x["op"] and
                      (want_row is None) == (pay is None) and
                      (pay is None or all((abs(float(pay[c]) - float(want_row[c])) <= 1e-6) if c in ("amount", "discount")
                                          else str(pay[c]) == str(want_row[c]) for c in want_row if c in pay)))
            elif name == "telemetry":
                et = C.utc(x["event_ts"])
                fut = int((et - C.utc(x["ingest_ts"])).total_seconds() > 300)
                ok = r[1] == et.strftime("%Y-%m-%dT%H:%M:%S") and int(r[2] or 0) == 0 == fut
            else:
                kg = x["weight"]
                for ov in ovs:
                    if ov["supplier"] == x["supplier"] and x["offset"] >= ov["from_offset"] and first[e][1] == ov.get("part", 0):
                        kg *= ov["factor"]
                ok = abs(float(r[1]) - kg) <= 1e-6
            if not ok:
                ev["content"].append(dict(table=name, event=list(e)))
    # outputs. After a FAILED run the published outputs legitimately lag the ledger (they change only at a run's final
    # commit, while non-transactional protocols commit consumption per topic): output comparisons are deferred, the ledger,
    # bronze and coverage checks above still apply
    ev["outputs_deferred"] = not last_ok
    if not last_ok:
        ok = not any(ev[k] for k in ("coverage", "event_class", "content", "multiplicity"))
        for k in ("event_class", "content", "multiplicity"):
            ev[k] = ev[k][:100]
        return ok, ev
    tabs = C.tables(st, spec)
    want_s = derive_silver(spec, keep)
    want_l = C.derive_late(spec, keep)
    gs = {r[0]: r for r in (tabs.get("silver_orders") or [])}
    for k in sorted(set(want_s) | set(gs)):
        w, g = want_s.get(k), gs.get(k)
        if w is None or g is None or w[2] != g[2] or w[1] != g[1] or abs(w[3] - g[3]) > 0.011:
            ev["silver_mismatch"].append(k)
    ev["late_mismatch"] = len(want_l ^ {r[0] for r in (tabs.get("late_events") or [])})
    sla, vol = R1O.derive_gold(spec, want_s, keep, want_l, ovs)
    g_sla = {r[0]: r[1:] for r in (tabs.get("gold_sla") or [])}
    ev["sla_mismatch"] = sum(1 for w in set(sla) | set(g_sla) if sla.get(w) is None or g_sla.get(w) is None or
                             sla[w][0] != g_sla[w][0] or sla[w][1] != g_sla[w][1])
    g_vol = {(r[0], r[1]): r[2] for r in (tabs.get("gold_supplier_volume") or [])}
    ev["volume_mismatch"] = sum(1 for k in set(vol) | set(g_vol) if vol.get(k) is None or g_vol.get(k) is None or
                                abs(vol[k] - g_vol[k]) > 0.0021)
    # the accounting summary the pipeline publishes must equal its own ledger classes AND the derived classes
    wa = Counter()
    for k, (c, eid) in want.items():
        wa[(k[0], {"accepted": "applied", "duplicate": "duplicate"}.get(c, "quarantined" if c.startswith("q:") else c))] += 1
    ga = Counter({(t, s_): n for t, s_, n in (tabs.get("record_accounting") or []) if s_ != "late"})
    ev["accounting"] = [dict(topic=t, status=s_, want=wa.get((t, s_), 0), got=ga.get((t, s_), 0))
                        for t, s_ in sorted(set(wa) | set(ga)) if wa.get((t, s_), 0) != ga.get((t, s_), 0)]
    ok = not any(ev[k] for k in ("silver_mismatch", "late_mismatch", "coverage", "accounting", "sla_mismatch", "volume_mismatch",
                                 "event_class", "quarantine_rows", "content", "multiplicity"))
    for k in ("silver_mismatch", "event_class", "quarantine_rows", "content", "multiplicity"):
        ev[k] = ev[k][:100]
    return ok, ev
