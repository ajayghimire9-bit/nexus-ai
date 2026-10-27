"""R1 independent observation-conformance monitor (NOT LOCKED). Standard library only; imports nothing from NEXUS, the replay
helper, the checks, the template or the environment. It reads the AUTHORITATIVE observation of ONE tick k
(log/_obs/tick_k.json, written by the environment) and the object under test, never a later observation, a fault label or the
data generator.

check_view(view_log, obs)       a replayed / live log directory as a consumer would see it at tick k
    partition_early         a partition directory the observation does not list as created by k
    partition_missing       an observed, open partition absent from the view
    partition_unavailable_exposed  readable segments of a partition the observation marks unavailable at k
    segment_missing         a segment observed as available at k absent from the view
    segment_unobserved      a segment in the view that is not published by k (future) or never existed
    segment_retained_wrongly a segment in the view that the observation says has expired by k
    order_violation         a view segment whose records' offsets / count differ from the observed segment
    schema_future           a registry record, or a record naming a schema version, not registered by k
check_consumer(state, obs)      a consumer's durable state after a run (or after a crash) at tick k
    ack_beyond_available    committed offset beyond the observed contiguous-available end of the partition
    ack_beyond_durable      an offset below the committed offset with no durable consumption record
    txn_effect_violation    a record of an aborted or still-open transaction recorded as applied"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


def load_obs(log, k):
    f = Path(log) / "_obs" / f"tick_{k:04d}.json"
    return json.loads(f.read_text())


def _view_segments(view):
    segs, parts = {}, set()
    for d in sorted(Path(view).glob("*/p*")):
        if d.parent.name == "_obs" or not d.is_dir():
            continue
        key = (d.parent.name, int(d.name[1:]))
        parts.add(key)
        if not os.access(d, os.R_OK):
            continue
        for f in sorted(d.glob("*.jsonl")):
            lines = [l for l in f.read_text().split("\n") if l]
            segs[key + (int(f.stem),)] = lines
    return parts, segs


def check_view(view, obs):
    k = obs["tick"]
    out = []
    op = {(p["topic"], p["part"]): p for p in obs["partitions"]}
    parts, segs = _view_segments(view)
    for key in sorted(parts - set(op)):
        out.append(dict(kind="partition_early", where=f"{key[0]}/p{key[1]}", tick=k))
    for key in sorted(set(op) - parts):
        if op[key]["state"] == "open":
            out.append(dict(kind="partition_missing", where=f"{key[0]}/p{key[1]}", tick=k))
    for key in sorted(parts & set(op)):
        if op[key]["state"] != "open" and any(sk[:2] == key for sk in segs):
            out.append(dict(kind="partition_unavailable_exposed", where=f"{key[0]}/p{key[1]}", tick=k))
    oseg = {(s["topic"], s["part"], s["base"]): s for s in obs["segments"]}
    for key, s in sorted(oseg.items()):
        if s["available"] and key not in segs and (key[0], key[1]) in parts:
            out.append(dict(kind="segment_missing", where=f"{key[0]}/p{key[1]}@{key[2]}", tick=k))
    reg = {(r["subject"], r["version"]) for r in obs["registry"]}
    for key, lines in sorted(segs.items()):
        s = oseg.get(key)
        where = f"{key[0]}/p{key[1]}@{key[2]}"
        if s is None:
            out.append(dict(kind="segment_unobserved", where=where, tick=k))
            continue
        if not s["available"]:
            out.append(dict(kind="segment_retained_wrongly" if s["pub"] <= k else "segment_unobserved", where=where, tick=k))
            continue
        offs = []
        for l in lines:
            try:
                offs.append(json.loads(l).get("offset"))
            except ValueError:
                offs.append(None)                      # an undecodable line keeps its position; its offset is positional
        want = list(range(s["base"], s["end"]))
        if len(lines) != len(want) or any(o is not None and o != w for o, w in zip(offs, want)):
            out.append(dict(kind="order_violation", where=where, tick=k))
        for l in lines:
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if key[0] == "_schemas" and (x.get("subject", "orders"), x.get("version")) not in reg:
                out.append(dict(kind="schema_future", where=where, detail=f"registry {x.get('subject')} v{x.get('version')}", tick=k))
            elif key[0] in ("orders_cdc", "backfill_orders", "telemetry") and "schema_version" in x and "control" not in x:
                subj = "telemetry" if key[0] == "telemetry" else "orders"
                if (subj, x["schema_version"]) not in reg:
                    out.append(dict(kind="schema_future", where=where, detail=f"record names {subj} v{x['schema_version']}", tick=k))
                    break
    return out


def _committed(st):
    st = Path(st)
    if (st / "offsets.json").exists():
        try:
            return {(t, int(p)): n for t, p, n in json.loads((st / "offsets.json").read_text())["off"]}
        except (ValueError, KeyError):
            return {}
    if (st / "lake.db").exists():
        try:
            con = sqlite3.connect(f"file:{st / 'lake.db'}?mode=ro", uri=True)
            rows = con.execute("SELECT topic, part, next FROM _offsets").fetchall()
            con.close()
            return {(t, p): n for t, p, n in rows}
        except sqlite3.Error:
            return {}
    return {}


def _consumed(st):
    db = Path(st) / "lake.db"
    if not db.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("SELECT topic, part, offset, status FROM _consumed").fetchall()
        con.close()
    except sqlite3.Error:
        return {}
    return {(t, p, o): s for t, p, o, s in rows}


def check_consumer(st, obs):
    k = obs["tick"]
    out = []
    com, cons = _committed(st), _consumed(st)
    for (t, p), n in sorted(com.items()):
        o = obs["offsets"].get(f"{t}/{p}")
        if o is not None and n > o["contiguous_end"]:
            out.append(dict(kind="ack_beyond_available", where=f"{t}/p{p}", detail=f"committed {n} > contiguous {o['contiguous_end']}",
                            tick=k))
        missing = [x for x in range(n) if (t, p, x) not in cons]
        if missing:
            out.append(dict(kind="ack_beyond_durable", where=f"{t}/p{p}", detail=f"{len(missing)} offsets below {n} not durably "
                                                                                  f"consumed (first {missing[0]})", tick=k))
    for txn, v in obs.get("txns", {}).items():
        if v["status"] == "committed":
            continue
        bad = [o for o in v["offsets"] if cons.get((v["topic"], v["part"], o)) == "applied"]
        if bad:
            out.append(dict(kind="txn_effect_violation", where=f"{v['topic']}/p{v['part']}", detail=f"{v['status']} txn {txn}: "
                                                                                                  f"{len(bad)} records applied", tick=k))
    return out
