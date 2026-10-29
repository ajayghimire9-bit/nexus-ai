"""Phase 4 real-file DE project world (NOT LOCKED). Extends the Phase 3 world (campaign3.de_world: real runtimes, public
checks, an independent hidden-batch evaluator) to REAL pipeline files and COMPOSITIONAL MULTI-FAULT projects.

Workspace (agent-visible):
  data/visible.csv            the visible landing batch (all text)
  checkpoint.json / watermark.json   operational state read by the pipeline at run time
  pipeline.sql | pipeline.py  the legacy pipeline: a SQLite 3 script (SQLite projects) or a PySpark 4 DataFrame script
                              (Spark projects, executed with spark.sql.ansi.enabled=true), written in varied legacy styles
  contract.json               output / quarantine tables, output column types, public checks incl. the stakeholder's golden
                              rows for the visible batch, the unique key; plain-language notes
Hidden: 2 held-out batches (more rows, different state values) and their expected tables from the pure-Python reference
(ir.interpret of the business-truth spec; never an engine). evaluate() executes the SUBMITTED FILE TEXT on the project's
engine over the hidden batches and compares tables exactly (reals at 2 decimals) and the quarantine ids.

Mechanism families (each = a business rule with a correct form and a legacy defect form):
  source     F1 parse       malformed numeric text: quarantine or default 0 (legacy: plain CAST; SQLite silently parses a
                            prefix / 0, Spark ANSI raises CAST_INVALID_INPUT)
             F2 ratio       unit_price = amount / units, real, rounded to 2, NULL when units = 0 (legacy: native division -
                            SQLite truncates, Spark raises DIVIDE_BY_ZERO - and no rounding)
             F3 latest      exactly the latest version per business key (legacy: no dedup)
             F4 replay      exactly-once after a crash: offset > committed checkpoint, one row per event id (legacy: neither)
             F5 fill        missing dimension values get the contract label (legacy: raw value)
             F6 watermark   events older than watermark - allowed lateness are excluded (legacy: no filter)
  untouched  F7 normalize   dimension codes arrive with stray case / whitespace; group / report on UPPER(TRIM(code))
             F8 tombstone   SCD-2 change feed: the latest record per key wins and keys whose latest change is a delete ('D')
                            are removed (legacy: latest record only)
A project has a primary family and k faults (k = 1..4: the primary + k-1 other compatible mechanisms), optionally plus
mechanisms that the legacy pipeline already implements correctly. Untouched families never appear in a project unless
explicitly allowed (only Stage 4 / panel builders allow them). Shapes: row-level, entity (latest per key), aggregate."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import shutil
import sqlite3
from pathlib import Path

from nexus.de_phase4 import ir

SOURCE_FAMS = ("F1", "F2", "F3", "F4", "F5", "F6")
UNTOUCHED_FAMS = ("F7", "F8")
FAM_NAME = dict(F1="parse", F2="ratio", F3="latest", F4="replay", F5="fill", F6="watermark", F7="normalize", F8="tombstone")
SHAPES = {"row": ("F1", "F2", "F4", "F5", "F6", "F7"), "entity": ("F1", "F2", "F3", "F6", "F8"),
          "agg": ("F1", "F4", "F5", "F6", "F7")}
POOLS = dict(units=["qty", "quantity", "units", "n_items"], price=["price", "unit_cost", "list_price"],
             amount=["amount", "gross", "total_value"], key=["order_id", "sku", "account_id"], ver=["version", "rev", "seq"],
             event=["event_id", "msg_id"], offset=["offset", "log_pos"], region=["region", "zone", "market"],
             ts=["event_ts", "ts", "recorded_at"], val=["value", "reading", "delta"], flag=["op", "change_type", "action"])
MALFORMED = ["n/a", "", "12x", "?", "1,5", "-", " "]


# ------------------------------------------------------------------ runtimes: execute pipeline TEXT on a real engine
class RunError(Exception):
    def __init__(self, cls, msg):
        super().__init__(msg)
        self.cls, self.msg = cls, msg


class SQLiteCode:
    name, lang = "sqlite", "sql"

    def run(self, code, header, rows, state):
        con = sqlite3.connect(":memory:")
        try:
            con.execute("CREATE TABLE raw (" + ", ".join(f'"{h}" TEXT' for h in header) + ', "__rowid" INTEGER)')
            con.executemany(f"INSERT INTO raw VALUES ({','.join('?' * (len(header) + 1))})",
                            [tuple(r[h] for h in header) + (i,) for i, r in enumerate(rows)])
            for fname, d in state.items():
                ks = list(d)
                con.execute(f'CREATE TABLE "state_{fname.rsplit(".", 1)[0]}" (' + ", ".join(f'"{k}"' for k in ks) + ")")
                con.execute(f'INSERT INTO "state_{fname.rsplit(".", 1)[0]}" VALUES ({",".join("?" * len(ks))})', [d[k] for k in ks])
            try:
                con.executescript(code)
                cur = con.execute("SELECT * FROM clean")
                names = [c[0] for c in cur.description]
                clean = [dict(zip(names, r)) for r in cur.fetchall()]
                rejects = None
                if con.execute("SELECT name FROM sqlite_master WHERE name = 'rejects'").fetchone():
                    cur = con.execute("SELECT * FROM rejects")
                    names = [c[0] for c in cur.description]
                    rejects = [dict(zip(names, r)) for r in cur.fetchall()]
            except sqlite3.Error as e:
                raise RunError(type(e).__name__, str(e)[:200])
            return dict(clean=clean, rejects=rejects)
        finally:
            con.close()


class SparkCode:
    """One persistent local SparkSession per worker process (local[2], 1 shuffle partition, whole-stage codegen and
    adaptive query execution off and the cached input batch on 1 partition for tiny batches - 17.9 vs 28.9 ms per script
    execution, artifacts/mi_logs/mi-agi4-s1-sparkbench-b2.log - UI off, ANSI on, driver bound to 127.0.0.1: the Phase 3 33 s
    start-up was the macOS hostname lookup)."""
    name, lang = "spark", "py"
    _spark, _dfs = None, {}

    @classmethod
    def session(cls):
        if cls._spark is None:
            os.environ["JAVA_HOME"] = "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
            os.environ["PATH"] = "/opt/homebrew/opt/openjdk@17/bin:" + os.environ.get("PATH", "")
            os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"
            quiet = Path(__file__).resolve().parents[3] / "config" / "log4j2-quiet.properties"
            os.environ["PYSPARK_SUBMIT_ARGS"] = f"--driver-java-options -Dlog4j2.configurationFile={quiet} pyspark-shell"
            import logging
            for lg in ("SQLQueryContextLogger", "DataFrameQueryContextLogger", "PySparkLogger", "pyspark", "py4j"):
                logging.getLogger(lg).disabled = True       # pyspark's Python-side structured error logs (stderr noise)
            from pyspark.sql import SparkSession
            s = (SparkSession.builder.master("local[2]").appName("nexus-phase4").config("spark.ui.enabled", "false")
                 .config("spark.driver.host", "127.0.0.1").config("spark.driver.bindAddress", "127.0.0.1")
                 .config("spark.sql.shuffle.partitions", "1").config("spark.sql.ansi.enabled", "true")
                 .config("spark.sql.codegen.wholeStage", "false").config("spark.sql.adaptive.enabled", "false")
                 .config("spark.driver.memory", "1g")
                 .config("spark.log.structuredLogging.enabled", "false").getOrCreate())
            s.sparkContext.setLogLevel("OFF")
            cls._spark = s
        return cls._spark

    @classmethod
    def warm(cls):
        cls.session().sql("SELECT 1").collect()

    def _raw(self, header, rows):
        key = hashlib.sha1(json.dumps([header, [[r[h] for h in header] for r in rows]]).encode()).hexdigest()
        if key not in self._dfs:
            if len(self._dfs) > 256:
                self._dfs.clear()
            s = self.session()
            schema = ", ".join(f"`{h}` string" for h in header) + ", `__rowid` int"
            df = s.createDataFrame([tuple(r[h] for h in header) + (i,) for i, r in enumerate(rows)], schema=schema).coalesce(1)
            self._dfs[key] = df.cache()
        return self._dfs[key]

    def run(self, code, header, rows, state):
        s = self.session()
        raw = self._raw(header, rows)
        ns = {}
        try:
            exec(compile(code, "pipeline.py", "exec"), ns)              # noqa: S102  (the project's own pipeline script)
            res = ns["run"](s, raw, json.loads(json.dumps(state)))
            clean = [r.asDict() for r in res["clean"].collect()]
            rejects = [r.asDict() for r in res["rejects"].collect()] if res.get("rejects") is not None else None
        except Exception as e:                                            # noqa: BLE001
            cls = getattr(e, "getCondition", lambda: None)() or type(e).__name__
            raise RunError(str(cls), str(e).split("\n")[0][:200])
        return dict(clean=clean, rejects=rejects)


RUNTIMES = {"sqlite": SQLiteCode, "spark": SparkCode}
LANG = {"sqlite": "sql", "spark": "py"}


# ------------------------------------------------------------------ batches / tables
def read_csv(path):
    with open(path, newline="") as fh:
        r = csv.reader(fh)
        header = next(r)
        return header, [dict(zip(header, row)) for row in r]


def write_csv(path, header, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow([r[h] for h in header])


def state_of(ws):
    out = {}
    for p in sorted(Path(ws).glob("*.json")):
        if p.name != "contract.json":
            out[p.name] = json.loads(p.read_text())
    return out


def num(v):
    """Reals compare at 6 decimals: an unrounded 3.3333 is NOT the contract's 3.33 (Phase 3 compared at 2 decimals, which
    hid missing ROUND repairs on the visible batch)."""
    return round(v, 6) if isinstance(v, float) else v


def table_key(rows, cols):
    return sorted((tuple(num(r.get(c)) for c in cols) for r in rows), key=repr)


# ------------------------------------------------------------------ the independent evaluator
def evaluate(project, code, runtime=None):
    """Run the submitted pipeline TEXT on the project's engine over both hidden batches; compare with the reference."""
    rt = runtime or RUNTIMES[project["runtime"]]()
    hid = Path(project["hidden_dir"])
    fails = []
    for b in ("hidden1.csv", "hidden2.csv"):
        header, rows = read_csv(hid / b)
        state = dict(state_of(project["ws"]), **project["hidden_state"][b])
        try:
            res = rt.run(code, header, rows, state)
        except RunError as e:
            fails.append(f"{b}: runtime {e.cls}")
            continue
        ref = json.loads((hid / (b + ".expected.json")).read_text())
        cols = ref["output_cols"]
        if table_key(res["clean"], cols) != table_key([dict(zip(cols, r)) for r in ref["output"]], cols):
            fails.append(f"{b}: output differs")
        if ref.get("quarantine_ids") is not None:
            got = sorted(str(r.get("id")) for r in (res.get("rejects") or []))
            if got != sorted(ref["quarantine_ids"]):
                fails.append(f"{b}: quarantine differs")
    return dict(ok=not fails, fails=fails, kind="hidden_batches_on_engine")


# ------------------------------------------------------------------ business-truth / legacy specs from mechanisms
def build(shape, faults, oks, nm, params):
    """(truth, legacy) specs. faults: mechanisms the legacy pipeline gets wrong; oks: mechanisms it already gets right."""
    has = set(faults) | set(oks)
    T, Lg = dict(outputs=[]), dict(outputs=[])

    def both(fam, good, bad):
        return good, (bad if fam in faults else good)

    def typed(col, parse_col):
        c = ["col", col]
        if "F1" in has and parse_col == col:
            if params["policy"] == "quarantine":
                return both("F1", ["try_int", c], ["cast_int", c])
            return both("F1", ["coalesce", ["try_int", c], ["lit", 0]], ["cast_int", c])
        return ["cast_int", c], ["cast_int", c]

    def region_expr():
        t = l = ["col", nm["region"]]
        if "F7" in has:
            t, l = ["norm_text", t], (l if "F7" in faults else ["norm_text", l])
        if "F5" in has:
            t2 = ["coalesce", ["nullif_empty", t], ["lit", params["label"]]]
            l = l if "F5" in faults else ["coalesce", ["nullif_empty", l], ["lit", params["label"]]]
            t = t2
        return t, l

    pc = params.get("parse_col")
    # stage 1 / 2: row identity and selection
    filt_t, filt_l = [], []
    if shape == "entity":
        dd = dict(key=nm["key"], order=["cast_int", ["col", nm["ver"]]])
        T["dedup"] = dd
        if "F3" not in faults:
            Lg["dedup"] = dict(dd)
        if "F8" in has:
            f = ["ne", ["col", nm["flag"]], ["lit", "D"]]
            filt_t.append(f)
            if "F8" not in faults:
                filt_l.append(f)
    if "F4" in has:
        T["dedup"] = dict(key=nm["event"])
        f = ["gt", ["cast_int", ["col", nm["offset"]]], ["file", "checkpoint.json", "last_committed_offset"]]
        filt_t.append(f)
        if "F4" not in faults:
            Lg["dedup"] = dict(key=nm["event"])
            filt_l.append(f)
    if "F6" in has:
        f = ["ge", ["cast_int", ["col", nm["ts"]]], ["sub", ["file", "watermark.json", "watermark"],
                                                     ["file", "watermark.json", "allowed_lateness"]]]
        filt_t.append(f)
        if "F6" not in faults:
            filt_l.append(f)
    for spec, fs in ((T, filt_t), (Lg, filt_l)):
        if fs:
            spec["filter"] = _and_all(fs)
    if "F1" in has and params["policy"] == "quarantine":
        q = ["not", ["valid_int", ["col", pc]]]
        T["quarantine"] = q
        if "F1" not in faults:
            Lg["quarantine"] = q
    # stage 3: outputs
    if shape == "row":
        ut, ul = typed(nm["units"], pc)
        pt, pl = typed(nm["price"], pc)
        for spec, u, p in ((T, ut, pt), (Lg, ul, pl)):
            spec["outputs"].append(["id", ["col", "id"]])
            spec["outputs"].append([nm["units"], u])
        if "F2" in has:
            at = ["cast_int", ["col", nm["amount"]]]
            T["outputs"].append(["unit_price", ["round2", ["div_real", at, ["nullif_zero", ut]]]])
            Lg["outputs"].append(["unit_price", ["div", at, ul] if "F2" in faults else ["round2", ["div_real", at, ["nullif_zero", ul]]]])
        else:
            T["outputs"].append(["line_total", ["mul", pt, ut]])
            Lg["outputs"].append(["line_total", ["mul", pl, ul]])
        if "F5" in has or "F7" in has:
            rt_, rl_ = region_expr()
            T["outputs"].append([nm["region"], rt_])
            Lg["outputs"].append([nm["region"], rl_])
    elif shape == "entity":
        pt, pl = typed(nm["price"], pc)
        for spec, p in ((T, pt), (Lg, pl)):
            spec["outputs"] += [[nm["key"], ["col", nm["key"]]], [nm["ver"], ["cast_int", ["col", nm["ver"]]]], [nm["price"], p]]
        if "F2" in has:
            at, ut = ["cast_int", ["col", nm["amount"]]], ["cast_int", ["col", nm["units"]]]
            T["outputs"].append(["unit_price", ["round2", ["div_real", at, ["nullif_zero", ut]]]])
            Lg["outputs"].append(["unit_price", ["div", at, ut] if "F2" in faults else ["round2", ["div_real", at, ["nullif_zero", ut]]]])
    else:
        vt, vl = typed(nm["val"], pc)
        if "F5" in has or "F7" in has:
            gt_, gl_ = region_expr()
            T["group"], Lg["group"] = [nm["region"], gt_], [nm["region"], gl_]
        else:
            T["group"], Lg["group"] = [nm["key"], ["col", nm["key"]]], [nm["key"], ["col", nm["key"]]]
        T["outputs"].append(["total", vt])
        Lg["outputs"].append(["total", vl])
    return T, Lg


def _and_all(fs):
    out = None
    for f in fs:
        out = f if out is None else ["and", out, f]
    return out


def gen_rows(shape, has, rng, n, nm, params, bad_p):
    regions = ["EU", "US", "APAC"]
    rows = []
    if shape == "entity":
        keys = [f"k{j}" for j in range(max(3, n // 3))]
        seen = set()
        for i in range(n * 2):
            if len(rows) >= n:
                break
            k, v = rng.choice(keys), rng.randint(1, 9)
            if (k, v) in seen:
                continue
            seen.add((k, v))
            rows.append({"id": f"r{i}", nm["key"]: k, nm["ver"]: str(v), nm["price"]: str(rng.randint(1, 50))})
    else:
        for i in range(n):
            rows.append({"id": f"r{i}"})
    for i, r in enumerate(rows):
        if shape == "row" or (shape == "entity" and "F2" in has):
            r[nm["units"]] = str(rng.randint(0, 9) if "F2" in has else rng.randint(1, 20))
            r[nm["amount"]] = str(rng.randint(0, 200))
            if shape == "row":
                r[nm["price"]] = str(rng.randint(1, 50))
        if shape == "agg":
            r[nm["val"]] = str(rng.randint(1, 9))
            r[nm["key"]] = rng.choice(["a", "b", "c"])
        if shape != "entity" and ("F5" in has or "F7" in has):
            reg = rng.choice(regions)
            if "F7" in has and rng.random() < 0.45:
                reg = rng.choice([reg.lower(), f" {reg}", f"{reg} ", reg.capitalize(), f" {reg.lower()} "])
            if "F5" in has and rng.random() < 0.25:
                reg = rng.choice(["", " "])
            r[nm["region"]] = reg
        if "F4" in has:
            r[nm["event"]], r[nm["offset"]] = f"e{i}", str(i + 1)
        if "F6" in has:
            r[nm["ts"]] = str(100 + 3 * i + rng.randint(-8, 2))
        if "F8" in has:
            r[nm["flag"]] = rng.choice(["U", "U", "D"])
    if "F1" in has:
        pc = params["parse_col"]
        for r in rows:
            if rng.random() < bad_p:
                r[pc] = rng.choice(MALFORMED)
    if "F4" in has:                                   # replay after a crash: a block of events lands twice
        dup = rows[n // 3: n // 3 + max(2, n // 4)]
        rows = rows + [dict(r) for r in dup]
    return rows


def notes(shape, has, nm, params):
    out = []
    if "F1" in has:
        out.append(f"{params['parse_col']} must be an integer; malformed values " +
                   ("are rejected to the quarantine table" if params["policy"] == "quarantine" else "count as 0"))
    if "F2" in has:
        out.append("unit_price = amount / units as a real number rounded to 2 decimals; NULL when units is 0")
    if shape == "entity":
        out.append(f"exactly one row per {nm['key']}: the latest {nm['ver']}")
    if "F4" in has:
        out.append("after recovery every event is counted exactly once; events at or before the committed offset are done")
    if "F5" in has:
        out.append(f"missing {nm['region']} values get the label {params['label']}")
    if "F6" in has:
        out.append(f"events older than the watermark minus the allowed lateness are late and excluded")
    if "F7" in has:
        out.append(f"{nm['region']} codes are case- and whitespace-insensitive and reported upper-case")
    if "F8" in has:
        out.append(f"a key whose latest change has {nm['flag']} = 'D' was deleted and must not appear")
    return out


def _types(rows, cols):
    t = {}
    for c in cols:
        v = next((r.get(c) for r in rows if r.get(c) is not None), None)
        t[c] = "real" if isinstance(v, float) else "int" if isinstance(v, int) else "text"
    return t


# ------------------------------------------------------------------ project builder
def make_project(fam, k, seed, runtime, root, allowed=SOURCE_FAMS):
    for attempt in range(60):
        p = _make(fam, k, seed, runtime, root, attempt, allowed)
        if p is not None:
            return p
    raise RuntimeError(f"could not build an identifiable project {fam} k{k} {seed}")


def _make(fam, k, seed, runtime, root, attempt, allowed):
    if fam not in allowed:
        raise ValueError(f"family {fam} not allowed here")
    rng = random.Random(f"p4de|{fam}|{k}|{seed}|{runtime}|{attempt}")
    shape = rng.choice([s for s, fs in SHAPES.items() if fam in fs])
    others = [f for f in SHAPES[shape] if f != fam and f in allowed and f not in UNTOUCHED_FAMS]
    if fam == "F8":
        others = [f for f in others if f != "F4"]
    if len(others) < k - 1:
        return None
    faults = [fam] + rng.sample(others, k - 1)
    if "F3" in faults and "F4" in faults:
        return None
    rest = [f for f in others if f not in faults and not (f == "F4" and shape == "entity")]
    oks = [f for f in rest if rng.random() < 0.25]
    has = set(faults) | set(oks)
    nm = {c: rng.choice(v) for c, v in POOLS.items()}
    params = dict(policy=rng.choice(["quarantine", "default"]), label=rng.choice(["UNKNOWN", "OTHER"]), lateness=rng.choice([5, 10]))
    params["parse_col"] = {"row": rng.choice([nm["units"], nm["price"]]), "entity": nm["price"], "agg": nm["val"]}[shape]
    truth, legacy = build(shape, faults, oks, nm, params)
    pid = f"{fam}.k{k}.{runtime}.{seed}"
    ws, hid = Path(root) / pid / "workspace", Path(root) / pid / "hidden"
    for d in (ws.parent,):
        if d.exists():
            shutil.rmtree(d)
    (ws / "data").mkdir(parents=True)
    hid.mkdir(parents=True)
    n = rng.randint(12, 18)
    batches = {"visible.csv": gen_rows(shape, has, rng, n, nm, params, 0.25),
               "hidden1.csv": gen_rows(shape, has, rng, n + 8, nm, params, 0.3),
               "hidden2.csv": gen_rows(shape, has, rng, n + 14, nm, params, 0.3)}
    states = {}
    for b, rows in batches.items():
        st = {}
        if "F4" in has:
            st["checkpoint.json"] = {"last_committed_offset": rng.randint(2, max(3, len(rows) // 3))}
        if "F6" in has:
            st["watermark.json"] = {"watermark": 100 + 3 * len(rows) // 2 + rng.randint(-2, 2), "allowed_lateness": params["lateness"]}
        states[b] = st
    header = list(batches["visible.csv"][0].keys())
    try:
        refs = {b: ir.interpret(truth, rows, states[b]) for b, rows in batches.items()}
    except ir.RefError:
        return None
    cols = ir.out_cols(truth)
    vis = refs["visible.csv"]
    if len(vis["clean"]) < 2:
        return None
    # per-fault identifiability on the real SQLite engine: reverting ANY single fault changes the visible result
    sq = SQLiteCode()
    want = (table_key(vis["clean"], cols), sorted(r["id"] for r in vis["rejects"]) if vis["rejects"] is not None else None)

    def visible_result(spec):
        try:
            res = sq.run(ir.lower_sql(spec), header, batches["visible.csv"], states["visible.csv"])
        except RunError:
            return "error"
        return (table_key(res["clean"], cols), sorted(str(r["id"]) for r in res["rejects"]) if res["rejects"] is not None else None)
    if visible_result(truth) != want:                  # the business truth runs identically on the engine
        return None
    for f in faults:
        _, one = build(shape, [f], [x for x in has if x != f], nm, params)
        if visible_result(one) == want:
            return None
    # write the workspace
    write_csv(ws / "data" / "visible.csv", header, batches["visible.csv"])
    for fname, d in states["visible.csv"].items():
        (ws / fname).write_text(json.dumps(d))
    hidden_state = {}
    for b in ("hidden1.csv", "hidden2.csv"):
        write_csv(hid / b, header, batches[b])
        r = refs[b]
        (hid / (b + ".expected.json")).write_text(json.dumps(dict(
            output=[[row[c] for c in cols] for row in r["clean"]], output_cols=cols,
            quarantine_ids=sorted(x["id"] for x in r["rejects"]) if r["rejects"] is not None else None)))
        hidden_state[b] = states[b]
    unique = {"row": "id", "entity": nm["key"], "agg": cols[0]}[shape]
    checks = [dict(kind="no_error"), dict(kind="example_rows", cols=cols, rows=[[row[c] for c in cols] for row in vis["clean"]]),
              dict(kind="row_count", n=len(vis["clean"])), dict(kind="unique", col=unique)]
    if vis["rejects"] is not None:
        checks.append(dict(kind="quarantine_ids", id="id", ids=sorted(x["id"] for x in vis["rejects"])))
    lang = LANG[runtime]
    contract = dict(output_table="clean", quarantine_table="rejects" if vis["rejects"] is not None else None, output_cols=cols,
                    output_types=_types(vis["clean"], cols), unique_key=unique, runtime=runtime, pipeline_file=f"pipeline.{lang}",
                    engine_semantics="Apache Spark 4.0.1, spark.sql.ansi.enabled=true" if runtime == "spark" else "SQLite 3",
                    public_checks=checks, notes=notes(shape, has, nm, params))
    style_rng = random.Random(f"style|{pid}")
    hdr = ["legacy pipeline (owner: data platform)"] + (["TODO: verify against the contract"] if style_rng.random() < 0.5 else [])
    if lang == "sql":
        style = dict(kw=style_rng.choice(["upper", "lower"]), comments=style_rng.random() < 0.7, header=hdr,
                     views=style_rng.choice([("stage1", "stage2"), ("s1_dedup", "s2_select"), ("v_identity", "v_rows")]))
    else:
        style = dict(names=style_rng.choice([("stage1", "stage2", "kept"), ("deduped", "selected", "valid"), ("df1", "df2", "df3")]),
                     comments=style_rng.random() < 0.7, header=hdr, where=style_rng.choice(["filter", "where"]))
    (ws / f"pipeline.{lang}").write_text(ir.lower(legacy, lang, style))
    (ws / "contract.json").write_text(json.dumps(contract, indent=1))
    (ws / "README.md").write_text(f"Goal: repair pipeline.{lang} so it satisfies contract.json on {contract['engine_semantics']}.\n")
    return dict(pid=pid, family=fam, k=k, faults=faults, oks=oks, shape=shape, seed=seed, runtime=runtime, lang=lang, ws=str(ws),
                hidden_dir=str(hid), hidden_state=hidden_state, params=params, names=nm)
