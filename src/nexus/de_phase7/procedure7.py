"""Phase 7 investigation procedures (NOT LOCKED): the Phase 6 typed language (de_phase6.procedure6, unchanged; its read /
resolve / ask actions are reused as they are) extended with

  ["search", mode, skills]   now the bounded-archive search (search7) under the memory's archive policy: Full's learned
                             policy_w when present, else the fixed diversity / beam rule
  ["check_coverage"]         inspect the CURRENT pipeline's behaviour at every documented subject (accept7.coverage):
                             obligations become decision points that resolve / ask can discharge
  ["submit_or_abstain"]      the SHARED BARRIER (every arm): when the procedure never checked coverage, the barrier computes
                             it (charged) and abstains while an obligation is open - it never resolves one

Costs are DETERMINISTIC: engine executions (search work + barrier / coverage probes) x RUN_S, plus QUESTION_COST_S per
question; measured wall time is recorded separately and never enters an admission decision.

Composition (learn_round): from the current program, typed single / pair insertions and sampled delete / swap / parameter
/ wrap / call edits, scored by REPLAY of cached source experience on the proposal-selection pool; an edit is adopted only
by admit7 (admission5 + no lost completion: never trade a verified completion for abstentions) and must then not be worse
on a separate untouched confirmation set. A round's adopted block that contains search / resolve / ask / coverage becomes
a named reusable procedure (call)."""
from __future__ import annotations

import copy
import itertools
import json
import time

from nexus.de_phase5 import admission5 as A5
from nexus.de_phase6 import ir6, pipeline6 as P6, procedure6 as PR, skills6 as SK, world6 as W6
from nexus.de_phase7 import accept7 as AC7, search7 as S7

RUN_S = 0.004                                            # deterministic cost of one engine execution (frozen at Stage 1)
QUESTION_COST_S = PR.QUESTION_COST_S
SOURCES = PR.SOURCES
SEED = [["search", "whole", "off"], ["submit_or_abstain"]]
FIXED_STRATEGY = [["read_all"], ["search", "whole", "on"], ["check_coverage"], ["resolve", "calibrated"], ["if", "unresolved", [["ask", "conflicted"]]],
                  ["resolve", "calibrated"], ["submit_or_abstain"]]
COND_NAMES = PR.COND_NAMES + ("coverage_checked",)
TYPES = dict(PR.TYPES, check_coverage=(("hypotheses",), ("hypotheses",)))


def palette():
    return PR.palette() + [["check_coverage"]]


class State(PR.State):
    def __init__(self, project, backend, mem):
        super().__init__(project, backend, mem)
        self.coverage_checked = False
        self.cost.update(probe_runs=0, work=0)
        self.barrier = dict(computed=False, obligations=0, probe_runs=0)


def cond(st, c):
    if isinstance(c, list) and c[0] == "not":
        return not cond(st, c[1])
    if c == "coverage_checked":
        return st.coverage_checked
    return PR.cond(st, c)


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
            st.log("call", dict(procedure=s[1], conditions_at_entry={c: cond(st, c) for c in COND_NAMES}))
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


def _add_coverage(st, by):
    if st.coverage_checked or not st.has_candidate:
        return 0
    st.coverage_checked = True
    cov = st.b.coverage(st.p, st.cand, [d.get("ref") for d in st.dps])
    st.cost["probe_runs"] += cov["probe_runs"]
    new = copy.deepcopy(cov["obligations"])
    st.dps += new
    PR._attach(st)
    st.log("check_coverage", dict(by=by, obligations=[dict(stage=d["stage"], column=d["col"], options=d["options"]) for d in new],
                                  equivalences=cov["equivalences"], uncovered=len(cov["uncovered"])))
    return len(new)


def a_check_coverage(st):
    _add_coverage(st, "procedure")


def a_submit(st):
    if st.decision is not None:
        return
    if st.has_candidate and not st.coverage_checked:          # the shared barrier: evidence obligation, never a resolution
        n = _add_coverage(st, "barrier")
        st.barrier.update(computed=True, obligations=n)
    PR.a_submit(st)
    if st.decision["kind"] == "abstain" and st.barrier["obligations"] and st.unresolved():
        st.decision["reason"] += " (barrier: open requirement obligation)"


ACTIONS = dict(PR.ACTIONS, search=a_search, check_coverage=a_check_coverage, submit_or_abstain=a_submit)


def investigate(project, backend, mem, prog, library=None):
    st = State(project, backend, mem)
    run(prog, st, library or {})
    return st


def chosen_specs(st):
    cov = [d for d in st.dps if str(d["pos"]).startswith("cov:")]
    rest = [d for d in st.dps if not str(d["pos"]).startswith("cov:")]
    saved, st.dps = st.dps, rest
    specs = copy.deepcopy(PR.chosen_specs(st))
    st.dps = saved
    for d in cov:
        if st.decision["choices"][f"{d['stage']}:{d['pos']}"] == d["options"][1]:
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


def cost_s(st_cost):
    return RUN_S * (st_cost.get("work", 0) + st_cost.get("probe_runs", 0)) + QUESTION_COST_S * st_cost.get("questions", 0)


# ------------------------------------------------------------------ live backend
def search_digest(mem):
    return json.dumps(dict(w=mem.get("de", {}).get("w", {}), skills=sorted(mem.get("de", {}).get("skills", {}).items(), key=str),
                              policy=mem.get("policy_w"), M={k: mem.get("M", {}).get(k) for k in ("src_work", "archive_cap", "worse_delta")}),
                         sort_keys=True, default=str)


class Live:
    def __init__(self, work_budget, wall_cap=8.0, touch=None):
        self.work_budget, self.wall_cap = work_budget, wall_cap
        self.cache, self.invs = {}, {}
        self.proposer = SK.SkillProposer()
        self.touch = touch if touch is not None else {}

    def read(self, project, src):
        return PR.read_claims(project["ws"], src)

    def _inv(self, project):
        if project["pid"] not in self.invs:
            self.invs[project["pid"]] = P6.Inv6(project)
        return self.invs[project["pid"]]

    def search(self, project, mem, mode, skills):
        wb = self.work_budget(project, mem) if callable(self.work_budget) else self.work_budget
        key = (project["pid"], search_digest(mem), mode, skills, wb)
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
        M = mem.get("M", {})
        r = S7.search(inv, mem, work_budget=wb, wall_cap=self.wall_cap, policy_w=mem.get("policy_w"), mode=mode, use_skills=skills == "on",
                      skills_mod=self.proposer, cfg={k: M[k] for k in ("archive_cap", "worse_delta") if k in M})
        ev = r["events"]
        for k_, n_ in (("worse_delta", ev["worse_decision"]), ("archive_cap", ev["archive_full"]), ("src_work", int(r["work_exhausted"]))):
            self.touch[k_] = self.touch.get(k_, 0) + n_
        self.invs[project["pid"]] = inv
        out = dict(outcome=r["outcome"], has_candidate=r["outcome"] in ("submitted", "ambiguous"), path=r["path"], specs=r["specs"], dps=r["dps"],
                   cost=dict(work=r["work"], sqlite_runs=inv.runs["sqlite"], duckdb_runs=inv.runs["duckdb"], spark_runs=inv.runs["spark"],
                             wall_s=round(time.time() - t0, 3)),
                   events=ev, regressions=r["regressions"], start_features=r["start_features"], via_skill=r.get("via_skill", False),
                   skill_trace=[t for t in r["trace"] if t["step"] == "skill_bound"], solution_nodes=r.get("solution_nodes", []),
                   other_nodes=r.get("other_nodes", []), solution_kinds=r.get("solution_kinds", []), work_exhausted=r["work_exhausted"],
                   partial=_best_partial(r))
        self.cache[key] = out
        return copy.deepcopy(out)

    def coverage(self, project, cand, skip_refs):
        inv = self._inv(project)
        c = {}
        cov = AC7.coverage(inv, cand["specs"], cost=c, skip_refs=skip_refs)
        return dict(cov, probe_runs=c.get("probe_runs", 0))

    def ask(self, project, dp):
        return PR.Live.ask(self, project, dp)


def _best_partial(r):
    """The best retained intermediate program of an unsolved search (incomplete experience), or None."""
    return r.get("best_partial") if r["outcome"] == "none" else None


# ------------------------------------------------------------------ cached replay (procedure composition)
class Cached:
    def __init__(self, caches):
        self.c = caches

    def read(self, project, src):
        return copy.deepcopy(self.c[project["pid"]]["reads"][src])

    def search(self, project, mem, mode, skills):
        return copy.deepcopy(self.c[project["pid"]]["search"][f"{mode}|{skills}"])

    def coverage(self, project, cand, skip_refs):
        cfg = cand.get("_cfg")
        return copy.deepcopy(self.c[project["pid"]]["coverage"][cfg])

    def ask(self, project, dp):
        a = copy.deepcopy(self.c[project["pid"]]["answers"].get(akey(dp), dict(answer="no_probe")))
        if a.get("answer") == "output":
            dp["option_keys"] = a["option_keys"]
        return a


def akey(dp):
    return f"{dp['stage']}:{dp['pos']}:{dp['op']}"


def build_entry(project, live, mem, configs=(("whole", "on"), ("whole", "off"), ("decompose", "on"), ("decompose", "off"))):
    """Execute each search configuration once (identical inputs reuse the executed search), the coverage of each
    candidate, one stakeholder answer per decision point, and the hidden outcome of every option combination."""
    e = dict(pid=project["pid"], reads={s: live.read(project, s) for s in SOURCES}, search={}, coverage={}, answers={}, combos={})
    single = len(project["stages"]) == 1
    no_sk = not mem.get("de", {}).get("skills")
    for mode, sk in configs:
        cfg = f"{mode}|{sk}"
        same = f"{'whole' if single else mode}|{'off' if no_sk else sk}"
        if same != cfg and same in e["search"]:
            e["search"][cfg] = dict(e["search"][same], reused_from=same)
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
            if akey(dp) not in e["answers"]:
                a = live.ask(project, dp)
                a["option_keys"] = dp["option_keys"]
                e["answers"][akey(dp)] = a
        if r["has_candidate"]:
            for opts in itertools.product(*[dp["options"] for dp in dps]) if dps else [()]:
                st = State(project, live, mem)
                st.has_candidate, st.cand, st.dps = True, r, copy.deepcopy(dps)
                st.decision = dict(kind="submit", choices={f"{dp['stage']}:{dp['pos']}": o for dp, o in zip(dps, opts)})
                o = outcome(project, st)
                e["combos"][cfg + "|" + json.dumps([str(x) for x in opts])] = dict(verified=o["verified"], wrong=o["wrong"])
    e["any_verifiable"] = any(v["verified"] for v in e["combos"].values())
    e["undecided"] = bool(project.get("undecided"))
    return e


def replay_row(entry, st):
    d = st.decision
    if d["kind"] == "submit":
        cfg = next((f"{t['obs']['mode']}|{t['obs']['skills']}" for t in st.trace if t["action"] == "search"), None)
        k = f"{cfg}|" + json.dumps([str(d["choices"][f"{dp['stage']}:{dp['pos']}"]) for dp in st.dps])
        v = entry["combos"].get(k, dict(verified=False, wrong=True))
        correct, completed, wrong = v["verified"], v["verified"], v["wrong"]
    else:
        correct, completed, wrong = not entry["any_verifiable"], False, False
    return dict(correct=correct, completed=completed, wrong=wrong, cost=dict(wall_s=cost_s(st.cost), questions=0), decision=d["kind"],
                questions=st.cost["questions"], executed=st.executed)


def score(prog, library, projects, caches, mem):
    b = Cached(caches)
    rows = {}
    for p in projects:
        st = investigate(p, b, mem, prog, library)
        rows[p["pid"]] = replay_row(caches[p["pid"]], st)
    return rows


def admit7(base, trial, min_saving=0.1):
    """admission5 (more wrong never; fewer correct never; equal-zero cost promotion never) + never lose a verified completion
    (no trade of completions for easy abstentions). Question cost is already inside the deterministic cost."""
    ok, why = A5.admit(base, trial, min_saving=min_saving, q_cost=0.0)
    if ok and why["lost"]:
        return False, dict(why, reason="loses a verified completion")
    return ok, why


def not_worse(base, trial):
    wb, wt = sum(r["wrong"] for r in base.values()), sum(r["wrong"] for r in trial.values())
    cb, ct = sum(r["correct"] for r in base.values()), sum(r["correct"] for r in trial.values())
    lost = sorted(p for p in base if base[p]["completed"] and not trial.get(p, {}).get("completed"))
    return wt <= wb and ct >= cb and not lost, dict(correct=[cb, ct], wrong=[wb, wt], lost=lost)


def _flatten(prog, path=()):
    for i, s in enumerate(prog):
        yield path + (i,), s
        if s[0] == "if":
            yield from _flatten(s[2], path + (i, 2))


def proposals(prog, library, rng, n_sampled=16, typed_pairs=True):
    flat = copy.deepcopy(prog)
    out = []
    pal = palette()
    for i in range(len(flat) + 1):
        for s in pal:
            new = copy.deepcopy(flat)
            st_ = copy.deepcopy(s)
            new.insert(i, st_)
            out.append(("insert", new, [st_], f"insert {s} at {i}"))
        if typed_pairs:
            for a in pal:
                for b in pal:
                    if set(TYPES[a[0]][1]) & set(TYPES[b[0]][0]) and a[0] != b[0]:
                        new = copy.deepcopy(flat)
                        a_, b_ = copy.deepcopy(a), copy.deepcopy(b)
                        new[i:i] = [a_, b_]
                        out.append(("insert_pair", new, [a_, b_], f"insert {a} + {b} at {i}"))
    for _ in range(n_sampled):
        et = rng.choice(["delete", "swap", "param", "wrap", "call"])
        new = copy.deepcopy(flat)
        if not new:
            continue
        i = rng.randrange(len(new))
        if et == "delete" and new[i][0] != "submit_or_abstain":
            old = new.pop(i)
            out.append(("delete", new, [], f"delete {old}"))
        elif et == "swap" and i + 1 < len(new):
            new[i], new[i + 1] = new[i + 1], new[i]
            out.append(("swap", new, [new[i]], f"swap {i}"))
        elif et == "param":
            alts = [s for s in pal if s[0] == new[i][0] and s != new[i]]
            if alts:
                new[i] = copy.deepcopy(rng.choice(alts))
                out.append(("param", new, [new[i]], f"set {i} -> {new[i]}"))
        elif et == "wrap" and new[i][0] not in ("if", "submit_or_abstain"):
            c = rng.choice(list(COND_NAMES) + [["not", x] for x in COND_NAMES])
            new[i] = ["if", c, [new[i]]]
            out.append(("wrap", new, [new[i]], f"wrap {i} in if {c}"))
        elif et == "call" and library:
            name = rng.choice(sorted(library))
            stmt = ["call", name]
            new.insert(i, stmt)
            out.append(("call", new, [stmt], f"insert call {name} at {i}"))
    return out


def learn_round(prog, library, pool, caches, confirm, conf_caches, mem, rng, cycles=3, typed_pairs=True, round_id=0, touch=None):
    """One learning round: up to `cycles` adopted edits on the proposal-selection pool, then a confirmation check of the
    round's final program against the round's starting program on untouched examples. Returns the (possibly unchanged)
    program, library and a log; the starting program is kept if confirmation fails."""
    start_prog, start_lib = copy.deepcopy(prog), copy.deepcopy(library)
    prog, library, log = copy.deepcopy(prog), copy.deepcopy(library), []
    base = score(prog, library, pool, caches, mem)
    n_adopted, reached_bound = 0, False
    for cyc in range(cycles):
        best = None
        for et, new, block, desc in proposals(prog, library, rng, typed_pairs=typed_pairs):
            rows = score(new, library, pool, caches, mem)
            ok, why = admit7(base, rows)
            if ok:
                key = (sum(r["correct"] for r in rows.values()), -sum(r["cost"]["wall_s"] for r in rows.values()), -len(json.dumps(new)))
                if best is None or key > best[0]:
                    best = (key, new, block, desc, rows, why)
        log.append(dict(round=round_id, cycle=cyc, proposals_scored=True, best=best[3] if best else None))
        if best is None:
            break
        _, new, block, desc, rows, why = best
        n_adopted += 1
        if cyc == cycles - 1:
            reached_bound = True
        if len(block) >= 2 or (block and block[0][0] in ("search", "resolve", "ask", "check_coverage")):
            name = f"proc{len(library) + 1}"
            helped = [p for p in rows if rows[p]["correct"] and not base[p]["correct"]] or \
                     [p for p in rows if rows[p]["completed"] and rows[p]["cost"]["wall_s"] < base[p]["cost"]["wall_s"]]
            library[name] = dict(body=copy.deepcopy(block), interface="InvestigationState -> InvestigationState", helped=helped,
                                 provenance=dict(round=round_id, cycle=cyc, edit=desc, validation=sorted(rows)), utility=why)
            first = block[0]
            for path_, s_ in list(_flatten(new)):
                if any(s_ is b_ for b_ in block[1:]):
                    c_ = new
                    for k_ in path_[:-1]:
                        c_ = c_[k_]
                    c_.pop(path_[-1])
                    break
            first[:] = ["call", name]
        prog, base = new, score(new, library, pool, caches, mem)
        log.append(dict(round=round_id, cycle=cyc, adopted=desc, why={k: v for k, v in why.items() if k != "lost"}, program=copy.deepcopy(prog)))
    if touch is not None and reached_bound:
        touch["proc_cycles"] = touch.get("proc_cycles", 0) + 1
    if n_adopted and confirm:
        b0 = score(start_prog, start_lib, confirm, conf_caches, mem)
        b1 = score(prog, library, confirm, conf_caches, mem)
        ok, why = not_worse(b0, b1)
        log.append(dict(round=round_id, confirmation=ok, why=why, n=len(confirm)))
        if not ok:
            return start_prog, start_lib, log
    return prog, library, log
