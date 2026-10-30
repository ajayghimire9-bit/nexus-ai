"""Phase 10F project generator (NOT LOCKED): de_phase10d.world10d with the QUANTITY-vs-ARRIVAL-SEQUENCE SHORTCUT REMOVED.

Phase 10E audit finding 1: world10d replays an order item with a correction whose quantity is ALWAYS larger (q + 1..3) and whose
ingest sequence is always later (60+), so `ORDER BY qty DESC` was an exact alias of `ORDER BY seq DESC` on every batch: 16 of
A4_rep1's 24 verified held-out repairs ordered the replay dedup by `units`. Changes (everything else is world10d verbatim; the
functions below are copies of world10d.gen_batch / make_project10d / _make with only the marked lines changed):
  1  gen_batch: a replay correction DEcreases the quantity with probability 1/2 when it can (q > 1: uniform 1..q-1), else
     increases it (q + 1..3); the later ingest sequence is unchanged (60 + 1..30). Quantity is independent of arrival order.
  2  _make, projects whose faults include `replay` (training S_replay, admission, dreams and every held-out composition): at least
     one replayed item in a visible batch has a later sequence with a LOWER quantity, and the quantity alias (the truth with the
     item dedup ordered by quantity) must FAIL a visible public check / contract AND change a hidden batch, so a quantity-ordered
     repair can neither pass visible acceptance nor verify by accident.
Project ids are P10F.*; generation stays numeric-seeded (random.Random(seed * 1000 + attempt))."""
from __future__ import annotations

import copy  # noqa: F401
import json
import random
import shutil
from pathlib import Path

import yaml

from nexus.de_phase10d import ir10d as IR
from nexus.de_phase10d.world10d import (POOLS, DISTRACT, MECH_NODE, EXCLUSIVE, distractor_value, widths, truth_spec, inject, contracts,  # noqa: F401
                                        run_contracts, fct_cols, visible_fail, target_rows, write_csv, read_csv, load_tables)


def quantity_alias(truth, nm):
    """The shortcut repair: the truth with the item dedup ordered by quantity instead of the arrival sequence."""
    a = copy.deepcopy(truth)
    a["stg"]["stg_order_items"]["dedup"] = dict(a["stg"]["stg_order_items"]["dedup"], order=["try_int", ["col", nm["qty"]]])
    return a


def decreases(items, nm):
    """Replayed items whose LATER version (higher sequence) has a LOWER quantity."""
    g = {}
    for r in items:
        g.setdefault(r[nm["iid"]], []).append((int(r[nm["seq"]]), int(r[nm["qty"]])))
    return sum(1 for v in g.values() if len(v) > 1 and sorted(v)[-1][1] < sorted(v)[0][1])


def gen_batch(rng, nm, tabs, dcols, size=1.0):
    n_c = round(rng.randint(8, 11) * size)
    ids = rng.sample(range(1, 90), n_c)
    cdc, ts, ev, deleted, alive = [], 1000, 1, set(), {}
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
            cdc.append({nm["ev"]: str(ev), nm["payload"]: json.dumps({"op": op, "before": before, "after": after, "ts_ms": ts}), nm["off"]: str(100 + ev)})
            ev += 1
    if not deleted:
        c = rng.choice(sorted(alive))
        ts += 3
        cdc.append({nm["ev"]: str(ev), nm["payload"]: json.dumps({"op": "d", "before": alive.pop(c), "after": None, "ts_ms": ts}), nm["off"]: str(100 + ev)})
        deleted.add(c)
    rng.shuffle(cdc)
    orders, items, pays = [], [], []
    oid, iid, pid = rng.randint(100, 200), 1, 1
    custs = ids + [rng.randint(91, 110) for _ in range(2)]                 # 2 orphan customer references
    for _ in range(round(rng.randint(18, 24) * size)):
        oid += rng.randint(1, 3)
        c = rng.choice(custs)
        dirty = rng.random() < 0.12
        orders.append({nm["oid"]: str(oid), nm["fk"]: (f"{c:03d}" if rng.random() < 0.45 else str(c)), nm["ts"]: str(rng.randint(1000, 1400)),
                       nm["ccy"]: rng.choice(["USD", "EUR", "GBP"]), nm["total"]: (rng.choice(["12x", "", "n/a"]) if dirty else str(rng.randint(100, 9999))),
                       nm["status"]: rng.choice(["placed", "shipped", "returned"])})
        for _ in range(rng.choice([0, 1, 2, 2, 3])):
            q = rng.randint(1, 5)
            items.append({nm["iid"]: str(iid), nm["ofk"]: str(oid), nm["qty"]: str(q), nm["seq"]: str(rng.randint(1, 50)), nm["price"]: str(rng.randint(5, 90))})
            if rng.random() < 0.25:                                    # replayed with a correction and a later ingest sequence
                q2 = rng.randint(1, q - 1) if (rng.random() < 0.5 and q > 1) else q + rng.randint(1, 3)      # Phase 10F: quantity DEcoupled
                items.append({nm["iid"]: str(iid), nm["ofk"]: str(oid), nm["qty"]: str(q2), nm["seq"]: str(60 + rng.randint(1, 30)),
                              nm["price"]: str(rng.randint(5, 90))})
            iid += 1
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
                r[dname] = distractor_value(rng, dname, j)
        out[t] = rows
    known = [c for c in ids if c not in deleted]
    target = []
    for c in rng.sample(known, max(1, len(known) // 2)) + rng.sample(sorted(deleted), len(deleted)) + [rng.randint(111, 119) for _ in range(2)]:
        target.append(c)
    return out, sorted(set(target))


def make_project10d(spec, seed, root):
    """spec: dict(family, faults, engine, legacy, names, n_tables, width). world10d.make_project10d with the Phase 10F generator."""
    for attempt in range(60):
        p = _make(spec, seed, root, attempt)
        if p is not None:
            return p
    raise RuntimeError(f"could not build a phase-10F project {spec} seed {seed}")


def _make(spec, seed, root, attempt):
    rng = random.Random(seed * 1000 + attempt)
    nm = dict(POOLS[spec.get("names", "base")])
    n_tables = spec.get("n_tables") or rng.choice([3, 4, 5])
    if "asof_dir" in spec["faults"]:
        n_tables = 5
    if spec.get("legacy") == "scala" and n_tables == 5:
        n_tables = 4                                          # the Scala lifter has no as-of form (disclosed)
    target_w = spec.get("width") or rng.randint(62, 118)
    tabs, extra = widths(rng, n_tables, target_w)
    pool = [d for d in DISTRACT]
    rng.shuffle(pool)
    dcols, i = {}, 0
    for t in tabs:
        dcols[t] = [f"{pool[(i + j) % len(pool)]}" + ("" if (i + j) < len(pool) else f"_{(i + j) // len(pool)}") for j in range(extra[t])]
        i += extra[t]
    truth = truth_spec(nm, tabs, dcols, rng)
    legacy = inject(truth, spec["faults"], nm)
    batches, states = {}, {}
    for b, sz in (("visible", 2.0), ("visible_b", 2.0), ("hidden1", 2.0), ("hidden2", 2.5)):     # amendment 4: ~2x rows per batch
        T, keys = gen_batch(rng, nm, tabs, dcols, sz)
        batches[b] = T
        states[b] = dict(fct_target=target_rows(rng, keys, truth))
    n_cols = sum(len(batches["visible"][t][0]) for t in tabs)
    if not 60 <= n_cols <= 120:
        return None
    for f in spec["faults"]:                                   # every fault individually effective (visible fail + hidden change)
        one = inject(truth, [f], nm)
        if not any(visible_fail(one, truth, batches[v], states[v], nm) for v in ("visible", "visible_b")):
            return None
        if not any(visible_fail(one, truth, batches[b], states[b], nm) for b in ("hidden1", "hidden2")):
            return None
    if not any(visible_fail(legacy, truth, batches[v], states[v], nm) for v in ("visible", "visible_b")):
        return None
    if "replay" in spec["faults"]:                             # Phase 10F: the quantity alias must be refutable on visible AND hidden data
        alias = quantity_alias(truth, nm)
        if not any(decreases(batches[v]["order_items"], nm) for v in ("visible", "visible_b")):
            return None
        if not any(visible_fail(alias, truth, batches[v], states[v], nm) for v in ("visible", "visible_b")):
            return None
        if not any(visible_fail(alias, truth, batches[b], states[b], nm) for b in ("hidden1", "hidden2")):
            return None
    pid = f"P10F.{spec['family']}.{spec['engine']}.{spec['legacy']}.{seed}"
    ws, hid = Path(root) / pid / "workspace", Path(root) / pid / "hidden"
    if ws.parent.exists():
        shutil.rmtree(ws.parent)
    for d in (ws / "data", ws / "data" / "b", ws / "models", ws / "state", hid):
        d.mkdir(parents=True, exist_ok=True)
    from nexus.de_phase10d import legacy10d as LG
    for t in tabs:
        write_csv(ws / "data" / f"{t}.csv", batches["visible"][t])
        write_csv(ws / "data" / "b" / f"{t}.csv", batches["visible_b"][t])
        for b in ("hidden1", "hidden2"):
            write_csv(hid / f"{b}_{t}.csv", batches[b][t])
    (ws / "state" / "fct_target.json").write_text(json.dumps(states["visible"]["fct_target"]))
    (ws / "state" / "fct_target_b.json").write_text(json.dumps(states["visible_b"]["fct_target"]))
    for b in ("hidden1", "hidden2"):
        (hid / f"{b}_state.json").write_text(json.dumps(states[b]))
        R = IR.interpret(truth, batches[b], states[b])
        (hid / f"{b}_expected.json").write_text(json.dumps(dict(cols=fct_cols(truth), rows=[[r.get(c) for c in fct_cols(truth)] for r in R["fct_out"]])))
    files = LG.write_legacy(legacy, spec["legacy"], ws)
    Rv = IR.interpret(truth, batches["visible"], states["visible"])
    Rb = IR.interpret(truth, batches["visible_b"], states["visible_b"])
    cols = fct_cols(truth)
    schema = dict(version=2, models=[dict(name=rel, columns=[dict(name=col, tests=[test if test != "accepted_values" else {"accepted_values": {"values": ["c", "u", "r"]}}])])
                                     for node, ts in contracts(nm).items() for rel, test, col in ts if test != "grain"]
                  + [dict(name="int_orders", tests=[{"equal_rowcount": {"compare_model": "ref('stg_orders')"}}])])
    (ws / "models" / "schema.yml").write_text(yaml.safe_dump(schema, sort_keys=False))
    contract = dict(nodes=["stg", "int", "fct"], files=files, legacy_language=spec["legacy"], engine=spec["engine"], tables=tabs,
                    public_checks=[dict(kind="example_rows", cols=cols, rows=[[r.get(c) for c in cols] for r in Rv["fct_out"]]), dict(kind="row_count", n=len(Rv["fct_out"])),
                                   dict(kind="unique", col="cust_key")],
                    public_checks_b=[dict(kind="example_rows", cols=cols, rows=[[r.get(c) for c in cols] for r in Rb["fct_out"]]), dict(kind="row_count", n=len(Rb["fct_out"]))],
                    names=nm)
    (ws / "contract.json").write_text(json.dumps(contract, indent=1))
    (hid / "truth.json").write_text(json.dumps(truth))
    return dict(pid=pid, family=spec["family"], faults=list(spec["faults"]), nodes_faulted=sorted({MECH_NODE[f] for f in spec["faults"]}), engine=spec["engine"],
                legacy=spec["legacy"], ws=str(ws), hidden_dir=str(hid), n_tables=len(tabs), n_cols=n_cols, names=nm, seed=seed, spec=spec)

