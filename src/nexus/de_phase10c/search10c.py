"""Phase 10C unified search over L0 U L* with arm-matched zero-gain bridge machinery (NOT LOCKED).

Active only when mem['guide']['v10c'] is set (every Phase 10C arm); earlier arms keep search8 / search7 / search10b.
Differences from search10b.search_bridge (the Phase 10B bridge search, unchanged):
  MACROS AS ATOMIC STEPS   library macros (L*) are bound at EVERY expanded node, per stage, against that node's current
                           program (skills6.bind; role-form rebinding), filtered by their STAGE-LOCAL precondition (the
                           residual symptoms of that stage at that node). One bound macro = one child = one evaluation; its
                           edits extend the path in one step. A macro therefore counts when it clears ITS sub-problem
                           (the usual improvement / neutral archive rules) - the whole pipeline need not pass after it, so
                           m_A then m_B can chain on a composition never seen in training (owner upgrade 1 / 3).
  NO ROOT-ONLY METHOD QUEUE  search8's root method queue (whole-pipeline acceptance only) is not used by any Phase 10C arm;
                           every arm gets the full work budget in one archive search.
  RESIDUAL-SYMPTOM TOKENS  guide tokens: action (primitive operator or macro content hash) x {relative stage position, the
                           node's check / diff / error features, the failing schema-test kinds of the candidate's OWN stage}.
                           No paradigm, family, column-name or absolute stage-index token exists (owner upgrade 2).
  ONE BRIDGE MACHINERY FOR EVERY ARM  each node's candidates get an ORDER SCORE from the arm's guide: G_learned = ranker
                           score; G_fixed = minus the position in the fixed order (macros first - capped - then search7's fixed
                           operator interleaving). A neutral child whose order score is within the node's top BRIDGE_M is a
                           bridge; BRIDGE_SLOTS of every 10 expansions go to the best open bridge (its top BRIDGE_K children).
                           Learned arms mix ranker order 4:3 with the fixed order (progressive widening keeps every child
                           reachable); fixed arms use the fixed order. Same slots, K, M, work budget and wall cap in all arms."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import time

from nexus.de_phase6 import engines6 as E, pipeline6 as P6, skills6 as SK
from nexus.de_phase7 import search7 as S7
from nexus.de_phase8 import search8 as S8
from nexus.de_phase10 import guide10 as G
from nexus.de_phase10b import fixes10b, search10b as SB  # noqa: F401  (ROUND primitive, idempotent coverage, bridge constants)
from nexus.de_phase10c import fixes10c  # noqa: F401  (shared verifier fix: no submission with an untestable requirement)

BRIDGE_SLOTS, BRIDGE_K, BRIDGE_M = SB.BRIDGE_SLOTS, SB.BRIDGE_K, SB.BRIDGE_M
MAC_CAP, BIND_CAP, PRE_MATCH, RATIO = 8, 2, 0.5, 4 / 7
_ORIG_S8 = getattr(S8.search, "_phase8_original", S8.search)


def mac_id(skill):
    return "mac:" + hashlib.sha1(skill["canonical"].encode()).hexdigest()[:10]


def symptoms(ev, k, n_stages):
    """Residual symptoms of stage k at a node: its own failing schema-test kinds (or here:clean) + the end-to-end check / diff /
    error features (an inner stage's fault propagates to the end checks, so a precondition learned where the stage was LAST
    stays matchable where the same stage is inner - position-invariant)."""
    sf = ev["stage_fail"][k] if k < len(ev["stage_fail"]) else []
    s = {f"here:{f.split(':')[0]}" for f in sf} or {"here:clean"}
    return s | {f for f in ev["features"] if f.startswith(("fail:", "diff:", "err:"))}


def ctx(ev, k, n_stages):
    pos = "pos:last" if k == n_stages - 1 else "pos:first" if k == 0 else "pos:inner"
    return [pos] + sorted(symptoms(ev, k, n_stages)) + sorted(ev["features"])[:20]


def tokens(action, c, roles=()):
    return [action, f"{action}|{c[0]}"] + [f"{action}|ev:{f}" for f in c[1:]] + [f"{action}|{r}" for r in roles]


def prim_roles(op, prm, dom):
    out = []
    try:
        for x in SK.abstract_edit(op, prm, dom, True)[1:]:
            out += [f"{x[0]}:{r}" for r in x[1]] if isinstance(x[1], (tuple, list)) else [f"{x[0]}=lit"]
    except Exception:                                          # noqa: BLE001
        pass
    return out


def pre_ok(skill, sym):
    pre = set(skill.get("pre") or [])
    return not pre or len(pre & sym) / len(pre) >= PRE_MATCH


def macro_cands(inv, mem, node):
    """Bound macros at this node: (k, label, s2, edits, sid)."""
    skills = (mem.get("de") or {}).get("skills") or {}
    out = []
    n = len(inv.stages)
    for sid in sorted(skills):
        sk = skills[sid]
        if len(sk["edits"]) < 2:
            continue
        for k in range(n):
            if not pre_ok(sk, symptoms(node["ev"], k, n)):
                continue
            for path in SK.bind(sk, inv, node["specs"], k, cap=BIND_CAP):
                sp = P6.replay(inv, path, node["specs"])
                if sp[k] != node["specs"][k]:
                    out.append((k, mac_id(sk), sp[k], path, sid))
    return out


def candidates(inv, mem, node, mode):
    """All children of a node in FIXED order (macros first, capped; then search7's fixed operator interleaving), each with
    its guide tokens. Returns list of dict(k, op, s2, prm, edits, sid, toks)."""
    n = len(inv.stages)
    out = []
    for k, label, s2, edits, sid in macro_cands(inv, mem, node)[:MAC_CAP]:
        out.append(dict(k=k, op=label, s2=s2, prm=json.dumps(edits, default=list), edits=edits, sid=sid, toks=tokens(label, ctx(node["ev"], k, n))))
    fixed_mem = dict(mem, de=dict(mem.get("de", {}), w={}))
    for k, op, s2, prm in G._ORIG_CHILDREN(inv, fixed_mem, node, mode, None):
        dom = inv.dom(k, node["specs"])
        out.append(dict(k=k, op=op, s2=s2, prm=prm, edits=[(k, op, prm)], sid=None, toks=tokens(f"op:{op}", ctx(node["ev"], k, n), prim_roles(op, prm, dom))))
    return out


def ordered(mem, cands):
    """(child order, order scores) under the arm's guide."""
    g = mem.get("guide") or {}
    w = g.get("w") if g.get("kind") == "learned" else None
    if not w:
        return list(cands), {id(c): -i for i, c in enumerate(cands)}
    sc = {id(c): G.score(w, c["toks"]) for c in cands}
    guided = sorted(cands, key=lambda c: -sc[id(c)])
    out, seen, gi, fi, n = [], set(), 0, 0, 0
    while gi < len(guided) or fi < len(cands):
        use_g = gi < len(guided) and (fi >= len(cands) or (n % 7) < round(7 * RATIO))
        n += 1
        c = guided[gi] if use_g else cands[fi]
        if use_g:
            gi += 1
        else:
            fi += 1
        if id(c) in seen:
            continue
        seen.add(id(c))
        out.append(c)
    return out, sc


def search(inv, mem, work_budget=700, wall_cap=6.0, policy_w=None, mode="whole", use_skills=True, skills_mod=None, order=None, cfg=None):
    cfg = dict(S7.ARCHIVE, **(cfg or {}))
    w = policy_w or S7.FIXED_W
    t0 = time.time()
    work = lambda: sum(inv.runs.values())                                     # noqa: E731
    w0 = work()
    ev0 = inv.run(inv.legacy, True)
    tick = itertools.count()
    events = dict(improvement=0, neutral=0, worse=0, regression=0, error=0, retained=0, evicted=0, duplicate=0, expanded=0, worse_decision=0,
                  archive_full=0, bridges_marked=0, bridge_expansions=0, macro_children=0, macro_improvements=0)
    regress = []
    trace = [dict(step="investigate", failed=ev0["failed"], stage_fail=ev0["stage_fail"], features=sorted(ev0["features"]))]
    deadline = t0 + wall_cap
    for f in range(len(inv.folds)):
        if f:
            inv.set_fold(f)
            ev0 = inv.run(inv.legacy, True)
        root = dict(id=next(tick), path=[], specs=[copy.deepcopy(s) for s in inv.legacy], ev=ev0, parent=None, kind="root", novel=True, macros=[])
        archive = [root]
        seen, sigs = {json.dumps(root["specs"], sort_keys=True)}, {}
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
                out = S7._out("ambiguous_cut" if cl["status"] == "cut" else "submitted" if cl["status"] == "unique" else "ambiguous", n,
                              [] if cl["status"] == "cut" else cl["dps"], inv, t0, w0, trace, events, regress, archive, expanded)
                out["macro_steps"] = n.get("macros", [])
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
                ch, sc = ordered(mem, candidates(inv, mem, node, mode))
                vals = sorted(sc.values(), reverse=True)
                node["rank_cut"] = vals[min(BRIDGE_M, len(vals)) - 1] if vals else float("inf")
                node["it"] = iter([(c, sc[id(c)]) for c in ch])
            node["n_exp"] = node.get("n_exp", 0) + 1
            events["expanded"] += 1
            n_new = 0
            for c, rs in node["it"]:
                if work() - w0 >= work_budget or time.time() > deadline:
                    break
                k, op, s2 = c["k"], c["op"], c["s2"]
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
                if c["sid"]:
                    events["macro_children"] += 1
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
                if c["sid"] and kind == "improvement":
                    events["macro_improvements"] += 1
                if kind == "regression":
                    regress.append(dict(op=op, pre=sorted(node["ev"]["features"])))
                if kind not in ("error", "regression"):
                    final_key = P6.okey(inv, specs, inv.rows) if kind in ("neutral", "worse") else str(ev["score"]) + key[:40]
                    sig = S7._sig(inv, final_key)
                    novel = sig not in sigs
                    if kind in ("neutral", "worse") and not novel:
                        events["duplicate"] += 1
                    else:
                        child = dict(id=next(tick), path=node["path"] + [tuple(e) for e in c["edits"]], specs=specs, ev=ev, parent=node["id"], kind=kind,
                                     novel=novel, op=op, native=native, stage_progress=max(0.0, (p_st - n_st) / max(1, p_st)),
                                     macros=node.get("macros", []) + ([[len(node["path"]), len(c["edits"]), c["sid"]]] if c["sid"] else []))
                        if c["sid"]:
                            child["via_skill"] = True
                        if kind == "neutral" and rs >= node["rank_cut"]:
                            child.update(bridge=True, rank_score=rs)
                            events["bridges_marked"] += 1
                        sigs[sig] = child["id"]
                        keep = True
                        if sum(1 for n in archive if not n.get("done")) >= cfg["archive_cap"]:
                            events["archive_full"] += 1
                            victim = min((n for n in archive if not n.get("done") and not n.get("n_exp") and n["kind"] != "root"),
                                         key=lambda n: S7.priority(n, w), default=None)
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
                work_exhausted=work() - w0 >= work_budget, events=events, regressions=regress[:40], start_features=sorted(ev0["features"]), solution_nodes=[], other_nodes=[],
                macro_steps=[])


def s8_search(inv, mem, work_budget, wall_cap, mode="whole", use_skills=True, skills_mod=None, cfg=None):
    if (mem.get("guide") or {}).get("v10c"):
        r = search(inv, mem, work_budget, wall_cap, mode=mode, cfg=cfg)
        r["method_queue"] = None
        r.setdefault("via_skill", False)
        return r
    return _ORIG_S8(inv, mem, work_budget, wall_cap, mode=mode, use_skills=use_skills, skills_mod=skills_mod, cfg=cfg)


s8_search._phase8_original = _ORIG_S8
S8.search = s8_search                                        # procedure8.Live.search resolves S8.search at call time
