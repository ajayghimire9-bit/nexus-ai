"""Phase 10G project generator (NOT LOCKED): de_phase10f.world10f (quantity independent of the arrival sequence) plus DESIGNED
AMBIGUITY and BUDGETED EVIDENCE CHANNELS.

spec["amb"] in {None, "seq", "time", "grain"} makes the initial visible batches leave 2-3 candidate repairs of ONE edit tied on every
visible check; the hidden batches and exactly one evidence channel separate them:
  seq    (needs the replay fault)        the item dedup ORDER: the true load sequence vs two twin sequence columns (ingest-batch
         sequence, audit counter) that rise with it inside every visible replay group but are OUT OF ORDER on some re-deliveries in
         hidden data                                                                        -> channel 1 (out-of-order replay slice)
  time   (needs qualify_order)            the CDC dedup ORDER: event time ts_ms vs arrival order (kafka offset / event id); no
         visible update arrives late, but hidden data has deleted customers whose pre-delete update arrives AFTER the delete
                                                                                            -> channel 2 (boundary / late-arrival slice)
  grain  (needs fanout)                   the child PRE-AGGREGATION: SUM vs MAX of the line quantity; on visible data every extra
         line of a multi-line order has zero units, hidden orders have several positive lines -> channel 3 (multi-child grain slice)
Without a designed ambiguity, the same data properties are visible (a late-arriving update, out-of-order twins, positive multi-line
quantities), so those alternatives fail visible checks and no tie of these kinds arises (enforced by rejection sampling).

EVIDENCE CHANNELS (released only on request; each is an extra batch: input tables + target state + the expected fct_out example rows
and row count, generated from the truth like the visible batches, and TARGETED: bland for every other mechanism):
  1 request_out_of_order_replay_slice   one line per order, many re-delivered lines with out-of-order twins, no late CDC events
  2 request_boundary_timestamp_slice    late-arriving pre-delete updates, one line per order, no re-deliveries
  3 request_multi_child_grain_slice     2-3 positive lines per order, no re-deliveries, no late CDC events
  4 request_upstream_lineage_contract   bland (in THIS world the producer notes never split a tie: a decoy channel, disclosed)
  5 request_stakeholder_clarification   bland (no business-rule conflict is generated: a decoy channel, disclosed)
Build validity (rejection sampling, numeric seed * 1000 + attempt): with amb = a, every alias of a (the truth with the competing
choice) passes both visible batches, changes a hidden batch, FAILS channel CH[a] and passes every other channel; every alias of the
other mechanisms whose fault is present fails a visible batch. Project ids P10G.*"""
from __future__ import annotations

import copy
import json
import random
import shutil
from pathlib import Path

import yaml

from nexus.de_phase10d import ir10d as IR
from nexus.de_phase10f.world10f import (POOLS, DISTRACT, MECH_NODE, distractor_value, widths, truth_spec, inject, contracts,  # noqa: F401
                                        fct_cols, visible_fail, target_rows, write_csv, read_csv, load_tables, quantity_alias, decreases)

CHANNELS = {1: "request_out_of_order_replay_slice", 2: "request_boundary_timestamp_slice", 3: "request_multi_child_grain_slice",
            4: "request_upstream_lineage_contract", 5: "request_stakeholder_clarification"}
CH = {"seq": 1, "time": 2, "grain": 3}
NEEDS = {"seq": "replay", "time": "qualify_order", "grain": "fanout"}
TWINS = dict(base=("ingest_batch_seq", "audit_counter"), heldout=("batch_load_no", "audit_ctr"))
PROBE = {1: dict(late=0, oo=0.6, zero_multi=False, lines=(1,), replay=0.7), 2: dict(late=3, oo=0.0, zero_multi=False, lines=(1,), replay=0.0),
         3: dict(late=0, oo=0.0, zero_multi=False, lines=(2, 3), replay=0.0), 4: dict(late=0, oo=0.0, zero_multi=False, lines=(1,), replay=0.0),
         5: dict(late=0, oo=0.0, zero_multi=False, lines=(1,), replay=0.0)}


def gen_batch10g(rng, nm, tabs, dcols, size, twins, late=1, oo=0.3, zero_multi=False, lines=(0, 1, 2, 2, 3), replay=0.25):
    """world10f.gen_batch with: `late` deleted customers whose pre-delete version ARRIVES after the delete (event id / offset swapped,
    event time kept); twin sequence columns, out of order on a re-delivery with probability `oo` (each independently); every extra line
    of a multi-line order with zero units if `zero_multi`; line-count choices and re-delivery rate as given."""
    n_c = round(rng.randint(8, 11) * size)
    ids = rng.sample(range(1, 90), n_c)
    cdc, ts, ev, deleted, alive, rows_of = [], 1000, 1, set(), {}, {}
    for c in ids:
        row = {nm["cust"]: c, nm["seg"]: rng.choice(["gold", "silver", "bronze"]), nm["ctry"]: rng.choice(["us", "de", "fr"]), nm["email"]: f"u{c}@x.io"}
        evs = [("c", None, dict(row))]
        for _ in range(rng.randint(0, 2)):
            new = dict(evs[-1][2], **{nm["seg"]: rng.choice(["gold", "silver", "bronze"])})
            evs.append(("u", evs[-1][2], new))
        if rng.random() < 0.3:
            evs.append(("d", evs[-1][2], None))
            deleted.add(c)
        else:
            alive[c] = evs[-1][2]
        for op, before, after in evs:
            ts += rng.randint(1, 9)
            r = {nm["ev"]: str(ev), nm["payload"]: json.dumps({"op": op, "before": before, "after": after, "ts_ms": ts}), nm["off"]: str(100 + ev)}
            cdc.append(r)
            rows_of.setdefault(c, []).append(r)
            ev += 1
    if not deleted:
        c = rng.choice(sorted(alive))
        ts += 3
        r = {nm["ev"]: str(ev), nm["payload"]: json.dumps({"op": "d", "before": alive.pop(c), "after": None, "ts_ms": ts}), nm["off"]: str(100 + ev)}
        cdc.append(r)
        rows_of.setdefault(c, []).append(r)
        deleted.add(c)
    lateable = [c for c in sorted(deleted) if len(rows_of[c]) >= 2]
    rng.shuffle(lateable)
    for c in lateable[:late]:                                    # the pre-delete version arrives after the delete
        a, b = rows_of[c][-2], rows_of[c][-1]
        a[nm["ev"]], b[nm["ev"]] = b[nm["ev"]], a[nm["ev"]]
        a[nm["off"]], b[nm["off"]] = b[nm["off"]], a[nm["off"]]
    rng.shuffle(cdc)
    t1, t2 = twins
    orders, items, pays = [], [], []
    oid, iid, pid = rng.randint(100, 200), 1, 1
    custs = ids + [rng.randint(91, 110) for _ in range(2)]
    for _ in range(round(rng.randint(18, 24) * size)):
        oid += rng.randint(1, 3)
        c = rng.choice(custs)
        dirty = rng.random() < 0.12
        orders.append({nm["oid"]: str(oid), nm["fk"]: (f"{c:03d}" if rng.random() < 0.45 else str(c)), nm["ts"]: str(rng.randint(1000, 1400)),
                       nm["ccy"]: rng.choice(["USD", "EUR", "GBP"]), nm["total"]: (rng.choice(["12x", "", "n/a"]) if dirty else str(rng.randint(100, 9999))),
                       nm["status"]: rng.choice(["placed", "shipped", "returned"])})
        order_lines = []
        for _ in range(rng.choice(list(lines))):
            q = rng.randint(1, 5)
            s = rng.randint(1, 50)
            a = {nm["iid"]: str(iid), nm["ofk"]: str(oid), nm["qty"]: str(q), nm["seq"]: str(s), nm["price"]: str(rng.randint(5, 90)),
                 t1: str(10 * s + rng.randint(0, 9)), t2: str(600 + 7 * s + rng.randint(0, 6))}
            vers = [a]
            if rng.random() < replay:                                  # re-delivered with a correction and a later load sequence
                q2 = rng.randint(1, q - 1) if (rng.random() < 0.5 and q > 1) else q + rng.randint(1, 3)
                s2 = 60 + rng.randint(1, 30)
                b = {nm["iid"]: str(iid), nm["ofk"]: str(oid), nm["qty"]: str(q2), nm["seq"]: str(s2), nm["price"]: str(rng.randint(5, 90)),
                     t1: str(10 * s2 + rng.randint(0, 9)), t2: str(600 + 7 * s2 + rng.randint(0, 6))}
                if rng.random() < oo:
                    b[t1] = str(int(a[t1]) - rng.randint(1, 9))           # out-of-order ingest batch
                if rng.random() < oo:
                    b[t2] = str(int(a[t2]) - rng.randint(1, 6))           # out-of-order audit counter
                vers.append(b)
            order_lines.append(vers)
            iid += 1
        if zero_multi and len(order_lines) >= 2:
            for vers in order_lines[1:]:
                for v in vers:
                    v[nm["qty"]] = "0"
        for vers in order_lines:
            items += vers
        for _ in range(rng.choice([0, 1, 1, 2])):
            pays.append({nm["pid"]: str(pid), nm["pofk"]: str(oid), nm["amt"]: str(rng.randint(50, 5000)), nm["method"]: rng.choice(["card", "wire", "cash"])})
            pid += 1
    rates = [{nm["ccy"]: c, nm["vfrom"]: str(v), nm["rate"]: str(rng.randint(8000, 13000))} for c in ("USD", "EUR", "GBP") for v in (900, 1100, 1250)]
    T = dict(cdc_customers=cdc, orders=orders, order_items=items, payments=pays, fx_rates=rates)
    out = {}
    for t in tabs:
        rows = T[t] or [dict.fromkeys(next(iter(T[t] or [{}])), None)]
        for r in rows:
            for j, dname in enumerate(dcols[t]):
                if dname not in twins:
                    r[dname] = distractor_value(rng, dname, j)
        out[t] = rows
    known = [c for c in ids if c not in deleted]
    target = list(rng.sample(known, max(1, len(known) // 2))) + rng.sample(sorted(deleted), len(deleted)) + [rng.randint(111, 119) for _ in range(2)]
    return out, sorted(set(target))


def aliases(mech, truth, nm, twins):
    """The competing (wrong) repairs of a mechanism, as edits of the truth."""
    out = []
    if mech == "seq":
        for tw in twins:
            a = copy.deepcopy(truth)
            a["stg"]["stg_order_items"]["dedup"] = dict(a["stg"]["stg_order_items"]["dedup"], order=["try_int", ["col", tw]])
            out.append(a)
    elif mech == "time":
        for c in (nm["off"], nm["ev"]):
            a = copy.deepcopy(truth)
            a["stg"]["stg_customers"]["dedup"] = dict(a["stg"]["stg_customers"]["dedup"], order=["try_int", ["col", c]])
            out.append(a)
    elif mech == "grain":
        a = copy.deepcopy(truth)
        j = a["int"]["joins"][0]
        j["agg"] = dict(j["agg"], measures=[[m[0], "max", m[2]] for m in j["agg"]["measures"]])
        out.append(a)
    return out


def make_project10g(spec, seed, root):
    """spec: dict(family, faults, amb, engine, legacy, names)."""
    amb = spec.get("amb")
    if amb is not None and NEEDS[amb] not in spec["faults"]:
        raise ValueError(f"ambiguity {amb} needs the {NEEDS[amb]} fault")
    for attempt in range(150):
        p = _make(spec, seed, root, attempt)
        if p is not None:
            return p
    raise RuntimeError(f"could not build a phase-10G project {spec} seed {seed}")


def _make(spec, seed, root, attempt):
    rng = random.Random(seed * 1000 + attempt)
    amb = spec.get("amb")
    nm = dict(POOLS[spec.get("names", "base")])
    twins = TWINS[spec.get("names", "base")]
    n_tables = spec.get("n_tables") or rng.choice([3, 4, 5])
    if "asof_dir" in spec["faults"]:
        n_tables = 5
    if spec.get("legacy") == "scala" and n_tables == 5:
        n_tables = 4
    target_w = spec.get("width") or rng.randint(62, 116)
    tabs, extra = widths(rng, n_tables, target_w)
    pool = [d for d in DISTRACT]
    rng.shuffle(pool)
    dcols, i = {}, 0
    for t in tabs:
        dcols[t] = [f"{pool[(i + j) % len(pool)]}" + ("" if (i + j) < len(pool) else f"_{(i + j) // len(pool)}") for j in range(extra[t])]
        i += extra[t]
    dcols["order_items"] = dcols["order_items"] + list(twins)
    truth = truth_spec(nm, tabs, dcols, rng)
    legacy = inject(truth, spec["faults"], nm)
    vis = dict(late=0 if amb == "time" else 1, oo=0.0 if amb == "seq" else 0.3, zero_multi=amb == "grain")
    hid = dict(late=2, oo=0.3, zero_multi=False)
    batches, states = {}, {}
    for b, sz, mode in (("visible", 2.0, vis), ("visible_b", 2.0, vis), ("hidden1", 2.0, hid), ("hidden2", 2.5, hid)):
        T, keys = gen_batch10g(rng, nm, tabs, dcols, sz, twins, **mode)
        batches[b] = T
        states[b] = dict(fct_target=target_rows(rng, keys, truth))
    for e, mode in PROBE.items():
        T, keys = gen_batch10g(rng, nm, tabs, dcols, 1.0, twins, **mode)
        batches[f"probe{e}"] = T
        states[f"probe{e}"] = dict(fct_target=target_rows(rng, keys, truth))
    n_cols = sum(len(batches["visible"][t][0]) for t in tabs)
    if not 60 <= n_cols <= 120:
        return None
    V, H, P = ("visible", "visible_b"), ("hidden1", "hidden2"), [f"probe{e}" for e in PROBE]
    fails = lambda s, bs: [visible_fail(s, truth, batches[b], states[b], nm) for b in bs]     # noqa: E731
    for f in spec["faults"]:
        one = inject(truth, [f], nm)
        if not any(fails(one, V)) or not any(fails(one, H)):
            return None
    if not any(fails(legacy, V)):
        return None
    if "replay" in spec["faults"]:
        alias = quantity_alias(truth, nm)
        if not any(decreases(batches[v]["order_items"], nm) for v in V) or not any(fails(alias, V)) or not any(fails(alias, H)):
            return None
    for mech, need in NEEDS.items():
        if need not in spec["faults"]:
            continue
        for a in aliases(mech, truth, nm, twins):
            if mech == amb:
                pf = fails(a, P)
                if any(fails(a, V)) or not any(fails(a, H)) or not pf[CH[mech] - 1] or any(x for e, x in enumerate(pf, 1) if e != CH[mech]):
                    return None
            elif not any(fails(a, V)):
                return None
    pid = f"P10G.{spec['family']}.{amb or 'none'}.{spec['engine']}.{spec['legacy']}.{seed}"
    ws, hd = Path(root) / pid / "workspace", Path(root) / pid / "hidden"
    if ws.parent.exists():
        shutil.rmtree(ws.parent)
    for d in (ws / "data", ws / "data" / "b", ws / "models", ws / "state", hd):
        d.mkdir(parents=True, exist_ok=True)
    from nexus.de_phase10d import legacy10d as LG
    cols = fct_cols(truth)
    for t in tabs:
        write_csv(ws / "data" / f"{t}.csv", batches["visible"][t])
        write_csv(ws / "data" / "b" / f"{t}.csv", batches["visible_b"][t])
        for b in list(H) + P:
            write_csv(hd / f"{b}_{t}.csv", batches[b][t])
    (ws / "state" / "fct_target.json").write_text(json.dumps(states["visible"]["fct_target"]))
    (ws / "state" / "fct_target_b.json").write_text(json.dumps(states["visible_b"]["fct_target"]))
    for b in list(H) + P:
        (hd / f"{b}_state.json").write_text(json.dumps(states[b]))
        R = IR.interpret(truth, batches[b], states[b])
        (hd / f"{b}_expected.json").write_text(json.dumps(dict(cols=cols, rows=[[r.get(c) for c in cols] for r in R["fct_out"]])))
    files = LG.write_legacy(legacy, spec["legacy"], ws)
    Rv = IR.interpret(truth, batches["visible"], states["visible"])
    Rb = IR.interpret(truth, batches["visible_b"], states["visible_b"])
    schema = dict(version=2, models=[dict(name=rel, columns=[dict(name=col, tests=[test if test != "accepted_values" else {"accepted_values": {"values": ["c", "u", "r"]}}])])
                                     for node, ts in contracts(nm).items() for rel, test, col in ts if test != "grain"]
                  + [dict(name="int_orders", tests=[{"equal_rowcount": {"compare_model": "ref('stg_orders')"}}])])
    (ws / "models" / "schema.yml").write_text(yaml.safe_dump(schema, sort_keys=False))
    contract = dict(nodes=["stg", "int", "fct"], files=files, legacy_language=spec["legacy"], engine=spec["engine"], tables=tabs,
                    public_checks=[dict(kind="example_rows", cols=cols, rows=[[r.get(c) for c in cols] for r in Rv["fct_out"]]), dict(kind="row_count", n=len(Rv["fct_out"])),
                                   dict(kind="unique", col="cust_key")],
                    public_checks_b=[dict(kind="example_rows", cols=cols, rows=[[r.get(c) for c in cols] for r in Rb["fct_out"]]), dict(kind="row_count", n=len(Rb["fct_out"]))],
                    names=nm, evidence_channels=CHANNELS)
    (ws / "contract.json").write_text(json.dumps(contract, indent=1))
    (hd / "truth.json").write_text(json.dumps(truth))
    return dict(pid=pid, family=spec["family"], faults=list(spec["faults"]), amb=amb, nodes_faulted=sorted({MECH_NODE[f] for f in spec["faults"]}),
                engine=spec["engine"], legacy=spec["legacy"], ws=str(ws), hidden_dir=str(hd), n_tables=len(tabs), n_cols=n_cols, names=nm, seed=seed, spec=spec,
                attempt=attempt)
