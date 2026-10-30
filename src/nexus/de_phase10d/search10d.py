"""Phase 10D search over L0 U L* on DAG specs (NOT LOCKED): de_phase10c.search10c's unified archive search (macros as atomic
children bound at every node with stage-local residual-symptom preconditions; residual-symptom guide tokens; ONE bridge machinery
for fixed and learned guidance; no root method queue) on dag10d.Inv10d:
  candidates   macros first (capped) then the L0 operators interleaved round-robin in a fixed operator order (G_fixed); a
               learned guide ranks the same candidates (4:3 with the fixed order)
  acceptance   a candidate whose visible evidence is ok (public checks + every node contract) is Occam-pruned (edits visible data
               cannot justify are dropped; amendment 2) and re-run on the DECLARED engine
               (DuckDB / SQLite / Polars / PySpark) and submitted if still ok (no requirement decision points in Phase 10D)
  localize     (Arm 5 only) expand only the FIRST DAG node (stg_ -> int_ -> fct_) whose contract fails; all nodes when none fails"""
from __future__ import annotations

import copy
import itertools
import json
import time

from nexus.de_phase7 import search7 as S7
from nexus.de_phase10c import search10c as S10
from nexus.de_phase10d import dag10d as D

BRIDGE_SLOTS, BRIDGE_K, BRIDGE_M, MAC_CAP, RATIO = S10.BRIDGE_SLOTS, S10.BRIDGE_K, S10.BRIDGE_M, S10.MAC_CAP, S10.RATIO
ARCHIVE = dict(S7.ARCHIVE)


def prim_roles(op, prm, dom):
    out = []
    for x in D.abstract_edit(op, prm, dom)[1:]:
        out += [f"{x[0]}:{r}" for r in x[1]] if isinstance(x[1], (tuple, list)) else [f"{x[0]}={x[1]}"]
    return out


def stages_of(inv, node, mode):
    if mode == "localize":
        failing = [k for k, fs in enumerate(node["ev"]["stage_fail"]) if fs and fs != ["error"]]
        if failing:
            return [failing[0]]
    return [0, 1, 2]


def macro_cands(inv, mem, node, stages):
    skills = (mem.get("de") or {}).get("skills") or {}
    out = []
    for sid in sorted(skills):
        sk = skills[sid]
        if len(sk["edits"]) < 2:
            continue
        for k in stages:
            if not S10.pre_ok(sk, S10.symptoms(node["ev"], k, 3)):
                continue
            for path in D.bind(sk, inv, node["specs"], k):
                sp = D.replay(inv, path, node["specs"])
                if sp[k] != node["specs"][k]:
                    out.append((k, S10.mac_id(sk), sp[k], path, sid))
    return out


def candidates(inv, mem, node, mode):
    stages = stages_of(inv, node, mode)
    out = []
    for k, label, s2, edits, sid in macro_cands(inv, mem, node, stages)[:MAC_CAP]:
        out.append(dict(k=k, op=label, s2=s2, prm=json.dumps(edits, default=list), edits=edits, sid=sid, toks=S10.tokens(label, S10.ctx(node["ev"], k, 3))))
    per_op = []
    for op in D.OPS:
        k = D.OP_NODE[op]
        if k not in stages:
            continue
        dom = inv.dom(k, node["specs"])
        per_op.append([dict(k=k, op=op, s2=s2, prm=prm, edits=[(k, op, prm)], sid=None,
                            toks=S10.tokens(f"op:{op}", S10.ctx(node["ev"], k, 3), prim_roles(op, prm, dom))) for s2, prm in D.candidates(op, node["specs"][k], dom)])
    for row in itertools.zip_longest(*per_op):                    # fixed operator interleaving (breadth over operator types)
        out += [c for c in row if c is not None]
    return out


def prune(inv, n, events):
    """OCCAM PRUNING (amendment 2, before any target): drop every edit of an accepted path whose removal keeps every visible
    check and node contract passing (last edit first); a macro-bound or spurious edit that visible data cannot justify is not
    submitted. Each trial is one charged reference execution."""
    path = [tuple(e) for e in n["path"]]
    i = len(path) - 1
    while i >= 0 and len(path) > 1:
        trial = path[:i] + path[i + 1:]
        sp = D.replay(inv, trial)
        ev = inv.run(sp, True)
        if ev["ok"]:
            path = trial
            n.update(path=path, specs=sp, ev=ev, macros=[m for m in n.get("macros", []) if m[0] + m[1] <= len(path)])
            events["pruned_edits"] = events.get("pruned_edits", 0) + 1
        i -= 1


def search(inv, mem, work_budget=600, wall_cap=4.0, mode="whole", cfg=None):
    cfg = dict(ARCHIVE, **(cfg or {}))
    w = S7.FIXED_W
    t0 = time.time()
    work = lambda: sum(inv.runs.values())                                      # noqa: E731
    w0 = work()
    ev0 = inv.run(inv.legacy, True)
    tick = itertools.count()
    events = dict(improvement=0, neutral=0, worse=0, regression=0, error=0, retained=0, evicted=0, duplicate=0, expanded=0, worse_decision=0,
                  archive_full=0, bridges_marked=0, bridge_expansions=0, macro_children=0, macro_improvements=0, engine_verify_failed=0)
    trace = [dict(step="investigate", failed=ev0["failed"], stage_fail=ev0["stage_fail"], features=sorted(ev0["features"]))]
    regress = []
    deadline = t0 + wall_cap
    root = dict(id=next(tick), path=[], specs=[copy.deepcopy(s) for s in inv.legacy], ev=ev0, parent=None, kind="root", novel=True, macros=[])
    archive = [root]
    seen, sigs = {json.dumps(root["specs"], sort_keys=True)}, {}
    expanded = []
    while work() - w0 < work_budget and time.time() < deadline:
        ready = [n for n in archive if n["ev"]["ok"] and not n.get("tried")]
        res = None
        for n in sorted(ready, key=lambda n: -n["ev"]["score"]):
            n["tried"] = True
            prune(inv, n, events)
            if not n.get("native"):
                ev_n = inv.run(n["specs"], prescreen=False)
                if not ev_n["ok"]:
                    events["engine_verify_failed"] += 1
                    trace.append(dict(step="engine_verify_failed", edits=n["path"], error=ev_n.get("error")))
                    continue
            res = n
            break
        if res is not None:
            out = S7._out("submitted", res, [], inv, t0, w0, trace, events, regress, archive, expanded)
            out["macro_steps"] = res.get("macros", [])
            return out
        cand = [n for n in archive if not n.get("done") and len(n["path"]) < cfg["max_depth"]]
        if not cand:
            break
        bridges = [n for n in cand if n.get("bridge") and not n.get("bridge_done")]
        bridge_turn = bool(bridges) and events["expanded"] % 10 in BRIDGE_SLOTS
        if bridge_turn:
            node = max(bridges, key=lambda n: (n["rank_score"], -n["id"]))
            node["bridge_done"] = True
            events["bridge_expansions"] += 1
        else:
            node = max(cand, key=lambda n: (S7.priority(n, w), -n["id"]))
        if node.get("n_exp", 0) == 0:
            expanded.append(node)
            ch, sc = S10.ordered(mem, candidates(inv, mem, node, mode))
            vals = sorted(sc.values(), reverse=True)
            node["rank_cut"] = vals[min(BRIDGE_M, len(vals)) - 1] if vals else float("inf")
            node["it"] = iter([(c, sc[id(c)]) for c in ch])
        node["n_exp"] = node.get("n_exp", 0) + 1
        events["expanded"] += 1
        n_new = 0
        for c, rs in node["it"]:
            if work() - w0 >= work_budget or time.time() > deadline:
                break
            specs = list(node["specs"])
            specs[c["k"]] = c["s2"]
            key = json.dumps(specs, sort_keys=True)
            if key in seen:
                events["duplicate"] += 1
                continue
            seen.add(key)
            n_new += 1
            ev = inv.run(specs, True)
            if c["sid"]:
                events["macro_children"] += 1
            gain = ev["score"] - node["ev"]["score"]
            n_st = sum(len(fs) for fs in ev["stage_fail"])
            p_st = sum(len(fs) for fs in node["ev"]["stage_fail"])
            lost = set(node["ev"]["passed"]) - set(ev["passed"])
            if ev.get("error"):
                kind = "error"
            elif lost and gain < 0:
                kind = "regression"
            elif gain > 0 or ev["ok"]:
                kind = "improvement"
            elif abs(gain) < 1e-9:
                kind = "neutral"
            elif gain >= -cfg["worse_delta"]:
                kind = "worse"
                events["worse_decision"] += 1
            else:
                kind = "regression"
                events["worse_decision"] += 1
            events[kind] += 1
            if c["sid"] and kind == "improvement":
                events["macro_improvements"] += 1
            if kind == "regression":
                regress.append(dict(op=c["op"], pre=sorted(node["ev"]["features"])))
            if kind not in ("error", "regression"):
                fkey = inv.okey(specs) if kind in ("neutral", "worse") else str(ev["score"]) + key[:40]
                sg = D.sig(fkey)
                novel = sg not in sigs
                if kind in ("neutral", "worse") and not novel:
                    events["duplicate"] += 1
                else:
                    child = dict(id=next(tick), path=node["path"] + [tuple(e) for e in c["edits"]], specs=specs, ev=ev, parent=node["id"], kind=kind,
                                 novel=novel, op=c["op"], native=False, stage_progress=max(0.0, (p_st - n_st) / max(1, p_st)),
                                 macros=node.get("macros", []) + ([[len(node["path"]), len(c["edits"]), c["sid"]]] if c["sid"] else []))
                    if c["sid"]:
                        child["via_skill"] = True
                    if kind == "neutral" and rs >= node["rank_cut"]:
                        child.update(bridge=True, rank_score=rs)
                        events["bridges_marked"] += 1
                    sigs[sg] = child["id"]
                    keep = True
                    if sum(1 for n in archive if not n.get("done")) >= cfg["archive_cap"]:
                        events["archive_full"] += 1
                        victim = min((n for n in archive if not n.get("done") and not n.get("n_exp") and n["kind"] != "root"), key=lambda n: S7.priority(n, w), default=None)
                        if victim is None or S7.priority(victim, w) >= S7.priority(child, w):
                            events["evicted"] += 1
                            keep = False
                        else:
                            archive.remove(victim)
                            events["evicted"] += 1
                    if keep:
                        archive.append(child)
                        events["retained"] += 1
            if n_new >= (BRIDGE_K if bridge_turn else cfg["widen"]):
                break
        else:
            node["done"] = True
    best = max((n for n in archive if n["kind"] != "root" and n["ev"]["score"] > root["ev"]["score"]), key=lambda n: n["ev"]["score"], default=None)
    best_partial = None if best is None else dict(path=best["path"], gain=round(best["ev"]["score"] - root["ev"]["score"], 4),
                                                  stage_fixed=sum(map(len, root["ev"]["stage_fail"])) - sum(map(len, best["ev"]["stage_fail"])))
    return dict(outcome="none", best_partial=best_partial, path=None, specs=None, dps=[], trace=trace, runs=dict(inv.runs), work=work() - w0, wall=round(time.time() - t0, 3),
                work_exhausted=work() - w0 >= work_budget, events=events, regressions=regress[:40], start_features=sorted(ev0["features"]), solution_nodes=[], other_nodes=[],
                macro_steps=[], via_skill=False)
