"""Phase 11 Stage 1: engine-semantics probe (NOT LOCKED; development fixtures only). python scripts/agi11_engine_probe.py OUT.json
Records how DuckDB and SQLite actually behave on the edge cases the Phase 11 core must define before freezing its semantics."""
import json, sqlite3, sys
import duckdb
Q = {"div0_double": "SELECT CAST(1 AS DOUBLE) / 0", "div0_int": "SELECT 1 / 0", "intdiv0": "SELECT 1 // 0", "mod0": "SELECT 5 % 0",
     "int_div_type": "SELECT 7 / 2", "json_num": """SELECT json_extract_string('{"a": 1.50}', '$.a')""", "json_exp": """SELECT json_extract_string('{"a": 1e3}', '$.a')""",
     "json_str": """SELECT json_extract_string('{"a": "x"}', '$.a')""", "json_bool": """SELECT json_extract_string('{"a": true}', '$.a')""",
     "json_obj": """SELECT json_extract_string('{"a": {"b": 1}}', '$.a')""", "json_missing": """SELECT json_extract_string('{"a": 1}', '$.b')""",
     "json_null": """SELECT json_extract_string('{"a": null}', '$.a')""", "json_valid_bad": "SELECT json_valid('{bad')", "regex": "SELECT regexp_full_match('-12', '[+-]?[0-9]+')",
     "cast_big": "SELECT CAST('99999999999999999999' AS BIGINT)", "overflow": "SELECT CAST(9223372036854775807 AS BIGINT) + 1",
     "sum_type": "SELECT typeof(SUM(x)) FROM (VALUES (1::BIGINT)) t(x)", "null_order": "SELECT x FROM (VALUES (2),(NULL),(1)) t(x) ORDER BY x DESC"}
out = {"duckdb_version": duckdb.__version__, "sqlite_version": sqlite3.sqlite_version, "duckdb": {}, "sqlite": {}}
for k, q in Q.items():
    try:
        out["duckdb"][k] = repr(duckdb.sql(q).fetchall())
    except Exception as e:
        out["duckdb"][k] = f"ERROR {type(e).__name__}: {str(e)[:80]}"
S = {"div0": "SELECT 1.0 / 0", "intdiv": "SELECT 7 / 2", "json_num": """SELECT json_extract('{"a": 1.50}', '$.a')""", "json_text": """SELECT CAST(json_extract('{"a": 1.50}', '$.a') AS TEXT)""",
     "json_bad": "SELECT json_valid('{bad')", "null_order": "SELECT x FROM (SELECT 2 x UNION ALL SELECT NULL UNION ALL SELECT 1) ORDER BY x DESC NULLS LAST",
     "window": "SELECT x, ROW_NUMBER() OVER (ORDER BY x) FROM (SELECT 2 x UNION ALL SELECT 1)"}
c = sqlite3.connect(":memory:")
for k, q in S.items():
    try:
        out["sqlite"][k] = repr(c.execute(q).fetchall())
    except Exception as e:
        out["sqlite"][k] = f"ERROR {type(e).__name__}: {str(e)[:80]}"
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps(out, indent=1))
