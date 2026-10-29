"""Phase 4 DE learner (NOT LOCKED): the Phase 3 operating cycle (campaign3.de_learner) on REAL pipeline files.

INVESTIGATE  read contract.json, the state files, the visible batch and pipeline.sql / pipeline.py; lift the file into the
             stage IR (adapter: sqlglot / Python ast); execute the legacy file on the project's engine (+ on SQLite for a
             Spark project: differential evidence); split the golden rows (de_accept_v2: 80 % synthesis / 20 % held back)
ATTEMPT      best-first repair search over generic operators (ops.py), ordered by the learned policy pi_de, the failure-
             archive priority and the improver's localisation order; WHOLE-pipeline or STAGE-WISE decomposition; every
             candidate is lowered to the project's language and the TEXT is executed on the real engine. For Spark projects
             the improver's cross-engine mode 'sqlite_first' screens candidates on SQLite (cheap) and executes on Spark only
             those that pass there, then continues Spark-natively from Spark failures (ANSI errors) - 'off' = Spark only.
LEARN FROM FAILURE  refutations (edits that did not change the evidence), VERIFIED partial repairs (more synthesis checks
             AND no loss on the held-back split; recorded with the evidence features they removed and their stage) go to P;
             refuted submissions (hidden-batch failures during source learning) update the disambiguation preferences
REPAIR / VERIFY  submit only through de_accept_v2; the independent evaluator then runs the submitted FILE on hidden batches
REUSE        admitted skills (full repairs and stage skills promoted from P) and pi_de / prefs apply to the next project.
The stall rule ends a search when the best score has not improved for max(0.25 s, stall_frac x budget) (an engineer
escalating). With cross_engine = sqlite_first a Spark project is searched on SQLite; Spark-native search continues only
from SQLite-passing candidates that failed on Spark (ANSI semantics) - when SQLite screening finds nothing, the search ends
(Spark-native search from scratch is ~40x slower per candidate)."""
from __future__ import annotations

import copy
import itertools
import json
import random
import re
import time
from pathlib import Path

from nexus.de_phase4 import accept as AC, adapter as AD, ir, ops as O, world as W

M0_SEARCH = dict(localize="policy", decompose="whole", max_depth=6, stall_frac=0.2, cross_engine="sqlite_first")
M0_MEMORY = dict(p_priority=0.5, skill_match=0.5, max_skills=12, prune_unused=0)
M0_LEARN = dict(lr=1.0, neg_lr=0.5, partial_lr=0.5)
M0_AMBIG = dict(mode="pref", margin=1.0)


def empty_de():
    return dict(w={}, skills={}, P=[], prefs={}, next_id=0)


# ------------------------------------------------------------------ investigation
class Investigation:
    def __init__(self, project, runtime, gate=True):
        ws = Path(project["ws"])
        self.pid, self.rt, self.gate = project["pid"], runtime, gate
        self.sq = W.SQLiteCode() if runtime.name != "sqlite" else runtime
        self.contract = json.loads((ws / "contract.json").read_text())
        self.text, self.lang, self.legacy = AD.read_pipeline(ws)          # raises AD.Unsupported
        self.header, self.rows = W.read_csv(ws / "data" / "visible.csv")
        self.state = W.state_of(ws)
        self.files = [(f, k) for f, d in self.state.items() for k, v in d.items() if isinstance(v, (int, float))]
        self.domain = {c: {r[c] for r in self.rows} for c in self.header}
        n_int = {c: sum(ir._is_int(r[c]) for r in self.rows) for c in self.header}
        cast_in_legacy = {n[1][1] for _, _, x in ir.exprs(self.legacy) + [("d", 0, (self.legacy.get("dedup") or {}).get("order") or ["lit", 0])]
                          for n in ir.walk(x) if n[0] in ("cast_int", "try_int", "valid_int") and n[1][0] == "col"}
        # integer-like: the legacy author casts it to an integer, or at least half of the visible values are integers
        self.int_like = {c for c in self.header if c != "id" and (c in cast_in_legacy or n_int[c] >= 0.5 * len(self.rows))}
        self.dirty_cols = {c for c in self.int_like if n_int[c] < len(self.rows)}
        self.num_range = {c: (min(v), max(v)) for c in self.int_like
                          for v in [[int(r[c].strip()) for r in self.rows if ir._is_int(r[c])]] if v}
        self.text_cols = {c for c in self.header if c != "id" and c not in self.int_like}
        self.unique_cols = {c for c in self.header if len(self.domain[c]) == len(self.rows)}
        raw_vals = {v for r in self.rows for v in r.values()}
        ex = next(c for c in self.contract["public_checks"] if c["kind"] == "example_rows")
        self.consts_num = [0]
        self.consts_str = sorted({v for row in ex["rows"] for v in row if isinstance(v, str) and v not in raw_vals})
        q = next((c for c in self.contract["public_checks"] if c["kind"] == "quarantine_ids"), None)
        self.q_all = q["ids"] if q else None
        self.folds = AC.folds(ex["rows"], self.q_all, self.pid) if gate else [(ex["rows"], [], self.q_all, [])]
        self.set_fold(0)
        self.cols = ex["cols"]
        self.n_rows = next(c["n"] for c in self.contract["public_checks"] if c["kind"] == "row_count")
        self.ukey = next((c["col"] for c in self.contract["public_checks"] if c["kind"] == "unique"), None)
        self.runs = {"engine": 0, "sqlite_screen": 0}

    def set_fold(self, f):
        self.fold = f
        self.synth, self.held, self.q_synth, self.q_held = self.folds[f]

    def exec(self, spec, rows, engine=None):
        rt = engine or self.rt
        self.runs["engine" if rt is self.rt else "sqlite_screen"] += 1
        return rt.run(ir.lower(spec, rt.lang), self.header, rows, self.state)

    def _checks(self, res):
        out = res["clean"]
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
        if self.q_all is None:                      # the contract has no quarantine table: producing one breaks the schema
            mark("schema", res.get("rejects") is None)
        else:
            got = {str(r.get("id")) for r in (res.get("rejects") or [])}
            mark("quarantine_ids", set(self.q_synth) <= got and len(got) == len(self.q_all))
            held_ok = held_ok and set(self.q_held) <= got
        return passed, failed, held_ok

    def run(self, spec, engine=None):
        try:
            res = self.exec(spec, self.rows, engine)
        except W.RunError as e:
            n = 4 + bool(self.ukey)
            return dict(ok=False, held_ok=False, error=e.cls, err_loc=_err_loc(e.msg), passed=[], failed=["no_error"],
                        features={f"err:{_err_class(e.cls)}", "fail:no_error"}, score=0.0, n_checks=n)
        passed, failed, held_ok = self._checks(res)
        passed = ["no_error"] + passed
        feats = {f"fail:{k}" for k in failed} | self.diff_features(res)
        return dict(ok=not failed, held_ok=held_ok, error=None, passed=passed, failed=failed, features=feats,
                    score=len(passed) + self.graded(res), n_checks=len(passed) + len(failed), held_graded=self.graded(res, self.held))

    def visible_ok(self, spec, engine=None):
        """Synthesis + held-back checks on the project engine (screened on SQLite first for a Spark project), or only on
        `engine` when given."""
        if engine is not None:
            e = self.run(spec, engine)
            return e["ok"] and e["held_ok"]
        if self.sq is not self.rt:
            e = self.run(spec, self.sq)
            if not (e["ok"] and e["held_ok"]):
                return False
        e = self.run(spec)
        return e["ok"] and e["held_ok"]

    def graded(self, res, rows=None):
        rows = self.synth if rows is None else rows
        out = res["clean"]
        if not rows:
            return 0.0
        have = {tuple(W.num(r.get(c)) for c in self.cols) for r in out}
        frac = sum(tuple(W.num(v) for v in row) in have for row in rows) / len(rows)
        close = max(0.0, 1 - abs(len(out) - self.n_rows) / max(self.n_rows, 1))
        got = {r.get(self.cols[0]): r for r in out}
        num = []
        for row in rows:
            g = got.get(row[0])
            for j, c in enumerate(self.cols[1:], 1):
                w_, h = row[j], (g or {}).get(c)
                if isinstance(w_, (int, float)) and not isinstance(w_, bool):
                    num.append(0.0 if not isinstance(h, (int, float)) else max(0.0, 1 - abs(h - w_) / max(abs(w_), abs(h), 1)))
        numc = sum(num) / len(num) if num else 0.0
        return round(0.6 * frac + 0.25 * close + 0.1 * numc, 4)

    def diff_features(self, res):
        cols = self.cols
        got = {}
        for r in res["clean"]:
            got.setdefault(W.num(r.get(cols[0])), []).append(r)
        feats = set()
        want = {W.num(row[0]) for row in self.synth}
        if any(len(v) > 1 for v in got.values()):
            feats.add("diff:dup_keys")
        if len(res["clean"]) > self.n_rows:
            feats.add("diff:extra_rows")
        if want - set(got):
            feats.add("diff:missing_rows")
        if len(res["clean"]) < self.n_rows:
            feats.add("diff:too_few_rows")
        for row in self.synth:
            g = got.get(W.num(row[0]))
            if not g:
                continue
            for j, c in enumerate(cols[1:], 1):
                want_v, have = row[j], g[0].get(c)
                if W.num(want_v) == W.num(have):
                    continue
                if want_v is None:
                    feats.add("diff:expect_null")
                elif have is None:
                    feats.add("diff:got_null")
                elif isinstance(want_v, float) and isinstance(have, (int, float)) and int(want_v) == int(have):
                    feats.add("diff:fraction_lost")
                elif isinstance(want_v, float) and isinstance(have, float):
                    feats.add("diff:precision")
                elif isinstance(want_v, str):
                    feats.add("diff:text_value")
                else:
                    feats.add("diff:value")
        return feats


def _err_loc(msg):
    m = re.search(r"The value '([^']*)'", msg) or re.search(r"\[(\w+)\]", msg)
    return m.group(0) if m else msg[:60]


def _err_class(cls):
    c = str(cls).upper()
    for k in ("CAST_INVALID_INPUT", "DIVIDE_BY_ZERO", "NUMBER_FORMAT", "ARITHMETIC", "ANALYSIS"):
        if k in c:
            return k
    return c[:30]


# ------------------------------------------------------------------ search
class Node:
    __slots__ = ("spec", "path", "pre", "ev", "tick", "stage_i", "expanded")

    def __init__(self, spec, path, pre, ev, tick, stage_i=0):
        self.spec, self.path, self.pre, self.ev, self.tick, self.stage_i, self.expanded = spec, path, pre, ev, tick, stage_i, False


def _p_count(de, op, feats):
    return min(3, sum(1 for p in de["P"] if p["kind"] == "partial" and p["op"] == op and p["fixes"] and set(p["fixes"]) <= feats))


def op_order(de, feats, S, Mm, order=None):
    if order is not None:
        return list(order)
    bias = {"policy": lambda o: 0.0, "stage_asc": lambda o: 0.3 * (3 - O.STAGE[o]), "stage_desc": lambda o: 0.3 * (O.STAGE[o] - 1)}
    b = bias[S["localize"]]
    sc = {o: sum(de["w"].get(f, {}).get(o, 0.0) for f in feats) + Mm["p_priority"] * _p_count(de, o, feats) + b(o) for o in O.OPS}
    return sorted(O.OPS, key=lambda o: (-sc[o], O.OPS.index(o)))


def stage_order(S):
    return {"stage_desc": (3, 2, 1)}.get(S["localize"], (1, 2, 3))


def solve(project, de, runtime, budget_s=2.5, M=None, order=None, use_skills=True, gate=True, explore=False):
    """Investigate -> attempt -> repair -> verify through de_accept_v2. Returns the episode record."""
    from nexus.campaign2 import improver as I
    M = M or []
    S = dict(M0_SEARCH, **(I.first(M, "search") or {}))
    Mm = dict(M0_MEMORY, **(I.first(M, "memory") or {}))
    A = dict(M0_AMBIG, **(I.first(M, "ambiguity") or {}))
    t0 = time.time()
    deadline = t0 + budget_s
    try:
        inv = Investigation(project, runtime, gate=gate)
    except AD.Unsupported as e:
        return dict(outcome="abstain_unsupported", spec=None, code=None, edits=None, runs=0, runs_by={}, wall=time.time() - t0,
                    note=str(e), trace=[], refutations=[], partials=[], start_features=[], choices=[], gate=[])
    spark = inv.sq is not inv.rt
    ev0 = inv.run(inv.legacy)
    feats0 = set(ev0["features"])
    evs0 = None
    if spark:
        evs0 = inv.run(inv.legacy, inv.sq)
        feats0 |= evs0["features"]
    trace = [dict(step="investigate", file=f"pipeline.{inv.lang}", error=ev0.get("error"), failed=ev0["failed"],
                  features=sorted(feats0), differential_sqlite=sorted(evs0["features"]) if evs0 else None)]
    refutations, partials, gate_log, choices = [], [], [], []
    tick = itertools.count()
    seen_by_engine = {"screen": set(), "engine": set()}
    result = {}

    def finish(node, status, chosen=None):
        spec = chosen if chosen is not None else node.spec
        return dict(outcome="submitted" if status != "ambiguous" else "abstain_ambiguous", spec=spec if status != "ambiguous" else None,
                    edits=[(o, p) for o, p in node.path], edit_pre=list(node.pre), status=status)

    def try_accept(node):
        """de_accept_v2 on a node that passes the synthesis checks on the project engine. -> record | None (rejected)."""
        if not gate:
            return finish(node, "no_gate")
        if not node.ev["held_ok"]:
            gate_log.append(dict(edits=node.path, rejected="held_back", fold=inv.fold))
            return "held_fail"
        viol = AC.invariants(inv, node.spec)
        if viol:
            gate_log.append(dict(edits=node.path, rejected="probe", violations=viol))
            return None
        cl = AC.closure(inv, node.spec, node.path, de.get("prefs", {}), A["margin"] if A["mode"] == "pref" else 1e9, explore,
                        deadline=deadline)
        gate_log.append(dict(edits=node.path, closure=cl["status"], scope=cl["scope"], classes=cl.get("classes")))
        if cl.get("choice"):
            choices.append(cl["choice"])
        if cl["status"] == "ambiguous":
            return finish(node, "ambiguous")
        return finish(node, cl["status"], cl["spec"])

    def expand(node, engine, ops_seq, frontier, key):
        """Expand one node; returns an accepted record, 'timeout', or None."""
        feats = node.ev["features"]
        for op in ops_seq:
            for s2, prm in O.candidates(op, node.spec, inv):
                if time.time() > deadline:
                    return "timeout"
                k = ir.canon(s2)
                if k in seen_by_engine[key]:
                    continue
                seen_by_engine[key].add(k)
                ev2 = inv.run(s2, engine)
                child = Node(s2, node.path + [(op, prm)], node.pre + [sorted(feats)], ev2, next(tick), 0)
                if len(trace) < 400:
                    trace.append(dict(step="attempt", engine=engine.name, edits=[f"{o}({p})" for o, p in child.path], error=ev2.get("error"),
                                      failed=ev2["failed"]))
                if ev2["ok"]:
                    if engine is inv.rt:
                        r = try_accept(child)
                        if r is not None:
                            return r
                    else:                                # screened on SQLite: promote to the project engine
                        evp = inv.run(s2)
                        cp = Node(s2, child.path, child.pre, evp, next(tick))
                        if evp["ok"]:
                            r = try_accept(cp)
                            if r is not None:
                                return r
                        else:                            # an engine-semantics failure (ANSI): continue Spark-natively
                            result.setdefault("promoted", []).append(cp)
                            return "promoted"
                    continue
                gain = ev2["score"] - node.ev["score"]
                if gain > 0:
                    rec = dict(op=op, prm=prm, stage=O.STAGE[op], pre=sorted(feats), fixes=sorted(feats - ev2["features"]), gain=round(gain, 4),
                               verified=bool(ev2.get("held_graded", 0) >= node.ev.get("held_graded", 0)))
                    partials.append(rec)
                    frontier.append(child)
                elif gain == 0 and ((ev2["features"] != feats and ev2.get("error") is None) or
                                    (ev2.get("error") and node.ev.get("error") and ev2.get("err_loc") != node.ev.get("err_loc"))):
                    child.ev = dict(ev2, score=ev2["score"] - 0.01)
                    frontier.append(child)
                elif ev2["features"] == feats:
                    refutations.append(dict(op=op, pre=sorted(feats)))
        return None

    def best_first(frontier, engine, key, phase_deadline):
        best_t, best_s = time.time(), max((n.ev["score"] for n in frontier), default=0)
        stall = max(0.25, S["stall_frac"] * budget_s)
        while time.time() <= min(deadline, phase_deadline):
            cand = [n for n in frontier if len(n.path) < S["max_depth"] and not n.expanded]
            if not cand:
                return None
            node = max(cand, key=lambda n: (n.ev["score"], -len(n.path), -n.tick))
            if S["decompose"] == "stagewise":
                stg = stage_order(S)
                if node.stage_i >= len(stg):
                    node.expanded = True
                    continue
                ops_seq = [o for o in op_order(de, node.ev["features"], S, Mm, order) if O.STAGE[o] == stg[node.stage_i]]
                node.stage_i += 1
                if node.stage_i >= len(stg):
                    node.expanded = True
            else:
                node.expanded = True
                ops_seq = op_order(de, node.ev["features"], S, Mm, order)
            n_before = len(frontier)
            r = expand(node, engine, ops_seq, frontier, key)
            if r is not None:
                return r
            new_best = max((n.ev["score"] for n in frontier[n_before:]), default=-1)
            if new_best > best_s:
                best_s, best_t = new_best, time.time()
            elif time.time() - best_t > stall:
                trace.append(dict(step="stall", engine=engine.name, after_s=round(time.time() - t0, 3)))
                return "stall"
        return "timeout"

    def run_phase(root_nodes, engine, key, phase_deadline=float("inf")):
        frontier = list(root_nodes)
        # 1. retrieved skills first (reuse): guided operator sequences from the legacy state
        if use_skills and order is None:
            sk = []
            for sid, s in de["skills"].items():
                pre = set(s["pre"])
                ov = len(pre & feats0) / max(1, len(pre)) if s.get("kind") == "stage" else len(pre & feats0) / max(1, len(pre | feats0))
                if ov >= Mm["skill_match"]:
                    sk.append((ov, sid, s["ops"]))
            for ov, sid, ops_ in sorted(sk, reverse=True):
                node = root_nodes[0]
                for op in ops_:
                    n_before = len(frontier)
                    r = expand(node, engine, [op], frontier, key)
                    if isinstance(r, dict):
                        trace.append(dict(step="reuse", skill=sid))
                        de["skills"][sid]["uses"] = de["skills"][sid].get("uses", 0) + 1
                        return r
                    if r is not None:
                        return r
                    kids = frontier[n_before:]
                    if not kids:
                        break
                    node = max(kids, key=lambda n: n.ev["score"])
        return best_first(frontier, engine, key, phase_deadline)

    out = None
    for f in range(len(inv.folds)):                     # K-fold rotation of the held-back split (de_accept_v2 step 1)
        if time.time() > deadline:
            break
        if f:
            inv.set_fold(f)
            seen_by_engine["screen"], seen_by_engine["engine"] = set(), set()
            result.clear()
            ev0, evs0 = inv.run(inv.legacy), (inv.run(inv.legacy, inv.sq) if spark else None)
            trace.append(dict(step="next_fold", fold=f, after_s=round(time.time() - t0, 3)))
        if spark and S["cross_engine"] == "sqlite_first":
            rootA = Node(inv.legacy, [], [], evs0, next(tick))
            r = run_phase([rootA], inv.sq, "screen", phase_deadline=time.time() + 0.6 * (deadline - time.time()))
            if not isinstance(r, dict) and r != "held_fail" and result.get("promoted"):
                seeds = result["promoted"][:3]
                trace.append(dict(step="spark_native", from_promoted=len(seeds), after_s=round(time.time() - t0, 3)))
                r = best_first(seeds, inv.rt, "engine", float("inf"))
        else:
            r = run_phase([Node(inv.legacy, [], [], ev0, next(tick))], inv.rt, "engine")
        if isinstance(r, dict):
            out = r
            break
        if r != "held_fail":
            break                                      # no candidate at all under this fold: more evidence will not help
    rec = dict(outcome=out["outcome"] if out else "abstain_none", spec=out["spec"] if out else None,
               edits=out["edits"] if out else None, edit_pre=out.get("edit_pre") if out else None, status=out.get("status") if out else None,
               runs=inv.runs["engine"] + inv.runs["sqlite_screen"], runs_by=dict(inv.runs), wall=round(time.time() - t0, 3),
               trace=trace, start=dict(failed=ev0["failed"], error=ev0.get("error")), refutations=refutations, partials=partials,
               start_features=sorted(feats0), n_checks=ev0["n_checks"], choices=choices, gate=gate_log, lang=inv.lang)
    rec["code"] = ir.lower(rec["spec"], inv.lang) if rec["spec"] else None
    return rec


# ------------------------------------------------------------------ learning
def learn(de, rec, project, cfg, verified):
    """cfg: lr, neg_lr, partial_lr, use_failures (False = Solved-Only: learns only from verified solves)."""
    if rec.get("edits") is None and rec["outcome"] == "abstain_unsupported":
        return
    if verified:
        for (op, prm), pre in zip(rec["edits"], rec["edit_pre"]):
            for f in pre:
                de["w"].setdefault(f, {})[op] = de["w"].get(f, {}).get(op, 0.0) + cfg["lr"]
        for ch in rec.get("choices", []):              # consistent with the hidden batches - weak evidence (the alternative
            de["prefs"][ch["chosen"]] = de["prefs"].get(ch["chosen"], 0.0) + 0.25      # was not tested)
    if not cfg["use_failures"]:
        return
    for r in rec.get("refutations", [])[:40]:
        for f in r["pre"]:
            de["w"].setdefault(f, {})[r["op"]] = de["w"].get(f, {}).get(r["op"], 0.0) - cfg["neg_lr"]
    if rec["outcome"] == "submitted" and not verified:                  # a refuted submission (hidden-batch failure)
        for ch in rec.get("choices", []):
            de["prefs"][ch["chosen"]] = de["prefs"].get(ch["chosen"], 0.0) - 1.0
            for c in ch["rejected"]:
                de["prefs"][c] = de["prefs"].get(c, 0.0) + 0.5
        de["P"].append(dict(project=project["pid"], kind="refuted_submission", edits=rec["edits"], choices=rec.get("choices"),
                            evidence="independent hidden-batch evaluation (source feedback)"))
    if not verified:
        for p in rec.get("partials", [])[:12]:
            if not p["verified"] or not p["fixes"]:
                continue
            de["P"].append(dict(project=project["pid"], kind="partial", op=p["op"], prm=p["prm"], stage=p["stage"], pre=p["pre"],
                                fixes=p["fixes"], gain=p["gain"], evidence="synthesis checks + no loss on the held-back split"))
            for f in p["fixes"]:
                de["w"].setdefault(f, {})[p["op"]] = de["w"].get(f, {}).get(p["op"], 0.0) + cfg.get("partial_lr", 0.5)
    de["P"] = de["P"][-cfg.get("max_P", 80):]


def skill_from(rec, project):
    return dict(ops=[o for o, _ in rec["edits"]], pre=rec["start_features"], params_example=[p for _, p in rec["edits"]],
                contract=dict(runtime=project["runtime"], lang=rec.get("lang")), provenance=project["pid"], kind="full",
                origin="pure_synthesis", validated_on=[])


def provisional_skills(de):
    """Stage skills from P: an operator that removed the same evidence features in >= 2 unsolved projects (verified partials)."""
    groups = {}
    for p in de["P"]:
        if p["kind"] == "partial":
            groups.setdefault((p["op"], tuple(p["fixes"])), []).append(p)
    out = []
    for (op, fixes), ps in groups.items():
        if len({p["project"] for p in ps}) >= 2:
            out.append(dict(ops=[op], pre=list(fixes), params_example=[ps[0]["prm"]], contract=dict(satisfied="partial"),
                            provenance=sorted({p["project"] for p in ps}), kind="stage", stage=ps[0]["stage"], origin="P_partial",
                            tier="provisional", validated_on=[]))
    return out


FEATS = ["fail:example_rows", "fail:row_count", "fail:unique", "fail:quarantine_ids", "fail:no_error", "diff:value",
         "diff:extra_rows", "diff:dup_keys", "diff:missing_rows", "diff:got_null", "diff:text_value", "err:CAST_INVALID_INPUT",
         "err:DIVIDE_BY_ZERO", "diff:fraction_lost", "diff:expect_null", "diff:too_few_rows"]


def random_skill(rng):
    return dict(ops=[rng.choice(O.OPS) for _ in range(rng.randint(1, 3))], pre=sorted(rng.sample(FEATS, 2)), params_example=[],
                contract={}, provenance="random", kind=rng.choice(["full", "stage"]), origin="random", tier="random", validated_on=[])
