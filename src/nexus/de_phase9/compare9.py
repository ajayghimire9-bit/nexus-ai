"""Phase 9 future-learning comparator (NOT LOCKED; human evaluation infrastructure).

eval_memory   a frozen memory under the SAME procedure F0 and archive rule on a stratified block; per task it records the
              EXPOSURE: which obligations / decision points existed, how each was resolved (claim, calibrated trust,
              clarification, unresolved), whether the method queue accepted a learned method, the decision, and the
              deterministic cost components (engine work + probes, questions, document reads).
costs         C_acquire (learning trajectory: per-project deterministic cost + method-admission search work),
              C_future (the block evaluation), C_discovery (screen + clone trajectories + selection, charged separately);
              proxies (question 2.0 s, read 0.1 s) are MODEL ASSUMPTIONS, reported with sensitivity (read 0 / 0.1; question
              0 / 2 / 5); measured wall is recorded separately.
select        candidate vs incumbent on the block (predeclared): never more accepted wrong repairs (trajectory or block);
              either MORE verified completions on the block, or the same non-empty verified set with acquisition+future
              cost >= 10 % lower and no more unresolved obligations; zero-completion ties never win; information volume is
              not a reward."""
from __future__ import annotations

import copy
import json

from nexus.de_phase7 import world7 as W7
from nexus.de_phase8 import lineage8 as L8, procedure8 as PR8

PROXIES = [dict(read=r, question=q) for r in (0.0, 0.1) for q in (0.0, 2.0, 5.0)]


def build_block(items, root):
    out = []
    for stratum, spec, seed in items:
        try:
            p = W7.make_project7(spec, seed, root)
        except RuntimeError as e:
            out.append(dict(stratum=stratum, seed=seed, error=str(e)[:80]))
            continue
        p["stratum"] = stratum
        out.append(p)
    return out


def det_cost(c, read=PR8.READ_COST_S, question=PR8.QUESTION_COST_S):
    return PR8.RUN_S * (c.get("work", 0) + c.get("probe_runs", 0)) + question * c.get("questions", 0) + read * c.get("reads", 0)


def eval_memory(mem, projects, live=None, prog=None):
    live = live or PR8.Live(L8.W_SRC, L8.WALL_SRC)
    rows = {}
    for p in projects:
        if "error" in p:
            continue
        st = PR8.investigate(p, live, copy.deepcopy(mem), prog or PR8.F0, {})
        o = PR8.outcome(p, st)
        rows[p["pid"]] = dict(stratum=p["stratum"], undecided=bool(p["undecided"]), verified=o["verified"], wrong=o["wrong"], decision=o["decision"],
                              reason=st.decision.get("reason"), cost=dict(st.cost), cost_s=round(det_cost(st.cost), 4),
                              points=[dict(kind=d.get("kind") or d.get("op"), via=d["via"], conflict=d["conflict"], undecided=d["undecided"],
                                           claims=len(d.get("claims") or [])) for d in st.dps],
                              trust_used=any((d["via"] or "").startswith("trust") for d in st.dps), questions=st.cost["questions"],
                              method_accepted=bool(((st.cand or {}).get("method_queue") or {}).get("accepted")), obligations=st.obligation_status,
                              unresolved=len(st.unresolved()))
    return rows


def summary(rows):
    v = list(rows.values())
    return dict(n=len(v), verified=sum(r["verified"] for r in v), wrong=sum(r["wrong"] for r in v),
                justified=sum(r["decision"] == "abstain" and r["undecided"] for r in v),
                unsolved_answerable=sum(not r["verified"] and not r["undecided"] for r in v), solved=sorted(p for p, r in rows.items() if r["verified"]),
                unresolved_points=sum(r["unresolved"] for r in v), trust_used=sum(r["trust_used"] for r in v),
                method_accepted=sum(r["method_accepted"] for r in v), questions=sum(r["questions"] for r in v),
                cost_s=round(sum(r["cost_s"] for r in v), 3), by_stratum={s: sum(r["verified"] for r in v if r["stratum"] == s) for s in sorted({r["stratum"] for r in v})})


def proxy_costs(rows, acq_cost_components):
    out = []
    for px in PROXIES:
        fut = sum(det_cost(r["cost"], **px) for r in rows.values())
        acq = sum(det_cost(c, **px) for c in acq_cost_components)
        out.append(dict(px, future=round(fut, 3), acquire=round(acq, 3), total=round(fut + acq, 3)))
    return out


def select(inc, cand, inc_acq_wrong=0, cand_acq_wrong=0, inc_acq_cost=0.0, cand_acq_cost=0.0):
    """-> (wins, reason). inc / cand: summary() of the block rows."""
    if cand["wrong"] > inc["wrong"] or cand_acq_wrong > inc_acq_wrong:
        return False, "adds an accepted wrong repair"
    if cand["verified"] > inc["verified"]:
        return True, "more verified completions on the disjoint future block"
    if cand["verified"] < inc["verified"]:
        return False, "fewer verified completions"
    if cand["verified"] == 0:
        return False, "zero-completion tie"
    if cand["solved"] != inc["solved"]:
        return False, "same count, different solved set: no cost claim"
    if cand["unresolved_points"] > inc["unresolved_points"]:
        return False, "more unresolved obligations"
    ti, tc = inc_acq_cost + inc["cost_s"], cand_acq_cost + cand["cost_s"]
    if tc <= 0.9 * ti:
        return True, f"same verified set, acquisition+future cost {tc:.2f} vs {ti:.2f} (>= 10 % lower)"
    return False, "tie: no quality or >= 10 % cost advantage"


def mem_digest(mem):
    return json.dumps(dict(trust=mem["trust"], w=mem["de"]["w"], skills=sorted(mem["de"]["skills"].values(), key=lambda s: s["canonical"]),
                           src=sorted(json.dumps(x, sort_keys=True, default=list) for x in mem["skill_src"])), sort_keys=True, default=list)
