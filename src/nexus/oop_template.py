"""OOP-track pipeline generator (NOT LOCKED). The R2 consumer (r2_template, unchanged) with 8 of its 18 author-written switches
REMOVED and replaced by code NEXUS synthesises from primitives (oop_synthesizer) and inlines into pipeline.py:

  hole         replaces the switches                       synthesised artefact
  syn_decode   schema_handling, discount_unit               def fn_<id>(a, fields, types) -> canonical orders row (dict)
  syn_net      fx                                           def fn_<id>(p, fx) -> net amount
  syn_status   malformed, fx_unknown                        def fn_<id>(topic, rec, row, fx, whs) -> class label
  syn_silver   apply_order, backfill_merge, deletes         class StreamOrganelle_<id> (ingest / retract / flush), only when a
                                                            Markov state violation is found; else a pure filter
The 10 remaining switches (commit_protocol, dedup, ts_parse, ts_format, gold_maintenance, lateness, partition_discovery,
snapshots, txn_isolation, gap_handling) are infrastructure / time semantics and stay author-written template decisions in
Phase 1 (disclosed). A hole's options are the ids of the programs synthesised so far (PROG); emit() inlines the chosen
programs, the helper defs found by anti-unification across them, and aliases fn_decode / fn_net / fn_status /
SilverOrganelle. Exact, asserted text patches of r2_template.SRC; no removed decision is referenced afterwards."""
from __future__ import annotations

import json

from nexus import oop_synthesizer as S
from nexus import r2_template as RT2

SYNTH_HOLES = ("syn_decode", "syn_net", "syn_status", "syn_silver")
REMOVED = ("schema_handling", "discount_unit", "fx", "fx_unknown", "malformed", "apply_order", "backfill_merge", "deletes")
OLD2HOLE = {"schema_handling": "syn_decode", "discount_unit": "syn_decode", "fx": "syn_net", "fx_unknown": "syn_status",
            "malformed": "syn_status", "apply_order": "syn_silver", "backfill_merge": "syn_silver", "deletes": "syn_silver"}
ARGS = {"syn_decode": ["a", "fields", "types"], "syn_net": ["p", "fx"], "syn_status": ["topic", "rec", "row", "fx", "whs"]}
ALIAS = {"syn_decode": "fn_decode", "syn_net": "fn_net", "syn_status": "fn_status"}
ROW_FIELDS = ["order_id", "warehouse_id", "status", "amount", "currency", "discount", "promised_ts", "deleted"]

PROG = {h: {} for h in SYNTH_HOLES}            # hole -> {program id: dict(kind, node | spec)}
DECISIONS = {d: o for d, o in RT2.DECISIONS.items() if d not in REMOVED}
DECISIONS.update({h: [] for h in SYNTH_HOLES})
STAGE_OF = {d: s for d, s in RT2.STAGE_OF.items() if d not in REMOVED}
STAGE_OF.update(syn_decode="decode", syn_net="silver", syn_status="ingest", syn_silver="silver")
CORRECT = {d: o for d, o in RT2.CORRECT.items() if d not in REMOVED}
DEPLOY_DEFAULT = RT2.DEPLOY_DEFAULT
config_from_spec = RT2.config_from_spec


def reset():
    for h in SYNTH_HOLES:
        PROG[h].clear()
        DECISIONS[h] = []


def snapshot():
    return {h: dict(PROG[h]) for h in SYNTH_HOLES}


def restore(snap):
    """Programs synthesised in one ops run never leak into another run of the same project."""
    for h in SYNTH_HOLES:
        PROG[h].clear()
        PROG[h].update(snap[h])
        DECISIONS[h] = list(snap[h])


def register(hole, prog):
    """Adds a synthesised program as a new option of its hole; returns its id (content hash)."""
    pid = "p" + S.node_id(prog)
    if pid not in PROG[hole]:
        PROG[hole][pid] = prog
        DECISIONS[hole].append(pid)
    return pid


def remap(names):
    out = []
    for d in names:
        d = OLD2HOLE.get(d, d)
        if d in DECISIONS and d not in out:
            out.append(d)
    return out


def _body(src_, start, end):
    i = src_.index(start)
    j = src_.index(end, i)
    return i, j


PATCHES = [
    ("""class StageError(Exception):
    pass
""", """class StageError(Exception):
    pass


# ---------------------------------------------------------------- code written by NEXUS (synthesised; not author-written)
{SYNTH}
# ---------------------------------------------------------------- end of synthesised code
"""),
    ("""                soft = 1 if row and row["deleted"] else 0
                if DEC["fx_unknown"] == "quarantine" and row and row.get("currency") not in cfg["fx"]:
                    status = "unknown_currency"
                elif DEC["txn_isolation"] == "read_committed" and rec.get("txn_id"):""",
     """                soft = 1 if row and row.get("deleted") else 0
                try:
                    lab = fn_status(topic, rec, row, cfg["fx"], cfg["warehouses"])
                except Exception as e:
                    raise StageError(f"stage=ingest status topic={topic} part={part} offset={o}: {type(e).__name__} {e}")
                if lab != "accepted":
                    status = lab
                elif DEC["txn_isolation"] == "read_committed" and rec.get("txn_id"):"""),
    ("""            elif topic == "manifests":
                try:
                    kg = float(rec["weight"])
                except (TypeError, ValueError):
                    kg = None
                if kg is None:
                    status = "malformed" if DEC["malformed"] == "quarantine" else "dropped"
                else:""",
     """            elif topic == "manifests":
                try:
                    lab = fn_status(topic, rec, None, cfg["fx"], cfg["warehouses"])
                    kg = float(rec["weight"]) if lab == "accepted" else None
                except Exception as e:
                    raise StageError(f"stage=ingest status topic={topic} part={part} offset={o}: {type(e).__name__} {e}")
                if kg is None:
                    status = lab
                else:"""),
    ("""    con.execute("CREATE TABLE quarantine AS SELECT topic, msg_id, CASE status WHEN 'malformed' THEN 'malformed_weight' "
                "WHEN 'future' THEN 'future_event' WHEN 'unknown_currency' THEN 'unknown_currency' ELSE 'poison' END AS reason "
                "FROM _consumed WHERE status IN ('malformed', 'future', 'poison', 'unknown_currency')")""",
     """    con.execute("CREATE TABLE quarantine AS SELECT topic, msg_id, CASE WHEN status = 'malformed' THEN 'malformed_weight' "
                "WHEN status = 'future' THEN 'future_event' WHEN status LIKE 'q:%' THEN substr(status, 3) ELSE status END AS reason "
                "FROM _consumed WHERE status IN ('malformed', 'future', 'poison', 'unknown_currency') OR status LIKE 'q:%'")"""),
]

DECODE_NEW = '''def decode_payload(con, rec, cfg):
    reg = registry(con, "orders", rec.get("schema_version", 1), None)
    if reg is None:
        reg = {"fields": cfg["v1"], "types": {"discount": "int"}}
    a = rec.get("after")
    if a is None:
        return None, reg
    return fn_decode(a, reg["fields"], reg.get("types", {})), reg


'''
BUILD_NEW = '''def build(con, cfg):
    rows = con.execute("SELECT msg_id, key, sv, op, payload, soft, source, seq FROM bronze_orders ORDER BY seq").fetchall()
    org = SilverOrganelle()
    for r in rows[:1000000]:
        org.ingest({"msg_id": r[0], "key": r[1], "sv": r[2], "op": r[3], "payload": json.loads(r[4]), "soft": r[5],
                    "source": r[6], "seq": r[7]})
    out = []
    for r in org.flush():
        p = r["payload"]
        out.append((r["key"], p["warehouse_id"], p["status"], fn_net(p, cfg["fx"]), p["promised_ts"]))
'''


def _src():
    s = RT2.SRC
    for a, b in PATCHES:
        if s.count(a) != 1:
            raise RuntimeError(f"OOP template patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    i, j = _body(s, "def decode_payload(con, rec, cfg):\n", "def ingest(con, log, st, cfg, tick):\n")
    s = s[:i] + DECODE_NEW + s[j:]
    i, j = _body(s, "def build(con, cfg):\n", "    prev = {r[0]: r for r in con.execute(")
    s = s[:i] + BUILD_NEW + s[j:]
    for d in REMOVED:
        if f'DEC["{d}"]' in s:
            raise RuntimeError(f"removed decision {d} still referenced")
    return s


SRC = _src()


def synth_code(choice):
    """The inlined code block for the chosen programs: anti-unified helper defs, one def per function hole, the class."""
    progs = {}
    for h in ("syn_decode", "syn_net", "syn_status"):
        p = PROG[h][choice[h]]
        if h == "syn_decode":
            for f in ROW_FIELDS:
                progs[f"{h}.{f}"] = p["fields"][f]
        else:
            progs[h] = p["node"]
    rw, defs = S.anti_unify(progs)
    parts = [S.def_source(fid, params, body) for fid, params, body in defs]
    for h in ("syn_decode", "syn_net", "syn_status"):
        fid = "fn_" + choice[h][1:]
        if h == "syn_decode":
            parts.append(S.function_source(fid, ARGS[h], {f: rw[f"{h}.{f}"] for f in ROW_FIELDS}, ROW_FIELDS))
        else:
            parts.append(S.function_source(fid, ARGS[h], rw[h]))
        parts.append(f"{ALIAS[h]} = {fid}\n")
    sp = PROG["syn_silver"][choice["syn_silver"]]
    cid = choice["syn_silver"][1:]
    parts.append(S.organelle_source(cid, sp["spec"]))
    parts.append(f"SilverOrganelle = StreamOrganelle_{cid}\n")
    return "\n\n".join(parts)


def emit(choice):
    missing = set(DECISIONS) - set(choice)
    if missing:
        raise ValueError(f"missing decisions {sorted(missing)}")
    for k, v in choice.items():
        if k in DECISIONS and v not in DECISIONS[k]:
            raise ValueError(f"{k}={v} not an option")
    dec = {k: choice[k] for k in DECISIONS if k not in SYNTH_HOLES}
    return SRC.replace("{DECISIONS}", json.dumps(dec, sort_keys=True)).replace("{SYNTH}", synth_code(choice))
