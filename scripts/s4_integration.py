"""Stage 4 REAL integration (NOT LOCKED). Runs with the separate venv /Users/ajayghimire/.claude-worktrees/venv-s456
(deltalake 1.6.6, psycopg 3.3.6, pyarrow 26.0.0); local PostgreSQL 14.18; no network service, no paid service.

Real components
  * source database      a throw-away local PostgreSQL 14 cluster (initdb, wal_level=logical)
  * CDC                  a logical replication slot with the built-in test_decoding plugin (log-based CDC from the WAL;
                         Debezium uses pgoutput/decoderbufs over the same slot mechanism - Debezium itself is NOT used)
  * source checkpoint    the replication slot's confirmed position (durable in PostgreSQL); advanced only after the sink
                         commit, and only to an OLDER batch (delayed acknowledgement window) so a rollback can re-read
  * lakehouse table      a Delta Lake table (delta-rs) on local disk: ACID commits, optimistic concurrency, time travel
  * crashes              real SIGKILL of the consumer process (phase-boundary kills + random-time kills + kill during recovery)
Contract: per key, the change with the higher SOURCE ROW VERSION wins (MERGE ... WHEN MATCHED AND target.ver < source.ver).
row_version is stamped by a trigger from a sequence on every insert / update (row locks serialise changes to a key, so the
order per key is exact); REPLICA IDENTITY FULL makes a delete carry the old row, and its tombstone gets version 2v+1 (above
its own row, below any later change 2w, w > v). A concurrent backfill (REPEATABLE READ snapshot) writes each row with its own
row_version through the same rule. (A first version tagged changes with WAL record LSNs and snapshot rows with
pg_current_wal_lsn(); seed 1 exposed the race: a DELETE whose record precedes the snapshot LSN but commits after it lost to the
snapshot row and was revived. Record LSN order is not commit order.)
Rollback: DeltaTable.restore(v) is one atomic table commit; the slot position cannot move back, so recovery is COORDINATED:
the delayed acknowledgement keeps the changes after v in the slot and the idempotent version-guarded MERGE replays them.
The atomicity boundary is the single Delta commit; this is not a global atomic rollback across database + lake.
Oracle: the final non-deleted Delta rows must equal `SELECT * FROM orders` in PostgreSQL (and no duplicate keys)."""
import json, os, random, re, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

PG_BIN = "/opt/homebrew/bin"
PORT = 55437


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


class PG:
    def __init__(self, root):
        self.root = Path(root)
        self.data, self.sock = self.root / "pgdata", self.root / "sock"
        self.sock.mkdir(parents=True, exist_ok=True)
        r = sh(f"{PG_BIN}/initdb", "-D", str(self.data), "-U", "nexus", "--auth=trust", "-E", "UTF8")
        assert r.returncode == 0, r.stderr
        with open(self.data / "postgresql.conf", "a") as f:
            f.write(f"\nwal_level = logical\nmax_replication_slots = 4\nmax_wal_senders = 4\nport = {PORT}\n"
                    f"unix_socket_directories = '{self.sock}'\nlisten_addresses = ''\nfsync = on\n")
        r = sh(f"{PG_BIN}/pg_ctl", "-D", str(self.data), "-l", str(self.root / "pg.log"), "-w", "start")
        assert r.returncode == 0, r.stderr + (self.root / "pg.log").read_text()[-500:]
        self.dsn = f"host={self.sock} port={PORT} user=nexus dbname=postgres"

    def stop(self):
        sh(f"{PG_BIN}/pg_ctl", "-D", str(self.data), "-m", "fast", "stop")


CONSUMER = r'''
import json, os, re, sys, time
import psycopg, pyarrow as pa
from deltalake import DeltaTable, write_deltalake, CommitProperties, Transaction
from deltalake.exceptions import CommitFailedError
DSN, LAKE, MODE = sys.argv[1], sys.argv[2], sys.argv[3]          # MODE: live | backfill
BAD = os.environ.get("NEXUS_BAD_DEPLOY") == "1"
PAUSE = os.environ.get("NEXUS_PHASES") == "1"
ACK_LAG = int(os.environ.get("NEXUS_ACK_LAG", "3"))
SCHEMA = pa.schema([("id", pa.int64()), ("warehouse", pa.string()), ("status", pa.string()), ("amount", pa.float64()),
                    ("deleted", pa.bool_()), ("ver", pa.int64()), ("lsn", pa.int64()), ("source", pa.string())])
FIELD = re.compile(r"(\w+)\[[^\]]+\]:('(?:[^']|'')*'|\S+)")


def phase(p):
    if PAUSE:
        print("PHASE " + p, flush=True); time.sleep(0.15)


def lsn_int(s):
    a, b = s.split("/"); return (int(a, 16) << 32) | int(b, 16)


def merge(rows, app):
    batch = pa.Table.from_pylist(rows, schema=SCHEMA)
    for attempt in range(20):
        try:
            dt = DeltaTable(LAKE)
            (dt.merge(batch, predicate="t.id = s.id", source_alias="s", target_alias="t",
                      commit_properties=CommitProperties(app_transactions=[Transaction(app, max(r["lsn"] for r in rows))]))
               .when_matched_update_all(predicate="t.ver < s.ver").when_not_matched_insert_all().execute())
            return
        except CommitFailedError:
            time.sleep(0.05 * (attempt + 1))
    raise RuntimeError("merge kept conflicting")


def parse(data, lsn):
    m = re.match(r"table public\.orders: (INSERT|UPDATE|DELETE): (.*)", data)
    if not m:
        return None
    f = {k: (v[1:-1].replace("''", "'") if v.startswith("'") else v) for k, v in FIELD.findall(m.group(2))}
    rv = int(f["row_version"])
    if m.group(1) == "DELETE":                       # REPLICA IDENTITY FULL: the old row (and its version) is in the event
        return dict(id=int(f["id"]), warehouse=None, status=None, amount=None, deleted=True, ver=2 * rv + 1, lsn=lsn, source="live")
    amt = float(f["amount"]) * (10 if BAD else 1)
    return dict(id=int(f["id"]), warehouse=f["warehouse"], status=f["status"], amount=amt, deleted=f["deleted"] == "true",
                ver=2 * rv, lsn=lsn, source="live")


if not DeltaTable.is_deltatable(LAKE):
    try:
        write_deltalake(LAKE, pa.Table.from_pylist([], schema=SCHEMA), mode="append")
    except Exception:
        pass
con = psycopg.connect(DSN, autocommit=True)
if MODE == "backfill":
    with psycopg.connect(DSN) as c2:
        c2.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
        snap = lsn_int(c2.execute("SELECT pg_current_wal_lsn()::text").fetchone()[0])
        rows = c2.execute("SELECT id, warehouse, status, amount::float8, deleted, row_version FROM orders ORDER BY id").fetchall()
        c2.execute("COMMIT")
    for i in range(0, len(rows), 25):                        # slow, concurrent with live changes
        chunk = [dict(id=r[0], warehouse=r[1], status=r[2], amount=r[3], deleted=r[4], ver=2 * r[5], lsn=snap, source="backfill")
                 for r in rows[i:i + 25]]
        merge(chunk, "nexus-backfill")
        time.sleep(0.2)
    print("BACKFILL_DONE", len(rows), flush=True)
    sys.exit(0)
idle = 0
acked, cursor = [], None          # cursor = last processed COMMIT lsn (commit order is monotone in decoding order)
while idle < int(os.environ.get("NEXUS_IDLE_EXIT", "6")):
    phase("before_read")
    msgs = con.execute("SELECT lsn::text, data FROM pg_logical_slot_peek_changes('nexus', NULL, NULL)").fetchall()
    if cursor is not None:
        pos = next((i for i, (l, d) in enumerate(msgs) if d.startswith("COMMIT") and lsn_int(l) == cursor), None)
        msgs = msgs[pos + 1:] if pos is not None else msgs
    take, n = [], 0
    for l, d in msgs:                                            # whole transactions, about 400 messages per batch
        take.append((l, d)); n += 1
        if d.startswith("COMMIT") and n >= 400:
            break
    while take and not take[-1][1].startswith("COMMIT"):
        take.pop()
    if not take:
        idle += 1; time.sleep(0.25); continue
    idle = 0
    rows = [r for r in (parse(d, lsn_int(l)) for l, d in take) if r]
    last = take[-1][0]
    if rows:
        best = {}
        for r in rows:
            if r["id"] not in best or r["ver"] > best[r["id"]]["ver"]:
                best[r["id"]] = r
        phase("before_write")
        merge(list(best.values()), "nexus-live")
        phase("after_write_before_ack")
    cursor = lsn_int(last)
    acked.append(last)
    if len(acked) > ACK_LAG:                                  # delayed acknowledgement: keep ACK_LAG batches re-readable
        con.execute("SELECT pg_replication_slot_advance('nexus', %s::pg_lsn)", (acked[-1 - ACK_LAG],))
        phase("after_ack")
    if os.environ.get("NEXUS_ONE_BATCH") == "1":
        break
print("CONSUMER_EXIT", flush=True)
'''


def run_demo(root, venv_py, seed=0, kills=8):
    import psycopg
    rng = random.Random(f"s4-int:{seed}")
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    pg = PG(root)
    log = []
    try:
        con = psycopg.connect(pg.dsn, autocommit=True)
        con.execute("CREATE TABLE orders (id int PRIMARY KEY, warehouse text, status text, amount numeric(10,2), deleted bool DEFAULT false, "
                    "row_version bigint)")
        con.execute("CREATE SEQUENCE orders_version")      # explicit source version: one per committed row change
        con.execute("CREATE FUNCTION stamp() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN NEW.row_version := nextval('orders_version'); "
                    "RETURN NEW; END $$")
        con.execute("CREATE TRIGGER stamp BEFORE INSERT OR UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION stamp()")
        con.execute("ALTER TABLE orders REPLICA IDENTITY FULL")
        for i in range(1, 121):                                   # pre-history: only the backfill sees these as initial state
            con.execute("INSERT INTO orders VALUES (%s, %s, 'PLACED', %s, false)", (i, rng.choice(["W1", "W2", "W3"]), round(rng.uniform(10, 900), 2)))
        con.execute("SELECT pg_create_logical_replication_slot('nexus', 'test_decoding')")
        lake = root / "lake" / "silver_orders"
        cons = root / "consumer.py"
        cons.write_text(CONSUMER)

        def writer_step(n):
            for _ in range(n):
                op = rng.random()
                k = rng.randint(1, 160)
                if op < 0.35:
                    con.execute("INSERT INTO orders VALUES (%s, %s, 'PLACED', %s, false) ON CONFLICT (id) DO UPDATE SET status='PLACED', "
                                "deleted=false", (k, rng.choice(["W1", "W2", "W3"]), round(rng.uniform(10, 900), 2)))
                elif op < 0.75:
                    con.execute("UPDATE orders SET status=%s, amount=amount*%s WHERE id=%s",
                                (rng.choice(["SHIPPED", "DELIVERED", "CANCELLED"]), round(rng.uniform(0.8, 1.2), 3), k))
                elif op < 0.88:
                    con.execute("UPDATE orders SET deleted=true WHERE id=%s", (k,))
                else:
                    con.execute("DELETE FROM orders WHERE id=%s", (k,))

        def consumer(env=None, kill_at=None, kill_after=None):
            e = dict(os.environ, **(env or {}))
            p = subprocess.Popen([venv_py, str(cons), pg.dsn, str(lake), "live"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, env=e)
            killed = None
            t0 = time.time()
            if kill_at:
                ph, nth = kill_at
                seen = 0
                for line in p.stdout:
                    if line.startswith("PHASE " + ph):
                        seen += 1
                        if seen == nth:
                            p.send_signal(signal.SIGKILL); killed = ph; break
            elif kill_after is not None:
                time.sleep(kill_after)
                if p.poll() is None:
                    p.send_signal(signal.SIGKILL); killed = f"t+{kill_after:.2f}s"
            out, err = p.communicate(timeout=300)
            return dict(killed=killed, exit=p.returncode, err=err[-300:], wall=time.time() - t0)

        # 1) concurrent backfill + live changes + live consumer
        bf = subprocess.Popen([venv_py, str(cons), pg.dsn, str(lake), "backfill"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        writer_step(60)
        log.append(dict(step="live consumer during backfill", **consumer(env={"NEXUS_IDLE_EXIT": "3"})))
        writer_step(60)
        bf_out = bf.communicate(timeout=300)
        log.append(dict(step="backfill", exit=bf.returncode, out=bf_out[0][-80:], err=bf_out[1][-300:]))
        # 2) crash sweep: SIGKILL at each phase boundary (and again during recovery), with writes between
        for ph in ("before_read", "before_write", "after_write_before_ack", "after_ack"):
            writer_step(25)
            r = consumer(env={"NEXUS_PHASES": "1", **({"NEXUS_ACK_LAG": "0"} if ph == "after_ack" else {})}, kill_at=(ph, 1))
            log.append(dict(step=f"kill at {ph}", **r))
            r2 = consumer(env={"NEXUS_PHASES": "1"}, kill_at=("before_write", 1))      # crash DURING recovery
            log.append(dict(step=f"kill during recovery after {ph}", **r2))
        for i in range(kills):
            writer_step(15)
            log.append(dict(step=f"random SIGKILL {i}", **consumer(kill_after=rng.uniform(0.3, 2.0))))
        log.append(dict(step="drain", **consumer(env={"NEXUS_IDLE_EXIT": "3"})))
        check1 = compare(pg.dsn, lake)
        # 3) bad deploy then coordinated rollback
        from deltalake import DeltaTable
        good_version = DeltaTable(str(lake)).version()
        writer_step(40)
        log.append(dict(step="bad deploy (amount x10)", **consumer(env={"NEXUS_BAD_DEPLOY": "1", "NEXUS_IDLE_EXIT": "3"})))
        bad_check = compare(pg.dsn, lake)
        dt = DeltaTable(str(lake))
        dt.restore(good_version)                                     # one atomic Delta commit
        log.append(dict(step=f"restore Delta to version {good_version} (atomic table commit)", version_after=DeltaTable(str(lake)).version()))
        # the slot still holds the un-acknowledged changes after the restored version (delayed ack); replay them
        log.append(dict(step="replay after rollback", **consumer(env={"NEXUS_IDLE_EXIT": "3"})))
        check2 = compare(pg.dsn, lake)
        slot = con.execute("SELECT confirmed_flush_lsn::text, restart_lsn::text FROM pg_replication_slots WHERE slot_name='nexus'").fetchone()
        return dict(log=log, after_crash_sweep=check1, after_bad_deploy=bad_check, after_rollback_replay=check2,
                    delta_versions=DeltaTable(str(lake)).version(), slot=dict(confirmed_flush=slot[0], restart=slot[1]),
                    history_ops=[h.get("operation") for h in DeltaTable(str(lake)).history()][:6])
    finally:
        pg.stop()


def compare(dsn, lake):
    import psycopg
    from deltalake import DeltaTable
    with psycopg.connect(dsn) as c:
        src = {r[0]: (r[1], r[2], round(float(r[3]), 2)) for r in
               c.execute("SELECT id, warehouse, status, amount FROM orders WHERE NOT deleted").fetchall()}
    t = DeltaTable(str(lake)).to_pyarrow_table().to_pylist()
    ids = [r["id"] for r in t]
    live = {r["id"]: (r["warehouse"], r["status"], round(r["amount"], 2)) for r in t if not r["deleted"]}
    extra, missing = set(live) - set(src), set(src) - set(live)
    wrong = [k for k in set(src) & set(live) if src[k] != live[k]]
    return dict(match=not extra and not missing and not wrong and len(ids) == len(set(ids)), source_rows=len(src),
                lake_rows=len(t), extra=len(extra), missing=len(missing), wrong=len(wrong), duplicate_keys=len(ids) - len(set(ids)))


if __name__ == "__main__":
    venv_py = "/Users/ajayghimire/.claude-worktrees/venv-s456/bin/python"
    t0 = time.time()
    runs = {}
    for seed in [int(x) for x in (sys.argv[1:] or ["0", "1"])]:
        r = run_demo(Path(tempfile.mkdtemp(prefix="s4int_")) / "run", venv_py, seed=seed)
        r["kills_delivered"] = sum(1 for x in r["log"] if x.get("killed"))
        runs[seed] = r
        print(seed, {k: r[k] for k in ("after_crash_sweep", "after_bad_deploy", "after_rollback_replay", "kills_delivered")})
        print("   kill points reached:", sorted({x["killed"] for x in r["log"] if x.get("killed") and not x["killed"].startswith("t+")}))
    out = Path(__file__).resolve().parents[1] / "artifacts/s4_integration.json"
    out.write_text(json.dumps(dict(runs=runs, wall_s=time.time() - t0, versions=dict(postgres="14.18", deltalake="1.6.6",
                                                                                    psycopg="3.3.6", pyarrow="26.0.0")), indent=1, default=str))
