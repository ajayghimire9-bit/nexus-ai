"""Phase 4 Stage 1 Spark execution-cost benchmark (NOT LOCKED; one dev project): ms per pipeline-script execution under
session settings for tiny batches. python scripts/agi4_spark_bench.py MASTER"""
import json, sys, time
from nexus.de_phase4 import world as W, ir, adapter as A
master = sys.argv[1]
p = W.make_project("F4", 2, 53620, "spark", "var/agi4_ws/dev")
text, lang, spec = A.read_pipeline(p["ws"])
header, rows = W.read_csv(p["ws"] + "/data/visible.csv")
state = W.state_of(p["ws"])
code = ir.lower(spec, "py")
src = W.SparkCode.session.__func__
W.SparkCode._spark = None
import os
from pyspark.sql import SparkSession
os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"
rt = W.SparkCode()
t = time.time()
s = W.SparkCode.session()
if master != "local[2]":
    s.stop()
    W.SparkCode._spark = (SparkSession.builder.master(master).appName("bench").config("spark.ui.enabled", "false")
                          .config("spark.driver.host", "127.0.0.1").config("spark.driver.bindAddress", "127.0.0.1")
                          .config("spark.sql.shuffle.partitions", "1").config("spark.sql.ansi.enabled", "true")
                          .config("spark.sql.codegen.wholeStage", "false").getOrCreate())
s = W.SparkCode.session()
start = time.time() - t
fixed = ir.lower(dict(spec, outputs=[[n, ["try_int", x[1]] if x[0] == "cast_int" else x] for n, x in spec["outputs"]]), "py")


def one(c):
    try:
        rt.run(c, header, rows, state)
    except W.RunError:
        pass


def bench(n=20):
    W.SparkCode._dfs.clear()
    one(code), one(fixed)
    t = time.time()
    for _ in range(n):
        one(code)
        one(fixed)
    return round((time.time() - t) / (2 * n) * 1000, 1)
res = dict(master=master, session_s=round(start, 2), default=bench())
s.conf.set("spark.sql.adaptive.enabled", "false")
res["aqe_off"] = bench()
orig = W.SparkCode._raw
def raw1(self, header, rows):
    key = ("c1", len(rows), json.dumps([[r[h] for h in header] for r in rows]))
    if key not in self._dfs:
        sch = ", ".join(f"`{h}` string" for h in header) + ", `__rowid` int"
        self._dfs[key] = self.session().createDataFrame([tuple(r[h] for h in header) + (i,) for i, r in enumerate(rows)], sch).coalesce(1).cache()
    return self._dfs[key]
W.SparkCode._raw = raw1
res["aqe_off_coalesce1"] = bench()
s.conf.set("spark.sql.optimizer.excludedRules", "")
print(json.dumps(res))
