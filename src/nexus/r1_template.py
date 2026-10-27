"""R1 pipeline generator (NOT LOCKED): the Stage 4 template (s4_template, unchanged) plus two decisions for rules every R1
spec declares:
  txn_isolation   read_uncommitted (apply transactional records at once) | read_committed (hold records carrying txn_id in
                  a durable pending table until txn_commit; on txn_abort mark them aborted, never apply)
  gap_handling    skip (read every visible segment at or past the committed offset - the Stage 4 behaviour) |
                  wait_contiguous (stop at the first offset hole; never acknowledge past it)
Control records other than snapshot controls are consumed with status 'control' (accounted as applied, never bronze rows).
The source is produced by exact, asserted text patches of s4_template.SRC, so every other line is the Stage 4 consumer."""
from __future__ import annotations

import json

from nexus import s4_template as T

DECISIONS = dict(T.DECISIONS, txn_isolation=["read_uncommitted", "read_committed"], gap_handling=["skip", "wait_contiguous"])
CORRECT = dict(T.CORRECT, txn_isolation={"read_committed"}, gap_handling={"wait_contiguous"})
STAGE_OF = dict(T.STAGE_OF, txn_isolation="ingest", gap_handling="read")
DEPLOY_DEFAULT = T.DEPLOY_DEFAULT
config_from_spec = T.config_from_spec

PATCHES = [
    # durable pending table for undecided transactions
    ("CREATE TABLE IF NOT EXISTS _rev_acc (warehouse_id TEXT PRIMARY KEY, revenue REAL);\n",
     "CREATE TABLE IF NOT EXISTS _rev_acc (warehouse_id TEXT PRIMARY KEY, revenue REAL);\n"
     "CREATE TABLE IF NOT EXISTS _txn_pending (txn_id TEXT, msg_id TEXT, key INTEGER, sv INTEGER, op TEXT, payload TEXT,\n"
     "                                         soft INTEGER, source TEXT, tick INTEGER, part INTEGER, offset INTEGER);\n"),
    # gap handling in the segment reader
    ("""def read_new(log, topic, part, start, limit):
    out = []
    for f in sorted(glob.glob(os.path.join(log, topic, f"p{part}", "*.jsonl"))):
        base = int(os.path.basename(f).split(".")[0])
        with open(f) as fh:
            lines = fh.read().split("\\n")
        for i, line in enumerate(lines):""",
     """def read_new(log, topic, part, start, limit):
    out = []
    nxt = start
    for f in sorted(glob.glob(os.path.join(log, topic, f"p{part}", "*.jsonl")), key=lambda f: int(os.path.basename(f).split(".")[0])):
        base = int(os.path.basename(f).split(".")[0])
        with open(f) as fh:
            lines = fh.read().split("\\n")
        if DEC["gap_handling"] == "wait_contiguous":
            n = len(lines) - (1 if lines and lines[-1] == "" else 0)
            if base + n <= nxt:
                continue
            if base > nxt:
                return out                     # an offset hole: wait for it, never acknowledge past it
        for i, line in enumerate(lines):"""),
    ("""            if limit is not None and len(out) >= limit:
                return out
            out.append((off, line))""",
     """            if limit is not None and len(out) >= limit:
                return out
            out.append((off, line))
            nxt = off + 1"""),
    # transaction markers + pending records
    ("""            elif "control" in rec:
                con.execute("INSERT OR REPLACE INTO snapshot_ctl VALUES (?,?)", (mid, json.dumps(rec)))""",
     """            elif "control" in rec:
                con.execute("INSERT OR REPLACE INTO snapshot_ctl VALUES (?,?)", (mid, json.dumps(rec)))
                if not str(rec["control"]).startswith("snapshot"):
                    status = "control"
                if DEC["txn_isolation"] == "read_committed" and rec["control"] in ("txn_commit", "txn_abort"):
                    pend = con.execute("SELECT msg_id, key, sv, op, payload, soft, source, tick, part, offset FROM _txn_pending "
                                       "WHERE txn_id=? ORDER BY offset", (rec["txn_id"],)).fetchall()
                    for p_mid, p_key, p_sv, p_op, p_pay, p_soft, p_src, p_tick, p_part, p_off in pend:
                        if rec["control"] == "txn_commit":
                            seq += 1
                            con.execute(f"{verb} INTO bronze_orders VALUES (?,?,?,?,?,?,?,?,?)",
                                        (p_mid, p_key, p_sv, p_op, p_pay, p_soft, p_src, p_tick, seq))
                        con.execute("UPDATE _consumed SET status=? WHERE topic=? AND part=? AND offset=?",
                                    ("applied" if rec["control"] == "txn_commit" else "aborted", p_src, p_part, p_off))
                    con.execute("DELETE FROM _txn_pending WHERE txn_id=?", (rec["txn_id"],))"""),
    ("""                soft = 1 if row and row["deleted"] else 0
                seq += 1
                con.execute(f"{verb} INTO bronze_orders VALUES (?,?,?,?,?,?,?,?,?)",
                            (mid, rec["key"], rec["source_version"], rec["op"], json.dumps(row), soft, topic, rt, seq))""",
     """                soft = 1 if row and row["deleted"] else 0
                if DEC["txn_isolation"] == "read_committed" and rec.get("txn_id"):
                    con.execute("INSERT INTO _txn_pending VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                (rec["txn_id"], mid, rec["key"], rec["source_version"], rec["op"], json.dumps(row), soft, topic,
                                 rt, part, o))
                    status = "pending"
                else:
                    seq += 1
                    con.execute(f"{verb} INTO bronze_orders VALUES (?,?,?,?,?,?,?,?,?)",
                                (mid, rec["key"], rec["source_version"], rec["op"], json.dumps(row), soft, topic, rt, seq))"""),
    # accounting statuses
    ("""        st = {"applied": "applied", "dup": "duplicate", "dropped": "dropped"}.get(status, "quarantined")""",
     """        st = {"applied": "applied", "dup": "duplicate", "dropped": "dropped", "control": "applied", "aborted": "aborted",
              "pending": "pending"}.get(status, "quarantined")"""),
]


def _src():
    s = T.SRC
    for a, b in PATCHES:
        if s.count(a) != 1:
            raise RuntimeError(f"R1 template patch anchor not found exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    return s


SRC = _src()


def correct_choice():
    return {d: sorted(CORRECT[d])[-1] for d in DECISIONS}


def emit(choice):
    missing = set(DECISIONS) - set(choice)
    if missing:
        raise ValueError(f"missing decisions {sorted(missing)}")
    for k, v in choice.items():
        if v not in DECISIONS[k]:
            raise ValueError(f"{k}={v} not an option")
    return SRC.replace("{DECISIONS}", json.dumps({k: choice[k] for k in DECISIONS}, sort_keys=True))
