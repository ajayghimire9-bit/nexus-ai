"""Phase 10B search with RANKER-GUIDED ZERO-GAIN BRIDGE EXPANSION (NOT LOCKED; owner Phase 10B fix 2).

search_bridge is de_phase7.search7.search (copied; search7 is a protected file and stays unchanged) with two changes, active
only when mem['guide'] = {kind: learned, bridge: true, ...}:
  bridge marking   a child whose score gain is exactly 0 (a 'neutral' step, retained by the archive) and whose learned-ranker
                   score is within the node's top BRIDGE_M candidates is marked as a BRIDGE (a flat first step the ranker
                   believes in)
  bridge slots     3 of every 10 expansion decisions (BRIDGE_SLOTS) go to the best open bridge node (by ranker score): its
                   top BRIDGE_K ranker-ordered children (the follow-up steps a2) are evaluated at once, so a1 o a2 is tested
                   instead of deferring a1 behind score-improving nodes
  the other 7 slots expand by (score, ranker) priority; their children are mixed 4:3 between ranker order and the UNPRUNED
  fallback order (guide ratio 4/7) - i.e. ~40 % guided / 30 % bridge lookahead / 30 % fallback. Progressive widening
  keeps every child reachable (no pruning). Arms without the bridge flag use search7 unchanged."""
from __future__ import annotations

import copy
import itertools
import json
import time

from nexus.de_phase6 import engines6 as E, pipeline6 as P6
from nexus.de_phase7 import search7 as S7
from nexus.de_phase10 import guide10 as G

BRIDGE_SLOTS, BRIDGE_K, BRIDGE_M = (2, 5, 8), 3, 5
_ORIG_SEARCH = getattr(S7.search, "_phase7_original", S7.search)


def _rank_cut(inv, node, gw):
    if "rank_cut" not in node:
        feats = node["ev"]["features"]
        sc = sorted((G.score(gw, G.tokens(op, k, prm, feats, inv.dom(k, node["specs"]))) for op in E.OPS for k in range(len(inv.stages))
                     for _, prm in E.candidates(op, node["specs"][k], inv.dom(k, node["specs"]))), reverse=True)
        node["rank_cut"] = sc[min(BRIDGE_M, len(sc)) - 1] if sc else float("inf")
    return node["rank_cut"]


def search_bridge(inv, mem, work_budget=700, wall_cap=6.0, policy_w=None, mode="whole", use_skills=True, skills_mod=None, order=None,
                  cfg=None):
    cfg = dict(S7.ARCHIVE, **(cfg or {}))
    gw = ((mem.get("guide") or {}).get("w") or {}) if (mem.get("guide") or {}).get("bridge") else {}
    w = policy_w or S7.FIXED_W
    t0 = time.time()
    work = lambda: sum(inv.runs.values())                                     # noqa: E731
    w0 = work()
    ev0 = inv.run(inv.legacy, True)
    tick = itertools.count()
    events = dict(improvement=0, neutral=0, worse=0, regression=0, error=0, retained=0, evicted=0, duplicate=0, expanded=0, worse_decision=0,
                  archive_full=0)
    regress = []
    trace = [dict(step="investigate", failed=ev0["failed"], stage_fail=ev0["stage_fail"], features=sorted(ev0["features"]))]
    deadline = t0 + wall_cap
    for f in range(len(inv.folds)):
        if f:
            inv.set_fold(f)
            ev0 = inv.run(inv.legacy, True)
        root = dict(id=next(tick), path=[], specs=[copy.deepcopy(s) for s in inv.legacy], ev=ev0, parent=None, kind="root", novel=True)
        archive = [root]
        seen, sigs = {json.dumps(root["specs"], sort_keys=True)}, {}
        if use_skills and skills_mod is not None and mem.get("de", {}).get("skills"):
            for path in skills_mod.proposals(mem["de"]["skills"], inv, root, ev0):
                specs = P6.replay(inv, path)
                ev = inv.run(specs, True)
                node = dict(id=next(tick), path=path, specs=specs, ev=ev, parent=root["id"], kind="skill", novel=True, op=path[-1][1] if path else None,
                            via_skill=True)
                archive.append(node)
                trace.append(dict(step="skill_bound", edits=path, ok=ev["ok"], score=round(ev["score"], 3)))
        expanded = []
        held_fail = False
        while work() - w0 < work_budget and time.time() < deadline:
            ready = [n for n in archive if n["ev"]["ok"] and not n.get("tried")]
            res = None
            for n in sorted(ready, key=lambda n: -n["ev"]["score"]):
                n["tried"] = True
                if not n["ev"]["held_ok"]:
                    held_fail = True
                    break
                if not n.get("native"):
                    ev_n = inv.run(n["specs"], prescreen=False)
                    if not (ev_n["ok"] and ev_n["held_ok"]):
                        trace.append(dict(step="engine_verify_failed", edits=n["path"], error=ev_n.get("error")))
                        archive.append(dict(n, id=next(tick), ev=ev_n, native=True, tried=False, done=False))
                        continue
                viol = P6.invariants(S7._Screen(inv), n["specs"])
                if not viol:
                    viol = P6.invariants(inv, n["specs"])
                if viol:
                    trace.append(dict(step="gate_reject", edits=n["path"], violations=viol))
                    continue
                cl = P6.closure(inv, n["path"], deadline=deadline + 2.0)
                trace.append(dict(step="closure", edits=n["path"], status=cl["status"], scope=cl["scope"]))
                res = (n, cl)
                break
            if held_fail:
                break
            if res is not None:
                n, cl = res
                if cl["status"] == "cut":
                    return S7._out("ambiguous_cut", n, [], inv, t0, w0, trace, events, regress, archive, expanded)
                return S7._out("submitted" if cl["status"] == "unique" else "ambiguous", n, cl["dps"], inv, t0, w0, trace, events, regress,
                            archive, expanded)
            cand = [n for n in archive if not n.get("done") and len(n["path"]) < cfg["max_depth"]]
            if not cand:
                break
            bridges = [n for n in cand if n.get("bridge") and not n.get("bridge_done")]
            slot = events["expanded"] % 10
            bridge_turn = bool(bridges) and slot in BRIDGE_SLOTS
            if bridge_turn:                                       # 30 %: lookahead from a flat, ranker-preferred first step
                node = max(bridges, key=lambda n: (n["rank_score"], -n["id"]))
                node["bridge_done"] = True
                events["bridge_expansions"] = events.get("bridge_expansions", 0) + 1
            else:
                node = max(cand, key=lambda n: (S7.priority(n, w), -n["id"]))
            if node.get("n_exp", 0) == 0:
                expanded.append(node)
                node["it"] = S7._children(inv, mem, node, mode, order)
            node["n_exp"] = node.get("n_exp", 0) + 1
            events["expanded"] += 1
            feats = node["ev"]["features"]
            n_new = 0
            for k, op, s2, prm in node["it"]:
                if work() - w0 >= work_budget or time.time() > deadline:
                    break
                specs = list(node["specs"])
                specs[k] = s2
                key = json.dumps(specs, sort_keys=True)
                if key in seen:
                    events["duplicate"] += 1
                    continue
                seen.add(key)
                n_new += 1
                native = node.get("native", False)
                ev = inv.run(specs, not native)
                gain = ev["score"] - node["ev"]["score"]
                n_st = sum(1 for fs in ev["stage_fail"] for _ in fs)
                p_st = sum(1 for fs in node["ev"]["stage_fail"] for _ in fs)
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
                if kind == "regression":
                    regress.append(dict(op=op, pre=sorted(feats)))
                if kind not in ("error", "regression"):
                    final_key = P6.okey(inv, specs, inv.rows) if kind in ("neutral", "worse") else str(ev["score"]) + key[:40]
                    sig = S7._sig(inv, final_key)
                    novel = sig not in sigs
                    if kind in ("neutral", "worse") and not novel:
                        events["duplicate"] += 1
                    else:
                        child = dict(id=next(tick), path=node["path"] + [(k, op, prm)], specs=specs, ev=ev, parent=node["id"], kind=kind,
                                     novel=novel, op=op, native=native, stage_progress=max(0.0, (p_st - n_st) / max(1, p_st)))
                        if kind == "neutral" and gw:
                            rs = G.score(gw, G.tokens(op, k, prm, feats, inv.dom(k, node["specs"])))
                            if rs >= _rank_cut(inv, node, gw):
                                child.update(bridge=True, rank_score=rs)
                                events["bridges_marked"] = events.get("bridges_marked", 0) + 1
                        sigs[sig] = child["id"]
                        keep = True
                        if sum(1 for n in archive if not n.get("done")) >= cfg["archive_cap"]:     # capacity counts OPEN programs
                            events["archive_full"] += 1
                            victim = min((n for n in archive if not n.get("done") and not n.get("n_exp") and n["kind"] != "root"),
                                         key=lambda n: S7.priority(n, w), default=None)       # expanded programs (ancestors) stay
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
        if not held_fail:
            break
    best = max((n for n in archive if n["kind"] != "root" and n["ev"]["score"] > archive[0]["ev"]["score"]), key=lambda n: n["ev"]["score"], default=None)
    best_partial = None if best is None else dict(path=best["path"], gain=round(best["ev"]["score"] - archive[0]["ev"]["score"], 4),
                                                  stage_fixed=sum(map(len, archive[0]["ev"]["stage_fail"])) - sum(map(len, best["ev"]["stage_fail"])),
                                                  kinds=[a.get("kind") for a in S7._ancestors(best, archive)])
    return dict(outcome="none", best_partial=best_partial, path=None, specs=None, dps=[], trace=trace, runs=dict(inv.runs), work=work() - w0, wall=round(time.time() - t0, 3),
                work_exhausted=work() - w0 >= work_budget, events=events, regressions=regress[:40], start_features=sorted(ev0["features"]), solution_nodes=[], other_nodes=[])


def search(inv, mem, *a, **k):
    if (mem.get("guide") or {}).get("bridge"):
        return search_bridge(inv, mem, *a, **k)
    return _ORIG_SEARCH(inv, mem, *a, **k)


search._phase7_original = _ORIG_SEARCH
S7.search = search                                           # search8 resolves S7.search at call time
