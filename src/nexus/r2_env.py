"""R2 environment (NOT LOCKED; environment side). Builds on r1_env / s4_env / s5_incidents without changing them.

de4 worlds: W1 / W2 (inspected in Stages 4-6) in every world; X1 aborted transactions (even seeds) / X2 delayed segment gap
(odd seeds) in src / dev / val worlds - known development material since R1; test worlds instead realise ONE withheld class
from tick 9:
  X3 unknown currency (even seeds): a few new orders are written in a currency outside the declared fx table
  X4 registry discount unit (odd seeds): orders schema v4 (registered at tick 9) declares discount_unit = fraction and every
     later orders record carries its discount as a fraction of 1
Both rules are declared in every de4 spec. The X3 / X4 hooks run only for split == "test" (the seal script)."""
from __future__ import annotations

import json
import random
from datetime import timedelta

from nexus import r1_env as RE
from nexus import s4_env as E
from nexus import s5_incidents as I

POOLS = RE.POOLS
Obs, write_tick, write_log, retention, retention_fn, append_records, partition_states = (
    RE.Obs, RE.write_tick, RE.write_log, RE.retention, RE.retention_fn, RE.append_records, RE.partition_states)
UNKNOWN_CCY = "JPY"


class _G4(RE._G3):
    def __init__(self, seed, split, attempt):
        super().__init__(seed, split, attempt)
        self.r = random.Random(f"de4:{split}:{seed}:{attempt}")
        pools, r = POOLS[split], self.r
        self.n = {k: v[r.choice(pools)] for k, v in E.NAMES.items()}
        self.fx = dict(E.FX[max(pools)])
        self.L = r.choice(E.LATENESS_H[r.choice(pools)])
        self.tz_mixed = r.random() < 0.7


def x_class(seed, split):
    if split == "test":
        return "X3" if seed % 2 == 0 else "X4"
    return "X1" if seed % 2 == 0 else "X2"


def hook_for(w):
    return {"X1": RE._x1, "X2": RE._x2, "X3": _x3, "X4": _x4}.get(w.get("x_class"))


def encode(w, scenario, incidents=()):
    return E.encode(w, scenario, incidents, hook=hook_for(w))


def make_world(seed, split):
    for attempt in range(300):
        g = _G4(seed, split, attempt)
        whs, live, hist = E._versions(g)
        w = dict(seed=seed, split=split, attempt=attempt, whs=whs, n=g.n, fx=g.fx, L=g.L, tz_mixed=g.tz_mixed,
                 withheld=True, live=live, hist=hist, rseed=f"de4-enc:{split}:{seed}:{attempt}", x_class=x_class(seed, split),
                 ns="de4")
        enc = encode(w, "build")
        f = E.features(enc["truth"])
        ok = (f["out_of_order_keys"] >= 2 and f["late_corrections"] >= 2 and f["backfill_overwrite_traps"] >= 2
              and f["backfill_resurrection_traps"] >= 2 and f["late_telemetry"] >= 2 and f["soft"] >= 1 and f["hard"] >= 1
              and f["dups"] >= 2 and f["float_discounts"] >= 2 and f["renamed_amounts"] >= 2 and f["malformed"] >= 1
              and f["heldout_late_corrections"] >= 1 and f["partition2_keys"] >= 2 and enc["truth"].get("x_realised"))
        if ok:
            ok = bool(encode(w, "ops")["truth"].get("x_realised"))
        if ok:
            w["features"] = f
            w["spec"] = spec(w)
            return w
    raise RuntimeError("could not realise every fault class")


def spec(w):
    s = RE.spec(w)
    s["project"] = f"de4-{w['split']}-{w['seed']}"
    s["currency_rule"] = ("an order record whose currency is not in fx_to_usd is quarantined (reason unknown_currency) and never "
                          "enters silver / gold")
    s["registry"]["discount_unit"] = ("a registry version may declare types.discount_unit = fraction: discount percent = value x "
                                      "100 (absent = percent)")
    return s


# ------------------------------------------------------------------------------------------------ withheld hooks (test only)
def _x3(pending, w, r, scenario):
    """X3: up to 3 orders CREATED from tick 9 carry a currency outside the fx table in every version."""
    cur = w["n"]["currency"]
    created = sorted({rec["key"] for tk, tp, p, rec in pending if tp == "orders_cdc" and tk >= 9 and rec.get("op") == "c"})
    keys = sorted(r.sample(created, min(3, len(created))))
    for tk, tp, p, rec in pending:
        if tp == "orders_cdc" and rec.get("key") in keys and rec.get("after") and cur in rec["after"]:
            rec["after"][cur] = UNKNOWN_CCY
    return dict(x_class="X3", unknown_currency_keys=keys, x_realised=len(keys) >= 2)


def _x4(pending, w, r, scenario):
    """X4: orders schema v4 registered at tick 9 declares discount_unit = fraction; every later v3 orders record becomes v4
    with its discount written as a fraction."""
    n = w["n"]
    fields = {c: n[c] for c in ("order_id", "warehouse_id", "status", "amount", "currency", "discount", "promised_ts", "deleted")}
    fields.update(amount=n["amount_v2"], channel=n["channel"])
    pending.append((9, "_schemas", 0, dict(msg_id="reg-orders-4", ingest_ts=E.iso(E.T0 + 8 * E.D + timedelta(minutes=1)),
                                           subject="orders", version=4, fields=fields,
                                           types={"discount": "float", "discount_unit": "fraction"})))
    moved, seen = 0, set()
    for tk, tp, p, rec in pending:
        if tp == "orders_cdc" and tk >= 9 and rec.get("schema_version") == 3 and rec.get("after"):
            rec["schema_version"] = 4
            if id(rec["after"]) not in seen:             # a retry duplicate shares its payload object: convert once
                seen.add(id(rec["after"]))
                rec["after"][n["discount"]] = round(float(rec["after"][n["discount"]]) / 100.0, 6)
                moved += 1
    return dict(x_class="X4", discount_fraction_records=moved, x_realised=moved >= 3)


# ------------------------------------------------------------------------------------------------ ops worlds
def schedule(seed, split):
    r = random.Random(f"de4-incidents:{split}:{seed}")
    names = r.sample(RE.SEEN_OPS, 2)
    ticks = sorted(r.sample(range(8, 14), len(names)))
    if "snapshot_interrupted" in names:
        i = names.index("snapshot_interrupted")
        names[i], names[0] = names[0], names[i]
    return [(n, t) for n, t in zip(names, ticks)]


def ops_world(w, split, seed, forced=None):
    r = random.Random(f"de4-ops:{split}:{seed}")
    incs = [I.CLASSES[n](t, r) for n, t in (forced if forced is not None else schedule(seed, split))]
    enc = E.encode(w, "ops", incidents=incs, hook=hook_for(w))
    I._reoffset(enc)
    I._rebind(enc)
    t = enc["truth"]
    t["poison"] = [dict(topic=tp, part=p, offset=x["offset"], tick=tk) for tk, parts in enc["log"].items()
                   for (tp, p), rs in parts.items() for x in rs if x.get("_poison")]
    if t.get("aborted"):
        pos = {x["msg_id"]: (tk, p, x["offset"]) for tk, parts in enc["log"].items() for (tp, p), rs in parts.items()
               for x in rs if tp == "orders_cdc"}
        for a in t["aborted"]:
            a["tick"], a["part"], a["offset"] = pos[a["msg_id"]]
    t["incidents"] = [dict(name=i.name, tick=i.tick) for i in incs]
    _first_copy_truth(enc)
    return enc, incs


def _first_copy_truth(enc):
    """Identity rule (every spec): msg_id identifies an event and its FIRST delivery is the event; later copies are
    duplicates. An incident that alters only a later copy (s5 ClockSkew rewrites every telemetry record ingested in its window,
    including a retry duplicate of an earlier valid record) must not relabel the event. Each telemetry truth event's
    event_ts / future flag is therefore taken from its first delivered copy (R2 evaluator correction found by the
    reproducer, report 0.9; R1 scores are not rescored)."""
    first = {}
    for tk, parts in enc["log"].items():
        for (tp, p), rs in parts.items():
            if tp != "telemetry":
                continue
            for x in rs:
                k = x["msg_id"]
                if k not in first or (x["ingest_ts"], tk, p, x["offset"]) < first[k][0]:
                    first[k] = ((x["ingest_ts"], tk, p, x["offset"]), x)
    fixed = 0
    for e in enc["truth"]["telemetry"]:
        if e["msg_id"] not in first:
            continue
        x = first[e["msg_id"]][1]
        if x.get("_poison"):
            continue
        raw = x["event_ts"]
        et = E.datetime.fromtimestamp(raw / 1000, E.timezone.utc) if isinstance(raw, (int, float)) else \
            E.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        fut = (et - E.datetime.fromisoformat(x["ingest_ts"].replace("Z", "+00:00"))).total_seconds() > 300
        if bool(e.get("future", False)) != fut:
            fixed += 1
            e["future"] = fut
            if not fut:
                e["event_ts"], e["event_raw"] = E.iso(et), raw
    enc["truth"]["first_copy_corrections"] = fixed
