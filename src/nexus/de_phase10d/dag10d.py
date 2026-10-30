"""Phase 10D investigation layer (NOT LOCKED): what NEXUS sees and the L0 repair operators over a 3-node DAG.

Inv10d(project)  reads ONLY the workspace: contract.json, the legacy node files (lifted by legacy10d), data/*.csv (visible batch),
                 state/fct_target.json, models/schema.yml. specs = [stg node spec, int node spec, fct node spec] (search 'stages').
  run(specs, prescreen=True)  executes the DAG on BOTH visible batches (reference interpreter = prescreen; the declared engine when
                 prescreen=False; amendment 3) and
                 returns the evidence: public checks (example rows of fct_out, row count, unique key), per-node contract failures
                 (stage_fail), residual-symptom features (fail:*, diff:*, err:*, stage_fail:*), a graded score. ok = every public
                 check AND every node contract passes.
  dom(k, specs)  column roles of node k's inputs (int / text / lowcard / unique / dupes / json / padded / nulls) for operator
                 enumeration and role abstraction
L0 OPERATORS (generic and column-parameterised: enumerated over EVERY eligible column, so wide schemas multiply the branching):
  stg  set_dedup (latest / oldest per key: every int key x int order column x direction), add_filter (every low-cardinality
       column x value as <>, every nullable column as NOT NULL; before or after the dedup), move_filter (pre <-> post),
       json_coalesce_before (take a CDC field from `before` when `after` is null)
  int  pre_aggregate (aggregate the child to the join-key grain: every int child column x sum / max / count), set_join_type
       (LEFT <-> INNER), cast_keys (compare typed keys), asof_backward, coalesce_out (every int output column)
  fct  merge_add_delete, merge_add_update, add_merge (MERGE INTO the target with delete detection; every latest / active
       relation x key column choice)
Role abstraction (abstract_edit) and binding (bind) follow skills6 (an edit's columns become role sets; literals stay literal)."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from nexus.de_phase6 import skills6 as SK
from nexus.de_phase10d import engines10d as EN, ir10d as IR, legacy10d as LG, world10d as W

NODES = ("stg", "int", "fct")


class Dom:
    def __init__(self, k, rels, spec_k):
        self.k, self.rels, self.spec = k, rels, spec_k
        self._roles = {}

    def roles(self, rel, col):
        key = (rel, col)
        if key not in self._roles:
            rows = self.rels.get(rel, [])
            vals = [r.get(col) for r in rows]
            nn = [v for v in vals if v not in (None, "")]
            r = set()
            if nn and all(isinstance(v, int) or re.fullmatch(r"[0-9]+", str(v)) for v in nn):
                r.add("int")
                if any(isinstance(v, str) and len(v) > 1 and v.startswith("0") for v in nn):
                    r.add("padded")
            else:
                r.add("text")
                if nn and all(str(v).startswith("{") for v in nn[:5]):
                    r.add("json")
                elif 1 < len(set(nn)) <= 4:
                    r.add("lowcard")
            r.add("unique" if len(set(map(str, nn))) == len(nn) else "dupes")
            if len(nn) < len(vals):
                r.add("nulls")
            self._roles[key] = tuple(sorted(r))
        return self._roles[key]

    def values(self, rel, col):
        return sorted({str(r.get(col)) for r in self.rels.get(rel, []) if r.get(col) not in (None, "")})


def _proj_rows(t, tables):
    return [{n: IR.ev(x, r) for n, x in t["cols"]} for r in tables[t["src"]]]


class Inv10d:
    def __init__(self, project, engine=None):
        self.p = project
        ws = Path(project["ws"])
        self.contract = json.loads((ws / "contract.json").read_text())
        self.legacy_spec = LG.read_and_lift(ws, self.contract)              # raises legacy10d.Unsupported
        self.legacy = [self.legacy_spec[n] for n in NODES]
        self.engine = engine or self.contract["engine"]
        self.stages = [dict(engine=self.engine, node=n) for n in NODES]
        self.tables = W.load_tables(ws, self.contract["tables"])
        self.state = dict(fct_target=json.loads((ws / "state/fct_target.json").read_text()))
        self.nm = self.contract["names"]
        ex = next(c for c in self.contract["public_checks"] if c["kind"] == "example_rows")
        self.cols, self.golden = ex["cols"], ex["rows"]
        self.n_rows = next(c["n"] for c in self.contract["public_checks"] if c["kind"] == "row_count")
        exb = next(c for c in self.contract["public_checks_b"] if c["kind"] == "example_rows")
        self.batches = [(self.tables, self.state, self.golden, self.n_rows),
                        ({t: W.read_csv(ws / "data" / "b" / f"{t}.csv") for t in self.contract["tables"]}, dict(fct_target=json.loads((ws / "state/fct_target_b.json").read_text())),
                         exb["rows"], next(c["n"] for c in self.contract["public_checks_b"] if c["kind"] == "row_count"))]
        self.runs = {"ref": 0, "duckdb": 0, "sqlite": 0, "polars": 0, "spark": 0}
        self.folds = [0]
        self._dom = {}
        self._memo = {}
        self.header = []
        self.rows = []

    def set_fold(self, f):
        pass

    @staticmethod
    def spec_of(specs):
        return dict(stg=specs[0], int=specs[1], fct=specs[2])

    def execute(self, specs, prescreen=True, tables=None, state=None):
        spec = self.spec_of(specs)
        T, S = tables or self.tables, state or self.state
        if prescreen:
            self.runs["ref"] += 1
            return IR.interpret(spec, T, S)
        self.runs[self.engine] += 1
        rels = sorted(spec["stg"]) + [t["latest_as"] for t in spec["stg"].values() if t.get("latest_as")] + ["int_orders", "fct_out"]
        out = EN.run(spec, T, S, self.engine, rels)
        return out

    def run(self, specs, prescreen=True):
        """Evidence on BOTH visible batches (amendment 3); one charged execution = one candidate on all visible batches."""
        self.runs["ref" if prescreen else self.engine] += 1
        passed, failed, feats = ["no_error"], [], set()
        stage_fail = [[], [], []]
        fr, cl, stp = [], [], []
        n_tests = sum(len(v) for v in W.contracts(self.nm).values())
        for bid, (T, S, golden, n_rows) in enumerate(self.batches):
            try:
                spec = self.spec_of(specs)
                if prescreen:
                    R = IR.interpret_cached(spec, T, S, self._memo, bid)
                else:
                    rels = sorted(spec["stg"]) + [t["latest_as"] for t in spec["stg"].values() if t.get("latest_as")] + ["int_orders", "fct_out"]
                    R = EN.run(spec, T, S, self.engine, rels)
            except Exception as e:                                   # noqa: BLE001
                cls = type(e).__name__[:24]
                return dict(ok=False, held_ok=False, error=cls, passed=[], failed=["no_error"], stage_fail=[["error"]] * 3,
                            features={f"err:{cls}", "fail:no_error"}, score=0.0)
            out = R["fct_out"]
            want = IR.table_key([dict(zip(self.cols, r)) for r in golden], self.cols)
            hs = set(IR.table_key(out, self.cols))
            fr.append(sum(1 for x in want if x in hs) / max(1, len(want)))
            cl.append(max(0.0, 1 - abs(len(out) - n_rows) / max(1, n_rows)))
            if fr[-1] < 1.0:
                failed.append("example_rows")
            if len(out) != n_rows:
                failed.append("row_count")
            keys = [IR.canon(r.get("cust_key")) for r in out]
            if len(keys) != len(set(keys)):
                failed.append("unique")
            cf = W.run_contracts(R, self.nm)
            for i, n in enumerate(NODES):
                stage_fail[i] = sorted(set(stage_fail[i]) | set(cf[n]))
            stp.append(1 - sum(len(cf[n]) for n in NODES) / n_tests)
            feats |= self.diff(out, golden, n_rows)
        failed = sorted(set(failed))
        passed += [c for c in ("example_rows", "row_count", "unique") if c not in failed]
        feats |= {f"fail:{c}" for c in failed} | {f"stage_fail:{t.split(':')[0]}" for fs in stage_fail for t in fs}
        ok = not failed and not any(stage_fail)
        return dict(ok=ok, held_ok=True, error=None, passed=passed, failed=failed + [f"contract:{t}" for fs in stage_fail for t in fs], stage_fail=stage_fail,
                    features=feats, score=1 + len(passed) + 0.6 * sum(fr) / len(fr) + 0.3 * sum(cl) / len(cl) + 0.5 * sum(stp) / len(stp))

    def diff(self, out, golden, n_rows):
        f = set()
        got = {}
        for r in out:
            got.setdefault(IR.canon(r.get("cust_key")), []).append(r)
        if any(len(v) > 1 for v in got.values()):
            f.add("diff:dup_keys")
        if len(out) > n_rows:
            f.add("diff:extra_rows")
        if len(out) < n_rows:
            f.add("diff:too_few_rows")
        for row in golden:
            g = got.get(IR.canon(row[0]))
            if not g:
                f.add("diff:missing_rows")
                continue
            for j, c in enumerate(self.cols[1:], 1):
                a, b = IR.canon(row[j]), IR.canon(g[0].get(c))
                if a != b:
                    f.add("diff:got_null" if b is None else "diff:expect_null" if a is None else "diff:value")
        return f

    def okey(self, specs):
        try:
            R = IR.interpret(self.spec_of(specs), self.tables, self.state)
            Rb = IR.interpret(self.spec_of(specs), *self.batches[1][:2])
            return json.dumps([IR.table_key(R["fct_out"], self.cols), IR.table_key(R["int_orders"], [self.nm["oid"]]), IR.table_key(Rb["fct_out"], self.cols)])
        except Exception:                                           # noqa: BLE001
            return "error"

    def dom(self, k, specs):
        key = (k, json.dumps(specs[:k + 1], sort_keys=True, default=str))
        if key not in self._dom:
            if k == 0:
                rels = {name: _proj_rows(t, self.tables) for name, t in specs[0].items()}
            else:
                try:
                    R = IR.interpret(dict(stg=specs[0], int=specs[1], fct=specs[2]), self.tables, self.state)
                except Exception:                                   # noqa: BLE001
                    R = {}
                rels = {r: R.get(r, []) for r in (list(specs[0]) + [t["latest_as"] for t in specs[0].values() if t.get("latest_as")] + ["int_orders"])}
            self._dom[key] = Dom(k, rels, specs[k])
        return self._dom[key]


# ------------------------------------------------------------------ L0 operators (generic, column-parameterised)
OPS = ("set_dedup", "add_filter", "move_filter", "json_coalesce_before", "pre_aggregate", "set_join_type", "cast_keys", "asof_backward",
       "coalesce_out", "merge_add_delete", "merge_add_update", "add_merge")
OP_NODE = dict(set_dedup=0, add_filter=0, move_filter=0, json_coalesce_before=0, pre_aggregate=1, set_join_type=1, cast_keys=1, asof_backward=1,
               coalesce_out=1, merge_add_delete=2, merge_add_update=2, add_merge=2)


def _with(spec_k, rel, **kw):
    s = dict(spec_k)
    s[rel] = dict(spec_k[rel], **kw)
    return s


def _joins(spec_k, j, **kw):
    s = dict(spec_k)
    s["joins"] = list(spec_k["joins"])
    s["joins"][j] = dict(spec_k["joins"][j], **kw)
    return s


def candidates(op, spec_k, dom):
    if OP_NODE[op] != dom.k:
        return []
    out = []
    if dom.k == 0:
        for rel in sorted(spec_k):
            t = spec_k[rel]
            cols = [n for n, _ in t["cols"]]
            if op == "set_dedup":                                  # latest / oldest per key: every int key x int order x direction
                ints = [c for c in cols if "int" in dom.roles(rel, c)]
                cur = t.get("dedup")
                cands = []
                for kc in ints:
                    for oc in ints:
                        if oc == kc:
                            continue
                        for desc in (True, False):
                            d = dict(key=["try_int", ["col", kc]], order=["try_int", ["col", oc]], desc=desc)
                            if d != cur:
                                changed = 3 if not cur else sum(d[f] != cur.get(f, True if f == "desc" else None) for f in ("key", "order", "desc"))
                                cands.append((changed, len(cands), (_with(spec_k, rel, dedup=d), f"{rel}|{kc}|{oc}|{'desc' if desc else 'asc'}")))
                out += [c for _, _, c in sorted(cands, key=lambda x: x[:2])]   # MINIMAL CHANGE first (amendment 1, before any target)
            elif op == "add_filter":                               # every low-cardinality value (<>) and every nullable column, pre / post
                conds = [(["ne", ["col", c], ["lit", v]], f"ne|{c}|{v}") for c in cols if "lowcard" in dom.roles(rel, c) for v in dom.values(rel, c)]
                conds += [(["notnull", ["col", c]], f"notnull|{c}|") for c in cols if "nulls" in dom.roles(rel, c)]
                for pos in ("pre", "post") if t.get("dedup") else ("pre",):
                    for cond, tag in conds:
                        if cond not in t.get("pre", []) + t.get("post", []):
                            out.append((_with(spec_k, rel, **{pos: t.get(pos, []) + [cond]}), f"{rel}|{pos}|{tag}"))
            elif op == "move_filter" and t.get("dedup"):
                for src, dst in (("pre", "post"), ("post", "pre")):
                    for i, c in enumerate(t.get(src, [])):
                        rest = t[src][:i] + t[src][i + 1:]
                        out.append((_with(spec_k, rel, **{src: rest, dst: t.get(dst, []) + [c]}), f"{rel}|{src}|{i}|{c[0]}"))
            elif op == "json_coalesce_before":
                for i, (n, x) in enumerate(t["cols"]):
                    if x[0] == "json" and x[2].startswith("after."):
                        cs = [list(cc) for cc in t["cols"]]
                        cs[i] = [n, ["coalesce", x, ["json", x[1], "before." + x[2][6:]]]]
                        out.append((_with(spec_k, rel, cols=cs), f"{rel}|{n}"))
    elif dom.k == 1:
        for j, jn in enumerate(spec_k["joins"]):
            if op == "pre_aggregate" and jn["how"] != "asof" and jn["rkey"][0] in ("try_int", "col"):
                by = sorted(IR.cols_of(jn["rkey"]))[0]
                for o, _ in jn["take"][:1]:
                    for m in sorted(c for c in (dom.rels.get(jn["rel"]) or [{}])[0] if "int" in dom.roles(jn["rel"], c) and c != by):
                        for f in ("sum", "max", "count"):
                            agg = dict(by=by, measures=[[o, f, ["col", m]]])
                            if agg != jn.get("agg"):
                                out.append((_joins(spec_k, j, agg=agg, take=[[o, o]]), f"{j}|{m}|{f}"))
            elif op == "set_join_type" and jn["how"] in ("left", "inner"):
                out.append((_joins(spec_k, j, how="left" if jn["how"] == "inner" else "inner"), f"{j}|{'left' if jn['how'] == 'inner' else 'inner'}"))
            elif op == "cast_keys" and jn["how"] != "asof" and (jn["lkey"][0] != "try_int" or jn["rkey"][0] != "try_int"):
                out.append((_joins(spec_k, j, **{side: (jn[side] if jn[side][0] == "try_int" else ["try_int", jn[side]]) for side in ("lkey", "rkey")}), str(j)))
            elif op == "asof_backward" and jn["how"] == "asof" and jn.get("strategy") == "forward":
                out.append((_joins(spec_k, j, strategy="backward"), str(j)))
        if op == "coalesce_out":
            for i, (n, x) in enumerate(spec_k["out"]):
                if x == ["col", n] and "int" in dom.roles("int_orders", n):
                    s = dict(spec_k)
                    s["out"] = list(spec_k["out"])
                    s["out"][i] = [n, ["coalesce", x, ["lit", 0]]]
                    out.append((s, n))
    else:
        m = spec_k.get("merge")
        if op == "merge_add_delete" and m and not m["delete"]:
            out.append((dict(spec_k, merge=dict(m, delete=True)), ""))
        elif op == "merge_add_update" and m and not m["update"]:
            out.append((dict(spec_k, merge=dict(m, update=True)), ""))
        elif op == "add_merge" and not m:
            for lr in [r for r in dom.rels if r.endswith("_latest")]:
                active = lr[: -len("_latest")]
                for kc in sorted(c for c in (dom.rels.get(lr) or [{}])[0] if "int" in dom.roles(lr, c) and "unique" in dom.roles(lr, c)):
                    out.append((dict(spec_k, merge=dict(key=spec_k["group"][0][0], update=True, delete=True, deletes=dict(rel=lr, key=["try_int", ["col", kc]], minus=active))),
                                f"{lr}|{kc}"))
    return out


def rel_role(dom, rel):
    t = (dom.spec or {}).get(rel) if dom.k == 0 else None
    r = []
    if t is not None:
        r.append("cdc" if any(x[0] in ("json", "coalesce") and "json" in json.dumps(x) for _, x in t["cols"]) else "plain")
        r.append("dedup" if t.get("dedup") else "nodedup")
    return tuple(r) or ("node",)


def abstract_edit(op, prm, dom, fine=True):
    parts = prm.split("|") if prm else []
    if dom.k == 0 and parts:
        rel = parts[0]
        out = [op, ("rel", rel_role(dom, rel))]
        if op == "set_dedup":
            out += [("key", dom.roles(rel, parts[1])), ("order", dom.roles(rel, parts[2])), ("dir", parts[3])]
        elif op == "add_filter":
            out += [("pos", parts[1]), ("cond", parts[2]), ("col", dom.roles(rel, parts[3]))]
            if parts[2] == "ne":
                out.append(("value", parts[4]))
        elif op == "move_filter":
            out += [("from", parts[1]), ("cond", parts[3])]
        elif op == "json_coalesce_before":
            out.append(("col", dom.roles(rel, parts[1])))
        return tuple(out)
    if dom.k == 1 and parts:
        if op == "coalesce_out":
            return (op, ("col", dom.roles("int_orders", parts[0])))
        jn = dom.spec["joins"][int(parts[0])]
        jr = ("how:" + jn["how"], "agg" if jn.get("agg") else "noagg", "typed" if jn["lkey"][0] == "try_int" else "raw")
        out = [op, ("join", jr)]
        if op == "pre_aggregate":
            out += [("col", dom.roles(jn["rel"], parts[1])), ("agg", parts[2])]
        elif op == "set_join_type":
            out.append(("to", parts[1]))
        return tuple(out)
    if dom.k == 2 and op == "add_merge":
        return (op, ("key", dom.roles(parts[0], parts[1])))
    return (op,)


def bind(skill, inv, specs, k, cap=2):
    """Concrete edit paths at node k that ground the (role-form) skill in THIS project."""
    paths = [([], specs)]
    for e in skill["edits"]:
        e = SK._tup(e)
        if OP_NODE.get(e[0]) != k:
            return []
        nxt = []
        for path, sp in paths:
            dom = inv.dom(k, sp)
            for s2, prm in candidates(e[0], sp[k], dom):
                if SK._matches(e, abstract_edit(e[0], prm, dom)):
                    sp2 = list(sp)
                    sp2[k] = s2
                    nxt.append((path + [(k, e[0], prm)], sp2))
                    if len(nxt) >= cap:
                        break
        paths = nxt[:cap]
        if not paths:
            return []
    return [p for p, _ in paths]


def replay(inv, path, start=None):
    specs = [copy.deepcopy(s) for s in (start if start is not None else inv.legacy)]
    for k, op, prm in path:
        nxt = next((s for s, p in candidates(op, specs[k], inv.dom(k, specs)) if p == prm), None)
        if nxt is not None:
            specs[k] = nxt
    return specs


# ------------------------------------------------------------------ hidden verification (evaluation only)
def verify_hidden(project, specs, engine=None):
    hid = Path(project["hidden_dir"])
    c = json.loads((Path(project["ws"]) / "contract.json").read_text())
    eng = engine or c["engine"]
    spec = Inv10d.spec_of(specs)
    fails = []
    for b in ("hidden1", "hidden2"):
        T = W.load_tables(hid, c["tables"], prefix=f"{b}_")
        S = json.loads((hid / f"{b}_state.json").read_text())
        exp_ = json.loads((hid / f"{b}_expected.json").read_text())
        try:
            got = EN.run(spec, T, S, eng, ["fct_out"])["fct_out"]
        except Exception as e:                                      # noqa: BLE001
            fails.append(f"{b}: runtime {type(e).__name__}")
            continue
        if IR.table_key(got, exp_["cols"]) != IR.table_key([dict(zip(exp_["cols"], r)) for r in exp_["rows"]], exp_["cols"]):
            fails.append(f"{b}: output differs")
    return dict(ok=not fails, fails=fails)


def sig(x):
    return hashlib.sha1(str(x).encode()).hexdigest()[:12]
