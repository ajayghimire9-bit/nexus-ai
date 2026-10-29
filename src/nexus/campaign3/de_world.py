"""Phase 3 real-pipeline project world (NOT LOCKED): data-engineering projects executed on their ACTUAL runtimes
(SQLite 3 and Apache Spark 4.0 with ANSI mode on), each with an independent evaluator.

A project is a workspace directory:
  data/visible.csv          the visible landing batch (every column landed as text, as from CSV)
  checkpoint.json / *.json  operational state files (e.g. a recovery checkpoint, a watermark)
  pipeline.json             the legacy pipeline as a declarative spec (rendered by `render` to the runtime's SQL)
  pipeline.sql              the same pipeline rendered for the project's runtime (what an engineer would read)
  contract.json             the public business contract: output / quarantine tables, column types, and machine-checkable
                            PUBLIC CHECKS (the agent may execute them on the visible batch)
  README.md                 a plain-language goal statement
Hidden (never written to the workspace): 2 held-out landing batches and the reference implementation (pure Python, not the
runtime) used by `evaluate`, which runs the submitted pipeline on the real runtime over the hidden batches and compares
output and quarantine tables exactly (reals at 2 decimals), and re-checks every public check.

Families (business mechanisms; each project instance draws column names from realistic pools, so nothing is keyed on names):
  source  G1 type-parse migration      text quantities / prices; malformed values must go to quarantine, or default to a
                                       contract value; the legacy plain CAST silently gives 0 in SQLite and raises
                                       CAST_INVALID_INPUT under Spark 4 ANSI
          G2 derived-metric repair     unit price = amount / units; legacy integer division (truncation) and no zero guard;
                                       contract wants a real rounded to 2, NULL when units = 0 (Spark ANSI raises
                                       DIVIDE_BY_ZERO)
          G3 latest-version dedup      several versions per business key; contract: exactly the latest version per key
          G4 exactly-once recovery     a replayed event log after a crash; checkpoint.json holds the last committed offset;
                                       contract: aggregate each event once (offset > checkpoint, unique event id)
  holdout G5 default-fill for missing dimension values (contract default label for NULL / empty region codes)
          G6 late-data watermark       drop events older than the watermark minus the allowed lateness (watermark.json)
Levels: 1 = one defect (the family's), 2 = the family defect plus a G1-style parse defect on another column."""
from __future__ import annotations

import csv
import io
import json
import os
import random
import shutil
import sqlite3
from pathlib import Path

POOLS = dict(units=["qty", "quantity", "units", "n_items"], price=["price", "unit_cost", "list_price"],
             amount=["amount", "gross", "total_value"], key=["order_id", "sku", "account_id"], ver=["version", "rev", "seq"],
             event=["event_id", "msg_id"], offset=["offset", "log_pos"], region=["region", "zone", "market"],
             ts=["event_ts", "ts", "recorded_at"], val=["value", "reading", "delta"])


# ------------------------------------------------------------------ pipeline spec + dialect rendering
def E(op, *a):
    return [op] + list(a)


def render_expr(e, d):
    op = e[0]
    if op == "col":
        return f'"{e[1]}"' if d == "sqlite" else f"`{e[1]}`"
    if op == "lit":
        v = e[1]
        return "NULL" if v is None else (f"'{v}'" if isinstance(v, str) else repr(v))
    if op == "file":                                   # a value read from a workspace state file (resolved at run time)
        return repr(e[2])
    if op == "cast_int":
        return f"CAST({render_expr(e[1], d)} AS INTEGER)" if d == "sqlite" else f"CAST({render_expr(e[1], d)} AS INT)"
    if op == "cast_real":
        return f"CAST({render_expr(e[1], d)} AS REAL)" if d == "sqlite" else f"CAST({render_expr(e[1], d)} AS DOUBLE)"
    if op == "valid_int":
        x = f"TRIM({render_expr(e[1], d)})"
        return (f"({x} <> '' AND {x} NOT GLOB '*[^0-9]*')" if d == "sqlite" else f"({x} RLIKE '^[0-9]+$')")
    if op == "try_int":
        x = f"TRIM({render_expr(e[1], d)})"
        if d == "sqlite":
            return f"(CASE WHEN {x} <> '' AND {x} NOT GLOB '*[^0-9]*' THEN CAST({x} AS INTEGER) END)"
        return f"try_cast({x} AS INT)"
    if op in ("add", "sub", "mul"):
        s = {"add": "+", "sub": "-", "mul": "*"}[op]
        return f"({render_expr(e[1], d)} {s} {render_expr(e[2], d)})"
    if op == "div":                                    # the engine's native division (SQLite: integer truncation on ints)
        return f"({render_expr(e[1], d)} / {render_expr(e[2], d)})"
    if op == "div_real":
        return f"(({render_expr(e[1], d)}) * 1.0 / ({render_expr(e[2], d)}))"
    if op == "nullif_zero":
        return f"NULLIF({render_expr(e[1], d)}, 0)"
    if op == "round2":
        return f"ROUND({render_expr(e[1], d)}, 2)"
    if op == "coalesce":
        return f"COALESCE({render_expr(e[1], d)}, {render_expr(e[2], d)})"
    if op == "nullif_empty":
        return f"NULLIF(TRIM({render_expr(e[1], d)}), '')"
    if op in ("gt", "ge", "eq", "lt"):
        s = {"gt": ">", "ge": ">=", "eq": "=", "lt": "<"}[op]
        return f"({render_expr(e[1], d)} {s} {render_expr(e[2], d)})"
    if op == "and":
        return f"({render_expr(e[1], d)} AND {render_expr(e[2], d)})"
    if op == "not":
        return f"(NOT {render_expr(e[1], d)})"
    raise ValueError(op)


def resolve_files(e, ws):
    """Replace ['file', name, key] by ['file', name, value] using the workspace's state files."""
    if isinstance(e, dict):
        return {k: resolve_files(v, ws) for k, v in e.items()}
    if not isinstance(e, list):
        return e
    if e and e[0] == "file":
        v = json.loads((Path(ws) / e[1]).read_text())
        return ["file", e[1], v[e[2]] if isinstance(v, dict) else v]
    return [resolve_files(x, ws) for x in e]


def render(spec, d):
    """spec: {outputs: [[name, expr]], filter, quarantine, dedup: {key, order} | {key} (first by offset), group}
    -> {output_sql, quarantine_sql | None}."""
    src = "raw"
    base = src
    if spec.get("dedup"):
        dd = spec["dedup"]
        order = render_expr(dd["order"], d) if dd.get("order") else render_expr(["col", "__rowid"], d)
        direction = "DESC" if dd.get("order") else "ASC"
        base = (f"(SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY {render_expr(['col', dd['key']], d)} "
                f"ORDER BY {order} {direction}) AS __rn FROM {src}) WHERE __rn = 1)")
    conds = []
    if spec.get("filter"):
        conds.append(render_expr(spec["filter"], d))
    q = spec.get("quarantine")
    if q:
        conds.append(f"(NOT {render_expr(q, d)})")
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    cols = ", ".join(f"{render_expr(x, d)} AS {render_expr(['col', n], d)}" for n, x in spec["outputs"])
    if spec.get("group"):
        g = spec["group"]
        cols = (f"{render_expr(['col', g['key']], d)} AS {render_expr(['col', g['key']], d)}, "
                + ", ".join(f"SUM({render_expr(x, d)}) AS {render_expr(['col', n], d)}" for n, x in spec["outputs"]))
        out = f"SELECT {cols} FROM {base} AS t{where} GROUP BY {render_expr(['col', g['key']], d)}"
    else:
        out = f"SELECT {cols} FROM {base} AS t{where}"
    qs = None
    if q:
        qw = [render_expr(q, d)] + ([render_expr(spec["filter"], d)] if spec.get("filter") else [])
        qs = f"SELECT * FROM {base} AS t WHERE " + " AND ".join(qw)
    return dict(output_sql=out, quarantine_sql=qs)


# ------------------------------------------------------------------ runtimes
class RunError(Exception):
    def __init__(self, cls, msg):
        super().__init__(msg)
        self.cls, self.msg = cls, msg


def _rows_csv(path):
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        header = next(r)
        return header, [row for row in r]


class SQLiteRuntime:
    name = "sqlite"

    def run(self, ws, spec, batch="data/visible.csv"):
        header, rows = _rows_csv(Path(ws) / batch)
        con = sqlite3.connect(":memory:")
        try:
            cols = ", ".join(f'"{h}" TEXT' for h in header)
            con.execute(f'CREATE TABLE raw ({cols}, "__rowid" INTEGER)')
            con.executemany(f"INSERT INTO raw VALUES ({','.join('?' * (len(header) + 1))})",
                            [tuple(r) + (i,) for i, r in enumerate(rows)])
            sql = render(resolve_files(spec, ws), "sqlite")
            try:
                cur = con.execute(sql["output_sql"])
                names = [c[0] for c in cur.description]
                out = [dict(zip(names, r)) for r in cur.fetchall()]
                quar = None
                if sql["quarantine_sql"]:
                    cur = con.execute(sql["quarantine_sql"])
                    qn = [c[0] for c in cur.description]
                    quar = [dict(zip(qn, r)) for r in cur.fetchall()]
            except sqlite3.Error as e:
                raise RunError(type(e).__name__, str(e)[:200])
            return dict(output=out, quarantine=quar)
        finally:
            con.close()


class SparkRuntime:
    """One persistent local SparkSession per process (local[2], 1 shuffle partition, UI off, ANSI = Spark 4 default)."""
    name = "spark"
    _spark = None

    @classmethod
    def session(cls):
        if cls._spark is None:
            os.environ.setdefault("JAVA_HOME", "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
            os.environ["PATH"] = "/opt/homebrew/opt/openjdk@17/bin:" + os.environ.get("PATH", "")
            quiet = Path(__file__).resolve().parents[3] / "config" / "log4j2-quiet.properties"
            os.environ.setdefault("PYSPARK_SUBMIT_ARGS", f"--driver-java-options -Dlog4j2.configurationFile={quiet} pyspark-shell")
            import logging
            logging.getLogger("SQLQueryContextLogger").disabled = True      # pyspark's Python-side structured error log
            from pyspark.sql import SparkSession
            s = (SparkSession.builder.master("local[2]").appName("nexus-phase3").config("spark.ui.enabled", "false")
                 .config("spark.sql.shuffle.partitions", "1").config("spark.sql.ansi.enabled", "true")
                 .config("spark.driver.memory", "1g").config("spark.log.structuredLogging.enabled", "false").getOrCreate())
            s.sparkContext.setLogLevel("OFF")
            cls._spark = s
        return cls._spark

    @classmethod
    def warm(cls):
        """Start the JVM / session once per worker before any project clock starts (the start-up is charged to the ledger
        as runtime overhead, but not to any project's search budget)."""
        s = cls.session()
        s.sql("SELECT 1").collect()

    def run(self, ws, spec, batch="data/visible.csv"):
        s = self.session()
        header, rows = _rows_csv(Path(ws) / batch)
        df = s.createDataFrame([tuple(r) + (i,) for i, r in enumerate(rows)], schema=", ".join(f"`{h}` string" for h in header)
                               + ", `__rowid` int") if rows else s.createDataFrame([], ", ".join(f"`{h}` string" for h in header)
                                                                               + ", `__rowid` int")
        df.createOrReplaceTempView("raw")
        sql = render(resolve_files(spec, ws), "spark")
        try:
            out = [r.asDict() for r in s.sql(sql["output_sql"]).collect()]
            quar = [r.asDict() for r in s.sql(sql["quarantine_sql"]).collect()] if sql["quarantine_sql"] else None
        except Exception as e:                                # noqa: BLE001  (Py4J / AnalysisException / ArithmeticException)
            cls = getattr(e, "getCondition", lambda: None)() or type(e).__name__
            raise RunError(str(cls), str(e).split("\n")[0][:200])
        return dict(output=out, quarantine=quar)


RUNTIMES = {"sqlite": SQLiteRuntime, "spark": SparkRuntime}


# ------------------------------------------------------------------ public checks (agent-executable) and the evaluator
def _num(v):
    if v is None:
        return None
    if isinstance(v, float):
        return round(v, 2)
    return v


def table_key(rows, cols):
    return sorted(tuple(_num(r.get(c)) if not isinstance(r.get(c), str) else r.get(c) for c in cols) for r in rows)


def run_check(chk, res, visible_rows):
    """One public check on a run result (visible batch). Returns True / False."""
    k = chk["kind"]
    out = res["output"]
    if k == "no_error":
        return True
    if k == "unique":
        vals = [r.get(chk["col"]) for r in out]
        return len(vals) == len(set(vals))
    if k == "not_null":
        return all(r.get(chk["col"]) is not None for r in out)
    if k == "example_rows":
        cols = chk["cols"]
        have = {tuple(_num(r.get(c)) for c in cols) for r in out}
        return all(tuple(_num(v) for v in ex) in have for ex in chk["rows"])
    if k == "row_count":
        return len(out) == chk["n"]
    if k == "quarantine_ids":
        q = res.get("quarantine") or []
        return sorted(str(r.get(chk["id"])) for r in q) == sorted(chk["ids"])
    if k == "no_rows_with_ids":
        return not {str(r.get(chk["id"])) for r in out} & set(chk["ids"])
    raise ValueError(k)


def evaluate(project, spec, runtime=None):
    """INDEPENDENT evaluation: run the submitted spec on the project's real runtime over the 2 hidden batches; compare
    output (and quarantine) tables exactly with the pure-Python reference; any runtime error fails."""
    rt = runtime or RUNTIMES[project["runtime"]]()
    hid = Path(project["hidden_dir"])
    fails = []
    for b in ("hidden1.csv", "hidden2.csv"):
        ws_tmp = hid / "ws"
        if ws_tmp.exists():
            shutil.rmtree(ws_tmp)
        shutil.copytree(project["ws"], ws_tmp)
        shutil.copy(hid / b, ws_tmp / "data" / "visible.csv")
        for sf in project.get("hidden_state", {}).get(b, {}):
            (ws_tmp / sf).write_text(json.dumps(project["hidden_state"][b][sf]))
        try:
            res = rt.run(ws_tmp, spec)
        except RunError as e:
            fails.append(f"{b}: runtime {e.cls}")
            continue
        ref = json.loads((hid / (b + ".expected.json")).read_text())
        cols = ref["output_cols"]
        if table_key(res["output"], cols) != table_key([dict(zip(cols, r)) for r in ref["output"]], cols):
            fails.append(f"{b}: output differs")
        if ref.get("quarantine_ids") is not None:
            got = sorted(str(r.get(ref["id_col"])) for r in (res.get("quarantine") or []))
            if got != sorted(ref["quarantine_ids"]):
                fails.append(f"{b}: quarantine differs")
    return dict(ok=not fails, fails=fails, kind="hidden_batches_on_runtime")


# ------------------------------------------------------------------ project generator
def _malformed(rng):
    return rng.choice(["n/a", "", "12x", "?", "1,5", "-"])


def _gen_rows(fam, rng, n, names, level, bad_p):
    rows = []
    if fam in ("G1", "G2", "G5"):
        for i in range(n):
            u = str(rng.randint(0, 9)) if fam == "G2" else str(rng.randint(1, 20))
            p = str(rng.randint(1, 50))
            a = str(rng.randint(0, 200))
            reg = rng.choice(["EU", "US", "APAC", "", "LATAM"]) if fam == "G5" else rng.choice(["EU", "US"])
            if fam == "G1" and rng.random() < bad_p:
                u = _malformed(rng)
            if level == 2 and rng.random() < bad_p:
                p = _malformed(rng)
            rows.append({"id": f"r{i}", names["units"]: u, names["price"]: p, names["amount"]: a, names["region"]: reg})
    elif fam == "G3":
        keys = [f"k{j}" for j in range(max(2, n // 3))]
        for i in range(n):
            p = str(rng.randint(1, 50))
            if level == 2 and rng.random() < bad_p:
                p = _malformed(rng)
            rows.append({"id": f"r{i}", names["key"]: rng.choice(keys), names["ver"]: str(rng.randint(1, 9)), names["price"]: p})
        seen = set()
        out = []
        for r in rows:                                     # versions unique per key (a well-defined latest)
            if (r[names["key"]], r[names["ver"]]) not in seen:
                seen.add((r[names["key"]], r[names["ver"]]))
                out.append(r)
        rows = out
    elif fam in ("G4", "G6"):
        keys = ["a", "b", "c"]
        for i in range(n):
            v = str(rng.randint(1, 9))
            if level == 2 and rng.random() < bad_p:
                v = _malformed(rng)
            rows.append({"id": f"r{i}", names["event"]: f"e{i}", names["offset"]: str(i + 1), names["key"]: rng.choice(keys),
                         names["val"]: v, names["ts"]: str(100 + i * 3 + rng.randint(-8, 2))})
        if fam == "G4":                                    # replay after a crash: a block of events appears twice
            dup = rows[n // 3: n // 3 + max(2, n // 4)]
            rows = rows + [dict(r) for r in dup]
    return rows


def _is_int(s):
    s = (s or "").strip()
    return s != "" and s.isdigit()


def reference(fam, params, rows, state):
    """Pure-Python reference business logic (never the runtime). Returns (output rows as lists, cols, quarantine ids)."""
    nm, level = params["names"], params["level"]
    quar = None

    def parse_price(r):
        return int(r[nm["price"]].strip()) if _is_int(r[nm["price"]]) else None

    if fam in ("G1", "G2", "G5"):
        out, quar = [], []
        for r in rows:
            u_ok, p_ok = _is_int(r[nm["units"]]), _is_int(r[nm["price"]])
            bad = (fam == "G1" and not u_ok and params["policy"] == "quarantine") or (level == 2 and not p_ok)
            if bad:
                quar.append(r["id"])
                continue
            u = int(r[nm["units"]].strip()) if u_ok else params.get("default", 0)
            p = int(r[nm["price"]].strip()) if p_ok else None
            if fam == "G1":
                out.append([r["id"], u, p * u if p is not None else None])
            elif fam == "G2":
                a = int(r[nm["amount"]])
                out.append([r["id"], round(a / u, 2) if u else None, p])
            else:
                reg = r[nm["region"]].strip() or params["default_label"]
                out.append([r["id"], reg, u * p])
        cols = {"G1": ["id", nm["units"], "line_total"], "G2": ["id", "unit_price", nm["price"]],
                "G5": ["id", nm["region"], "line_total"]}[fam]
        if level == 1 and not (fam == "G1" and params["policy"] == "quarantine"):
            quar = None
        return out, cols, quar
    if fam == "G3":
        best, quar = {}, []
        for r in rows:                                     # latest version per key first; then a malformed latest is rejected
            k, v = r[nm["key"]], int(r[nm["ver"]])
            if k not in best or v > best[k][0]:
                best[k] = (v, r)
        out = []
        for k, (v, r) in best.items():
            if level == 2 and not _is_int(r[nm["price"]]):
                quar.append(r["id"])
            else:
                out.append([k, v, parse_price(r)])
        return out, [nm["key"], nm["ver"], nm["price"]], (quar if level == 2 else None)
    if fam in ("G4", "G6"):
        agg, seen, quar = {}, set(), []
        for r in rows:
            if fam == "G4":
                if int(r[nm["offset"]]) <= state["checkpoint"] or r[nm["event"]] in seen:
                    continue
            else:
                if int(r[nm["ts"]]) < state["watermark"] - state["allowed_lateness"]:
                    continue
            if level == 2 and not _is_int(r[nm["val"]]):
                quar.append(r["id"])
                seen.add(r[nm["event"]])
                continue
            seen.add(r[nm["event"]])
            agg[r[nm["key"]]] = agg.get(r[nm["key"]], 0) + int(r[nm["val"]])
        return [[k, v] for k, v in agg.items()], [nm["key"], "total"], (quar if level == 2 else None)
    raise KeyError(fam)


def legacy_spec(fam, params):
    nm, level = params["names"], params["level"]
    if fam in ("G1", "G2", "G5"):
        u, p, a = (["cast_int", ["col", nm[k]]] for k in ("units", "price", "amount"))
        if fam == "G1":
            outs = [["id", ["col", "id"]], [nm["units"], u], ["line_total", ["mul", p, u]]]
        elif fam == "G2":
            outs = [["id", ["col", "id"]], ["unit_price", ["div", a, u]], [nm["price"], p]]
        else:
            outs = [["id", ["col", "id"]], [nm["region"], ["col", nm["region"]]], ["line_total", ["mul", u, p]]]
        return dict(outputs=outs)
    if fam == "G3":
        return dict(outputs=[[nm["key"], ["col", nm["key"]]], [nm["ver"], ["cast_int", ["col", nm["ver"]]]],
                             [nm["price"], ["cast_int", ["col", nm["price"]]]]])
    if fam in ("G4", "G6"):
        return dict(outputs=[["total", ["cast_int", ["col", nm["val"]]]]], group=dict(key=nm["key"]))
    raise KeyError(fam)


def make_project(fam, level, seed, runtime, root):
    """Write the workspace (agent-visible) and the hidden evaluation material for one project. Returns the project dict."""
    for attempt in range(30):
        p = _make(fam, level, seed, runtime, root, attempt)
        if p is not None:
            return p
    raise RuntimeError(f"could not build an identifiable project {fam} L{level} {seed}")


def _make(fam, level, seed, runtime, root, attempt):
    rng = random.Random(f"p3de|{fam}|{level}|{seed}|{runtime}|{attempt}")
    names = {k: rng.choice(v) for k, v in POOLS.items()}
    if names["key"] in (names["event"],):
        names["key"] = "account_id"
    params = dict(names=names, level=level)
    if fam == "G1":
        params["policy"] = rng.choice(["quarantine", "default"])
        params["default"] = 0
    if fam == "G5":
        params["default_label"] = rng.choice(["UNKNOWN", "OTHER"])
    if fam == "G6":
        params["lateness"] = rng.choice([5, 10])
    pid = f"{fam}.L{level}.{runtime}.{seed}"
    ws, hid = Path(root) / pid / "workspace", Path(root) / pid / "hidden"
    for d in (ws, hid):
        if d.exists():
            shutil.rmtree(d)
        (d / "data").mkdir(parents=True) if d == ws else d.mkdir(parents=True)
    n = rng.randint(10, 16)
    batches = {"visible.csv": _gen_rows(fam, rng, n, names, level, 0.25), "hidden1.csv": _gen_rows(fam, rng, n + 6, names, level, 0.3),
               "hidden2.csv": _gen_rows(fam, rng, n + 10, names, level, 0.3)}
    states = {}
    for b, rows in batches.items():
        st = {}
        if fam == "G4":
            st["checkpoint"] = rng.randint(2, max(3, len(rows) // 3))
        if fam == "G6":
            st["watermark"], st["allowed_lateness"] = 100 + 3 * len(rows) // 2, params["lateness"]
        states[b] = st
    header = list(batches["visible.csv"][0].keys())

    def write_csv(path, rows):
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            for r in rows:
                w.writerow([r[h] for h in header])
    write_csv(ws / "data" / "visible.csv", batches["visible.csv"])
    hidden_state = {}
    for b in ("hidden1.csv", "hidden2.csv"):
        write_csv(hid / b, batches[b])
        out, cols, quar = reference(fam, params, batches[b], states[b])
        (hid / (b + ".expected.json")).write_text(json.dumps(dict(output=out, output_cols=cols, quarantine_ids=quar, id_col="id")))
        hidden_state[b] = {}
        if fam == "G4":
            hidden_state[b]["checkpoint.json"] = {"last_committed_offset": states[b]["checkpoint"]}
        if fam == "G6":
            hidden_state[b]["watermark.json"] = {"watermark": states[b]["watermark"], "allowed_lateness": params["lateness"]}
    if fam == "G4":
        (ws / "checkpoint.json").write_text(json.dumps({"last_committed_offset": states["visible.csv"]["checkpoint"]}))
    if fam == "G6":
        (ws / "watermark.json").write_text(json.dumps({"watermark": states["visible.csv"]["watermark"],
                                                       "allowed_lateness": params["lateness"]}))
    vout, vcols, vquar = reference(fam, params, batches["visible.csv"], states["visible.csv"])
    # the stakeholder supplies the expected result of the visible batch (golden rows); hidden batches test generalisation
    checks = [dict(kind="no_error"), dict(kind="example_rows", cols=vcols, rows=vout), dict(kind="row_count", n=len(vout))]
    if fam == "G3":
        checks.append(dict(kind="unique", col=names["key"]))
    if vquar is not None:
        checks.append(dict(kind="quarantine_ids", id="id", ids=sorted(vquar)))
    contract = dict(output_table="clean", quarantine_table="rejects" if vquar is not None else None, output_cols=vcols,
                    runtime=runtime, engine_semantics="Spark 4.0 ANSI (spark.sql.ansi.enabled=true)" if runtime == "spark" else
                    "SQLite 3", public_checks=checks,
                    notes=_notes(fam, params))
    spec = legacy_spec(fam, params)
    (ws / "pipeline.json").write_text(json.dumps(spec, indent=1))
    (ws / "pipeline.sql").write_text(render(resolve_files(spec, ws), runtime)["output_sql"] + "\n")
    (ws / "contract.json").write_text(json.dumps(contract, indent=1))
    (ws / "README.md").write_text(f"Goal: make the legacy pipeline satisfy contract.json on {contract['engine_semantics']}.\n")
    # identifiability: the legacy pipeline must visibly fail a public check on the visible batch (SQLite semantics; under
    # Spark ANSI the same rows also raise or differ), otherwise the visible evidence cannot reveal the defect
    try:
        res = SQLiteRuntime().run(ws, spec)
        if all(run_check(c, res, None) for c in checks) and runtime == "sqlite":
            return None
    except RunError:
        pass
    if not _exposes(fam, level, params, batches["visible.csv"], states["visible.csv"]) or len(vout) < 2:
        return None                                    # also: the golden visible output must be non-trivial (>= 2 rows)
    return dict(pid=pid, family=fam, level=level, seed=seed, runtime=runtime, ws=str(ws), hidden_dir=str(hid),
                hidden_state=hidden_state, params=params)


def _exposes(fam, level, params, rows, state):
    """Per-defect identifiability: the visible batch shows at least one instance of every defect the project has."""
    nm = params["names"]
    bad = lambda c: any(not _is_int(r[nm[c]]) for r in rows)              # noqa: E731
    need = []
    if level == 2:
        need.append(bad("val") if fam in ("G4", "G6") else bad("price"))
    if fam == "G1":
        # exposure counts only rows that reach the output (a level-2 row with a malformed price is quarantined anyway)
        live = [r for r in rows if level == 1 or _is_int(r[nm["price"]])]
        need.append(any(not _is_int(r[nm["units"]]) for r in live))
        if params.get("policy") == "default":          # SQLite CAST parses '12x' / '1,5' as a prefix: must be visible too
            need.append(any(r[nm["units"]] in ("12x", "1,5") for r in live))
    if fam == "G2":
        live = [r for r in rows if level == 1 or _is_int(r[nm["price"]])]
        us = [int(r[nm["units"]]) for r in live]
        need.append(0 in us and any(u and int(r[nm["amount"]]) % u for u, r in zip(us, live)))
    if fam == "G3":
        ks = [r[nm["key"]] for r in rows]
        need.append(len(ks) > len(set(ks)))
        if level == 2:                                 # the malformed price must sit in a LATEST row to be visible
            best = {}
            for r in rows:
                if r[nm["key"]] not in best or int(r[nm["ver"]]) > int(best[r[nm["key"]]][nm["ver"]]):
                    best[r[nm["key"]]] = r
            need.append(any(not _is_int(r[nm["price"]]) for r in best.values()))
    if fam == "G4":
        need.append(any(int(r[nm["offset"]]) <= state["checkpoint"] for r in rows))
    if fam == "G5":
        need.append(any(not r[nm["region"]].strip() for r in rows))
    if fam == "G6":
        need.append(any(int(r[nm["ts"]]) < state["watermark"] - state["allowed_lateness"] for r in rows))
    return all(need)


def _notes(fam, params):
    """Plain-language contract notes (business rules as a stakeholder would state them; not machine-parsed by the agent)."""
    nm = params["names"]
    return {"G1": f"{nm['units']} must be an integer; malformed rows " +
                  ("are rejected to the quarantine table" if params.get("policy") == "quarantine" else f"use {params.get('default')}"),
            "G2": "unit_price = amount / units as a real number rounded to 2 decimals; NULL when units is 0",
            "G3": f"exactly one row per {nm['key']}: the latest {nm['ver']}",
            "G4": "after recovery every event is counted exactly once; events at or before the committed offset are done",
            "G5": f"missing {nm['region']} values get the label {params.get('default_label')}",
            "G6": f"events older than the watermark minus {params.get('lateness')} are late and excluded"}[fam]
