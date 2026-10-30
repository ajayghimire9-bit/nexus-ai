"""Phase 10D out-of-sandbox DAG IR (NOT LOCKED): multi-table, 3-node stg_ -> int_ -> fct_ pipelines.

SPEC = dict(stg={rel: tspec}, int=ispec, fct=fspec)                (one spec per DAG node; rel names are stg_<table>)
  tspec  dict(src, cols=[[name, expr]], pre=[cond], dedup=None | dict(key=expr, order=expr, desc=True), post=[cond], latest_as=None | rel)
         rows -> projection -> pre filters -> latest-per-key dedup (QUALIFY ROW_NUMBER() ... ORDER BY order DESC = 1) ->
         [latest_as: the deduplicated relation incl. tombstones] -> post filters
  ispec  dict(base, base_cols=[names], joins=[jspec], out=[[name, expr]])
         jspec dict(rel, how=left | inner | asof, lkey=expr(base), rkey=expr(rel row), agg=None | dict(by, measures=[[m, agg, expr]]),
                    take=[[outname, relcol]], by=None | [basecol, relcol] (asof equality), strategy=backward | forward (asof))
         agg = the child is PRE-AGGREGATED to the join key grain before joining (1-to-many fan-out guard)
  fspec  dict(src, group=[[name, expr]], measures=[[name, agg, expr]], merge=None | dict(key, update, delete, deletes=dict(rel, key, minus)))
         deleted keys = keys of `rel` (latest version per key, incl. tombstones) MINUS keys of `minus` (the active relation)
         MERGE INTO fct_target USING (fct_src minus deleted keys + delete rows) ON key
           WHEN MATCHED AND op = 'd' THEN DELETE (delete) / WHEN MATCHED THEN UPDATE (update) / WHEN NOT MATCHED AND op <> 'd' THEN INSERT
         merge None = full overwrite (fct_out = fct_src)
expr   ["col", c] ["lit", v] ["try_int", e] ["json", payload_col, "after.k"] ["coalesce", a, b] ["ne", a, b] ["eq", a, b] ["notnull", e]
agg    sum | count | max (SQL NULL semantics: sum / max of no non-null value is NULL; count counts non-null)
Values are text as landed (CSV); JSON scalars are extracted as TEXT in every engine; try_int trims and parses digits only.
Engine lowerings (DuckDB 1.1.3 SQL with QUALIFY, SQLite 3.50 SQL, Polars 2.1 LazyFrame code, PySpark 4.0.1 DataFrame code) and
legacy languages (Snowflake / Postgres / Hive SQL with MERGE INTO, dbt Jinja models, Scala Spark) live in engines10d / legacy10d."""
from __future__ import annotations

import json
import re

NODES = ("stg", "int", "fct")


def try_int(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s) if re.fullmatch(r"[0-9]+", s) else None


def json_get(s, path):
    if s is None:
        return None
    try:
        d = json.loads(s)
    except (ValueError, TypeError):
        return None
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    if d is None or isinstance(d, (dict, list)):
        return None
    return str(d) if not isinstance(d, str) else d


def ev(e, row):
    op = e[0]
    if op == "col":
        return row.get(e[1])
    if op == "lit":
        return e[1]
    if op == "try_int":
        return try_int(ev(e[1], row))
    if op == "json":
        return json_get(row.get(e[1]), e[2])
    if op == "coalesce":
        v = ev(e[1], row)
        return v if v is not None else ev(e[2], row)
    if op in ("ne", "eq"):
        a, b = ev(e[1], row), ev(e[2], row)
        if a is None or b is None:
            return None
        return (a != b) if op == "ne" else (a == b)
    if op == "notnull":
        return ev(e[1], row) is not None
    raise ValueError(f"unknown expression {op}")


def cols_of(e):
    if e[0] == "col":
        return {e[1]}
    if e[0] == "json":
        return {e[1]}
    return set().union(*[cols_of(x) for x in e[1:] if isinstance(x, list)]) if len(e) > 1 else set()


def agg(kind, vals):
    vs = [v for v in vals if v is not None]
    if kind == "count":
        return len(vs)
    if not vs:
        return None
    return sum(vs) if kind == "sum" else max(vs)


# ------------------------------------------------------------------ reference interpreter
def run_stg(t, tables, R):
    rows = [{n: ev(x, r) for n, x in t["cols"]} for r in tables[t["src"]]]
    rows = [r for r in rows if all(ev(c, r) is True for c in t.get("pre", []))]
    if t.get("dedup"):
        best = {}
        for r in rows:
            k = ev(t["dedup"]["key"], r)
            o = ev(t["dedup"]["order"], r)
            desc = t["dedup"].get("desc", True)
            if k not in best or (o is not None and (best[k][0] is None or (o > best[k][0] if desc else o < best[k][0]))):
                best[k] = (o, r)
        rows = [r for _, r in best.values()]
    if t.get("latest_as"):
        R[t["latest_as"]] = list(rows)
    return [r for r in rows if all(ev(c, r) is True for c in t.get("post", []))]


def run_int(s, R):
    base = [{c: r.get(c) for c in s["base_cols"]} for r in R[s["base"]]]
    for j in s["joins"]:
        rel = R[j["rel"]]
        if j.get("agg"):
            groups = {}
            for r in rel:
                groups.setdefault(r.get(j["agg"]["by"]), []).append(r)
            rel = [dict({j["agg"]["by"]: k}, **{m: agg(a, [ev(x, r) for r in rs]) for m, a, x in j["agg"]["measures"]}) for k, rs in groups.items()]
        out = []
        for b in base:
            if j["how"] == "asof":
                cands = [r for r in rel if r.get(j["by"][1]) == b.get(j["by"][0]) and ev(j["rkey"], r) is not None and ev(j["lkey"], b) is not None and
                         (ev(j["rkey"], r) <= ev(j["lkey"], b) if j.get("strategy", "backward") == "backward" else ev(j["rkey"], r) >= ev(j["lkey"], b))]
                m = sorted(cands, key=lambda r: ev(j["rkey"], r), reverse=j.get("strategy", "backward") == "backward")[:1]
            else:
                lk = ev(j["lkey"], b)
                m = [r for r in rel if lk is not None and ev(j["rkey"], r) == lk]
            if not m and j["how"] == "inner":
                continue
            for r in (m or [None]):
                out.append(dict(b, **{o: (r.get(c) if r else None) for o, c in j["take"]}))
        base = out
    return [{n: ev(x, r) for n, x in s["out"]} for r in base]


def merge(f, src, R, target):
    m = f["merge"]
    key = m["key"]
    D = set()
    if m.get("deletes"):
        d = m["deletes"]
        D = {ev(d["key"], r) for r in R[d["rel"]]} - {ev(d["key"], r) for r in R[d["minus"]]} - {None}      # soft-delete detection (anti-join)
    S = {r[key]: r for r in src if r[key] is not None and r[key] not in D}
    T = {r[key]: dict(r) for r in target}
    names = [n for n, _ in f["group"]] + [n for n, _, _ in f["measures"]]
    out = {}
    for k, t in T.items():
        if k in D:
            if m["delete"]:
                continue
            out[k] = {n: (k if n == key else None) for n in names} if m["update"] else t
        elif k in S:
            out[k] = S[k] if m["update"] else t
        else:
            out[k] = t
    for k, s in S.items():
        if k not in T:
            out[k] = s
    return list(out.values())


def run_fct(f, R, target):
    groups = {}
    for r in R[f["src"]]:
        groups.setdefault(tuple(ev(x, r) for _, x in f["group"]), []).append(r)
    src = [dict({n: k[i] for i, (n, _) in enumerate(f["group"])}, **{m: agg(a, [ev(x, r) for r in rs]) for m, a, x in f["measures"]}) for k, rs in groups.items()]
    R["fct_src"] = src
    return merge(f, src, R, target) if f.get("merge") else [dict(r) for r in src]


def interpret(spec, tables, state):
    """All relations of the DAG: stg_*, *_latest, int_orders, fct_src, fct_out."""
    R = dict(tables)
    for name, t in spec["stg"].items():
        R[name] = run_stg(t, tables, R)
    R["int_orders"] = run_int(spec["int"], R)
    R["fct_out"] = run_fct(spec["fct"], R, state.get("fct_target", []))
    return R


def node_outputs(spec):
    return dict(stg=sorted(spec["stg"]) + sorted(t["latest_as"] for t in spec["stg"].values() if t.get("latest_as")), int=["int_orders"], fct=["fct_out"])


# ------------------------------------------------------------------ canonical comparison
def canon(v):
    if v is None or v == "":
        return None if v is None else ""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, (int, float)):
        return v
    try:
        return int(str(v)) if re.fullmatch(r"-?[0-9]+", str(v)) else str(v)
    except ValueError:
        return str(v)


def table_key(rows, cols):
    return sorted(json.dumps([canon(r.get(c)) for c in cols], default=str) for r in rows)
