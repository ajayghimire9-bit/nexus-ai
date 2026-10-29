"""Phase 7 search over a BOUNDED ARCHIVE OF INTERMEDIATE PROGRAMS (NOT LOCKED). Built on de_phase6.pipeline6 (Inv6,
operators, de_accept_v3 gate functions), which is unchanged.

Phase 6 kept a child only when its score improved immediately, and booked unchanged evidence as a refutation with negative
policy weight; necessary neutral or temporarily worse steps were lost (erratum item 5). Phase 7:

  retention   a child enters the archive if it IMPROVES, or is NEUTRAL with a new behavioural signature (its visible output
              differs from every archived program), or is WORSE by at most worse_delta with a new signature; duplicates
              (same pipeline or same signature with a lower score) are dropped; capacity archive_cap, depth max_depth
  outcomes    each attempt is classified: improvement | neutral | worse | regression (a check its parent passed now fails) |
              error (runtime / unsupported); only REGRESSIONS lower an operator's weight (scoped to the evidence features)
  budget      a DETERMINISTIC work budget: engine executions (one per stage per candidate run), plus a wall safety cap
  widening    PROGRESSIVE: one expansion evaluates at most `widen` children of a node, in operator order (the learned evidence
              weights); a node stays open until its children are exhausted, and re-expanding it continues where it stopped
  gate screen a check-passing candidate is first screened by the de_accept_v3 invariants on SQLite; only survivors run the
              invariants on the declared engines (the final acceptance is always on the declared engines) - a disclosed
              search heuristic shared by every arm
  policy      expansion order and eviction use priority(node) = w . phi(node), with observable features phi (score, stage-test
              progress, depth, neutral / worse flag, novelty, the last operator's stage, times already expanded). Two
              policies, same capacities:
                FIXED   a strong hand-set diversity / beam rule (Fixed-Learner, and the fixed strategy arms)
                LEARNED w learned from DELAYED UTILITY: after a verified solve, the solution's archived ancestors are
                        positives and the other expanded nodes negatives; w moves toward the positives (contrastive step).
                        Every update keeps provenance (project, #pos, #neg).
Partial programs are hypotheses: passing one stage's tests is evidence only within those tests."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import time

from nexus.de_phase6 import engines6 as E, pipeline6 as P6
from nexus.de_phase7 import accept7, ops7  # noqa: F401  (register the v7 gate repair and the dedup-on-id parameterisation)

PHI = ("score", "stage_progress", "depth", "neutral", "worse", "novel", "stage1_op", "stage2_op", "stage3_op", "reexp", "bias")
FIXED_W = dict(score=1.0, stage_progress=0.6, depth=-0.08, neutral=-0.1, worse=-0.4, novel=0.3, stage1_op=0.05, stage2_op=0.0,
               stage3_op=0.0, reexp=-0.35, bias=0.0)
ARCHIVE = dict(archive_cap=48, max_depth=8, worse_delta=0.35, widen=40)


class _Screen:
    """The investigation seen through the SQLite screen (exec always prescreened)."""

    def __init__(self, inv):
        self._i = inv

    def __getattr__(self, k):
        return getattr(self._i, k)

    def exec(self, specs, rows=None, prescreen=True, final_only=True):
        return self._i.exec(specs, rows, True, final_only)


def phi(node):
    st = E.STAGE.get(node.get("op"), 0)
    return dict(score=node["ev"]["score"], stage_progress=node.get("stage_progress", 0.0), depth=len(node["path"]),
                neutral=1.0 if node.get("kind") == "neutral" else 0.0, worse=1.0 if node.get("kind") == "worse" else 0.0,
                novel=1.0 if node.get("novel") else 0.0, stage1_op=1.0 if st == 1 else 0.0, stage2_op=1.0 if st == 2 else 0.0,
                stage3_op=1.0 if st == 3 else 0.0, reexp=float(node.get("n_exp", 0)), bias=1.0)


def priority(node, w):
    f = phi(node)
    return sum(w.get(k, 0.0) * v for k, v in f.items())


def _sig(inv, ev_final):
    return hashlib.sha1(json.dumps(ev_final, default=str, sort_keys=True).encode()).hexdigest()[:12]


def update_policy(w, solved_nodes, other_nodes, lr=0.15, project=None, prov=None):
    """Delayed-utility contrastive update (Full only)."""
    if not solved_nodes or not other_nodes:
        return w
    mp = {k: sum(phi(n)[k] for n in solved_nodes) / len(solved_nodes) for k in PHI}
    mn = {k: sum(phi(n)[k] for n in other_nodes) / len(other_nodes) for k in PHI}
    w = {k: round(w.get(k, 0.0) + lr * (mp[k] - mn[k]) / (1 + abs(mp[k]) + abs(mn[k])), 5) for k in PHI}
    if prov is not None:
        prov.append(dict(project=project, positives=len(solved_nodes), negatives=len(other_nodes)))
    return w


def search(inv, mem, work_budget=700, wall_cap=6.0, policy_w=None, mode="whole", use_skills=True, skills_mod=None, order=None,
           cfg=None):
    cfg = dict(ARCHIVE, **(cfg or {}))
    w = policy_w or FIXED_W
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
                viol = P6.invariants(_Screen(inv), n["specs"])
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
                    return _out("ambiguous_cut", n, [], inv, t0, w0, trace, events, regress, archive, expanded)
                return _out("submitted" if cl["status"] == "unique" else "ambiguous", n, cl["dps"], inv, t0, w0, trace, events, regress,
                            archive, expanded)
            cand = [n for n in archive if not n.get("done") and len(n["path"]) < cfg["max_depth"]]
            if not cand:
                break
            node = max(cand, key=lambda n: (priority(n, w), -n["id"]))
            if node.get("n_exp", 0) == 0:
                expanded.append(node)
                node["it"] = _children(inv, mem, node, mode, order)
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
                    sig = _sig(inv, final_key)
                    novel = sig not in sigs
                    if kind in ("neutral", "worse") and not novel:
                        events["duplicate"] += 1
                    else:
                        child = dict(id=next(tick), path=node["path"] + [(k, op, prm)], specs=specs, ev=ev, parent=node["id"], kind=kind,
                                     novel=novel, op=op, native=native, stage_progress=max(0.0, (p_st - n_st) / max(1, p_st)))
                        sigs[sig] = child["id"]
                        keep = True
                        if sum(1 for n in archive if not n.get("done")) >= cfg["archive_cap"]:     # capacity counts OPEN programs
                            events["archive_full"] += 1
                            victim = min((n for n in archive if not n.get("done") and not n.get("n_exp") and n["kind"] != "root"),
                                         key=lambda n: priority(n, w), default=None)       # expanded programs (ancestors) stay
                            if victim is None or priority(victim, w) >= priority(child, w):
                                events["evicted"] += 1
                                keep = False
                            else:
                                archive.remove(victim)
                                events["evicted"] += 1
                        if keep:
                            archive.append(child)
                            events["retained"] += 1
                if n_new >= cfg["widen"]:
                    break
            else:
                node["done"] = True
        if not held_fail:
            break
    best = max((n for n in archive if n["kind"] != "root" and n["ev"]["score"] > archive[0]["ev"]["score"]), key=lambda n: n["ev"]["score"], default=None)
    best_partial = None if best is None else dict(path=best["path"], gain=round(best["ev"]["score"] - archive[0]["ev"]["score"], 4),
                                                  stage_fixed=sum(map(len, archive[0]["ev"]["stage_fail"])) - sum(map(len, best["ev"]["stage_fail"])),
                                                  kinds=[a.get("kind") for a in _ancestors(best, archive)])
    return dict(outcome="none", best_partial=best_partial, path=None, specs=None, dps=[], trace=trace, runs=dict(inv.runs), work=work() - w0, wall=round(time.time() - t0, 3),
                work_exhausted=work() - w0 >= work_budget, events=events, regressions=regress[:40], start_features=sorted(ev0["features"]), solution_nodes=[], other_nodes=[])


def _children(inv, mem, node, mode, order):
    """Children interleaved across operators (weighted round-robin): each round yields up to 1 + clip(evidence weight, 0, 3)
    candidates of every operator, operators in learned order - breadth over operator TYPES before depth inside one."""
    stages = list(range(len(inv.stages)))
    if mode == "decompose":
        failing = [k for k, fs in enumerate(node["ev"]["stage_fail"]) if fs]
        stages = [failing[0]] if failing else [len(inv.stages) - 1]
    de = mem.get("de", {})
    feats = node["ev"]["features"]
    ops = P6.op_order(de, feats, order)
    wsc = {o: sum(de.get("w", {}).get(f, {}).get(o, 0.0) for f in feats) for o in ops}

    def gen(op):
        for k in stages:
            for s2, prm in E.candidates(op, node["specs"][k], inv.dom(k, node["specs"])):
                yield k, op, s2, prm
    live = [(o, gen(o)) for o in ops]
    while live:
        nxt = []
        for o, g in live:
            alive = True
            for _ in range(1 + int(min(3, max(0, wsc[o])))):
                try:
                    yield next(g)
                except StopIteration:
                    alive = False
                    break
            if alive:
                nxt.append((o, g))
        live = nxt


def _ancestors(node, archive):
    byid = {n["id"]: n for n in archive}
    out, cur = [], node
    while cur is not None and cur.get("parent") is not None:
        out.append(cur)
        cur = byid.get(cur["parent"])
    return out


def _out(outcome, node, dps, inv, t0, w0, trace, events, regress, archive, expanded):
    anc = _ancestors(node, archive)
    ids = {n["id"] for n in anc}
    others = [n for n in expanded if n["id"] not in ids][:40]
    strip = lambda n: dict(path=n["path"], ev=dict(score=n["ev"]["score"]), kind=n.get("kind"), novel=n.get("novel"), op=n.get("op"),  # noqa: E731
                           stage_progress=n.get("stage_progress", 0.0))
    return dict(outcome=outcome, path=node["path"], specs=node["specs"], dps=dps, trace=trace, runs=dict(inv.runs), work=sum(inv.runs.values()) - w0,
                wall=round(time.time() - t0, 3), work_exhausted=False, events=events, regressions=regress[:40], start_features=sorted(trace[0]["features"]),
                via_skill=bool(node.get("via_skill") or any(a.get("via_skill") for a in anc)), solution_nodes=[strip(n) for n in anc],
                other_nodes=[strip(n) for n in others], solution_kinds=[n.get("kind") for n in anc])
