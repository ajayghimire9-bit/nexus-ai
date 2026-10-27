"""R1 environment (NOT LOCKED; environment side). Builds on s4_env / s5_incidents without changing their default behaviour.

* de3 worlds: W1 partition growth and W2 epoch-ms timestamps (inspected in Stages 4-6) are DEVELOPMENT classes here and
  occur in every split. Test worlds additionally realise ONE withheld class from tick 9 (after the build window):
    X1 aborted producer transactions (even seeds)   X2 delayed segment publication with a gap (odd seeds)
  Both rules are declared in every spec. The X1 / X2 hooks run ONLY for split == "test".
* Authoritative observations: the environment (broker / registry) journals what it does WHEN it does it - partition
  creation, segment publication (base / end offset, record tick, publication tick), deletion by retention, partition
  availability, registry versions, transaction records and markers - in log/_obs/journal.log, and materialises
  log/_obs/tick_NNNN.json = the facts as of tick NNNN only. Nothing here is inferred from surviving data records."""
from __future__ import annotations

import json
import os
import random
import stat
from datetime import timedelta
from pathlib import Path

from nexus import s4_env as E
from nexus import s5_incidents as I

KEEP = 6
POOLS = {"src": (0,), "dev": (0,), "val": (0, 1), "val_b": (0, 1), "test": (1, 2)}
SEEN_OPS = I.SEEN + I.WITHHELD                    # clock_skew / poison_message were inspected in Stages 4-6: seen now


class _G3:
    def __init__(self, seed, split, attempt):
        self.r = random.Random(f"de3:{split}:{seed}:{attempt}")
        pools, r = POOLS[split], self.r
        self.n = {k: v[r.choice(pools)] for k, v in E.NAMES.items()}
        self.fx = dict(E.FX[max(pools)])
        self.L = r.choice(E.LATENESS_H[r.choice(pools)])
        self.tz_mixed = r.random() < 0.7
        self.withheld = True                      # s4_env flag enabling W1 + W2 (development classes in R1)


def x_class(seed, split):
    return ("X1" if seed % 2 == 0 else "X2") if split == "test" else None


def hook_for(w):
    return {"X1": _x1, "X2": _x2}.get(w.get("x_class"))


def encode(w, scenario, incidents=()):
    return E.encode(w, scenario, incidents, hook=hook_for(w))


def make_world(seed, split):
    for attempt in range(300):
        g = _G3(seed, split, attempt)
        whs, live, hist = E._versions(g)
        w = dict(seed=seed, split=split, attempt=attempt, whs=whs, n=g.n, fx=g.fx, L=g.L, tz_mixed=g.tz_mixed,
                 withheld=g.withheld, live=live, hist=hist, rseed=f"de3-enc:{split}:{seed}:{attempt}",
                 x_class=x_class(seed, split), ns="de3")
        enc = encode(w, "build")
        f = E.features(enc["truth"])
        ok = (f["out_of_order_keys"] >= 2 and f["late_corrections"] >= 2 and f["backfill_overwrite_traps"] >= 2
              and f["backfill_resurrection_traps"] >= 2 and f["late_telemetry"] >= 2 and f["soft"] >= 1 and f["hard"] >= 1
              and f["dups"] >= 2 and f["float_discounts"] >= 2 and f["renamed_amounts"] >= 2 and f["malformed"] >= 1
              and f["heldout_late_corrections"] >= 1 and f["partition2_keys"] >= 2
              and (w["x_class"] is None or enc["truth"].get("x_realised")))
        if ok and w["x_class"]:
            ok = bool(encode(w, "ops")["truth"].get("x_realised"))
        if ok:
            w["features"] = f
            w["spec"] = spec(w)
            return w
    raise RuntimeError("could not realise every fault class")


def spec(w):
    s = E.spec(w)
    s["project"] = f"de3-{w['split']}-{w['seed']}"
    s["log"]["transactions"] = ("a record carrying txn_id takes effect only if a control record {control: txn_commit, txn_id} "
                                "follows on the same partition; after {control: txn_abort, txn_id} the transaction's records "
                                "never take effect (accounting status aborted); records of an undecided transaction are pending")
    s["log"]["contiguity"] = ("offsets within a partition are contiguous from 0; a segment may become visible later than a "
                              "segment with higher offsets; a consumer must never acknowledge an offset it has not durably "
                              "consumed")
    s["log"]["observations"] = ("log/_obs/tick_NNNN.json is the broker / registry metadata as of tick NNNN: partition "
                                "lifecycle, available segments, log-end and contiguous-available offsets, registry versions, "
                                "transaction states")
    s["accounting"] += "; aborted transaction records are accounted as aborted"
    return s


# ------------------------------------------------------------------------------------------------ withheld hooks
def _clamp(ts, tk, after):
    """An ingest timestamp > `after` inside tick tk."""
    end = E.T0 + tk * E.D - timedelta(seconds=1)
    a = E.datetime.fromisoformat(after.replace("Z", "+00:00"))
    t = E.datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
    return E.iso(min(max(t, a + timedelta(seconds=1)), end))


def _x1(pending, w, r, scenario):
    """X1: 2 committed + 3 aborted transactions on orders_cdc from tick 9. Aborted transactions carry PHANTOM changes (never
    in the truth) whose source_version would win if applied; markers follow on the same partition in the same tick."""
    nt = E.NT[scenario]
    cnt = {}
    for tk, tp, p, rec in pending:
        cnt[(tp, rec.get("msg_id"))] = cnt.get((tp, rec.get("msg_id")), 0) + 1
    by = {}
    for tk, tp, p, rec in pending:
        if (tp == "orders_cdc" and 9 <= tk <= nt - 1 and rec.get("op") == "u" and rec.get("after") and "control" not in rec
                and cnt[(tp, rec["msg_id"])] == 1):
            by.setdefault((tk, p), []).append(rec)
    groups = sorted((k, v) for k, v in by.items() if len(v) >= 2)
    r.shuffle(groups)
    need = {"commit": 2, "abort": 3}
    controls, aborted, tid = [], [], 0
    for (tk, p), recs in groups:
        if not any(need.values()):
            break
        kind = "abort" if need["abort"] and (not need["commit"] or r.random() < 0.6) else "commit"
        need[kind] -= 1
        tid += 1
        txn = f"tx{tk}-{p}-{tid}"
        recs = sorted(recs, key=lambda x: x["ingest_ts"])[:2]
        members = []
        if kind == "commit":
            for m in recs:
                m["txn_id"] = txn
                members.append(m)
        else:
            for j, m in enumerate(recs):
                ph = json.loads(json.dumps(m))
                ph.update(msg_id=f"xa{tid}-{j}", source_version=m["source_version"] + 500000, txn_id=txn,
                          ingest_ts=_clamp(m["ingest_ts"], tk, m["ingest_ts"]))
                for f, v in ph["after"].items():
                    if v in E.BUCKETS:
                        ph["after"][f] = "CANCELLED" if v != "CANCELLED" else "DELIVERED"
                pending.append((tk, "orders_cdc", p, ph))
                members.append(ph)
                aborted.append(dict(tick=tk, part=p, msg_id=ph["msg_id"], key=ph["key"]))
        last = max(m["ingest_ts"] for m in members)
        pending.append((tk, "orders_cdc", p, dict(msg_id=f"txn-{txn}-{kind}", ingest_ts=_clamp(last, tk, last),
                                                  control=f"txn_{kind}", txn_id=txn)))
        controls.append(dict(tick=tk, part=p, kind=kind, txn_id=txn))
    return dict(x_class="X1", txn_controls=controls, aborted=aborted, x_realised=not any(need.values()))


def _x2(pending, w, r, scenario):
    """X2: one orders_cdc segment (tick t0 in 9-10, partition 0 or 1) is published two ticks late while the segment of tick
    t0+1 is published on time: a hole that a consumer must not acknowledge past."""
    nt = E.NT[scenario]
    ticks = {}
    for tk, tp, p, rec in pending:
        if tp == "orders_cdc" and p < 2:
            ticks.setdefault(p, set()).add(tk)
    cands = [(t0, p) for p, ts in sorted(ticks.items()) for t0 in (9, 10) if t0 in ts and t0 + 1 in ts and t0 + 2 <= nt]
    if not cands:
        return dict(x_class="X2", publish_delay=[], x_realised=False)
    t0, p = r.choice(cands)
    return dict(x_class="X2", publish_delay=[[t0, "orders_cdc", p, t0 + 2]], x_realised=True)


# ------------------------------------------------------------------------------------------------ observations
class Obs:
    """Environment-side journal of broker / registry facts; tick files are pure functions of the events with tick <= k."""

    def __init__(self, root):
        self.d = Path(root) / "log" / "_obs"
        self.d.mkdir(parents=True, exist_ok=True)
        self.j = self.d / "journal.log"

    def event(self, **e):
        with open(self.j, "a") as fh:
            fh.write(json.dumps(e, sort_keys=True) + "\n")

    def events(self):
        return [json.loads(l) for l in self.j.read_text().splitlines()] if self.j.exists() else []

    def materialize(self, k):
        parts, segs, regs, txns, deleted = {}, [], [], {}, set()
        for e in self.events():
            if e["tick"] > k:
                continue
            key = f"{e.get('topic')}/{e.get('part')}"
            if e["ev"] == "partition_created":
                parts.setdefault(key, dict(topic=e["topic"], part=e["part"], created=e["tick"], state="open"))
            elif e["ev"] == "partition_state":
                parts[key]["state"] = e["state"]
            elif e["ev"] == "segment":
                segs.append(dict(topic=e["topic"], part=e["part"], base=e["base"], end=e["end"], tick=e["rtick"], pub=e["tick"],
                                 expires=e["rtick"] + KEEP))
            elif e["ev"] == "segment_deleted":
                deleted.add((e["topic"], e["part"], e["base"]))
            elif e["ev"] == "schema":
                regs.append(dict(subject=e["subject"], version=e["version"], offset=e["offset"], tick=e["tick"]))
            elif e["ev"] == "txn_record":
                t = txns.setdefault(e["txn_id"], dict(topic=e["topic"], part=e["part"], offsets=[], status="open"))
                t["offsets"].append(e["offset"])
            elif e["ev"] == "txn_marker":
                txns.setdefault(e["txn_id"], dict(topic=e["topic"], part=e["part"], offsets=[], status="open"))
                txns[e["txn_id"]].update(status=e["kind"] + "ted" if e["kind"] == "commit" else "aborted", marker=e["offset"])
        for s in segs:
            s["available"] = s["pub"] <= k < s["expires"] and (s["topic"], s["part"], s["base"]) not in deleted
        ends = {}
        for key, pinfo in parts.items():
            ss = sorted((s for s in segs if f"{s['topic']}/{s['part']}" == key), key=lambda s: s["base"])
            c = 0
            for s in ss:
                if s["base"] > c:
                    break
                c = max(c, s["end"])
            ends[key] = dict(log_end=max([s["end"] for s in ss] + [0]), contiguous_end=c)
        out = dict(tick=k, partitions=sorted(parts.values(), key=lambda p: (p["topic"], p["part"])),
                   segments=sorted(segs, key=lambda s: (s["topic"], s["part"], s["base"])), offsets=ends,
                   registry=sorted(regs, key=lambda x: (x["subject"], x["version"])),
                   txns={t: dict(v, offsets=sorted(v["offsets"])) for t, v in sorted(txns.items())})
        (self.d / f"tick_{k:04d}.json").write_text(json.dumps(out, sort_keys=True))
        return out


def _provision(enc, root, obs):
    for k in sorted({k for v in enc["log"].values() for k in v}):
        if not (k[0] == "orders_cdc" and k[1] >= 2):
            d = Path(root) / "log" / k[0] / f"p{k[1]}"
            if not d.exists():
                d.mkdir(parents=True)
                obs.event(ev="partition_created", topic=k[0], part=k[1], tick=1)


def publish_tick(enc, t):
    """Segments published at tick t: [(record_tick, (topic, part), recs)]."""
    delay = {(a, b, c): d for a, b, c, d in enc["truth"].get("publish_delay", [])}
    out = []
    for tk in range(1, t + 1):
        for k, recs in sorted(enc["log"].get(tk, {}).items()):
            if delay.get((tk,) + tuple(k), tk) == t:
                out.append((tk, k, sorted(recs, key=lambda x: x["offset"])))
    return out


def write_segment(root, topic, part, recs, rtick, t, obs):
    d = Path(root) / "log" / topic / f"p{part}"
    if not d.exists():
        d.mkdir(parents=True)
        obs.event(ev="partition_created", topic=topic, part=part, tick=t)
    lines = []
    for x in recs:
        if x.get("_poison"):
            lines.append('{"msg_id": "' + x["msg_id"] + '", "ingest_ts": "' + x["ingest_ts"] + '", "order_id": ' +
                         str(x["order_id"]) + ', "type": "DELIV')
        else:
            lines.append(json.dumps({k: v for k, v in x.items() if not k.startswith("_")}, sort_keys=True))
    was = stat.S_IMODE(os.stat(d).st_mode)
    if not was & stat.S_IWUSR:
        os.chmod(d, 0o755)
    (d / f"{recs[0]['offset']:08d}.jsonl").write_text("\n".join(lines) + "\n")
    if not was & stat.S_IWUSR:
        os.chmod(d, was)
    obs.event(ev="segment", topic=topic, part=part, base=recs[0]["offset"], end=recs[-1]["offset"] + 1, rtick=rtick, tick=t,
              n=len(recs))
    for x in recs:
        if topic == "_schemas":
            obs.event(ev="schema", subject=x.get("subject", "orders"), version=x["version"], offset=x["offset"], tick=t)
        elif x.get("txn_id") and "control" not in x:
            obs.event(ev="txn_record", txn_id=x["txn_id"], topic=topic, part=part, offset=x["offset"], tick=t)
        elif str(x.get("control", "")).startswith("txn_"):
            obs.event(ev="txn_marker", txn_id=x["txn_id"], topic=topic, part=part, kind=x["control"][4:], offset=x["offset"],
                      tick=t)


def write_tick(enc, root, t):
    obs = Obs(root)
    if t == 1:
        _provision(enc, root, obs)
    for rtick, (topic, part), recs in publish_tick(enc, t):
        write_segment(root, topic, part, recs, rtick, t, obs)
    return obs


def retention(root, tick, keep=KEEP):
    """Delete segments of record tick <= tick - keep (the journal knows each segment's record tick); journal + materialise."""
    obs = Obs(root)
    for e in obs.events():
        if e["ev"] == "segment" and e["rtick"] <= tick - keep:
            f = Path(root) / "log" / e["topic"] / f"p{e['part']}" / f"{e['base']:08d}.jsonl"
            if f.exists():
                d = f.parent
                was = stat.S_IMODE(os.stat(d).st_mode)
                os.chmod(d, 0o755)
                f.unlink()
                os.chmod(d, was)
                obs.event(ev="segment_deleted", topic=e["topic"], part=e["part"], base=e["base"], tick=tick)
    return obs.materialize(tick)


def write_log(enc, root, upto, start=1, archive=False):
    """Evaluator / build writer: ticks start..upto, one tick at a time (publication delays honoured). archive=True keeps
    every published segment (the engineer's visible log); otherwise retention runs each tick (a live log)."""
    for t in range(start, upto + 1):
        obs = write_tick(enc, root, t)
        if archive:
            obs.materialize(t)
        else:
            retention(root, t)


def retention_fn(root, tick):
    """For s4_evaluator.run_protocol: retention is already applied per tick by write_log; re-materialising is idempotent."""
    return retention(root, tick)


def append_records(root, topic, part, recs, start_offset, t):
    """Re-snapshot records appended by the source mid-tick (journalled like any publication)."""
    for i, x in enumerate(recs):
        x["offset"] = start_offset + i
    obs = Obs(root)
    write_segment(root, topic, part, recs, t, t, obs)
    obs.materialize(t)


def partition_states(root, t):
    """Journal availability changes the environment made (e.g. an unreadable partition during an incident)."""
    obs = Obs(root)
    cur = {f"{p['topic']}/{p['part']}": p["state"] for p in (obs.materialize(t)["partitions"])}
    for d in sorted(Path(root, "log").glob("*/p*")):
        if d.parent.name == "_obs":
            continue
        key = f"{d.parent.name}/{d.name[1:]}"
        st = "open" if os.access(d, os.R_OK) else "unavailable"
        if key in cur and cur[key] != st:
            obs.event(ev="partition_state", topic=d.parent.name, part=int(d.name[1:]), state=st, tick=t)
    return obs.materialize(t)


# ------------------------------------------------------------------------------------------------ ops worlds
def schedule(seed, split):
    r = random.Random(f"de3-incidents:{split}:{seed}")
    names = r.sample(SEEN_OPS, 2 if split == "test" else 3)
    ticks = sorted(r.sample(range(8, 14), len(names)))
    if "snapshot_interrupted" in names:
        i = names.index("snapshot_interrupted")
        names[i], names[0] = names[0], names[i]
    return [(n, t) for n, t in zip(names, ticks)]


def ops_world(w, split, seed, forced=None):
    r = random.Random(f"de3-ops:{split}:{seed}")
    incs = [I.CLASSES[n](t, r) for n, t in (forced or schedule(seed, split))]
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
    return enc, incs
