"""Phase 10C Stage 3: inexpensive EXTERNAL development audit (NOT LOCKED; diagnostic only - trains nothing, not evaluation data).
  python scripts/agi10c_external.py OUT.json

TASK PACK. 16 tasks written offline from PUBLIC real-world patterns (dbt jaffle_shop models, Debezium change envelopes,
Snowflake QUALIFY / MERGE / TRY_TO_NUMBER, Postgres DISTINCT ON, Hive '/' semantics, PySpark / Polars / Scala Spark jobs,
ISO-timestamp windows, NULL-unsafe filters, replayed duplicate batches). Code is in the form practitioners write it; the
data rows are small synthetic tables. Nothing is downloaded (no network ingestion is performed; disclosed).
PIPELINE per task (NEXUS's real code paths):
  1 NATIVE ingestion   ir6.lift(text, dialect) on the text as written
  2 ADAPTED ingestion  a HUMAN convention adapter (disclosed): SQL is re-wrapped as `CREATE TABLE clean AS <query>` with the
                       primary input renamed `raw` (NEXUS's loader convention); PySpark is wrapped into run(spark, raw, state)
  3 REPAIR             if the adapted text lifts and the task is single-table: a world6-format single-stage project (visible =
                       first rows, public checks = reference example rows + row count) is searched with search10c under the
                       Phase 10C A1 configuration (fixed guide, L0, 1,500 executions, 4 s); a submission is verified on ALL
                       rows (hidden) against the reference query (DuckDB)
CLASS (exactly one per task, first failure on the ADAPTED path; the native result is reported alongside):
  1 ingestion / parser / dialect   sqlglot cannot parse, or the lifter rejects a dialect construct the IR could express
  2 specification / grounding      needs several input tables (schema / key inference) or intent stated only in prose
  3 primitive / expressiveness     the IR has no construct for the repair (MERGE, JSON paths, CASE pivots, string times...)
  4 search horizon / ranking       expressible (the adapted REFERENCE lifts) but no verified candidate within budget
  5 verifier gap                   a candidate passed the public checks but is wrong on the full rows (or a correct one rejected)
  solved                           verified on all rows"""
import json, re, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import duckdb  # noqa: E402
import sqlglot  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import engines6 as E, ir6, pipeline6 as P6  # noqa: E402
from nexus.de_phase10c import lineage10c as LC, search10c as S10  # noqa: E402
import agi10c_train as TRN  # noqa: E402
from nexus.de_phase10c.rng10c import rng  # noqa: E402


def rows(cols, data):
    return [dict(zip(cols, [str(v) if v is not None else "" for v in r])) for r in data]


R0 = rng(10, 3, 0)
ORD = rows(["id", "user_id", "order_date", "status"], [(i, 1 + i % 5, f"2018-01-{1 + i % 28:02d}", ["placed", "shipped", "completed", "return_pending", "returned"][i % 5]) for i in range(1, 21)])
PAY = rows(["id", "order_id", "payment_method", "amount"], [(i, 1 + i % 20, ["credit_card", "coupon", "bank_transfer", "gift_card"][i % 4], 100 * (5 + i % 7) + 50 * (i % 2)) for i in range(1, 25)])
CUS = rows(["id", "first_name", "last_name"], [(i, f"F{i}", f"L{i}") for i in range(1, 6)])
ITEMS = rows(["order_id", "sku", "qty"], [(1 + i % 20, f"S{i % 4}", 1 + i % 3) for i in range(1, 41)])
CDC = rows(["customer_id", "status", "updated_at"], [(1 + i % 6, ["new", "active", "churned"][i % 3], 1000 + 7 * i) for i in range(1, 25)])
DBZ = rows(["payload"], [(json.dumps({"op": ["c", "u", "d"][i % 3], "after": {"id": i % 7, "v": i}, "before": None, "ts_ms": 1000 + i}),) for i in range(1, 19)])
SALES = rows(["id", "amount", "qty"], [(i, 100 + 13 * i, i % 4) for i in range(1, 21)])
RAWPAY = rows(["id", "amount"], [(i, (f"{10 * i}" if i % 5 else f"{i}x")) for i in range(1, 21)])
EVT = rows(["customer_id", "status", "event_ts"], [(1 + i % 5, ["a", "b", "c"][i % 3], 100 + 11 * i) for i in range(1, 21)])
NULLST = rows(["id", "status"], [(i, "" if i > 14 and i % 3 == 0 else ["open", "cancelled", "open", "shipped"][i % 4]) for i in range(1, 21)])
ISO = rows(["id", "amount", "event_ts"], [(i, 10 * i, f"2024-01-{25 + i % 8:02d}T{(7 * i) % 24:02d}:00:00Z" if 25 + i % 8 <= 31 else f"2024-02-0{(25 + i % 8) - 31}T01:00:00Z") for i in range(1, 21)])
REPLAY = rows(["id", "customer_id", "amount"], [(1 + i % 14, 1 + i % 4, 10 + i % 14) for i in range(1, 21)])

TASKS = [
    dict(id="T01", pattern="dbt jaffle_shop stg_payments (cents -> dollars)", lang="j2", tables=dict(payment=PAY), expect=1,
         legacy="select id as payment_id, order_id, payment_method, amount / 100 as amount from {{ source('stripe', 'payment') }}",
         ref="select id as payment_id, order_id, payment_method, cast(amount as double) / 100 as amount from raw"),
    dict(id="T02", pattern="dbt jaffle_shop customers (3-table CTE join + aggregates)", lang="postgres", tables=dict(customers=CUS, orders=ORD, payments=PAY), expect=2,
         legacy="with o as (select user_id, min(order_date) as first_order, count(*) as n from orders group by 1), p as (select o2.user_id, sum(amount) as ltv "
                "from payments join orders o2 on payments.order_id = o2.id group by 1) select c.id, o.first_order, o.n, p.ltv from customers c join o on c.id = o.user_id join p on c.id = p.user_id",
         ref=None),
    dict(id="T03", pattern="dbt jaffle_shop orders (payment-method pivot)", lang="postgres", tables=dict(payments=PAY), expect=3,
         legacy="select order_id, sum(case when payment_method = 'credit_card' then amount else 0 end) as credit_card_amount, sum(amount) as total from payments group by order_id",
         ref="select order_id, sum(case when payment_method = 'credit_card' then cast(amount as int) else 0 end) as credit_card_amount, sum(cast(amount as int)) as total from raw group by order_id"),
    dict(id="T04", pattern="1-to-many join fan-out (orders x order_items)", lang="postgres", tables=dict(orders=ORD, order_items=ITEMS), expect=2,
         legacy="select o.user_id, count(o.id) as orders from orders o join order_items i on o.id = i.order_id group by o.user_id", ref=None),
    dict(id="T05", pattern="Snowflake QUALIFY latest-per-key (ordering bug)", lang="snowflake", tables=dict(customers_cdc=CDC), expect=1,
         legacy="select customer_id, status from customers_cdc qualify row_number() over (partition by customer_id order by updated_at asc) = 1",
         ref="select customer_id, status from (select *, row_number() over (partition by customer_id order by cast(updated_at as int) desc) as rn from raw) where rn = 1"),
    dict(id="T06", pattern="MERGE INTO upsert (SCD1 dimension)", lang="snowflake", tables=dict(stg_customers=CDC), expect=3,
         legacy="merge into dim_customer d using stg_customers s on d.customer_id = s.customer_id when matched then update set status = s.status "
                "when not matched then insert (customer_id, status) values (s.customer_id, s.status)", ref=None),
    dict(id="T07", pattern="Debezium change envelope (JSON payload, delete tombstones)", lang="postgres", tables=dict(cdc_events=DBZ), expect=3,
         legacy="select payload::json->'after'->>'id' as id from cdc_events", ref=None),
    dict(id="T08", pattern="Hive -> DuckDB migration: '/' is real division, divide-by-zero", lang="hive", tables=dict(sales=SALES), expect=4,
         legacy="SELECT id, amount / qty AS unit_price FROM sales",
         ref="select id, round(cast(amount as double) / nullif(cast(qty as int), 0), 2) as unit_price from raw"),
    dict(id="T09", pattern="Snowflake dirty numeric cast (TRY_TO_NUMBER)", lang="snowflake", tables=dict(raw_payments=RAWPAY), expect=4,
         legacy="SELECT id, CAST(amount AS INTEGER) AS amount FROM raw_payments",
         ref="select id, coalesce(try_cast(trim(amount) as int), 0) as amount from raw"),
    dict(id="T10", pattern="Postgres DISTINCT ON latest event (ascending-order bug)", lang="postgres", tables=dict(events=EVT), expect=1,
         legacy="SELECT DISTINCT ON (customer_id) customer_id, status FROM events ORDER BY customer_id, event_ts ASC",
         ref="select customer_id, status from (select *, row_number() over (partition by customer_id order by cast(event_ts as int) desc) as rn from raw) where rn = 1"),
    dict(id="T11", pattern="NULL-unsafe <> filter drops unknown-status rows (issue text: keep them)", lang="postgres", tables=dict(orders=NULLST), expect=5, visible_n=12,
         legacy="SELECT id, status FROM orders WHERE status <> 'cancelled'",
         ref="select id, status from raw where status is null or trim(status) = '' or status <> 'cancelled'"),
    dict(id="T12", pattern="PySpark dropDuplicates keeps an arbitrary row (needs latest)", lang="py", tables=dict(events=EVT), expect=3,
         legacy="clean = events.dropDuplicates(['customer_id']).select('customer_id', 'status')",
         ref="select customer_id, status from (select *, row_number() over (partition by customer_id order by cast(event_ts as int) desc) as rn from raw) where rn = 1"),
    dict(id="T13", pattern="Polars pipeline (filter + unique keep='last')", lang="polars", tables=dict(events=EVT), expect=1,
         legacy="out = events.filter(pl.col('status') != 'c').unique(subset=['customer_id'], keep='last')", ref=None),
    dict(id="T14", pattern="Scala Spark when/otherwise tiering", lang="scala", tables=dict(sales=SALES), expect=3,
         legacy='val clean = sales.withColumn("tier", when(col("amount") > 200, "gold").otherwise("std")).select(col("id"), col("tier"))', ref=None),
    dict(id="T15", pattern="ISO-8601 string timestamp month window (<= last day drops its times)", lang="postgres", tables=dict(events=ISO), expect=3,
         legacy="SELECT id, amount FROM events WHERE event_ts >= '2024-01-01' AND event_ts <= '2024-01-31'",
         ref="select id, amount from raw where event_ts >= '2024-01-01' and event_ts < '2024-02-01'"),
    dict(id="T16", pattern="Replayed batch duplicates in an ELT load (dedup by id)", lang="sql", tables=dict(raw_orders=REPLAY), expect="solved",
         legacy="SELECT id, customer_id, amount FROM raw_orders",
         ref="select id, customer_id, amount from (select *, row_number() over (partition by id order by id) as rn from raw) where rn = 1"),
]


def adapt(t):
    prim = next(iter(t["tables"]))
    if t["lang"] in ("sql", "postgres", "snowflake", "hive"):
        q = re.sub(rf"\b{prim}\b", "raw", t["legacy"]) if len(t["tables"]) == 1 else t["legacy"]
        return f"CREATE TABLE clean AS {q};"
    if t["lang"] == "j2":
        return "{{ config(materialized='table') }}\nCREATE TABLE clean AS " + t["legacy"].replace("{{ source('stripe', 'payment') }}", "{{ ref('raw') }}") + ";"
    if t["lang"] == "py":
        body = t["legacy"].replace(prim, "raw")
        return f"from pyspark.sql import functions as F\n\n\ndef run(spark, raw, state):\n    {body}\n    return {{\"clean\": clean, \"rejects\": None}}\n"
    return t["legacy"]


def parse_ok(text, lang):
    d = {"sql": "sqlite", "postgres": "postgres", "snowflake": "snowflake", "hive": "hive", "j2": None}.get(lang)
    if d is None:
        return None, None
    try:
        sqlglot.parse(text if lang != "j2" else ir6.render_j2(text), read=d)
        return True, None
    except Exception as e:                                      # noqa: BLE001
        return False, str(e)[:120]


def lift(text, lang):
    try:
        return ir6.lift(text, lang), None
    except Exception as e:                                      # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:140]}"


def reference(t, data):
    con = duckdb.connect()
    for name, rs in t["tables"].items():
        cols = list(rs[0].keys())
        con.execute(f"create table {'raw' if len(t['tables']) == 1 else name} ({', '.join(c + ' varchar' for c in cols)})")
        con.executemany(f"insert into {'raw' if len(t['tables']) == 1 else name} values ({', '.join('?' for _ in cols)})", [[r[c] for c in cols] for r in (data if len(t['tables']) == 1 else rs)])
    cur = con.execute(t["ref"])
    cols = [d[0] for d in cur.description]
    return cols, [list(r) for r in cur.fetchall()]


def project(t, root):
    """world6-format single-stage workspace for a lifted single-table task."""
    rs = next(iter(t["tables"].values()))
    vis = rs[:t.get("visible_n", 14)]
    cols, out_v = reference(t, vis)
    _, out_all = reference(t, rs)
    ws, hid = Path(root) / t["id"] / "workspace", Path(root) / t["id"] / "hidden"
    for d in (ws / "data", ws / "pipeline", ws / "models", ws / "docs", hid):
        d.mkdir(parents=True, exist_ok=True)
    header = list(rs[0].keys())
    W.write_csv(ws / "data" / "visible.csv", header, vis)
    (ws / "pipeline" / "stage1.sql").write_text(adapt(t))
    lang = "sql" if t["lang"] == "sql" else t["lang"]
    checks = [dict(kind="no_error"), dict(kind="example_rows", cols=cols, rows=[[None if v is None else v for v in r] for r in out_v]), dict(kind="row_count", n=len(out_v))]
    (ws / "contract.json").write_text(json.dumps(dict(output_cols=cols, unique_key=None, public_checks=checks, quarantine_table=None, requirements=[],
                                                      stages=[dict(file="pipeline/stage1.sql", paradigm="EXT", engine="duckdb", legacy_language=lang, target_language="duckdb", model="stage1")]), default=str))
    return dict(pid=f"EXT.{t['id']}.0", ws=str(ws), hidden_dir=str(hid), stages=[dict(engine="duckdb", target_lang="duckdb", in_cols=header)], undecided=[]), cols, out_all, header, rs


def hidden_ok(specs, cols, out_all, header, rs):
    code = ir6.lower(specs[0], "duckdb")
    try:
        res = E.ENGINES["duckdb"]().run(code, header, rs, {})
    except Exception as e:                                      # noqa: BLE001
        return False, f"runtime {type(e).__name__}"
    return W.table_key(res["clean"], cols) == W.table_key([dict(zip(cols, r)) for r in out_all], cols), None


def main(out):
    t0 = time.time()
    mem = LC.arm_memory(TRN.fixed_trust()[0])
    res = []
    for t in TASKS:
        r = dict(id=t["id"], pattern=t["pattern"], lang=t["lang"], tables=len(t["tables"]), expected_class=t["expect"])
        r["native_parse"], r["native_parse_err"] = parse_ok(t["legacy"], t["lang"])
        spec, r["native_lift_err"] = lift(t["legacy"], t["lang"])
        r["native_lift"] = spec is not None
        a = adapt(t)
        r["adapted_parse"], r["adapted_parse_err"] = parse_ok(a, t["lang"])
        spec, r["adapted_lift_err"] = lift(a, t["lang"]) if t["lang"] != "polars" else (None, "no Polars lifter in NEXUS (ir6 languages: sql, hive, postgres, snowflake, duckdb, py, j2, scala)")
        r["adapted_lift"] = spec is not None
        if t["ref"] and len(t["tables"]) == 1:
            ref_lift, r["reference_lift_err"] = lift(f"CREATE TABLE clean AS {t['ref']};", "postgres")
            r["reference_expressible"] = ref_lift is not None
        else:
            r["reference_expressible"] = False
        if r["adapted_parse"] is False:
            cls, why = 1, r["adapted_parse_err"]
        elif not r["adapted_lift"]:
            if len(t["tables"]) > 1:
                cls, why = 2, f"{len(t['tables'])} input tables; the IR is single-input ({r['adapted_lift_err']})"
            elif t["lang"] in ("polars",) or re.search(r"parse error|cannot lift|Unsupported language", r["adapted_lift_err"] or "") and not re.search(r"(?i)merge|json|case|qualify|window|distinct", r["adapted_lift_err"] or ""):
                cls, why = 1, r["adapted_lift_err"]
            else:
                cls, why = 3, r["adapted_lift_err"]
        else:
            try:
                p, cols, out_all, header, rs = project(t, ROOT / "var/agi10c_ws/external")
                inv = P6.Inv6(p)
                sr = S10.search(inv, mem, LC.WORK, LC.WALL)
                r["search"] = dict(outcome=sr["outcome"], path=sr["path"], work=sr["work"])
                if sr["outcome"] == "submitted":
                    ok, err = hidden_ok(sr["specs"], cols, out_all, header, rs)
                    r["hidden_ok"], r["hidden_err"] = ok, err
                    cls, why = ("solved", "verified on all rows") if ok else (5, "passed the public checks, wrong on the full rows")
                else:
                    cls, why = (4, "expressible but not reached within the budget") if r["reference_expressible"] else (3, "no verified candidate and the reference repair does not lift into the IR")
            except Exception as e:                              # noqa: BLE001
                cls, why = 3, f"project / search error: {type(e).__name__}: {str(e)[:120]}"
        r["class"], r["why"] = cls, why
        res.append(r)
        print(t["id"], t["lang"], "native_lift", r["native_lift"], "adapted_lift", r["adapted_lift"], "->", cls, "|", str(why)[:110], flush=True)
    summary = dict(n=len(res), by_class={str(c): sum(1 for r in res if str(r["class"]) == str(c)) for c in (1, 2, 3, 4, 5, "solved")},
                   native_lifted=sum(r["native_lift"] for r in res), adapted_lifted=sum(r["adapted_lift"] for r in res),
                   matches_expected=sum(str(r["class"]) == str(r["expected_class"]) for r in res), wall=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(dict(summary=summary, tasks=res), indent=1, default=str))
    print(json.dumps(summary))


if __name__ == "__main__":
    main(*sys.argv[1:])
