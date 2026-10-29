"""Phase 4 Stage 1 Spark feasibility probe (NOT LOCKED; no project data): session start-up with the driver bound to
127.0.0.1 (macOS hostname-lookup delay) versus the Phase 3 33 s, per-execution cost of a small PySpark DataFrame script with
whole-stage codegen on / off, and the Spark 4 API used by the Phase 4 adapter (Column.try_cast, F.try_divide, F.nullif)."""
import os, sys, time
T0 = time.time()
os.environ["JAVA_HOME"] = "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
os.environ["PATH"] = "/opt/homebrew/opt/openjdk@17/bin:" + os.environ["PATH"]
os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"
from pathlib import Path
quiet = Path(__file__).resolve().parents[1] / "config" / "log4j2-quiet.properties"
os.environ["PYSPARK_SUBMIT_ARGS"] = f"--driver-java-options -Dlog4j2.configurationFile={quiet} pyspark-shell"
import logging
logging.getLogger("SQLQueryContextLogger").disabled = True
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window
t_imp = time.time() - T0
s = (SparkSession.builder.master("local[2]").appName("agi4-probe").config("spark.ui.enabled", "false")
     .config("spark.driver.host", "127.0.0.1").config("spark.driver.bindAddress", "127.0.0.1")
     .config("spark.sql.shuffle.partitions", "1").config("spark.sql.ansi.enabled", "true").config("spark.driver.memory", "1g")
     .config("spark.log.structuredLogging.enabled", "false").getOrCreate())
s.sparkContext.setLogLevel("OFF")
t_sess = time.time() - T0
s.sql("SELECT 1").collect()
t_first = time.time() - T0
rows = [(f"r{i}", str(i % 7), str(i % 5), "EU" if i % 2 else " eu", str(100 + i)) for i in range(16)]
raw = s.createDataFrame([r + (i,) for i, r in enumerate(rows)], "id string, qty string, price string, region string, ts string, __rowid int")
raw.cache().count()
def job():
    w = Window.partitionBy("region").orderBy(F.col("ts").cast("int").desc())
    s1 = raw.withColumn("__rn", F.row_number().over(w)).filter(F.col("__rn") == 1).drop("__rn")
    s2 = s1.filter(F.col("ts").cast("int") >= F.lit(100))
    out = s2.groupBy(F.upper(F.trim(F.col("region"))).alias("region")).agg(
        F.sum(F.round(F.try_divide(F.trim(F.col("price")).try_cast("int"), F.nullif(F.col("qty").cast("int"), F.lit(0))), 2)).alias("t"))
    return out.collect()
res = {}
for mode in ("codegen_on", "codegen_off"):
    if mode == "codegen_off":
        s.conf.set("spark.sql.codegen.wholeStage", "false")
    job()
    t = time.time()
    for _ in range(20):
        job()
    res[mode] = round((time.time() - t) / 20 * 1000, 1)
print(dict(import_s=round(t_imp, 1), session_s=round(t_sess, 1), first_query_s=round(t_first, 1), ms_per_script_exec=res,
           try_cast=hasattr(F.col("x"), "try_cast"), try_divide=hasattr(F, "try_divide"), nullif=hasattr(F, "nullif"), out=job()[:2]))
