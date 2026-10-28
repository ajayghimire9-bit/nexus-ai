"""Hole examples + synthesis driver (NOT LOCKED). The synthesiser's ONLY supervision: input/output examples obtained by calling
the operator-side spec monitor (oop_reconcile: decode_full / classify / derive_silver) as a BLACK BOX on records NEXUS can
see - the visible log at build time, the operator archive at ops time. The synthesiser never reads the monitor's source,
the evaluator or truth. (Disclosed limitation: the monitor is an executable specification, so NEXUS synthesises an
implementation that agrees with it on the records it has seen; it does not discover the spec's semantics.)

Per hole:
  syn_decode   every orders / backfill record carrying a payload: (a, fields, types) -> each canonical row field
  syn_net      every silver row of the derivation: (canonical row of its winning record, fx) -> net amount
  syn_status   every first delivery of an orders / backfill / manifests record outside a transaction:
               (topic, rec, row, fx, warehouses) -> class label (accepted | q:<reason>)
  syn_silver   accepted order events in arrival order, as the pipeline's bronze rows, for prefixes ending at ticks 4 / 8 /
               last: the set of (key, source_version) the silver table holds"""
from __future__ import annotations

import json
import time
from pathlib import Path

from nexus import oop_reconcile as R
from nexus import oop_synthesizer as S
from nexus import oop_template as T

ORDERS = ("orders_cdc", "backfill_orders")


def read_log(log, spec):
    """[(topic, part, offset, record or None, tick)] of every segment of a log directory."""
    out = []
    from nexus import s4_checks as C
    for f in sorted(Path(log).rglob("*.jsonl")):
        tp, p, base = f.parent.parent.name, int(f.parent.name[1:]), int(f.name.split(".")[0])
        for i, line in enumerate(x for x in f.read_text().split("\n") if x):
            try:
                r = json.loads(line)
            except ValueError:
                r = None
            out.append((tp, p, base + i, r, C.tick_of(r["ingest_ts"], spec) if r and r.get("ingest_ts") else 0))
    return out


def examples(spec, arch):
    pre = [(tp, p, o, r) for tp, p, o, r, tk in arch]
    regs = [(tp, p, o, r) for tp, p, o, r in pre if tp == "_schemas" and r]
    reg = R._reg(regs)
    cls = R.classify(spec, pre, regs)
    fx, whs = spec["fx_to_usd"], spec.get("warehouses", [])
    default = {"fields": spec["physical_names_v1"], "types": {"discount": "int"}}
    tick = {(tp, p, o): tk for tp, p, o, r, tk in arch}
    dec_in, dec_out, st_in, st_out = [], [], [], []
    seen = set()
    for (tp, p, o, r) in sorted(pre, key=lambda x: (x[0], x[1], x[2])):
        if r is None or tp == "_schemas" or "control" in r:
            continue
        if tp in ORDERS and r.get("after") and r.get("msg_id") not in seen:
            seen.add(r.get("msg_id"))
            rg = reg.get(("orders", r.get("schema_version", 1)), default)
            dec_in.append({"a": r["after"], "fields": rg["fields"], "types": rg.get("types", {})})
            dec_out.append(R.decode_full(spec, r, reg))
        c = cls.get((tp, p, o), (None,))[0]
        if tp in ORDERS + ("manifests",) and not r.get("txn_id") and c in ("accepted",) + tuple(
                x for x in [c] if x and x.startswith("q:") and x not in ("q:poison", "q:future_event")):
            row = R.decode_full(spec, r, reg) if tp in ORDERS and r.get("after") else None
            st_in.append({"topic": tp, "rec": r, "row": row, "fx": fx, "whs": whs})
            st_out.append(c)
    # silver: accepted order events (first copies; committed transactions) as bronze rows, arrival order
    order = {t: i for i, t in enumerate(spec["log"]["processing_order"])}
    acc = [(tp, p, o, r) for (tp, p, o, r) in pre if r and tp in ORDERS and "control" not in r and
           cls.get((tp, p, o), (None,))[0] == "accepted"]
    acc.sort(key=lambda x: (tick[(x[0], x[1], x[2])], order.get(x[0], 9), x[1], x[2]))
    rows = []
    for i, (tp, p, o, r) in enumerate(acc):
        pay = R.decode_full(spec, r, reg) if r.get("after") else None
        rows.append(({"msg_id": r["msg_id"], "key": r["key"], "sv": r["source_version"], "op": r["op"], "payload": pay,
                      "soft": 1 if pay and pay.get("deleted") else 0, "source": tp, "seq": i + 1}, tick[(tp, p, o)], (tp, p, r)))
    seqs, wants, net_in, net_out = [], [], [], []
    last = max([tk for _, tk, _ in rows] or [0])
    for T_ in sorted({min(4, last), min(8, last), last}):
        keep = [(tp, p, r) for tp, p, o, r in regs] + [x[2] for x in rows if x[1] <= T_]
        prov, sil = R.silver_provenance(spec, keep)
        seqs.append([x[0] for x in rows if x[1] <= T_])
        wants.append({(k, sv) for k, sv in prov.items()})
        if T_ == last:
            for k, v in sorted(sil.items()):
                win = next((x[0] for x in rows if x[0]["key"] == k and x[0]["sv"] == prov.get(k) and x[0]["payload"]), None)
                if win is not None:
                    net_in.append({"p": win["payload"], "fx": fx})
                    net_out.append(v[3])
    return dict(syn_decode=(dec_in, dec_out), syn_status=(st_in, st_out), syn_net=(net_in, net_out),
                syn_silver=(seqs, wants))


def _ok_scalar(node, ins, outs, tol=None):
    return all(S._eq(S.ev(node, e), y, tol) for e, y in zip(ins, outs))


NET_TOL = lambda t: 0.011        # noqa: E731  (the spec's net tolerance)


def consistent(hole, pid, ex):
    """Does the program pid agree with every example of its hole?"""
    if pid is None or pid not in T.PROG[hole]:
        return False
    p = T.PROG[hole][pid]
    if hole == "syn_decode":
        ins, outs = ex[hole]
        return all(_ok_scalar(p["fields"][f], ins, [o[f] for o in outs]) for f in T.ROW_FIELDS)
    if hole == "syn_net":
        return _ok_scalar(p["node"], *ex[hole], tol=NET_TOL)
    if hole == "syn_status":
        return _ok_scalar(p["node"], *ex[hole])
    seqs, wants = ex[hole]
    return all(S._flush_ok(p["spec"], s, w, _sid) for s, w in zip(seqs, wants))


def _sid(r):
    return (r["key"], r["sv"])


def synth_hole(hole, ex, max_s=120.0):
    """Synthesise one hole from its examples. Returns (program id or None, stats)."""
    t0 = time.process_time()
    st = dict(hole=hole)
    if hole == "syn_decode":
        ins, outs = ex[hole]
        if not ins:
            return None, dict(st, error="no examples")
        fields, per = {}, {}
        for f in T.ROW_FIELDS:
            n, s = S.synthesize_scalar(ins, [o[f] for o in outs], max_s=max(5.0, max_s / len(T.ROW_FIELDS)))
            per[f] = s
            if n is None:
                return None, dict(st, failed_field=f, per=per, cpu_s=round(time.process_time() - t0, 3))
            fields[f] = n
        prog = dict(kind="record", fields=fields)
        st["per"] = per
    elif hole in ("syn_net", "syn_status"):
        ins, outs = ex[hole]
        if not ins:
            return None, dict(st, error="no examples")
        n, s = S.synthesize_scalar(ins, outs, tol=NET_TOL if hole == "syn_net" else None, max_s=max_s)
        st.update(s)
        if n is None:
            return None, dict(st, cpu_s=round(time.process_time() - t0, 3))
        prog = dict(kind="function", node=n)
    else:
        seqs, wants = ex[hole]
        spec = S.synthesize_organelle(seqs, (wants, _sid), max_s=max_s, ignore=("msg_id", "seq"))
        st.update(kind=spec["kind"], tried=spec.get("tried"), markov_witness=bool(spec.get("witness")))
        if spec["kind"] == "unsolved":
            return None, dict(st, cpu_s=round(time.process_time() - t0, 3))
        prog = dict(kind="class", spec=spec)
    pid = T.register(hole, prog)
    st.update(pid=pid, cpu_s=round(time.process_time() - t0, 3))
    return pid, st


def synth_all(spec, arch, max_s=400.0):
    ex = examples(spec, arch)
    out, stats = {}, {}
    for h in T.SYNTH_HOLES:
        pid, st = synth_hole(h, ex, max_s=max_s / 4)
        out[h], stats[h] = pid, st
    stats["n_examples"] = {h: len(ex[h][0]) for h in T.SYNTH_HOLES}
    return out, stats, ex
