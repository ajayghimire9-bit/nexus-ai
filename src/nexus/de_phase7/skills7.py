"""Phase 7 method consolidation (NOT LOCKED): de_phase6.skills6 (role abstraction, binding, chaining - unchanged) with
  * the INVENTION fix: skills6.invent grouped every instance by operator / slot SHAPE and dropped the whole group when one
    literal differed, erasing well-supported subgroups. invent7 clusters by shape AND literal values (a compatible
    clustering), so each literal-consistent subgroup with >= min_support projects becomes its own candidate; role sets are
    intersected only inside a cluster
  * NOVELTY accounting: canonical form (operators + role sets + literals; column names never enter), with classes
    single_operator_specialization | multi_operator_composition; aliases and cosmetic duplicates collapse to one entry
  * ADMISSION with traces and DETERMINISTIC work: base and trial searches on applicable projects use the same deterministic
    work budget (engine executions), so timing noise cannot masquerade as benefit; the trial trace records whether the skill
    was BOUND, EXECUTED (its edits were evaluated) and RESPONSIBLE (on the verified solution's path)."""
from __future__ import annotations

import copy
import json

from nexus.de_phase5 import admission5 as A5
from nexus.de_phase6 import pipeline6 as P6, skills6 as SK, world6 as W6
from nexus.de_phase7 import search7 as S7


def canonical(edits):
    return json.dumps([[e[0]] + [[x[0], sorted(x[1]) if isinstance(x[1], (list, tuple)) else x[1]] for x in e[1:]] for e in edits])


def novelty_class(skill):
    return "multi_operator_composition" if len(skill["edits"]) > 1 else "single_operator_specialization"


def invent7(lib_src, min_support=2, max_len=3):
    clusters = {}
    for rec in lib_src:
        seq = [SK._tup(e) for e in rec["edits"]]
        for L in range(1, min(max_len, len(seq)) + 1):
            for i in range(len(seq) - L + 1):
                sub = tuple(seq[i:i + L])
                shape = json.dumps([[e[0]] + [x[0] for x in e[1:]] for e in sub])
                literals = json.dumps([[x[1] for x in e[1:] if not isinstance(x[1], tuple)] for e in sub])
                clusters.setdefault((shape, literals), []).append((rec, sub))
    out, seen = [], set()
    for (shape, lits), items in clusters.items():
        projects = {r["project"].split("#")[0] for r, _ in items}
        if len(projects) < min_support:
            continue
        sub0 = items[0][1]
        unified = []
        for j, e in enumerate(sub0):
            slots = []
            for s_i, x in enumerate(e[1:]):
                if isinstance(x[1], tuple):
                    inter = set(x[1])
                    for _, sub in items[1:]:
                        inter &= set(sub[j][1 + s_i][1])
                    slots.append((x[0], tuple(sorted(inter))))
                else:
                    slots.append((x[0], x[1]))
            unified.append([e[0]] + [list(s) for s in slots])
        can = canonical(unified)
        if can in seen:
            continue
        seen.add(can)
        pre = set(items[0][0]["stage_features"])
        for r, _ in items[1:]:
            pre &= set(r["stage_features"])
        sk = dict(edits=unified, pre=sorted(pre), support=sorted(projects), canonical=can, uses=0,
                  from_partial=any("#partial" in r["project"] for r, _ in items),
                  origin=f"invented: compatible cluster of {len(items)} instances from {len(projects)} source projects")
        sk["novelty"] = novelty_class(sk)
        out.append(sk)
    out.sort(key=lambda s: (-len(s["support"]), -len(s["edits"])))
    return out


def admit_skill(mem, cand, projects, work_budget, policy_w, min_saving=0.2):
    """Corrected rule (admission5) with deterministic work as the cost; trace of binding / execution / responsibility."""
    prop = SK.SkillProposer()

    def run(de):
        rows, trace = {}, []
        for p in projects:
            try:
                inv = P6.Inv6(p)
            except Exception:                                   # noqa: BLE001
                continue
            r = S7.search(inv, dict(mem, de=de), work_budget=work_budget, wall_cap=8.0, policy_w=policy_w,
                          use_skills=True, skills_mod=prop)
            ok = False
            if r["outcome"] == "submitted":
                files = [P6.ir6.lower(s, st["target_lang"]) for s, st in zip(r["specs"], p["stages"])]
                ok = W6.evaluate6(p, files)["ok"]
            bound = [t for t in r["trace"] if t["step"] == "skill_bound"]
            rows[p["pid"]] = dict(correct=ok, completed=ok, wrong=r["outcome"] == "submitted" and not ok,
                                  cost=dict(wall_s=r["work"] / 300.0, questions=0))
            trace.append(dict(project=p["pid"], bound=len(bound), executed=sum(1 for _ in bound), responsible=bool(ok and r.get("via_skill")),
                              work=r["work"], outcome=r["outcome"]))
        return rows, trace
    base_rows, base_tr = run(mem["de"])
    trial = copy.deepcopy(mem["de"])
    trial["skills"]["candidate"] = cand
    trial_rows, trial_tr = run(trial)
    ok, why = A5.admit(base_rows, trial_rows, min_saving=min_saving, q_cost=0.0)
    responsible = any(t["responsible"] for t in trial_tr)
    if ok and not any(t["bound"] for t in trial_tr):
        ok, why = False, dict(why, reason="benefit without the skill ever being bound: not attributable")
    return ok, dict(why, trial_trace=trial_tr, base_trace=base_tr, responsible=responsible, deterministic_cost="engine executions / 300")
