"""Phase 8 search with a SEPARATE, BOUNDED METHOD QUEUE (NOT LOCKED; frozen routing infrastructure shared by every arm).

Phase 7 inserted every bound skill path into the base archive, where well-scored skill nodes were expanded first and
displaced successful base search (three r0 P4 targets). search8 keeps one predeclared TOTAL work budget W:
  1 method queue: bound skill paths (skills6.SkillProposer, duplicates removed by pipeline) are evaluated in order until
    their spent work reaches METHOD_SLICE x W; a path that passes the visible checks goes through the same acceptance
    steps as base search (declared-engine verification, v7 invariants with the SQLite screen, the repair closure); the
    first accepted path is returned. Paths that do not pass are dropped: they never enter the base frontier.
  2 base search: de_phase7.search7 (fixed archive rule FIXED_W, no skills) with the REMAINING budget W - spent. An arm with
    an empty library therefore gets the full W; unused slice returns to base search.
Base search with W - spent does not reach everything reachable with W: no monotonic-solve guarantee is made."""
from __future__ import annotations

import json
import time

from nexus.de_phase6 import pipeline6 as P6
from nexus.de_phase7 import search7 as S7

METHOD_SLICE = 0.2


def search(inv, mem, work_budget, wall_cap, mode="whole", use_skills=True, skills_mod=None, cfg=None):
    t0 = time.time()
    work = lambda: sum(inv.runs.values())                                     # noqa: E731
    w0 = work()
    mq = dict(tried=0, passed_checks=0, accepted=False, work=0, slice=METHOD_SLICE * work_budget)
    trace = []
    skills = mem.get("de", {}).get("skills") or {}
    if use_skills and skills_mod is not None and skills:
        ev0 = inv.run(inv.legacy, True)
        root = dict(specs=list(inv.legacy), ev=ev0)
        seen = set()
        for path in skills_mod.proposals(skills, inv, root, ev0):
            if work() - w0 >= mq["slice"] or time.time() - t0 > wall_cap / 2:
                break
            specs = P6.replay(inv, path)
            key = json.dumps(specs, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            mq["tried"] += 1
            ev = inv.run(specs, True)
            trace.append(dict(step="skill_bound", edits=path, ok=ev["ok"], score=round(ev["score"], 3)))
            if not (ev["ok"] and ev["held_ok"]):
                continue
            mq["passed_checks"] += 1
            evn = inv.run(specs, prescreen=False)
            if not (evn["ok"] and evn["held_ok"]):
                continue
            if P6.invariants(S7._Screen(inv), specs) or P6.invariants(inv, specs):
                continue
            cl = P6.closure(inv, path, deadline=t0 + wall_cap)
            trace.append(dict(step="closure", edits=path, status=cl["status"], scope=cl["scope"], via="method_queue"))
            if cl["status"] == "cut":
                continue
            mq.update(accepted=True, work=work() - w0)
            return dict(outcome="submitted" if cl["status"] == "unique" else "ambiguous", path=path, specs=specs, dps=cl["dps"],
                        trace=[dict(step="investigate", features=sorted(ev0["features"]))] + trace, runs=dict(inv.runs), work=work() - w0,
                        wall=round(time.time() - t0, 3), work_exhausted=False, events=dict(method_queue=mq), regressions=[],
                        start_features=sorted(ev0["features"]), via_skill=True, solution_nodes=[], other_nodes=[], solution_kinds=["method"],
                        method_queue=mq)
    mq["work"] = work() - w0
    rest = max(0, work_budget - mq["work"])
    r = S7.search(inv, mem, work_budget=rest, wall_cap=max(0.5, wall_cap - (time.time() - t0)), policy_w=None, mode=mode, use_skills=False, cfg=cfg)
    r["trace"] = r["trace"][:1] + trace + r["trace"][1:]
    r["work"] = work() - w0
    r["method_queue"] = mq
    r["events"] = dict(r["events"], method_queue=mq)
    r["via_skill"] = False
    return r
