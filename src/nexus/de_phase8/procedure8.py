"""Phase 8 investigation procedures (NOT LOCKED): the Phase 6/7 typed language (read / read_all / search / check_coverage /
resolve / ask / submit_or_abstain, if / repeat / call) on the Phase 8 shared infrastructure:
  search            search8 (bounded method queue + base archive search under the FROZEN archive rule FIXED_W)
  check_coverage    coverage v8 (accept8: semantic obligations; absent implementations block)
  ask               the single clarification goes only to an obligation that a probe row can settle (absent
                    obligations have none); it is not consumed when nothing is askable
  submit_or_abstain the shared barrier computes coverage v8 when the procedure did not, never resolves an obligation, and
                    records each obligation's status (satisfied / refuted / conflict / insufficient)
F0 (the shared strong prior of BOTH cohorts and of every evaluation arm except A2) = Phase 7 FIXED_STRATEGY.
Deterministic cost: RUN_S per engine execution (search work + probes) + QUESTION_COST_S per question + READ_COST_S per
document read (a declared, legitimate investigation cost, so selective reading can be cheaper). Measured wall is recorded
separately. Replay (Cached) is a SCREEN: a counterfactual the cache cannot support (an unasked question, a search
configuration never run) marks the replayed row `unsupported` - unknown, neither success nor failure."""
from __future__ import annotations

import copy
import itertools
import json
import time

from nexus.de_phase6 import ir6, pipeline6 as P6, procedure6 as PR, skills6 as SK, world6 as W6
from nexus.de_phase7 import procedure7 as PR7
from nexus.de_phase8 import accept8 as AC8, search8 as S8

RUN_S, QUESTION_COST_S, READ_COST_S = PR7.RUN_S, PR7.QUESTION_COST_S, 0.1
SOURCES = PR.SOURCES
F0 = copy.deepcopy(PR7.FIXED_STRATEGY)
COND_NAMES = PR7.COND_NAMES
palette = PR7.palette


class State(PR7.State):
    def __init__(self, project, backend, mem):
        super().__init__(project, backend, mem)
        self.unsupported = False
        self.obligation_status = []


def cond(st, c):
    return PR7.cond(st, c)


def run(prog, st, library, root=True):
    for s in prog:
        if st.decision is not None or st.steps >= PR.MAX_STEPS:
            break
        st.steps += 1
        st.executed.add(id(s))
        op = s[0]
        if op == "if":
            run(s[2] if cond(st, s[1]) else (s[3] if len(s) > 3 else []), st, library, False)
        elif op == "repeat":
            for _ in range(min(int(s[1]), 3)):
                before = (len(st.unresolved()), st.asked, len(st.claims), st.coverage_checked)
                run(s[2], st, library, False)
                if (len(st.unresolved()), st.asked, len(st.claims), st.coverage_checked) == before:
                    break
        elif op == "call":
            st.log("call", dict(procedure=s[1]))
            run(library[s[1]]["body"], st, library, False)
        else:
            ACTIONS[op](st, *s[1:])
    if root and st.decision is None:
        a_submit(st)


def a_search(st, mode, skills):
    if st.has_candidate:
        return
    PR.a_search(st, mode, skills)
    st.cost["work"] += st.cand.get("cost", {}).get("work", 0)
    if st.cand.get("_unsupported"):
        st.unsupported = True


def _add_coverage(st, by):
    if st.coverage_checked or not st.has_candidate:
        return 0
    st.coverage_checked = True
    cov = st.b.coverage(st.p, st.cand, [d.get("ref") for d in st.dps])
    st.cost["probe_runs"] += cov["probe_runs"]
    new = copy.deepcopy(cov["obligations"])
    st.dps += new
    PR._attach(st)
    st.log("check_coverage", dict(by=by, obligations=[dict(kind=d.get("kind"), column=d["col"], options=d["options"]) for d in new]))
    return len(new)


def a_check_coverage(st):
    _add_coverage(st, "procedure")


def a_ask(st, target):
    if st.asked:
        return
    un = [d for d in st.unresolved() if d.get("probe") is not None]
    if not un:
        return
    pick = {"first": lambda: un[0], "unclaimed": lambda: next((d for d in un if not d["claims"]), un[0]),
            "conflicted": lambda: next((d for d in un if d["conflict"] or len({c["effect_at_boundary"] for c in d["claims"]}) > 1), un[0])}[target]()
    st.asked = True
    st.cost["questions"] += 1
    ans = st.b.ask(st.p, pick)
    if ans.get("answer") == "unsupported":
        st.unsupported = True
    st.log("ask", dict(stage=pick["stage"], target=target, answer=ans["answer"]))
    if ans["answer"] == "undetermined":
        pick["undecided"] = True
    elif ans["answer"] == "output":
        ok = [o for o, k in zip(pick["options"], pick["option_keys"]) if k == ans["key"]]
        if len(ok) == 1:
            pick["resolved"], pick["via"] = ok[0], "clarification"


def a_submit(st):
    if st.decision is not None:
        return
    if st.has_candidate and not st.coverage_checked:
        n = _add_coverage(st, "barrier")
        st.barrier.update(computed=True, obligations=n)
    PR.a_submit(st)
    st.obligation_status = [dict(kind=d.get("kind"), status=AC8.status(d)) for d in st.dps if str(d["pos"]).startswith("cov8:")]


ACTIONS = dict(PR.ACTIONS, search=a_search, check_coverage=a_check_coverage, ask=a_ask, submit_or_abstain=a_submit)


def investigate(project, backend, mem, prog, library=None):
    st = State(project, backend, mem)
    run(prog, st, library or {})
    return st


def chosen_specs(st):
    cov = [d for d in st.dps if str(d["pos"]).startswith("cov8:")]
    rest = [d for d in st.dps if not str(d["pos"]).startswith("cov8:")]
    saved, st.dps = st.dps, rest
    specs = copy.deepcopy(PR.chosen_specs(st))
    st.dps = saved
    for d in cov:
        ch = st.decision["choices"][f"{d['stage']}:{d['pos']}"]
        if d["options"] and ch != d["options"][0]:
            specs[d["stage"]] = W6._flip(specs[d["stage"]], d["ref"])
    return specs


def outcome(project, st):
    d = st.decision
    if d["kind"] != "submit":
        return dict(decision="abstain", reason=d["reason"], verified=False, wrong=False)
    specs = chosen_specs(st)
    files = [ir6.lower(s, stg["target_lang"]) for s, stg in zip(specs, project["stages"])]
    ev = W6.evaluate6(project, files)
    return dict(decision="submit", verified=ev["ok"], wrong=not ev["ok"], hidden=ev["fails"], files=files)


def cost_s(c):
    return RUN_S * (c.get("work", 0) + c.get("probe_runs", 0)) + QUESTION_COST_S * c.get("questions", 0) + READ_COST_S * c.get("reads", 0)


def search_digest(mem):
    return json.dumps(dict(w=mem.get("de", {}).get("w", {}), skills=sorted(mem.get("de", {}).get("skills", {}).items(), key=str)), sort_keys=True, default=str)


class Live:
    def __init__(self, work_budget, wall_cap=6.0):
        self.work_budget, self.wall_cap = work_budget, wall_cap
        self.cache, self.invs = {}, {}
        self.proposer = SK.SkillProposer()

    def read(self, project, src):
        return PR.read_claims(project["ws"], src)

    def _inv(self, project):
        if project["pid"] not in self.invs:
            self.invs[project["pid"]] = P6.Inv6(project)
        return self.invs[project["pid"]]

    def search(self, project, mem, mode, skills):
        key = (project["pid"], search_digest(mem), mode, skills, self.work_budget, S8.METHOD_SLICE)
        if key in self.cache:
            r = copy.deepcopy(self.cache[key])
            r["shared"] = True
            return r
        t0 = time.time()
        try:
            inv = P6.Inv6(project)
        except Exception as e:                           # noqa: BLE001  (Unsupported legacy)
            out = dict(outcome="unsupported", has_candidate=False, path=None, specs=None, dps=[], cost=dict(work=0, wall_s=0.0), note=str(e)[:80])
            self.cache[key] = out
            return copy.deepcopy(out)
        r = S8.search(inv, mem, self.work_budget, self.wall_cap, mode=mode, use_skills=skills == "on", skills_mod=self.proposer)
        self.invs[project["pid"]] = inv
        out = dict(outcome=r["outcome"], has_candidate=r["outcome"] in ("submitted", "ambiguous"), path=r["path"], specs=r["specs"], dps=r["dps"],
                   cost=dict(work=r["work"], sqlite_runs=inv.runs["sqlite"], duckdb_runs=inv.runs["duckdb"], spark_runs=inv.runs["spark"],
                             wall_s=round(time.time() - t0, 3)),
                   regressions=r.get("regressions", []), start_features=r.get("start_features", []), via_skill=r.get("via_skill", False),
                   skill_trace=[t for t in r["trace"] if t["step"] == "skill_bound"], method_queue=r.get("method_queue"),
                   solution_kinds=r.get("solution_kinds", []), partial=r.get("best_partial") if r["outcome"] == "none" else None)
        self.cache[key] = out
        return copy.deepcopy(out)

    def coverage(self, project, cand, skip_refs):
        c = {}
        return AC8.coverage8(self._inv(project), cand["specs"], cost=c, skip_refs=skip_refs)

    def ask(self, project, dp):
        return PR.Live.ask(self, project, dp)


# ------------------------------------------------------------------ replay screen
class Cached:
    def __init__(self, caches):
        self.c = caches

    def read(self, project, src):
        return copy.deepcopy(self.c[project["pid"]]["reads"][src])

    def search(self, project, mem, mode, skills):
        e = self.c[project["pid"]]["search"].get(f"{mode}|{skills}")
        if e is None:
            return dict(outcome="unsupported_counterfactual", has_candidate=False, path=None, specs=None, dps=[], cost=dict(work=0), _unsupported=True)
        return copy.deepcopy(e)

    def coverage(self, project, cand, skip_refs):
        return copy.deepcopy(self.c[project["pid"]]["coverage"][cand["_cfg"]])

    def ask(self, project, dp):
        a = self.c[project["pid"]]["answers"].get(akey(dp))
        if a is None:
            return dict(answer="unsupported")
        a = copy.deepcopy(a)
        if a.get("answer") == "output":
            dp["option_keys"] = a["option_keys"]
        return a


def akey(dp):
    return f"{dp['stage']}:{dp['pos']}:{dp['op']}"


def build_entry(project, live, mem, configs=(("whole", "on"), ("whole", "off"))):
    """Execute each configuration once (identical inputs reuse), its coverage, one answer per askable decision point, and
    the hidden outcome of every option combination (charged: this is real execution)."""
    e = dict(pid=project["pid"], reads={s: live.read(project, s) for s in SOURCES}, search={}, coverage={}, answers={}, combos={})
    no_sk = not mem.get("de", {}).get("skills")
    for mode, sk in configs:
        cfg = f"{mode}|{sk}"
        same = next((c for c in e["search"] if no_sk and c.split("|")[0] == mode), None) or f"{mode}|{'off' if no_sk else sk}"
        if same != cfg and same in e["search"]:                 # identical inputs (empty library): reuse, never re-execute
            e["search"][cfg] = dict(e["search"][same], reused_from=same, _cfg=cfg)
            e["coverage"][cfg] = e["coverage"][same]
            for k_, v_ in list(e["combos"].items()):
                if k_.startswith(same + "|"):
                    e["combos"][cfg + "|" + k_.split("|", 2)[2]] = v_
            continue
        r = live.search(project, mem, mode, sk)
        r["_cfg"] = cfg
        e["search"][cfg] = r
        dps = list(r["dps"])
        if r["has_candidate"]:
            cov = live.coverage(project, r, [d.get("ref") for d in dps])
            e["coverage"][cfg] = cov
            dps += cov["obligations"]
        else:
            e["coverage"][cfg] = dict(obligations=[], equivalences=[], uncovered=[], probe_runs=0)
        for dp in dps:
            if dp.get("probe") is not None and akey(dp) not in e["answers"]:
                a = live.ask(project, dp)
                a["option_keys"] = dp["option_keys"]
                e["answers"][akey(dp)] = a
        if r["has_candidate"] and all(d["options"] for d in dps):
            for opts in itertools.product(*[dp["options"] for dp in dps]) if dps else [()]:
                st = State(project, live, mem)
                st.has_candidate, st.cand, st.dps = True, r, copy.deepcopy(dps)
                st.decision = dict(kind="submit", choices={f"{dp['stage']}:{dp['pos']}": o for dp, o in zip(dps, opts)})
                o = outcome(project, st)
                e["combos"][cfg + "|" + json.dumps([str(x) for x in opts])] = dict(verified=o["verified"], wrong=o["wrong"])
    e["any_verifiable"] = any(v["verified"] for v in e["combos"].values())
    return e


def replay_row(entry, st):
    d = st.decision
    if d["kind"] == "submit":
        cfg = next((f"{t['obs']['mode']}|{t['obs']['skills']}" for t in st.trace if t["action"] == "search"), None)
        k = f"{cfg}|" + json.dumps([str(d["choices"][f"{dp['stage']}:{dp['pos']}"]) for dp in st.dps])
        v = entry["combos"].get(k)
        if v is None:
            st.unsupported = True
            v = dict(verified=False, wrong=False)
        correct, completed, wrong = v["verified"], v["verified"], v["wrong"]
    else:
        correct, completed, wrong = not entry["any_verifiable"], False, False
    return dict(correct=correct, completed=completed, wrong=wrong, cost=dict(wall_s=cost_s(st.cost), questions=0), decision=d["kind"],
                questions=st.cost["questions"], executed=st.executed, unsupported=st.unsupported,
                actions=[t["action"] for t in st.trace], signature=signature(st))


def signature(st):
    """What the procedure DID with the evidence on one task: decision and choices, documents read, questions asked, how
    each decision point / obligation was resolved, and the search configuration. Two procedures with equal signatures on
    a task acquired the same evidence and made the same decision there."""
    has_sk = bool(st.mem.get("de", {}).get("skills"))
    srch = next((f"{t['obs']['mode']}|{t['obs']['skills'] if has_sk else 'off'}" for t in st.trace if t["action"] == "search"), None)  # effective
    return json.dumps([st.decision.get("kind"), sorted((st.decision.get("choices") or {}).items()), sorted(st.read_sources), st.cost["questions"],
                       [(str(d["pos"])[:24], d["via"], d["undecided"]) for d in st.dps], srch], default=str)


def score(prog, library, projects, caches, mem):
    b = Cached(caches)
    return {p["pid"]: replay_row(caches[p["pid"]], investigate(p, b, mem, prog, library)) for p in projects}
