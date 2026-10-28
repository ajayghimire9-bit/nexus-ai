"""OOP-track environment (NOT LOCKED; environment side), namespace de5. r2_env (unchanged) plus two DEVELOPMENT fault classes
for the synthesised holes; every de5 spec declares their rules (and the R2 X3 / X4 rules):
  D1 registry amount unit (src / dev / val, (seed // 2) even): orders schema v4 registered at tick 9 declares
     types.amount_unit = minor; every later orders record carries its amount in minor units (x 100)
  D2 unknown warehouse     (src / dev / val, (seed // 2) odd): up to 3 orders CREATED from tick 9 name a warehouse outside the
     declared warehouses in every version; they are quarantined (reason unknown_warehouse), never silver / gold
src / dev / val worlds also keep X1 / X2 (r2_env.x_class). Test worlds realise ONLY the R2-withheld X3 (even) / X4 (odd) from
tick 9 - near-transfer of D2 / D1 (same rule shapes on a different field and constant); their generators run only in the seal
script. Disclosed: X3 / X4 have been known to the developer since R2."""
from __future__ import annotations

import random
from datetime import timedelta

from nexus import r2_env as R2E
from nexus import s4_env as E

POOLS = R2E.POOLS
Obs, write_tick, write_log, retention, retention_fn, append_records, partition_states = (
    R2E.Obs, R2E.write_tick, R2E.write_log, R2E.retention, R2E.retention_fn, R2E.append_records, R2E.partition_states)
UNKNOWN_WH = "W9"
WAREHOUSES = ["W1", "W2", "W3", "W4"]


class _G5(R2E._G4):
    def __init__(self, seed, split, attempt):
        super().__init__(seed, split, attempt)
        self.r = random.Random(f"de5:{split}:{seed}:{attempt}")
        pools, r = POOLS[split], self.r
        self.n = {k: v[r.choice(pools)] for k, v in E.NAMES.items()}
        self.fx = dict(E.FX[max(pools)])
        self.L = r.choice(E.LATENESS_H[r.choice(pools)])
        self.tz_mixed = r.random() < 0.7


def d_class(seed, split):
    if split == "test":
        return None
    return "D1" if (seed // 2) % 2 == 0 else "D2"


def _d1(pending, w, r, scenario):
    n = w["n"]
    fields = {c: n[c] for c in ("order_id", "warehouse_id", "status", "amount", "currency", "discount", "promised_ts", "deleted")}
    fields.update(amount=n["amount_v2"], channel=n["channel"])
    pending.append((9, "_schemas", 0, dict(msg_id="reg-orders-4", ingest_ts=E.iso(E.T0 + 8 * E.D + timedelta(minutes=1)),
                                           subject="orders", version=4, fields=fields,
                                           types={"discount": "float", "amount_unit": "minor"})))
    moved, seen = 0, set()
    for tk, tp, p, rec in pending:
        if tp == "orders_cdc" and tk >= 9 and rec.get("schema_version") == 3 and rec.get("after"):
            rec["schema_version"] = 4
            if id(rec["after"]) not in seen:             # a retry duplicate shares its payload object: convert once
                seen.add(id(rec["after"]))
                rec["after"][n["amount_v2"]] = round(float(rec["after"][n["amount_v2"]]) * 100.0, 4)
                moved += 1
    return dict(d_class="D1", amount_minor_records=moved, d_realised=moved >= 3)


def _d2(pending, w, r, scenario):
    wh = w["n"]["warehouse_id"]
    created = sorted({rec["key"] for tk, tp, p, rec in pending if tp == "orders_cdc" and tk >= 9 and rec.get("op") == "c"})
    keys = sorted(r.sample(created, min(3, len(created))))
    for tk, tp, p, rec in pending:
        if tp == "orders_cdc" and rec.get("key") in keys and rec.get("after") and wh in rec["after"]:
            rec["after"][wh] = UNKNOWN_WH
    return dict(d_class="D2", unknown_warehouse_keys=keys, d_realised=len(keys) >= 2)


def hook_for(w):
    hx = R2E.hook_for(w)
    hd = {"D1": _d1, "D2": _d2}.get(w.get("d_class"))
    if hd is None:
        return hx

    def both(pending, w_, r, scenario):
        out = dict(hx(pending, w_, r, scenario) or {}) if hx else {"x_realised": True}
        out.update(hd(pending, w_, r, scenario))
        return out
    return both


def encode(w, scenario, incidents=()):
    return E.encode(w, scenario, incidents, hook=hook_for(w))


def make_world(seed, split):
    for attempt in range(300):
        g = _G5(seed, split, attempt)
        whs, live, hist = E._versions(g)
        w = dict(seed=seed, split=split, attempt=attempt, whs=whs, n=g.n, fx=g.fx, L=g.L, tz_mixed=g.tz_mixed,
                 withheld=True, live=live, hist=hist, rseed=f"de5-enc:{split}:{seed}:{attempt}", x_class=R2E.x_class(seed, split),
                 d_class=d_class(seed, split), ns="de5")
        enc = encode(w, "build")
        f = E.features(enc["truth"])
        ok = (f["out_of_order_keys"] >= 2 and f["late_corrections"] >= 2 and f["backfill_overwrite_traps"] >= 2
              and f["backfill_resurrection_traps"] >= 2 and f["late_telemetry"] >= 2 and f["soft"] >= 1 and f["hard"] >= 1
              and f["dups"] >= 2 and f["float_discounts"] >= 2 and f["renamed_amounts"] >= 2 and f["malformed"] >= 1
              and f["heldout_late_corrections"] >= 1 and f["partition2_keys"] >= 2 and enc["truth"].get("x_realised"))
        if ok:
            t = encode(w, "ops")["truth"]
            ok = bool(t.get("x_realised")) and (w["d_class"] is None or bool(t.get("d_realised")))
        if ok:
            w["features"] = f
            w["spec"] = spec(w)
            return w
    raise RuntimeError("could not realise every fault class")


def spec(w):
    s = R2E.spec(w)
    s["project"] = f"de5-{w['split']}-{w['seed']}"
    s["warehouses"] = list(WAREHOUSES)
    s["warehouse_rule"] = ("an order record whose warehouse_id is not in warehouses is quarantined (reason unknown_warehouse) and "
                           "never enters silver / gold")
    s["registry"]["amount_unit"] = "a registry version may declare types.amount_unit = minor: amount = value / 100 (absent = major)"
    return s


schedule = R2E.schedule


def ops_world(w, split, seed, forced=None):
    r = random.Random(f"de5-ops:{split}:{seed}")
    from nexus import s5_incidents as I
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
    R2E._first_copy_truth(enc)
    return enc, incs
