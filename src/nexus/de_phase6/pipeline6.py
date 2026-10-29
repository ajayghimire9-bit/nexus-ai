"""Phase 6 multi-stage investigation, repair search and the unified acceptance gate de_accept_v3 (NOT LOCKED).

Inv6 reads a project's real stage files (any ir6 language), lifts each into the stage IR, and executes candidate pipelines
on the real engines (stage k's input = stage k-1's clean output). Evidence: the final public checks scored on the
synthesis fold of the golden rows (de_accept_v2 K-fold), every intermediate stage's schema.yml tests, runtime errors and
per-column diff kinds. Each stage has a Dom (its input under the current candidate), so the Phase 4 / Phase 6 operators
apply to any stage.

search(mode, skills, prescreen):
  whole      best-first over edits (stage, operator, parameter) of every stage, ordered by the learned policy pi
  decompose  stage-wise: edits only for the earliest stage whose schema.yml tests fail; the last stage is searched against
             the final checks (localises a CDC fault before an analytical join is touched)
  skills     invented skills (skills6) bound to the stage's schema are tried first and CHAINED across stages
  prescreen  Spark stages execute on SQLite during search (business semantics; cheap); survivors are verified on Spark
de_accept_v3 (applied by every arm): (1) held-back golden fold; (2) pipeline invariants - no crash on the declared engines
(ANSI), order invariance, stress rows (dirty / zero / empty), empty batch, relabelling invariance on identity columns, output
types and unique key; (3) ambiguity closure at edit distance 1 over ALL stages (other parameters, dropped edits, one
inserted edit), compared on boundary rows of every filter threshold AND on single-row probes built from every visible row
(the Phase 5 multi-filter boundary detector, now part of the gate). Disagreements become DECISION POINTS for the
investigation procedure; a closure cut by its caps abstains."""
from __future__ import annotations

import copy
import itertools
import json
import time
from pathlib import Path

import yaml

from nexus.de_phase4 import accept as AC, adapter as AD, ir, ops as O, world as W
from nexus.de_phase6 import engines6 as E, ir6, world6 as W6

MAX_ALTS, MAX_COMP = 500, 60


class Dom:
    def __init__(self, header, rows, state, legacy, golden_strs=()):
        self.header, self.rows, self.state, self.legacy = header, rows, state, legacy
        self.files = [(f, k) for f, d in state.items() for k, v in d.items() if isinstance(v, (int, float))]
        self.domain = {c: {r.get(c, "") for r in rows} for c in header}
        n_int = {c: sum(ir._is_int(r.get(c, "")) for r in rows) for c in header}
        cast = {n[1][1] for _, _, x in ir.exprs(legacy) for n in ir.walk(x) if n[0] in ("cast_int", "try_int", "valid_int") and n[1][0] == "col"}
        self.int_like = {c for c in header if c != "id" and (c in cast or n_int[c] >= 0.5 * max(1, len(rows)))}
        self.dirty_cols = {c for c in self.int_like if n_int[c] < len(rows)}
        self.text_cols = {c for c in header if c != "id" and c not in self.int_like}
        self.unique_cols = {c for c in header if len(self.domain[c]) == len(rows)}
        self.num_range = {c: (min(v), max(v)) for c in self.int_like for v in [[int(r[c].strip()) for r in rows if ir._is_int(r.get(c, ""))]] if v}
        raw_vals = {v for r in rows for v in r.values()}
        self.consts_num, self.consts_str = [0], sorted({s for s in golden_strs if s not in raw_vals})
        self.contract = {}


def _stage_tests(ws):
    p = Path(ws) / "models" / "schema.yml"
    if not p.exists():
        return {}
    out = {}
    for m in (yaml.safe_load(p.read_text()) or {}).get("models", []):
        tl = []
        for c in m.get("columns", []):
            for t in c.get("tests", []):
                if isinstance(t, dict) and "accepted_values" in t:
                    tl.append(dict(column=c["name"], test="accepted_values", values=t["accepted_values"]["values"]))
                else:
                    tl.append(dict(column=c["name"], test=t))
        out[m["name"]] = tl
    return out


class Inv6:
    def __init__(self, project, gate=True):
        self.p = project
        ws = Path(project["ws"])
        self.contract = json.loads((ws / "contract.json").read_text())
        self.stages = []
        self.legacy = []
        for k, st in enumerate(self.contract["stages"]):
            text = (ws / st["file"]).read_text()
            self.legacy.append(ir6.lift(text, st["legacy_language"]))                     # raises AD.Unsupported
            self.stages.append(dict(engine=st["engine"], target=st["target_language"], legacy_language=st["legacy_language"], model=st["model"],
                                    in_cols=None))
        self.header, self.rows = W.read_csv(ws / "data" / "visible.csv")
        for st in self.stages:
            st["in_cols"] = self.header
        self.state = W.state_of(ws)
        tests = _stage_tests(ws)
        self.tests = [tests.get(st["model"], []) for st in self.stages]
        ex = next(c for c in self.contract["public_checks"] if c["kind"] == "example_rows")
        self.cols, self.golden = ex["cols"], ex["rows"]
        self.golden_strs = {v for row in ex["rows"] for v in row if isinstance(v, str)}
        q = next((c for c in self.contract["public_checks"] if c["kind"] == "quarantine_ids"), None)
        self.q_all = q["ids"] if q else None
        self.n_rows = next(c["n"] for c in self.contract["public_checks"] if c["kind"] == "row_count")
        self.ukey = self.contract.get("unique_key")
        self.folds = AC.folds(ex["rows"], self.q_all, project["pid"]) if gate else [(ex["rows"], [], self.q_all, [])]
        self.set_fold(0)
        self.runs = {"sqlite": 0, "duckdb": 0, "spark": 0}
        self._dom = {}
        self.claim_refs = set()                         # subjects documented in the requirement files
        for src in ("contract.json", "docs/runbook.json", "docs/ticket.json"):
            fp = ws / src
            if fp.exists():
                d = json.loads(fp.read_text())
                for c in (d.get("requirements", []) if src == "contract.json" else d.get("claims", [])):
                    if "state_ref" in c.get("subject", {}):
                        self.claim_refs.add(json.dumps(c["subject"]["state_ref"]))

    def set_fold(self, f):
        self.fold = f
        self.synth, self.held, self.q_synth, self.q_held = self.folds[f]

    # ---- execution
    def exec(self, specs, rows=None, prescreen=True, final_only=True):
        for st in self.stages:
            e = "sqlite" if prescreen else st["engine"]
            self.runs[e] += 1
        final, per = W6.run_pipeline(self.stages, specs, self.rows if rows is None else rows, self.state, fast=prescreen)
        return final if final_only else (final, per)

    def dom(self, k, specs):
        key = (k, json.dumps(specs[:k], sort_keys=True))
        if key not in self._dom:
            rows = self.rows
            if k:
                try:
                    _, per = self.exec(list(specs[:k]) + list(specs[k:]), prescreen=True, final_only=False)
                    rows = [{c: ("" if v is None else (str(int(v)) if isinstance(v, float) and v == int(v) else str(v))) for c, v in r.items()}
                            for r in per[k - 1]["clean"]]
                except W.RunError:
                    rows = []
            header = list(rows[0].keys()) if rows else self.header
            self._dom[key] = Dom(header, rows, self.state, self.legacy[k], self.golden_strs if k == len(self.stages) - 1 else ())
        return self._dom[key]

    def checks(self, final, per):
        out = final["clean"]
        have = {tuple(W.num(r.get(c)) for c in self.cols) for r in out}
        passed, failed = [], []

        def mark(k, ok):
            (passed if ok else failed).append(k)
        mark("example_rows", all(tuple(W.num(v) for v in row) in have for row in self.synth))
        mark("row_count", len(out) == self.n_rows)
        if self.ukey:
            vals = [r.get(self.ukey) for r in out]
            mark("unique", len(vals) == len(set(vals)))
        held_ok = all(tuple(W.num(v) for v in row) in have for row in self.held)
        if self.q_all is None:
            mark("schema", final.get("rejects") is None)
        else:
            got = {str(r.get("id")) for r in (final.get("rejects") or [])}
            mark("quarantine_ids", set(self.q_synth) <= got and len(got) == len(self.q_all))
            held_ok = held_ok and set(self.q_held) <= got
        stage_fail = []
        for k, (tl, r) in enumerate(zip(self.tests, per)):
            if tl:
                stage_fail.append(W6.check_stage_tests(tl, r))
            else:
                stage_fail.append([])
        return passed, failed, held_ok, stage_fail

    def run(self, specs, prescreen=True):
        try:
            final, per = self.exec(specs, prescreen=prescreen, final_only=False)
        except W.RunError as e:
            return dict(ok=False, held_ok=False, error=e.cls, passed=[], failed=["no_error"], stage_fail=[["error"]] * len(self.stages),
                        features={f"err:{str(e.cls)[:24]}", "fail:no_error"}, score=0.0)
        passed, failed, held_ok, stage_fail = self.checks(final, per)
        n_tests = sum(len(t) for t in self.tests) or 1
        st_pass = 1 - sum(len(f) for f in stage_fail) / n_tests
        feats = {f"fail:{k}" for k in failed} | self.diff_features(final) | \
            {f"stage_fail:{f.split(':')[0]}" for fs in stage_fail for f in fs}
        return dict(ok=not failed, held_ok=held_ok, error=None, passed=["no_error"] + passed, failed=failed, stage_fail=stage_fail,
                    features=feats, score=1 + len(passed) + self.graded(final) + 0.5 * st_pass)

    def graded(self, res):
        out = res["clean"]
        rows = self.synth
        if not rows:
            return 0.0
        have = {tuple(W.num(r.get(c)) for c in self.cols) for r in out}
        frac = sum(tuple(W.num(v) for v in row) in have for row in rows) / len(rows)
        close = max(0.0, 1 - abs(len(out) - self.n_rows) / max(self.n_rows, 1))
        return round(0.6 * frac + 0.3 * close, 4)

    def diff_features(self, res):
        got = {}
        for r in res["clean"]:
            got.setdefault(W.num(r.get(self.cols[0])), []).append(r)
        f = set()
        if any(len(v) > 1 for v in got.values()):
            f.add("diff:dup_keys")
        if len(res["clean"]) > self.n_rows:
            f.add("diff:extra_rows")
        if len(res["clean"]) < self.n_rows:
            f.add("diff:too_few_rows")
        for row in self.synth:
            g = got.get(W.num(row[0]))
            if not g:
                f.add("diff:missing_rows")
                continue
            for j, c in enumerate(self.cols[1:], 1):
                if W.num(row[j]) != W.num(g[0].get(c)):
                    f.add("diff:text_value" if isinstance(row[j], str) else "diff:expect_null" if row[j] is None else
                          "diff:got_null" if g[0].get(c) is None else "diff:value")
        return f


# ------------------------------------------------------------------ the unified gate de_accept_v3
def _fresh(inv, rows):
    fresh = {c for c in inv.header if c == "id" or (c not in inv.dom(0, inv.legacy).int_like and len({r[c] for r in rows}) >= 0.6 * len(rows))}
    return fresh


def _probe(inv, j, fresh, tag="PQ"):
    r = dict(inv.rows[j % len(inv.rows)])
    for c in fresh:
        r[c] = f"{tag}{j}_{r[c]}"
    return r


def invariants(inv, specs):
    cols, types = inv.cols, inv.contract.get("output_types", {})
    d0 = inv.dom(0, specs)
    fresh = _fresh(inv, inv.rows)
    viol = []
    try:
        base = inv.exec(specs, prescreen=False)
        if W6.key_of(inv.exec(specs, inv.rows[::-1], prescreen=False), cols) != W6.key_of(base, cols):
            viol.append("order_dependence")
        stress = []
        for j, c in enumerate(sorted(d0.dirty_cols)):
            for v in ("n/a", "12x", ""):
                r = _probe(inv, 100 + 3 * j + len(stress), fresh)
                r[c] = v
                stress.append(r)
        for c in sorted(d0.int_like - d0.dirty_cols)[:3]:
            r = _probe(inv, 200 + len(stress), fresh)
            r[c] = "0"
            stress.append(r)
        for c in sorted(d0.text_cols - fresh)[:3]:
            r = _probe(inv, 300 + len(stress), fresh)
            r[c] = ""
            stress.append(r)
        st = inv.exec(specs, inv.rows + stress, prescreen=False)
        inv.exec(specs, inv.rows[:0], prescreen=False)
        last = specs[-1]
        uk = inv.ukey
        key_expr = last["group"][1] if last.get("group") and last["group"][0] == uk else next((x for n, x in last["outputs"] if n == uk), None)
        ren = set(fresh) | ({uk} if uk in inv.header and key_expr == ["col", uk] else set())
        mirror = [{c: ("z" + v if c in ren and v.strip() else v) for c, v in r.items()} for r in inv.rows]
        mres = inv.exec(specs, inv.rows + mirror, prescreen=False)
    except W.RunError as e:
        return [f"crash:{e.cls}"]
    for r in st["clean"]:
        for c, t in types.items():
            v = r.get(c)
            if v is not None and ((t == "int" and not (isinstance(v, int) and not isinstance(v, bool))) or
                                  (t == "real" and not isinstance(v, (int, float))) or (t == "text" and not isinstance(v, str))):
                viol.append(f"type:{c}")
                break
    uk = inv.ukey
    if uk and uk in cols:
        ks = [r.get(uk) for r in st["clean"]]
        if len(ks) != len(set(ks)):
            viol.append("unique")
        b = {r.get(uk): tuple(W.num(r.get(c)) for c in cols) for r in base["clean"]}
        s_ = {r.get(uk): tuple(W.num(r.get(c)) for c in cols) for r in st["clean"]}
        if any(k in s_ and s_[k] != v for k, v in b.items()) or any(k not in s_ for k in b):
            viol.append("corruption")
        if uk in ren:
            exp_ = base["clean"] + [{c: ("z" + str(v) if c == uk else v) for c, v in r.items()} for r in base["clean"]]
        else:
            exp_ = [{c: (2 * v if c != uk and isinstance(v, (int, float)) and not isinstance(v, bool) else v) for c, v in r.items()} for r in base["clean"]]
        if W.table_key(mres["clean"], cols) != W.table_key(exp_, cols):
            viol.append("relabelling")
    return sorted(set(viol))


def alternatives(inv, path):
    """Competing pipelines at edit distance 1 from the path [(stage, op, prm)]: other parameters, dropped, one inserted."""
    out, seen = [], set()
    x = replay(inv, path)
    seen.add(json.dumps(x, sort_keys=True))
    for i, (k, op, prm) in enumerate(path):
        before = replay(inv, path[:i])
        variants = [(s, p) for s, p in E.candidates(op, before[k], inv.dom(k, before)) if p != prm] + [(None, None)]
        for s, p in variants:
            specs = list(before)
            if s is not None:
                specs[k] = s
            y = replay(inv, path[i + 1:], specs)
            key = json.dumps(y, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(dict(specs=y, pos=i, stage=k, op=op, prm_x=prm, prm_y=p))
    for k in range(len(inv.stages)):
        dk = inv.dom(k, x)
        for op in E.OPS:
            for s, p in E.candidates(op, x[k], dk):
                if op in ("filter_file", "filter_cmp", "col_compare", "exclude_value"):
                    # inserted filters are hypotheses only on DOCUMENTED subjects (and never when vacuous on the visible
                    # stage input): every fault is visible by construction, so an undocumented extra filter is unmotivated
                    rhs = json.dumps(_parse(op, p)[2]) if op != "exclude_value" else None
                    if rhs not in inv.claim_refs or _vacuous(dk, s, x[k]):
                        continue
                y = list(x)
                y[k] = s
                key = json.dumps(y, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    out.append(dict(specs=y, pos=len(path), stage=k, op=op, prm_x=None, prm_y=p))
    return out


def _vacuous(dom, s_new, s_old):
    try:
        return sum(ir.ev(s_new["filter"], dict(r, __rowid=0), dom.state) is True for r in dom.rows) == \
            sum((ir.ev(s_old["filter"], dict(r, __rowid=0), dom.state) is True) if s_old.get("filter") else True for r in dom.rows)
    except Exception:                                  # noqa: BLE001  (a filter the reference cannot evaluate on dirty text)
        return False


def replay(inv, path, start=None):
    specs = [copy.deepcopy(s) for s in (start if start is not None else inv.legacy)]
    for k, op, prm in path:
        nxt = next((s for s, p in E.candidates(op, specs[k], inv.dom(k, specs)) if p == prm), None)
        if nxt is not None:
            specs[k] = nxt
    return specs


def _thresholds(specs, state):
    out = []
    for sp in specs:
        for n in ir.walk(sp.get("filter") or ["lit", None]):
            if n[0] in ("gt", "ge", "lt", "le") and n[1][0] == "cast_int" and n[1][1][0] == "col":
                rhs = n[2]
                out.append((n[1][1][1], rhs))
    return out


def probe_rows(inv, specs_list):
    """Single-row probes from every visible template: each filter column set to its threshold (state value, or the
    compared column's value), identity columns fresh."""
    fresh = _fresh(inv, inv.rows)
    rows = []
    for col, rhs in sorted({(c, json.dumps(r)) for s in specs_list for c, r in _thresholds(s, inv.state)}):
        rhs = json.loads(rhs)
        for j, base in enumerate(inv.rows):
            q = dict(base)
            for c in fresh:
                q[c] = f"PQ{j}_{q[c]}"
            if rhs[0] == "cast_int" and rhs[1][0] == "col":
                q[col] = q.get(rhs[1][1], q[col])
            else:
                try:
                    q[col] = str(ir.ev(rhs, {}, inv.state))
                except Exception:                    # noqa: BLE001
                    continue
            rows.append(q)
    return rows


def okey(inv, specs, rows):
    try:
        return json.dumps(W6.key_of(inv.exec(specs, rows, prescreen=True), inv.cols), default=str)
    except W.RunError:
        return "error"


def closure(inv, path, deadline=None):
    """-> dict(status unique | ambiguous | cut, decision points [...], scope)."""
    x = replay(inv, path)
    alts = alternatives(inv, path)
    if len(alts) > MAX_ALTS:
        return dict(status="cut", scope=dict(alternatives=len(alts)), dps=[])
    comp = []
    for a in alts:
        if deadline and time.time() > deadline:
            return dict(status="cut", scope=dict(alternatives=len(alts), note="budget"), dps=[])
        e = inv.run(a["specs"], prescreen=True)
        if not (e["ok"] and e["held_ok"]):
            continue
        comp.append(a)
        if len(comp) > MAX_COMP:
            return dict(status="cut", scope=dict(alternatives=len(alts), competitors=len(comp)), dps=[])
    probes = probe_rows(inv, [x] + [a["specs"] for a in comp])
    groups = {}
    for a in comp:
        diff_row = None
        for q in probes:
            if okey(inv, x, [q]) != okey(inv, a["specs"], [q]):
                diff_row = q
                break
        if diff_row is None:
            continue
        if invariants(inv, a["specs"]):
            continue
        groups.setdefault((a["stage"], a["pos"], a["op"]), []).append((a, diff_row))
    dps = []
    for (k, pos, op), items in sorted(groups.items()):
        prm_x = path[pos][2] if pos < len(path) else None
        options = [prm_x] + [a["prm_y"] for a, _ in items]
        specs = [x] + [a["specs"] for a, _ in items]
        probe = items[0][1]
        dp = dict(stage=k, pos=pos, op=op, options=options, specs=specs, probe=probe, ref=None, col=None, resolved=None, via=None,
                  conflict=False, undecided=False, claims=[])
        if op in ("filter_file", "filter_cmp", "col_compare"):
            parsed = [_parse(op, o) for o in options if o]
            if len({json.dumps(r) for _, _, r in parsed}) == 1 and len({c for c, _, _ in parsed}) == 1:
                dp["col"], _, dp["ref"] = parsed[0]
        dp["option_keys"] = [okey(inv, s, [probe]) for s in specs]
        dp["effects"] = ["kept" if k_ != "error" and json.loads(k_)[0] else "excluded" for k_ in dp["option_keys"]]
        dps.append(dp)
    return dict(status="unique" if not dps else "ambiguous", dps=dps, scope=dict(alternatives=len(alts), competitors=len(comp), decision_points=len(dps)))


def _parse(op, prm):
    if op == "col_compare":
        a, cmp, b = prm.split(" ")
        return a, cmp, ["cast_int", ["col", b]]
    c, cmp, v = prm.split(" ", 2)
    return c, cmp, json.loads(v)


# ------------------------------------------------------------------ repair search
def op_order(de, feats, order=None):
    if order:
        return list(order) + [o for o in E.OPS if o not in order]
    sc = {o: sum(de.get("w", {}).get(f, {}).get(o, 0.0) for f in feats) for o in E.OPS}
    return sorted(E.OPS, key=lambda o: (-sc[o], E.OPS.index(o)))


def search(inv, de, budget_s, mode="whole", use_skills=True, prescreen=True, order=None, max_depth=8, stall_frac=0.25, skills_mod=None):
    """-> dict(outcome submitted | ambiguous | none | unsupported, path, specs, dps, trace, runs, wall, partials, refutations)."""
    t0 = time.time()
    deadline = t0 + budget_s
    ev0 = inv.run(inv.legacy, prescreen)
    trace = [dict(step="investigate", failed=ev0["failed"], stage_fail=ev0["stage_fail"], features=sorted(ev0["features"]))]
    tick = itertools.count()
    refutations, partials = [], []
    result = {}
    for f in range(len(inv.folds)):
        if time.time() > deadline:
            break
        if f:
            inv.set_fold(f)
            ev0 = inv.run(inv.legacy, prescreen)
        seen = set()
        frontier = [dict(path=[], specs=[copy.deepcopy(s) for s in inv.legacy], ev=ev0, tick=next(tick), done=False)]
        if use_skills and skills_mod is not None and de.get("skills"):
            for path in skills_mod.proposals(de["skills"], inv, frontier[0], ev0):
                specs = replay(inv, path)
                ev = inv.run(specs, prescreen)
                frontier.append(dict(path=path, specs=specs, ev=ev, tick=next(tick), done=False, skill=True))
                trace.append(dict(step="skill", edits=path, ok=ev["ok"], score=round(ev["score"], 3)))
        best_t, best_s = time.time(), max(n["ev"]["score"] for n in frontier)
        stall = max(0.25, stall_frac * budget_s)
        while time.time() < deadline:
            ready = [n for n in frontier if n["ev"]["ok"] and not n.get("tried")]
            for n in sorted(ready, key=lambda n: -n["ev"]["score"]):
                n["tried"] = True
                if not n["ev"]["held_ok"]:
                    result = dict(held_fail=True)
                    break
                if prescreen and not n.get("native"):          # survivors of the SQLite screen run on the declared engines
                    ev_n = inv.run(n["specs"], prescreen=False)
                    if not (ev_n["ok"] and ev_n["held_ok"]):
                        trace.append(dict(step="engine_verify_failed", edits=n["path"], error=ev_n.get("error"), failed=ev_n["failed"]))
                        frontier.append(dict(n, ev=ev_n, done=False, native=True, tried=False, tick=next(tick)))
                        continue
                viol = invariants(inv, n["specs"])
                if viol:
                    trace.append(dict(step="gate_reject", edits=n["path"], violations=viol))
                    continue
                cl = closure(inv, n["path"], deadline=deadline + 0.5 * budget_s)
                trace.append(dict(step="closure", edits=n["path"], status=cl["status"], scope=cl["scope"]))
                if cl["status"] == "cut":
                    return _out("ambiguous_cut", n, [], inv, t0, trace, refutations, partials)
                return _out("submitted" if cl["status"] == "unique" else "ambiguous", n, cl["dps"], inv, t0, trace, refutations, partials)
            if result.get("held_fail"):
                break
            cand = [n for n in frontier if not n["done"] and len(n["path"]) < max_depth]
            if not cand:
                break
            node = max(cand, key=lambda n: (n["ev"]["score"], -len(n["path"]), -n["tick"]))
            node["done"] = True
            if mode == "decompose":
                failing = [k for k, fs in enumerate(node["ev"]["stage_fail"]) if fs]
                stages = [failing[0]] if failing else [len(inv.stages) - 1]
            else:
                stages = list(range(len(inv.stages)))
            feats = node["ev"]["features"]
            n_before = len(frontier)
            for op in op_order(de, feats, order):
                for k in stages:
                    for s2, prm in E.candidates(op, node["specs"][k], inv.dom(k, node["specs"])):
                        if time.time() > deadline:
                            break
                        specs = list(node["specs"])
                        specs[k] = s2
                        key = json.dumps(specs, sort_keys=True)
                        if key in seen:
                            continue
                        seen.add(key)
                        native = node.get("native", False)
                        ev = inv.run(specs, prescreen and not native)
                        child = dict(path=node["path"] + [(k, op, prm)], specs=specs, ev=ev, tick=next(tick), done=False, pre=sorted(feats),
                                     native=native)
                        gain = ev["score"] - node["ev"]["score"]
                        if gain > 0 or ev["ok"]:
                            frontier.append(child)
                            if gain > 0:
                                partials.append(dict(stage=k, op=op, prm=prm, pre=sorted(feats), fixes=sorted(feats - ev["features"]), gain=round(gain, 3)))
                        elif ev["features"] == feats:
                            refutations.append(dict(op=op, pre=sorted(feats)))
            new = max((n["ev"]["score"] for n in frontier[n_before:]), default=-1)
            if new > best_s:
                best_s, best_t = new, time.time()
            elif time.time() - best_t > stall:
                trace.append(dict(step="stall", after_s=round(time.time() - t0, 3)))
                break
        if not result.get("held_fail"):
            break
        result = {}
    return dict(outcome="none", path=None, specs=None, dps=[], trace=trace, runs=dict(inv.runs), wall=round(time.time() - t0, 3),
                refutations=refutations, partials=partials, start_features=sorted(ev0["features"]))


def _out(outcome, node, dps, inv, t0, trace, refutations, partials):
    return dict(outcome=outcome, path=node["path"], specs=node["specs"], dps=dps, trace=trace, runs=dict(inv.runs), wall=round(time.time() - t0, 3),
                refutations=refutations, partials=partials, start_features=sorted(trace[0]["features"]), edit_pre=[])


def verify_on_engines(inv, specs):
    """The submission's final acceptance run on the DECLARED engines (Spark included)."""
    e = inv.run(specs, prescreen=False)
    return e["ok"] and e["held_ok"], e
