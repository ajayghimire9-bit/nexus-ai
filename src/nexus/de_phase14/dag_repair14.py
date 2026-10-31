"""Phase 14 multi-node DAG fault localisation and node-only repair (NOT LOCKED; engineering machinery, not NEXUS learning).

WHAT THIS MODULE DOES
  0  NATIVE SOURCES      lift_sources builds a DAG from per-stage NATIVE source text: SQL in the sqlite / duckdb / spark dialects
                         (multi_engine14.from_sql) or Polars / PySpark method chains (multi_engine14.from_dataframe; parsed, never
                         executed). source_fidelity runs every ORIGINAL stage source natively on its own engine and compares it with
                         core11 on the lifted AST. It is FAIL-CLOSED: 'disagree' / 'core_error' -> unfaithful; 'unavailable' /
                         'native_error' / 'unsupported' / 'unchecked' -> unverified. repair_dag never lifts an unverified DAG.
                         native_fidelity (= _fidelity) merges it with the Phase 13 SQLite parse fidelity; compile_dag compiles a
                         (repaired) DAG back to any SQL dialect.
  1  DAG VIEW            dag_info reads a layered pipeline (stg_ -> int_ -> fct_; pipeline_lifter13.Pipeline stages in topological
                         order): dependencies, base sources, layers, downstream closures, sinks, and convention violations (order,
                         layer inversion, stg_ reading a model). Violations are reported, never silently fixed.
  2  LOCALIZE            localize_dag starts from pipeline_lifter13.localize: each observed node is executed on its OBSERVED upstream
                         outputs, so an observed node is independently verified or broken. For the first broken node it then:
                           a  COLUMN REPORT   per-column marginal bag diff over every output column (wide 50+ column nodes). One
                                              metered full check per observed batch.
                           b  LINEAGE         the mismatched columns are traced back through map items / fold measures of the
                                              node and its suspect span (its unobserved ancestors).
                           c  EXPLAIN         single-node counterfactual explanation: generic single structural edits (the
                                              proposals13 shadow edges; no repair templates) of the broken node AND of every
                                              span node, ranked by lineage relevance. A node is a suspect iff one of its edits
                                              makes the broken node reproduce every observation (one metered full check each).
                           d  PROBES          surviving explanations enter a proposals13 VersionSpace. Phase 13 program-aware
                                              probes (or the arm's injected menu) that split them are queried against the
                                              budgeted oracle with the arm's chooser. A lone explanation is CHALLENGED with one
                                              probe when a query remains. The final resolution test uses the COMMON
                                              pipeline_lifter13.resolution_menu (program-aware + static) for every arm.
                         Survivors on more than one node -> 'ambiguous' (the repair abstains). No explanation -> 'span' (fallback).
  3  LIFT ONLY THE NODE  lift_node repairs only the localised node:
                           a  NARROWED   the node restricted to its mismatched output items (+ fold keys / referenced measures)
                                         is lifted with pipeline_lifter13.lift_stage on projected observations (oracle answers
                                         projected likewise). The repair is SPLICED back into the full node and re-verified on
                                         every observation (core11 + native SQLite, metered).
                           b  FULL NODE  otherwise lift_stage on the node alone (span=[]; upstream observed outputs preserved).
                         An UNOBSERVED faulty node is repaired by its surviving explaining edit, verified through its observed
                         descendant (core11 + native SQLite). Unexplained faults fall back to the Phase 13 span lift, recorded as
                         scope 'span' (NOT node-isolated).
  4  DOWNSTREAM          verify_downstream: untouched nodes keep identical ASTs; every node keeps its schema contract; no node
     INVARIANTS          errors; every observed node matches (end_to_end); the native SQLite pipeline check agrees; every changed
                         node passes multi_engine14.conformance (fail-closed, sqlite required); and engine_dag_check executes the
                         WHOLE DAG on every dag / required engine with each stage reading that engine's OWN upstream outputs.
                         REQUIRED ENGINES GATE ACCEPTANCE: require_engines always contains DEFAULT_REQUIRED (sqlite) plus whatever
                         the caller adds, and is checked on the CALLER'S ROW BUDGET before any repair is accepted (repair_dag and
                         every external caller of verify_downstream, e.g. the runner's learned-operator stage). A required engine
                         that is unavailable, disagrees, errors or goes unchecked (budget refusal) fails 'required_engine_dag', so
                         the repair is never submitted. Unavailable OPTIONAL dag engines are reported, never simulated, never
                         counted as agreement.
  5  METERING            repair_dag holds ONE strict synth12 Budget per row (or the caller's shared row budget) and ONE query
                         allowance shared by fidelity, localisation, explanation, probes, lifts (merged forks) and verification
                         (including the whole-DAG required-engine execution).

DECLARED LIMITS  unobserved nodes are repairable only by a single structural edit (synthesis needs an observation of the node);
the explanation scan is capped (exhaustive=False is reported when truncated); column narrowing is a heuristic whose result is
always re-verified on the full node; DataFrame sources are lifted only for the documented multi_engine14 method subset.

ATTRIBUTION  all of this is general machinery written by the engineering team. What NEXUS contributes in a repair is only learned
state passed in (library functions `lib`, guide `costs`, a trained `chooser` / leader `prior`), reported per repair."""
from __future__ import annotations

import time
from collections import Counter
from decimal import Decimal

from nexus.de_phase11 import core11 as C
from nexus.de_phase12 import synth12 as S
from nexus.de_phase13 import pipeline_lifter13 as L
from nexus.de_phase13 import proposals13 as P
from nexus.de_phase14 import DAG_LAYERS, engine_available, layer_of
from nexus.de_phase14 import multi_engine14 as ME

EXPLAIN_PER_NODE, EXPLAIN_CAP, MAX_EXPLAIN_NODES, MAX_STR_CONSTS = 48, 192, 8, 8
DAG_WALL_S, LIFT_SHARE, QUERY_BUDGET, MAX_FAULTS = 20.0, 0.85, 2, 3
DEFAULT_ENGINES = ("sqlite", "duckdb", "polars")
DEFAULT_REQUIRED = ("sqlite",)                                    # whole-DAG native execution that ALWAYS gates acceptance
LIFT_KEYS = ("lib", "costs", "chooser", "prior", "observer", "menu", "require_unique", "holdout", "shadows", "edit_first", "widen",
             "native", "require_native")
SQL_ENGINE = {d: e for e, d in ME.ENGINE_DIALECT.items()}        # dialect -> engine executing it natively
DF_ENGINE = {"polars": "polars", "pyspark": "pyspark"}
_UNFAITHFUL = ("disagree", "core_error")
_PROJ = "__nx_proj"
_EXEC_ERRORS = L._EXEC_ERRORS


# ------------------------------------------------------------------ small helpers
def _pipe(x):
    return x if isinstance(x, L.Pipeline) else L.Pipeline(list(x))


def _out(budget):
    return budget is not None and budget.out()


def _fork(budget, share):
    el = time.time() - budget.t0
    return budget.fork(wall=el + share * max(0.0, budget.wall - el))


def _lift_kw(kw, strict=False):
    kw = dict(kw or {})
    bad = sorted(k for k in kw if k not in LIFT_KEYS)
    if bad and strict:
        raise ValueError(f"unknown lift options {bad}")
    return {k: v for k, v in kw.items() if k in LIFT_KEYS}


def _required(require_engines):
    """Effective required engines: DEFAULT_REQUIRED first, then the caller's (deduplicated, order kept; never empty)."""
    return tuple(dict.fromkeys(tuple(DEFAULT_REQUIRED) + tuple(e for e in (require_engines or ()) if e != "core11")))


def _colrefs(x, out=None):
    out = set() if out is None else out
    if isinstance(x, tuple) and x:
        if x[0] == "col" and len(x) == 2 and isinstance(x[1], str):
            out.add(x[1])
        else:
            for y in x[1:]:
                _colrefs(y, out)
    return out


def _schema(R):
    return tuple(sorted(zip((str(c) for c in R.cols), (str(t) for t in R.types))))


def _plain(v):
    if isinstance(v, Decimal):
        return int(v) if v.is_finite() and v == v.to_integral_value() else float(v)
    return v


def _reads(ast, env):
    return {x: env[x] for x in P._base_rels(ast) if x in env}


def project(R, cols):
    """R restricted to cols (core11 projection), None when R is None or lacks a column."""
    if R is None or any(c not in list(R.cols) for c in cols):
        return None
    return L._run(("map", ("rel", _PROJ), tuple((c, ("col", c)) for c in cols)), {_PROJ: R})


# ------------------------------------------------------------------ native sources (SQL dialects / DataFrame code)
def lift_sources(stages, sample_inputs):
    """stages: dicts dict(name, sql, dialect='sqlite') | dict(name, code, api='polars') | dict(name, ast) | (name, ast). Every stage
    is lifted to core11 (column resolution on sample_inputs + earlier stage outputs); its native source is kept for fidelity."""
    env, out = dict(sample_inputs or {}), []
    for s in stages:
        d = dict(s) if isinstance(s, dict) else dict(name=s[0], ast=s[1])
        name = d["name"]
        if d.get("sql") is not None:
            dialect = d.get("dialect", "sqlite")
            if dialect not in SQL_ENGINE:
                raise ME.EngineUnsupported(f"{name}: no engine for SQL dialect {dialect!r}")
            ast = ME.from_sql(d["sql"], dialect, L._cols_fn(dict(env)))
            st = dict(name=name, ast=ast, sql=None, origin=f"sql:{dialect}", source=d["sql"], front="sql", dialect=dialect,
                      engine=SQL_ENGINE[dialect])
        elif d.get("code") is not None:
            api = d.get("api", "polars")
            if api not in DF_ENGINE:
                raise ME.EngineUnsupported(f"{name}: unknown DataFrame api {api!r}")
            ast = ME.from_dataframe(d["code"], api, dict(env))
            st = dict(name=name, ast=ast, sql=None, origin=f"df:{api}", source=d["code"], front="df", api=api, engine=DF_ENGINE[api])
        else:
            st = dict(name=name, ast=d["ast"], sql=None, origin="given")
        out.append(st)
        R = L._run(st["ast"], env)
        if R is not None:
            env[name] = R
    return L.Pipeline(out)


def _is_source(st):
    return str(st.get("origin", "")).startswith(("sql:", "df:")) and bool(st.get("source"))


def _stage_fidelity(st, env, R, budget):
    eng = st.get("engine")
    if R is None:
        return "core_error", "core11 failed on the lifted AST"
    if not engine_available(eng):
        return "unavailable", f"{eng} is not installed"
    if not L._charge(budget, "full_checks"):
        return "unchecked", "budget refused the comparison"
    try:
        if st["front"] == "sql":
            names, rows = ME._SQL_RUNNERS[eng](st["source"], env)
            return ("agree" if ME.bag_equal(names, rows, R) else "disagree"), None
        r = ME.dataframe_fidelity(st["source"], env, st["api"], lifted=st["ast"])
        return {"error": "native_error"}.get(r["status"], r["status"]), r.get("detail")
    except ME.EngineUnavailable as e:
        return "unavailable", str(e)[:160]
    except Exception as e:                                         # noqa: BLE001 - any native failure: fidelity not established
        return "native_error", f"{type(e).__name__}: {str(e)[:160]}"


def source_fidelity(pipeline, batches, budget=None):
    """Lift fidelity of every native-source stage, FAIL-CLOSED: the ORIGINAL source runs on its own engine over the same inputs as
    core11 on the lifted AST (upstream outputs from core11). faithful only when >= 1 comparison ran and every one agreed."""
    p, B = _pipe(pipeline), L._batches(batches)
    src = {i for i, st in enumerate(p.stages) if _is_source(st)}
    if not src:
        return dict(checked=False, faithful=True, tally={}, rows=[], failures={}, reason="no_source_stage")
    rows, tally = [], Counter()
    for b in B:
        core, _ = p.run(b["inputs"])
        env = dict(b["inputs"])
        for i, st in enumerate(p.stages):
            R = core.get(st["name"])
            if i in src:
                status, detail = _stage_fidelity(st, _reads(st["ast"], env), R, budget)
                tally[status] += 1
                rows.append(dict(batch=b["name"], stage=st["name"], engine=st.get("engine"), status=status, detail=detail))
            if R is not None:
                env[st["name"]] = R
    failures = {k: v for k, v in tally.items() if k != "agree"}
    faithful = bool(tally.get("agree")) and not failures
    reason = None if faithful else ("unfaithful" if any(tally.get(k) for k in _UNFAITHFUL) else "unverified")
    return dict(checked=True, faithful=faithful, tally=dict(tally), rows=rows, failures=failures, reason=reason,
                engines=sorted({p.stages[i].get("engine") for i in src}))


def _fidelity(p, B, budget):
    """Phase 13 SQLite parse fidelity (origin 'sql') merged with Phase 14 native-source fidelity; fail-closed on either."""
    if not B:
        return dict(checked=False, faithful=True, tally={}, rows=[], reason="no_batches")
    parts = [f for f in (L.sql_fidelity(p, B, budget), source_fidelity(p, B, budget)) if f.get("checked")]
    if not parts:
        return dict(checked=False, faithful=True, tally={}, rows=[], reason="no_source_stage")
    tally = Counter()
    for f in parts:
        tally.update(f.get("tally") or {})
    faithful = all(f["faithful"] for f in parts)
    reason = None if faithful else ("unfaithful" if any(f.get("reason") == "unfaithful" for f in parts) else "unverified")
    return dict(checked=True, faithful=faithful, tally=dict(tally), rows=[r for f in parts for r in f.get("rows", [])], reason=reason)


def native_fidelity(pipeline, batches, budget=None):
    """Public name of the shared fail-closed fidelity gate (parse fidelity + native-source fidelity) on the caller's budget."""
    return _fidelity(_pipe(pipeline), L._batches(batches), budget)


def compile_dag(pipeline, sample_inputs, dialect="sqlite", lib=None):
    """Every stage compiled to `CREATE TABLE stage AS <sql>` in `dialect` (column lists resolved on sample_inputs)."""
    p, env, out = _pipe(pipeline), dict(sample_inputs), []
    for st in p.stages:
        try:
            sql, err = ME.to_engine_sql(st["ast"], dialect, L._cols_fn(dict(env)), lib), None
        except L.SqlUnsupported as e:
            sql, err = None, str(e)[:200]
        out.append(dict(name=st["name"], dialect=dialect, sql=sql, error=err))
        R = L._run(st["ast"], env)
        if R is not None:
            env[st["name"]] = R
    return out


def engine_dag_check(pipeline, batches, engine, budget=None):
    """Execute the WHOLE DAG on one engine, each stage reading that engine's OWN upstream outputs; every observed stage compared
    (one metered full check each). 'agree' only when >= 1 comparison ran and all agreed; unavailable engines are never agreement."""
    p, B = _pipe(pipeline), L._batches(batches)
    if not engine_available(engine):
        return dict(engine=engine, status="unavailable", compared=0)
    compared = 0
    for b in B:
        core, _ = p.run(b["inputs"])
        env = dict(b["inputs"])
        for st in p.stages:
            name, R0 = st["name"], core.get(st["name"])
            base = dict(engine=engine, stage=name, batch=b["name"], compared=compared)
            if R0 is None:
                return dict(base, status="core_error")
            r = ME.run_engine(engine, st["ast"], _reads(st["ast"], env))
            if r["status"] != "ok":
                return dict(base, status=r["status"], detail=r["detail"])
            types = dict(zip(R0.cols, R0.types))
            try:
                env[name] = ME.make_rel(r["names"], [types[c] for c in r["names"]],
                                        [tuple(ME._coerce(_plain(v), types[c]) for v, c in zip(row, r["names"])) for row in r["rows"]])
            except (KeyError, TypeError, ValueError, L.SqlUnsupported) as e:
                return dict(base, status="error", detail=f"{type(e).__name__}: {str(e)[:120]}")
            E = b["observed"].get(name)
            if E is not None:
                if not L._charge(budget, "full_checks"):
                    return dict(base, status="unchecked", detail="budget refused the comparison")
                compared += 1
                if not ME.bag_equal(r["names"], r["rows"], E):
                    return dict(base, status="disagree", compared=compared)
    return dict(engine=engine, status="agree" if compared else "unchecked", compared=compared)


# ------------------------------------------------------------------ DAG view
def _layer_rank(name):
    lay = layer_of(name)
    return None if lay is None else DAG_LAYERS.index(lay)


def downstream_of(pipeline, i):
    """Indices of every node that (transitively) reads node i."""
    p = _pipe(pipeline)
    names, out, frontier = p.names(), set(), {p.names()[i]}
    while frontier:
        nxt = set()
        for j, n in enumerate(names):
            if j != i and j not in out and set(p.deps(j)) & frontier:
                out.add(j)
                nxt.add(n)
        frontier = nxt
    return sorted(out)


def dag_info(pipeline):
    """Topology of a layered pipeline: deps, sources, layers, downstream closures, sinks and convention violations."""
    p = _pipe(pipeline)
    names = p.names()
    idx = {n: i for i, n in enumerate(names)}
    deps = {n: p.deps(i) for i, n in enumerate(names)}
    violations = []
    for n in names:
        rn = _layer_rank(n)
        for d in deps[n]:
            if idx[d] >= idx[n]:
                violations.append(dict(node=n, dep=d, kind="order"))
            rd = _layer_rank(d)
            if rn is not None and rd is not None and rd > rn:
                violations.append(dict(node=n, dep=d, kind="layer_inversion"))
            if rn == 0:
                violations.append(dict(node=n, dep=d, kind="stg_reads_model"))
    down = {n: [names[j] for j in downstream_of(p, idx[n])] for n in names}
    layers = {n: layer_of(n) for n in names}
    return dict(nodes=names, deps=deps, sources={n: sorted(P._base_rels(p.stages[idx[n]]["ast"]) - set(names)) for n in names},
                layers=layers, layered=all(v is not None for v in layers.values()), downstream=down,
                sinks=[n for n in names if not down[n]], violations=violations,
                origins={s["name"]: s.get("origin") for s in p.stages})


# ------------------------------------------------------------------ column report and lineage
def column_diff(R, E):
    """Per-column marginal bag diff of a computed relation R against an observation E (diagnostic; pairing is not checked)."""
    ec = list(E.cols)
    if R is None:
        return dict(error=True, mismatched=ec, missing=[], extra=[], rows_equal=False)
    rc = list(R.cols)
    missing, extra = [c for c in ec if c not in rc], [c for c in rc if c not in ec]
    mism = list(missing)
    for j, c in enumerate(ec):
        if c in rc:
            k = rc.index(c)
            if Counter(ME.norm(r[k]) for r in R.rows) != Counter(ME.norm(r[j]) for r in E.rows):
                mism.append(c)
    return dict(error=False, mismatched=mism, missing=missing, extra=extra, rows_equal=len(R.rows) == len(E.rows))


def column_report(pipeline, batches, i, budget=None):
    """Mismatched output columns of node i over every observed batch (node fed its observed upstream; one full check per batch)."""
    p, B = _pipe(pipeline), L._batches(batches)
    st = p.stages[i]
    mism, ncols, rows_bad, errs, complete, n = set(), 0, [], [], True, 0
    for b in B:
        E = b["observed"].get(st["name"])
        if E is None:
            continue
        if not L._charge(budget, "full_checks"):
            complete = False
            break
        n += 1
        d = column_diff(L._run(st["ast"], L._upstream_env(p, b, i)), E)
        mism |= set(d["mismatched"])
        ncols = max(ncols, len(E.cols))
        if d["error"]:
            errs.append(b["name"])
        elif not d["rows_equal"]:
            rows_bad.append(b["name"])
    return dict(node=st["name"], batches=n, n_columns=ncols, mismatched=sorted(mism), n_mismatched=len(mism),
                row_count_mismatch=rows_bad, errors=errs, complete=complete)


def _grow(ast, rel):
    if not isinstance(ast, tuple) or not ast:
        return
    h = ast[0]
    if h == "map" and len(ast) == 3:
        for o, e in ast[2]:
            if o in rel:
                rel |= _colrefs(e)
        _grow(ast[1], rel)
    elif h == "fold" and len(ast) == 4:
        hit = False
        for m in ast[3]:
            if m[0] in rel:
                hit = True
                if len(m) > 2 and m[2] is not None:
                    rel |= _colrefs(m[2])
        if hit:
            rel |= set(ast[2])
        _grow(ast[1], rel)
    elif h in ("filter", "rank") and len(ast) >= 2:
        _grow(ast[1], rel)
    elif h == "join" and len(ast) == 6:
        _grow(ast[2], rel)
        _grow(ast[3], rel)


def lineage(pipeline, i, span, cols):
    """Columns relevant to the mismatched columns of node i, traced back through node i and its span (nearest first)."""
    p, rel = _pipe(pipeline), set(cols)
    for j in [i] + sorted(span, reverse=True):
        _grow(p.stages[j]["ast"], rel)
    return rel


def _edit_target(orig, new):
    """Output column (map item / fold measure) changed by a single edit, None for structural edits elsewhere."""
    if not (isinstance(orig, tuple) and isinstance(new, tuple) and orig and new and orig[0] == new[0]):
        return None
    if orig[0] == "map" and len(orig) == 3 and len(new) == 3:
        if orig[1] == new[1]:
            for (o, e), (_, e2) in zip(orig[2], new[2]):
                if e != e2:
                    return o
            return None
        return _edit_target(orig[1], new[1])
    if orig[0] == "fold" and len(orig) == 4 and len(new) == 4 and orig[1] == new[1]:
        for m, m2 in zip(orig[3], new[3]):
            if m != m2:
                return m[0]
    return None


def _rank(target, relevant):
    if relevant is None or target is None:
        return 1
    return 0 if target in relevant else 2


def _consts(obs):
    out = {C.INT: {0}, C.NUM: {0.0}, C.STR: set()}
    for _, _, E in obs:
        for j, t in enumerate(E.types):
            if t == C.STR:
                vals = {r[j] for r in E.rows if r[j] is not None}
                if len(vals) <= 4:
                    out[C.STR] |= vals
    res = {t: sorted(v, key=repr) for t, v in out.items() if v}
    if C.STR in res:
        res[C.STR] = res[C.STR][:MAX_STR_CONSTS]
    return res


# ------------------------------------------------------------------ single-node counterfactual explanation
def _region_obs(p, B, i, region):
    reads, name, obs = sorted(P._base_rels(region)), p.stages[i]["name"], []
    for b in B:
        E = b["observed"].get(name)
        if E is None:
            continue
        env = L._upstream_env(p, b, i)
        if any(r not in env for r in reads):
            continue
        obs.append((b["name"], {r: env[r] for r in reads}, E))
    return obs


def explain_fault(pipeline, batches, i, span, budget=None, *, relevant=None, per_node=EXPLAIN_PER_NODE, cap=EXPLAIN_CAP):
    """Single edits of node i or of a span node that make node i reproduce every observation (one metered full check each)."""
    p, B = _pipe(pipeline), L._batches(batches)
    st = p.stages[i]
    defs = {p.stages[j]["name"]: p.stages[j]["ast"] for j in span}
    region = L._inline(st["ast"], defs) if span else st["ast"]
    obs = _region_obs(p, B, i, region)
    rep = dict(node=st["name"], region_size=L._size(region), observations=len(obs), checked=0, complete=True, reason=None,
               exhaustive=False, variants=[], per_node={}, region=region, obs=obs)
    if not obs:
        rep.update(complete=False, reason="no_observed_batch")
        return rep
    bmap = {b["name"]: b for b in B}
    consts, seen, exhaustive = _consts(obs), {region}, True
    order = [i] + sorted(span, reverse=True)
    if len(order) > MAX_EXPLAIN_NODES:
        order, exhaustive = order[:MAX_EXPLAIN_NODES], False
    for j in order:
        sj = p.stages[j]
        env_j = L._upstream_env(p, bmap[obs[0][0]], j)
        R = L._run(sj["ast"], env_j)
        ctx = dict(out_types=dict(zip(R.cols, R.types)) if R is not None else {}, consts=consts, cols=L._cols_fn(env_j),
                   join_kinds=tuple(getattr(C, "JOIN_KINDS", ("inner", "left"))))
        try:
            edits = P._rel_edits(sj["ast"], ctx)
        except _EXEC_ERRORS:
            edits = []
        ranked = sorted(range(len(edits)), key=lambda k: (_rank(_edit_target(sj["ast"], edits[k][0]), relevant), k))
        if len(ranked) > per_node:
            exhaustive = False
        tried = found = 0
        for k in ranked[:per_node]:
            ne, edge = edits[k]
            if j == i:
                reg = L._inline(ne, defs) if span else ne
            else:
                d2 = dict(defs)
                d2[sj["name"]] = ne
                reg = L._inline(st["ast"], d2)
            if reg in seen:
                continue
            seen.add(reg)
            if rep["checked"] >= cap:
                rep.update(complete=False, reason="explain_cap")
                break
            if not L._charge(budget, "full_checks"):
                rep.update(complete=False, reason="budget")
                break
            rep["checked"] += 1
            tried += 1
            if all(L._same(L._run(reg, env), E) for _, env, E in obs):
                found += 1
                rep["variants"].append(dict(node=sj["name"], index=j, edge=edge, ast=ne, region=reg,
                                            target=_edit_target(sj["ast"], ne)))
        rep["per_node"][sj["name"]] = dict(edits=len(edits), tried=tried, explaining=found)
        if not rep["complete"]:
            break
    rep["exhaustive"] = exhaustive and rep["complete"]
    return rep


def investigate_variants(variants, obs, schema, name, budget, *, oracle=None, queries_left=None, chooser=None, menu=None,
                         observer=None, challenge=True):
    """Phase 13 program-aware probes over competing explanations; oracle queries split them (or challenge a lone survivor)."""
    ql = queries_left if queries_left is not None else [0]
    vs = P.VersionSpace(L._task(obs, schema), [], budget=budget, shadows=False)
    owner, queries = {}, []
    for v in variants:
        m = vs._add(v["region"], v["region"], "candidate", edge=f"{v['node']}:{v['edge']}")
        if m is not None:
            owner[m["id"]] = v

    def ask(ch, scored, split, phase):
        try:
            E = oracle(name, ch["env"])
        except Exception:                                          # noqa: BLE001 - an external oracle failure ends querying
            E = None
        if E is None:
            return False
        if observer is not None:
            observer(dict(stage=name, scored=scored, splitting=split, chosen=ch, answer=E, vs=vs, phase=phase))
        ql[0] -= 1
        qn = f"loc_q{len(queries)}"
        rep = vs.observe(qn, ch["env"], E)
        queries.append(dict(name=qn, phase=phase, kind=ch["kind"], detail=ch["detail"], scored=len(scored), splitting=len(split),
                            falsified=len(rep["falsified"]), survivors=len(rep["survivors"])))
        return True
    while ql[0] > 0 and oracle is not None and len(vs.alive()) > 1 and not vs.exhausted and not _out(budget):
        props = menu(vs) if menu else P.program_aware_proposals(vs)
        scored = P.score_proposals(vs, props, leader=vs.leader())
        split = [s for s in scored if len(s["partition"]) > 1]
        if not split:
            break
        ch = chooser(split) if chooser else P.choose(split, "weighted")
        if ch is None or not ask(ch, scored, split, "disambiguate"):
            break
    challenged = False
    if challenge and ql[0] > 0 and oracle is not None and len(vs.alive()) == 1 and not vs.exhausted and not _out(budget):
        scored = P.score_proposals(vs, P.program_aware_proposals(vs), leader=vs.leader())
        ch = (chooser(scored) if chooser else P.choose(scored, "weighted")) if scored else None
        if ch is not None:
            challenged = ask(ch, scored, [], "challenge")
    alive = vs.alive()
    unresolved, reason, complete = bool(vs.exhausted), ("budget" if vs.exhausted else None), None
    if len(alive) > 1 and not unresolved:
        scored = P.score_proposals(vs, L.resolution_menu(vs), leader=vs.leader())    # COMMON menu for every arm
        complete = bool(scored.complete) and not vs.exhausted
        if vs.exhausted:
            unresolved, reason = True, "budget"
        elif any(len(s["partition"]) > 1 for s in scored):
            unresolved, reason = True, "unresolved_alternatives"
        elif not complete:
            unresolved, reason = True, "incomplete_scoring"
    survivors = [owner[m["id"]] for m in vs.alive() if m["id"] in owner]
    return dict(vs=vs.summary(), queries=queries, challenged=challenged, survivors=survivors,
                nodes=sorted({v["node"] for v in survivors}), unresolved=unresolved, reason=reason, scoring_complete=complete,
                resolution_menu=L.RESOLUTION_MENU)


# ------------------------------------------------------------------ localisation
def localize_dag(pipeline, batches, budget=None, *, oracle=None, queries_left=None, chooser=None, menu=None, observer=None,
                 explain=True):
    """Localise the faulty node: Phase 13 observed-upstream localisation, column report, lineage, single-node explanations and
    program-aware probes. status: no_fault | localized | ambiguous | span (unexplained; region fallback) | budget."""
    p, B = _pipe(pipeline), L._batches(batches)
    budget = budget if budget is not None else S.Budget(wall=DAG_WALL_S)
    base = L.localize(p, B, budget)
    out = dict(status=None, complete=base["complete"], broken=base["broken_name"], broken_index=base["broken"],
               span=base["span_names"], span_index=list(base["span"]), fault=None, fault_index=None, method=None, columns=None,
               relevant=None, explanation=None, investigation=None, variant=None, variant_unresolved=None, exhaustive=None,
               candidates=[], base=L._loc_brief(base), _variant=None)
    if not base["complete"]:
        out["status"] = "budget"
        return out
    i = base["broken"]
    if i is None:
        out["status"] = "no_fault"
        return out
    span = list(base["span"])
    out["columns"] = column_report(p, B, i, budget)
    if not out["columns"]["complete"]:
        out["status"] = "budget"
        return out
    rel = lineage(p, i, span, out["columns"]["mismatched"])
    out["relevant"] = sorted(rel)
    if not span:
        out.update(status="localized", fault=p.stages[i]["name"], fault_index=i, method="direct", exhaustive=True)
        return out
    if not explain:
        out.update(status="span", method="span_unexplained")
        return out
    ex = explain_fault(p, B, i, span, budget, relevant=rel)
    out["exhaustive"] = ex["exhaustive"]
    out["explanation"] = {k: v for k, v in ex.items() if k not in ("variants", "region", "obs")}
    out["explanation"]["variants"] = [dict(node=v["node"], edge=v["edge"], target=v["target"]) for v in ex["variants"][:32]]
    if ex["reason"] == "budget":
        out["status"] = "budget"
        return out
    if not ex["variants"]:
        out.update(status="span", method="span_unexplained")
        return out
    E0 = ex["obs"][0][2]
    inv = investigate_variants(ex["variants"], ex["obs"], tuple(zip(E0.cols, E0.types)), p.stages[i]["name"], budget, oracle=oracle,
                               queries_left=queries_left, chooser=chooser, menu=menu, observer=observer)
    out["investigation"] = {k: v for k, v in inv.items() if k != "survivors"}
    out["investigation"]["survivors"] = [dict(node=v["node"], edge=v["edge"]) for v in inv["survivors"][:32]]
    if inv["reason"] == "budget":
        out["status"] = "budget"
    elif not inv["nodes"]:
        out.update(status="span", method="explanations_falsified")
    elif len(inv["nodes"]) > 1:
        out.update(status="ambiguous", method="explained", candidates=inv["nodes"])
    else:
        j = p.index(inv["nodes"][0])
        out.update(status="localized", fault=inv["nodes"][0], fault_index=j, method="explained_observed" if j == i else "explained")
        if j != i:
            if inv["unresolved"]:
                out["variant_unresolved"] = inv["reason"]
            else:
                v = min(inv["survivors"], key=lambda v: (L._size(v["ast"]) or 0, str(v["edge"])))
                out["_variant"] = v
                out["variant"] = dict(node=v["node"], edge=v["edge"], target=v["target"],
                                      agreement_unproven=len(inv["survivors"]) > 1)
    return out


def _loc_public(loc):
    return {k: v for k, v in loc.items() if not k.startswith("_")}


# ------------------------------------------------------------------ node-only repair
def narrow_stage(ast, cols):
    """(narrowed AST, kept output names) restricting a top-level map to the given output columns (+ fold keys / referenced
    measures), or None when narrowing does not apply or would keep everything."""
    if not (isinstance(ast, tuple) and len(ast) == 3 and ast[0] == "map"):
        return None
    base, items = ast[1], ast[2]
    target = set(cols) & {o for o, _ in items}
    if not target:
        return None
    is_fold = isinstance(base, tuple) and len(base) == 4 and base[0] == "fold"
    keys = set(base[2]) if is_fold else set()
    kept = tuple((o, e) for o, e in items if o in target or (is_fold and P._is_col(e) and e[1] in keys))
    if len(kept) >= len(items):
        return None
    nbase = base
    if is_fold:
        refs = set()
        for _, e in kept:
            refs |= _colrefs(e)
        meas = tuple(m for m in base[3] if m[0] in refs)
        if not meas:
            return None
        nbase = ("fold", base[1], base[2], meas)
    return ("map", nbase, kept), [o for o, _ in kept]


def splice_stage(ast, narrowed, repaired):
    """Full node with the repaired narrowed items (and fold measures) spliced back; None when the shapes are incompatible."""
    if not (isinstance(repaired, tuple) and len(repaired) == 3 and repaired[0] == "map"):
        return None
    base, items = ast[1], ast[2]
    rb, ritems = repaired[1], dict(repaired[2])
    if set(ritems) != {o for o, _ in narrowed[2]}:
        return None
    if rb == narrowed[1]:
        nbase = base
    elif (isinstance(base, tuple) and base[0] == "fold" and isinstance(rb, tuple) and len(rb) == 4 and rb[0] == "fold"
          and rb[1] == base[1] and tuple(rb[2]) == tuple(base[2])):
        over = {m[0]: m for m in rb[3]}
        meas = tuple(over.pop(m[0], m) for m in base[3]) + tuple(over.values())
        nbase = ("fold", base[1], base[2], meas)
    else:
        return None
    return ("map", nbase, tuple((o, ritems.get(o, e)) for o, e in items))


def _verify_node(p, B, i, ast, budget, native):
    """Node i replaced by ast reproduces every observation of node i (core11 and, when native, SQLite). None when ok."""
    name, reads = p.stages[i]["name"], sorted(P._base_rels(ast))
    for b in B:
        E = b["observed"].get(name)
        if E is None:
            continue
        env = L._upstream_env(p, b, i)
        envr = {r: env[r] for r in reads if r in env}
        if not L._charge(budget, "full_checks"):
            return "budget"
        if not L._same(L._run(ast, envr), E):
            return "falsified"
        if native:
            if not L._charge(budget, "full_checks"):
                return "budget"
            st = L.native_check(ast, envr, E)["status"]
            if st != "agree":
                return f"native_{st}"
    return None


def _brief(r):
    return dict(status=r.get("status"), reason=r.get("reason"), method=r.get("method"), mode=r.get("mode"),
                queries_used=r.get("queries_used"), accepted_edge=r.get("accepted_edge"), provenance=r.get("provenance"),
                attempts=r.get("attempts"), native_query_checks=r.get("native_query_checks"))


def _narrow_attempt(p, B, i, nast, cols, budget, oracle, ql, kw, share):
    name, reads, nb = p.stages[i]["name"], sorted(P._base_rels(nast)), []
    out = dict(mode="narrowed", columns=list(cols), narrowed_size=L._size(nast), status="failed", reason=None, pipeline=None)
    for b in B:
        E = b["observed"].get(name)
        if E is None:
            continue
        env = L._upstream_env(p, b, i)
        if any(r not in env for r in reads):
            continue
        PE = project(E, cols)
        if PE is None:
            out["reason"] = "projection_failed"
            return out
        nb.append(dict(name=b["name"], inputs={r: env[r] for r in reads}, observed={name: PE}))
    if not nb:
        out["reason"] = "no_observed_batch"
        return out
    npipe = L.Pipeline([dict(name=name, ast=nast, sql=None, origin="narrowed")])
    nor = None if oracle is None else (lambda stage, env: project(oracle(name, env), cols))
    k2 = dict(kw)
    k2["widen"] = False
    lb = _fork(budget, share)
    r = L.lift_stage(npipe, nb, 0, span=[], oracle=nor, budget=lb, queries_left=ql, **k2)
    L._merge(budget, lb)
    out.update(lift=_brief(r), method=r.get("method"), provenance=r.get("provenance"))
    if r["status"] != "repaired":
        out.update(status=r["status"], reason=r["reason"])
        return out
    new = splice_stage(p.stages[i]["ast"], nast, r["repaired_ast"])
    if new is None:
        out["reason"] = "splice_incompatible"
        return out
    bad = _verify_node(p, B, i, new, budget, kw.get("native", True))
    if bad is not None:
        out.update(status="abstained" if bad == "budget" else "failed", reason=f"splice_{bad}")
        return out
    out.update(status="repaired", pipeline=p.replace(i, new, origin=f"dag14:narrowed:{r.get('method')}"))
    return out


def lift_node(pipeline, batches, i, budget, *, oracle=None, queries_left=None, mismatched=(), narrow=True, lift_kw=None,
              lift_share=LIFT_SHARE):
    """Repair ONLY node i: a column-narrowed lift spliced back (when applicable), else lift_stage on the node alone (span=[])."""
    p, B, kw = _pipe(pipeline), L._batches(batches), _lift_kw(lift_kw)
    ql = queries_left if queries_left is not None else [0]
    attempts = []
    nar = narrow_stage(p.stages[i]["ast"], mismatched) if narrow else None
    if nar is not None and not _out(budget):
        res = _narrow_attempt(p, B, i, nar[0], nar[1], budget, oracle, ql, kw, lift_share)
        attempts.append({k: v for k, v in res.items() if k != "pipeline"})
        if res["status"] == "repaired":
            return dict(status="repaired", reason=None, scope="node", mode="narrowed", node=p.stages[i]["name"], method=res["method"],
                        provenance=res.get("provenance"), pipeline=res["pipeline"], attempts=attempts)
    if _out(budget):
        return dict(status="abstained", reason="budget", scope="node", mode=None, node=p.stages[i]["name"], pipeline=None,
                    attempts=attempts, method=None, provenance=None)
    lb = _fork(budget, lift_share)
    r = L.lift_stage(p, B, i, span=[], oracle=oracle, budget=lb, queries_left=ql, **kw)
    L._merge(budget, lb)
    rec = _brief(r)
    rec["lift_mode"], rec["mode"] = rec.pop("mode"), "node"            # the lift's own attempt mode is kept apart (no key clash)
    attempts.append(rec)
    return dict(status=r["status"], reason=r["reason"], scope="node", mode="node", node=p.stages[i]["name"], method=r.get("method"),
                provenance=r.get("provenance"), pipeline=r.get("pipeline"), attempts=attempts)


def _apply_variant(p, B, loc, budget, native):
    """Repair an unobserved node by its surviving explaining edit, verified through its observed descendant."""
    v, i = loc["_variant"], loc["broken_index"]
    res = dict(scope="node", mode="explained_edit", node=v["node"], method="edit", provenance=None, pipeline=None,
               edge=v["edge"], attempts=[])
    obs = _region_obs(p, B, i, v["region"])
    if not obs:
        return dict(res, status="failed", reason="no_observed_batch")
    for _, env, E in obs:
        if not L._charge(budget, "full_checks"):
            return dict(res, status="abstained", reason="budget")
        if not L._same(L._run(v["region"], env), E):
            return dict(res, status="failed", reason="variant_falsified")
        if native:
            if not L._charge(budget, "full_checks"):
                return dict(res, status="abstained", reason="budget")
            st = L.native_check(v["region"], env, E)["status"]
            if st != "agree":
                return dict(res, status="failed", reason=f"variant_native_{st}")
    return dict(res, status="repaired", reason=None, pipeline=p.replace(v["index"], v["ast"], origin="dag14:explained_edit"))


def _repair_step(p, B, loc, budget, oracle, ql, kw, narrow, share):
    i = loc["broken_index"]
    if loc["status"] == "localized" and loc["fault_index"] == i:
        return lift_node(p, B, i, budget, oracle=oracle, queries_left=ql, mismatched=loc["columns"]["mismatched"], narrow=narrow,
                         lift_kw=kw, lift_share=share)
    if loc["status"] == "localized":
        if loc.get("_variant") is None:
            return dict(status="abstained", reason=loc.get("variant_unresolved") or "unresolved_alternatives", scope="node",
                        node=loc["fault"], mode=None, pipeline=None, method=None, provenance=None, attempts=[])
        return _apply_variant(p, B, loc, budget, kw.get("native", True))
    lb = _fork(budget, share)                                          # unexplained: Phase 13 region lift (NOT node-isolated)
    r = L.lift_stage(p, B, i, span=loc["span_index"], oracle=oracle, budget=lb, queries_left=ql, **kw)
    L._merge(budget, lb)
    return dict(status=r["status"], reason=r["reason"], scope="span", mode=r.get("mode"), node=p.stages[i]["name"],
                method=r.get("method"), provenance=r.get("provenance"), pipeline=r.get("pipeline"), attempts=[_brief(r)])


# ------------------------------------------------------------------ downstream invariants
def verify_downstream(before, after, batches, changed, budget=None, engines=DEFAULT_ENGINES, conformance_batches=2, dag_engines=(),
                      require_engines=DEFAULT_REQUIRED):
    """Invariants after a repair: untouched nodes identical, schema contracts kept, no node errors, observed nodes match end to
    end, native SQLite pipeline agreement, multi-engine conformance of every changed node, and whole-DAG native execution on every
    dag / required engine, metered on `budget` (the caller's row budget). Required engines are DEFAULT_REQUIRED plus the caller's
    and MUST agree (unavailable / disagree / error / unchecked fail 'required_engine_dag'); any optional dag engine that disagrees,
    errors or goes unchecked fails 'engine_dag'."""
    pb, pa, B = _pipe(before), _pipe(after), L._batches(batches)
    names, changed = pa.names(), list(changed)
    required = _required(require_engines)
    idx = {n: i for i, n in enumerate(names)}
    untouched = [] if pb.names() == names else ["node_set_changed"]
    if not untouched:
        untouched = [n for n, s, s0 in zip(names, pa.stages, pb.stages) if n not in changed and s["ast"] != s0["ast"]]
    down = sorted({names[k] for c in changed if c in idx for k in downstream_of(pa, idx[c])})
    schema_viol, exec_err, complete, widths = [], {}, True, {}
    for b in B:
        if not L._charge(budget, "full_checks"):
            complete = False
            break
        ob, _ = pb.run(b["inputs"])
        oa, ea = pa.run(b["inputs"])
        if ea:
            exec_err[b["name"]] = ea
        for n in names:
            E, Ra = b["observed"].get(n), oa.get(n)
            ref = E if E is not None else ob.get(n)
            if Ra is not None:
                widths[n] = max(widths.get(n, 0), len(Ra.cols))
            if ref is not None and Ra is not None and _schema(Ra) != _schema(ref):
                schema_viol.append(dict(batch=b["name"], node=n, want=_schema(ref), got=_schema(Ra)))
    e2e = L.end_to_end(pa, B, budget)
    nat = L.native_pipeline_check(pa, B, budget=budget) if B else None
    conf = []
    for n in changed:
        if n not in idx:
            continue
        k, ast = idx[n], pa.stages[idx[n]]["ast"]
        for b in B[:conformance_batches]:
            outs, _ = pa.run(b["inputs"])
            env = dict(b["inputs"])
            env.update({m: outs[m] for m in names[:k] if outs.get(m) is not None})
            r = ME.conformance(ast, _reads(ast, env), engines=engines, require=("sqlite",), budget=budget)
            conf.append(dict(node=n, batch=b["name"], conformant=r["conformant"], reason=r["reason"], statuses=r["statuses"]))
    dag = {e: engine_dag_check(pa, B, e, budget) for e in dict.fromkeys(tuple(required) + tuple(dag_engines))}
    req_bad = [e for e in required if dag[e]["status"] != "agree"]
    dag_bad = [e for e, r in dag.items() if r["status"] in ("disagree", "error", "core_error", "unchecked")]
    conformant = all(c["conformant"] for c in conf)
    native_ok = nat is None or bool(nat["all_agree"])
    dag_unchecked = any(r["status"] == "unchecked" for r in dag.values())
    failed = [k for k, bad in (("untouched_nodes_changed", untouched), ("schema_contract", schema_viol), ("node_errors", exec_err),
                               ("end_to_end", not e2e["ok"]), ("native_pipeline", not native_ok),
                               ("multi_engine_conformance", not conformant), ("required_engine_dag", req_bad),
                               ("engine_dag", dag_bad), ("budget", not complete or not e2e["complete"] or dag_unchecked))
              if bad]
    return dict(ok=not failed, failed=failed, complete=complete and e2e["complete"] and not dag_unchecked, changed=changed,
                downstream=down, untouched_violations=untouched, schema_violations=schema_viol[:16], node_errors=exec_err,
                end_to_end=e2e, native={k: v for k, v in (nat or {}).items() if k != "rows"}, native_ok=native_ok, conformance=conf,
                conformant=conformant, engines=list(engines), engine_dag=dag, dag_statuses={e: r["status"] for e, r in dag.items()},
                required_engines=list(required), required_engine_failures=req_bad, node_widths=widths,
                max_width=max(widths.values(), default=0))


# ------------------------------------------------------------------ full DAG repair
def repair_dag(pipeline, batches, *, oracle=None, query_budget=QUERY_BUDGET, wall=DAG_WALL_S, fc_cap=S.FC_CAP, max_faults=MAX_FAULTS,
               engines=DEFAULT_ENGINES, narrow=True, explain=True, lift_share=LIFT_SHARE, budget=None, queries_left=None,
               dag_engines=(), require_engines=DEFAULT_REQUIRED, **lift_kw):
    """Fidelity -> localize_dag -> node-only repair -> re-localise (at most max_faults) -> downstream invariants. ONE strict row
    budget (`budget` when the caller shares its row budget, else Budget(wall, fc_cap)) and ONE query allowance (`queries_left`
    when shared) cover every check, INCLUDING the whole-DAG native execution on every required engine (DEFAULT_REQUIRED plus the
    caller's) that must agree before 'repaired' is reported. Native-source stages (lift_sources) must pass fail-closed source
    fidelity before lifting. 'repaired' also requires a complete final localisation with no broken node. lift_kw: lib, costs,
    chooser, prior, observer, menu, require_unique, holdout, shadows, edit_first, widen, native, require_native (unknown keys raise
    ValueError)."""
    t0 = time.time()
    kw = _lift_kw(lift_kw, strict=True)
    required = _required(require_engines)
    p0, B = _pipe(pipeline), L._batches(batches)
    budget = budget if budget is not None else S.Budget(wall=wall, fc_cap=fc_cap)
    ql = queries_left if queries_left is not None else [int(query_budget) if oracle is not None else 0]
    if oracle is None:
        ql[0] = 0
    q0 = ql[0]
    w0 = {k: int(v) for k, v in budget.c.items()}
    info = dag_info(p0)
    fidelity = _fidelity(p0, B, budget)
    stop = L._fidelity_stop(fidelity)
    cur, steps = p0, []
    for _ in range(0 if stop else max_faults):
        loc = localize_dag(cur, B, budget, oracle=oracle, queries_left=ql, chooser=kw.get("chooser"), menu=kw.get("menu"),
                           observer=kw.get("observer"), explain=explain)
        if loc["status"] == "no_fault":
            break
        if loc["status"] in ("budget", "ambiguous"):
            stop = "budget" if loc["status"] == "budget" else "ambiguous_localization"
            steps.append(dict(localization=_loc_public(loc), repair=None))
            break
        rep = _repair_step(cur, B, loc, budget, oracle, ql, kw, narrow, lift_share)
        steps.append(dict(localization=_loc_public(loc), repair={k: v for k, v in rep.items() if k != "pipeline"}))
        if rep["status"] != "repaired" or rep.get("pipeline") is None:
            stop = rep["status"] or "failed"
            break
        cur = rep["pipeline"]
    changed = [s["name"] for s, s0 in zip(cur.stages, p0.stages) if s["ast"] != s0["ast"]]
    inv = verify_downstream(p0, cur, B, changed, budget=budget, engines=engines, dag_engines=dag_engines,
                            require_engines=required)
    final = L.localize(cur, B, budget)
    reps = [s["repair"] for s in steps if s["repair"] and s["repair"]["status"] == "repaired"]
    reason = None
    if stop is not None:
        status, reason = ("partial" if reps else stop), stop
    elif not inv["complete"] or not final["complete"]:
        status, reason = ("budget" if steps else "abstained"), "budget_exhausted_during_verification"
    elif not steps:
        status = "no_fault" if inv["end_to_end"]["ok"] else "unlocalized"
    elif inv["ok"] and final["broken"] is None:
        status = "repaired"
    else:
        status = "partial"
        reason = "max_faults_reached" if final["broken"] is not None else ",".join(inv["failed"]) or "invariants_failed"
    work = dict(budget.c)
    over = sorted(k for k, cap in (("full_checks", budget.fc_cap), ("rel_evals", budget.rel_cap), ("micro_evals", budget.sc_cap),
                                   ("constructed_asts", budget.ast_cap)) if work.get(k, 0) > cap)
    methods = [dict(node=r.get("node"), scope=r.get("scope"), mode=r.get("mode"), method=r.get("method"), edge=r.get("edge"),
                    provenance=r.get("provenance")) for r in reps]
    return dict(status=status, reason=reason, pipeline=cur, dag=info, steps=steps, changed_nodes=changed, repaired_nodes=len(reps),
                repair_methods=methods, node_isolated=bool(methods) and all(m["scope"] == "node" for m in methods),
                invariants=inv, final_localization=L._loc_brief(final), required_engines=list(required),
                required_engine_dag={e: inv["dag_statuses"].get(e) for e in required},
                source_fidelity={k: v for k, v in fidelity.items() if k != "rows"}, work=work,
                work_this_call={k: int(v) - w0.get(k, 0) for k, v in work.items()}, over_cap=over,
                exhausted=budget.exhausted, queries_used=q0 - ql[0], query_budget=q0, wall=round(time.time() - t0, 3),
                attribution=dict(machinery="dag_repair14 + pipeline_lifter13 + proposals13 + synth12 + multi_engine14 (engineering team)",
                                 learned=dict(library_functions=[m["provenance"] for m in methods if m["provenance"]],
                                              guide_costs=kw.get("costs") is not None, trained_chooser=kw.get("chooser") is not None,
                                              leader_prior=kw.get("prior") is not None, lib_size=len(kw.get("lib") or {}))))


__all__ = ["DEFAULT_ENGINES", "DEFAULT_REQUIRED", "LIFT_KEYS", "SQL_ENGINE", "DF_ENGINE", "lift_sources", "source_fidelity",
           "native_fidelity", "compile_dag", "engine_dag_check", "dag_info", "downstream_of", "column_diff", "column_report", "lineage",
           "project", "explain_fault", "investigate_variants", "localize_dag", "narrow_stage", "splice_stage", "lift_node",
           "verify_downstream", "repair_dag"]
