"""Phase 5 investigation: evidence -> action -> revision -> verified submission or justified abstention (NOT LOCKED).

HUMAN ENGINEERING (disclosed): the action implementations below, the policy language and its interpreter, the fixed policy
F0, the evidence-record formats. LEARNED (from source experience): evidence memory (claim-trust weights, counterexamples,
action outcomes), the Phase 4 repair memory reused by `search` (pi_de, P, prefs), and - in policy_learn.py - the
composition of investigation procedures.

Actions (each returns an observation and a measured cost; a Backend executes or replays them):
  read(source)       structured requirement claims from contract.json / docs/runbook.json / docs/ticket.json, each with
                     provenance (file, claim id, status, version, date) - a structured-contract diagnostic, no NL model
  search             the Phase 4 repair search (de_phase4.learner.solve, de_accept_v2 with ambiguity mode 'abstain'); its
                     unresolved disagreements become DECISION POINTS: competing edits at one position of the repair path,
                     each with its option specs (rebound to this project's schema by replay)
  search_more        a second search with twice the budget (only meaningful when no candidate was found)
  resolve(trust)     apply claims whose subject (a state-reference expression) matches a decision point: each option is
                     executed on a distinguishing boundary row and kept iff its effect matches the claim; conflicting claims
                     are decided by `trust` = none | newest | learned (evidence-memory weights over claim provenance)
  ask(target)        ONE bounded clarification per project: a 1-row distinguishing input for the chosen decision point; the
                     stakeholder returns the intended output for that row, or 'undetermined'; options that disagree with the
                     answer are refuted (a counterexample)
  submit_or_abstain  submit the rebound combination if every decision point is resolved, else abstain (with the reason)
Policy language (typed, executable): a program is a list of statements
  ["read", src] ["read_all"] ["search"] ["search_more"] ["resolve", trust] ["ask", target] ["submit_or_abstain"]
  ["if", cond, [then], [else]] ["repeat", n, [body]] ["call", procedure_name]
  conditions: has_candidate unresolved multi_unresolved conflict undecided asked claims_seen trust_memory, ["not", cond]
  ask targets: first last unclaimed conflicted lowconf
No statement can see family ids, generator internals, hidden tests or the reference program."""
from __future__ import annotations

import copy
import itertools
import json
import time
from pathlib import Path

from nexus.de_phase4 import accept as AC, ir, learner as L, lineage as LG, ops as O, world as W
from nexus.de_phase5 import world5 as W5

BUDGET = {"sqlite": 2.5, "spark": 10.0}
M_SEARCH = [[n, dict(p, mode="abstain") if n == "ambiguity" else dict(p)] for n, p in copy.deepcopy(LG.M0)]
QUESTION_COST_S = 2.0                     # pre-declared cost of one clarification, in cost-seconds (reported separately too)
MAX_STEPS = 40


# ------------------------------------------------------------------ evidence: claims with provenance
def read_claims(ws, source):
    p = Path(ws) / source
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    claims = d.get("requirements", []) if source == "contract.json" else d.get("claims", [])
    return [dict(c, provenance=dict(file=source, claim_id=c.get("id"))) for c in claims if "state_ref" in c.get("subject", {})]


def claim_features(c, others):
    f = {f"status:{c.get('status')}", f"source:{c['provenance']['file']}"}
    if others:
        f.add("newer_version" if c.get("version", 0) > max(o.get("version", 0) for o in others) else "older_version")
        f.add("newer_date" if c.get("updated", "") > max(o.get("updated", "") for o in others) else "older_date")
    return f


# ------------------------------------------------------------------ decision points from the repair search
def _parse_filter(prm):
    col, cmp, val = prm.split(" ", 2)
    return col, cmp, json.loads(val)


def _option_key(inv, spec, rows):
    try:
        res = inv.exec(spec, rows, inv.sq)
    except W.RunError:
        return "error"
    return [W.table_key(res["clean"], inv.contract["output_cols"]),
            sorted(str(r["id"]) for r in res["rejects"]) if res["rejects"] is not None else None]


def distinguishing_row(inv, dp):
    """A single input row on which the decision point's options produce different outputs (or None)."""
    cands = []
    targets = [(dp["col"], dp["ref"])] if dp.get("ref") is not None else \
        [(c, v) for c, _, v in (_parse_filter(o) for o in dp["options"] if o and dp["op"] == "filter_file")]
    for col, ref in targets:                           # rows at every option's own threshold, every visible row as template
        t = ir.ev(ref, {}, inv.state)
        for j, r in enumerate(inv.rows):
            q = dict(r)
            for c in AC._fresh_cols(inv):
                q[c] = f"PQ{j}"
            q[col] = str(t)
            cands.append(q)
    cands += AC.stress_rows(inv, dp["specs"][0])
    for q in cands[:120]:
        keys = [json.dumps(_option_key(inv, s, [q]), default=str) for s in dp["specs"]]
        if len(set(keys)) > 1:
            return q, keys
    return None, None


def decision_points(inv, path):
    """Unresolved disagreements around the candidate path, grouped by (position, operator)."""
    x = O.replay(inv.legacy, path, inv)
    eng = inv.sq if inv.sq is not inv.rt else None
    groups = {}
    for a in AC.alternatives(inv, path):
        if not inv.visible_ok(a["spec"], engine=eng) or AC.invariants(inv, a["spec"], eng):
            continue
        batches = [b for b in (AC.boundary_rows(inv, [x, a["spec"]]), AC.stress_rows(inv, x)) if b]
        try:
            same = [_option_key(inv, x, b) for b in batches] == [_option_key(inv, a["spec"], b) for b in batches]
        except W.RunError:
            same = False
        if same:                                      # Phase 5 closure extension: single-row probes from every template
            row, _ = distinguishing_row(inv, dict(op=a["op"], options=[path[a["pos"]][1] if a["pos"] < len(path) else None, a["prm_y"]],
                                                  specs=[x, a["spec"]], ref=None))
            if row is None:
                continue
        groups.setdefault((a["pos"], a["op"]), []).append(a)
    dps = []
    for (pos, op), alts in sorted(groups.items()):
        prm_x = path[pos][1] if pos < len(path) else None
        options = [prm_x] + [a["prm_y"] for a in alts]
        dp = dict(pos=pos, op=op, options=options, resolved=None, via=None, conflict=False, undecided=False, claims=[])
        if op == "filter_file":
            parsed = [_parse_filter(o) for o in options if o]
            refs = {json.dumps(v) for _, _, v in parsed}
            cols = {c for c, _, _ in parsed}
            if len(refs) == 1 and len(cols) == 1:
                dp["ref"], dp["col"] = json.loads(refs.pop()), cols.pop()
        dps.append(dp)
    for dp in dps:                                    # option specs: the path with this decision point's option
        dp["specs"] = [spec_for(inv, path, [(dp, o)]) for o in dp["options"]]
    return x, dps


def spec_for(inv, path, choices):
    """Rebind: replay the repair path on THIS project's legacy pipeline with the chosen option at each decision point."""
    p = list(path)
    tail = []
    for dp, o in choices:
        if dp["pos"] < len(p):
            p[dp["pos"]] = (dp["op"], o) if o is not None else None
        elif o is not None:
            tail.append((dp["op"], o))
    return O.replay(inv.legacy, [e for e in p if e is not None] + tail, inv)


# ------------------------------------------------------------------ evidence memory (learned from source experience)
def empty_evidence():
    return dict(claim_outcomes=[], counterexamples=[], actions=[], trust={})


def trust_weights(em):
    agg = {}
    for r in em["claim_outcomes"]:
        for f in r["features"]:
            a = agg.setdefault(f, [0, 0])
            a[0 if r["agreed"] else 1] += 1
    return {f: round((a - d) / (a + d + 3), 4) for f, (a, d) in agg.items()}   # ~3 consistent conflicts reach the 1.0 margin


def record_truth(em, project, dp, correct_option, how):
    """Once a decision point's correct option is known in a SOURCE project (hidden verification of a submission, or a
    stakeholder answer), record every claim's agreement (provenance + scope: this project only) and counterexamples."""
    for c in dp["claims"]:
        others = [o for o in dp["claims"] if o is not c]
        em["claim_outcomes"].append(dict(project=project["pid"], claim=c["provenance"], features=sorted(claim_features(c, others)),
                                         effect=c["effect_at_boundary"],
                                         conflict=bool(others) and len({o["effect_at_boundary"] for o in dp["claims"]}) > 1,
                                         agreed=c.get("_option") == correct_option, how=how,
                                         scope="claims about the boundary of a state reference, in this project only"))
    for o in dp["options"]:
        if o != correct_option:
            em["counterexamples"].append(dict(project=project["pid"], refutes=f"{dp['op']}({o}) at this decision point", how=how,
                                              scope="this project only (a sampled counterexample refutes a candidate; it does not "
                                                    "generalise the requirement)"))
    em["trust"] = trust_weights(em)


# ------------------------------------------------------------------ investigation state + interpreter
class State:
    def __init__(self, project, backend, em, mem):
        self.p, self.b, self.em, self.mem = project, backend, em, mem
        self.claims, self.read_sources = [], set()
        self.has_candidate, self.path, self.dps = None, None, []
        self.asked, self.decision, self.trace, self.steps, self.executed = False, None, [], 0, set()
        self.cost = dict(sqlite_runs=0, spark_runs=0, wall_s=0.0, questions=0, reads=0, searches=0)

    def unresolved(self):
        return [d for d in self.dps if d["resolved"] is None]

    def log(self, action, obs, decision=None):
        self.trace.append(dict(action=action, obs=obs, decision=decision))


COND_NAMES = ("has_candidate", "unresolved", "multi_unresolved", "conflict", "undecided", "asked", "claims_seen", "trust_memory")


def cond(st, c):
    if isinstance(c, list) and c[0] == "not":
        return not cond(st, c[1])
    return {"has_candidate": bool(st.has_candidate), "unresolved": bool(st.unresolved()), "multi_unresolved": len(st.unresolved()) > 1,
            "conflict": any(d["conflict"] and d["resolved"] is None for d in st.dps), "undecided": any(d["undecided"] for d in st.dps),
            "asked": st.asked, "claims_seen": bool(st.claims), "trust_memory": bool(st.em.get("trust"))}[c]


def run_policy(prog, st, library):
    for s in prog:
        if st.decision is not None or st.steps >= MAX_STEPS:
            return
        st.steps += 1
        st.executed.add(id(s))                        # execution coverage of program statements
        op = s[0]
        if op == "if":
            run_policy(s[2] if cond(st, s[1]) else (s[3] if len(s) > 3 else []), st, library)
        elif op == "repeat":
            for _ in range(min(int(s[1]), 3)):
                before = (len(st.unresolved()), st.asked, len(st.claims))
                run_policy(s[2], st, library)
                if (len(st.unresolved()), st.asked, len(st.claims)) == before:
                    break
        elif op == "call":
            st.log("call", dict(procedure=s[1], conditions_at_entry={c: cond(st, c) for c in COND_NAMES}))
            run_policy(library[s[1]]["body"], st, library)
        else:
            ACTIONS[op](st, *s[1:])
    if st.decision is None and prog is st.root:
        a_submit(st)


def a_read(st, src):
    if src in st.read_sources:
        return
    st.read_sources.add(src)
    st.cost["reads"] += 1
    new = st.b.read(st.p, src)
    st.claims += new
    st.log("read", dict(source=src, claims=[c["provenance"]["claim_id"] for c in new]))
    _attach_claims(st)


def a_read_all(st):
    for s in W5.SOURCES:
        a_read(st, s)


def _attach_claims(st):
    for dp in st.dps:
        if dp.get("ref") is None:
            continue
        dp["claims"] = [c for c in st.claims if c["subject"]["state_ref"] == dp["ref"]]


def a_search(st, more=False):
    if st.has_candidate is not None and not (more and not st.has_candidate):
        return
    r = st.b.search(st.p, st.mem, more=more)
    for k in ("sqlite_runs", "spark_runs", "wall_s"):
        st.cost[k] += r["cost"][k]
    st.cost["searches"] += 1
    st.has_candidate, st.path, st.dps = r["has_candidate"], r["path"], copy.deepcopy(r["dps"])
    st.log("search_more" if more else "search", dict(outcome=r["outcome"], edits=r["path"], shared=r.get("shared", False), decision_points=[
        dict(pos=d["pos"], op=d["op"], options=d["options"], ref=d.get("ref"), column=d.get("col")) for d in st.dps]))
    _attach_claims(st)


def a_search_more(st):
    a_search(st, more=True)


def _effects(st, dp):
    """Per option: is the distinguishing boundary row kept? (pre-computed by the backend by execution)."""
    return dp.get("boundary_effect")


def a_resolve(st, trust):
    w = st.em.get("trust", {})
    if trust == "stored_answer":                       # ablation only (not in the proposal palette): reuse the ANSWER
        tally = {}
        for r in st.em["claim_outcomes"]:
            eff = r["effect"] if r["agreed"] else ("kept" if r["effect"] == "excluded" else "excluded")
            tally[eff] = tally.get(eff, 0) + 1
        if tally:
            best = max(tally, key=tally.get)
            for dp in st.unresolved():
                if dp.get("boundary_effect"):
                    dp["resolved"] = next((o for o, e in zip(dp["options"], dp["boundary_effect"]) if e == best), None)
                    dp["via"] = "stored_answer" if dp["resolved"] is not None else None
            st.log("resolve", dict(trust="stored_answer", tally=tally))
        return
    for dp in st.unresolved():
        eff = _effects(st, dp)
        if not dp["claims"] or eff is None:
            continue
        for c in dp["claims"]:
            c["_option"] = next((o for o, e in zip(dp["options"], eff) if e == c["effect_at_boundary"]), None)
        effects = {c["effect_at_boundary"] for c in dp["claims"]}
        if len(effects) == 1:
            pick = dp["claims"][0]
            via = "claim"
        else:
            dp["conflict"] = True
            if trust == "newest":
                pick, via = max(dp["claims"], key=lambda c: (c.get("version", 0), c.get("updated", ""))), "trust:newest"
            elif trust == "learned" and w:
                sc = sorted(((sum(w.get(f, 0.0) for f in claim_features(c, [o for o in dp["claims"] if o is not c])), i)
                             for i, c in enumerate(dp["claims"])), reverse=True)
                if sc[0][0] - sc[1][0] < 1.0:
                    st.log("resolve", dict(pos=dp["pos"], conflict=True, trust="learned", margin=round(sc[0][0] - sc[1][0], 3)),
                           "unresolved: learned trust margin < 1.0")
                    continue
                pick, via = dp["claims"][sc[0][1]], "trust:learned"
            else:
                st.log("resolve", dict(pos=dp["pos"], conflict=True, trust=trust), "unresolved: conflicting claims")
                continue
        if pick.get("_option") is None:
            continue
        dp["resolved"], dp["via"] = pick["_option"], via
        st.log("resolve", dict(pos=dp["pos"], claims=[c["provenance"] for c in dp["claims"]], via=via, trust_weights_used=via == "trust:learned"),
               f"option {pick['_option']}")


def a_ask(st, target):
    if st.asked or not st.unresolved():
        return
    un = st.unresolved()
    w = st.em.get("trust", {})
    pick = {"first": lambda: un[0], "last": lambda: un[-1],
            "unclaimed": lambda: next((d for d in un if not d["claims"]), un[0]),
            "conflicted": lambda: next((d for d in un if d["conflict"] or len({c["effect_at_boundary"] for c in d["claims"]}) > 1), un[0]),
            "lowconf": lambda: min(un, key=lambda d: max([sum(w.get(f, 0) for f in claim_features(c, [o for o in d["claims"] if o is not c]))
                                                          for c in d["claims"]] or [-9]))}[target]()
    st.asked = True
    st.cost["questions"] += 1
    ans = st.b.ask(st.p, pick)
    st.log("ask", dict(pos=pick["pos"], target=target, probe=ans.get("probe"), answer=ans["answer"]))
    if ans["answer"] == "undetermined":
        pick["undecided"] = True
    elif ans["answer"] == "output":
        ok = [o for o, k in zip(pick["options"], ans["option_keys"]) if k == ans["key"]]
        if len(ok) == 1:
            pick["resolved"], pick["via"] = ok[0], "clarification"
            st.log("revise", dict(pos=pick["pos"], refuted=[o for o in pick["options"] if o != ok[0]]), f"option {ok[0]}")


def a_submit(st):
    if st.decision is not None:
        return
    if not st.has_candidate:
        st.decision = dict(kind="abstain", reason="no repair candidate")
    elif any(d["undecided"] for d in st.dps):
        st.decision = dict(kind="abstain", reason="requirement undetermined by the stakeholder")
    elif st.unresolved():
        st.decision = dict(kind="abstain", reason=f"{len(st.unresolved())} unresolved decision point(s)")
    else:
        st.decision = dict(kind="submit", choices={d["pos"]: d["resolved"] for d in st.dps})
    st.log("decide", None, st.decision)


ACTIONS = {"read": a_read, "read_all": a_read_all, "search": a_search, "search_more": a_search_more, "resolve": a_resolve,
           "ask": a_ask, "submit_or_abstain": a_submit}

# the strong FIXED policy (human-written; may read every contract, use evidence memory, probe and ask once)
F0 = [["read_all"], ["search"], ["if", ["not", "has_candidate"], [["search_more"]]], ["resolve", "learned"],
      ["if", "unresolved", [["ask", "first"]]], ["submit_or_abstain"]]


def investigate(project, backend, em, mem, prog, library=None):
    st = State(project, backend, em, mem)
    st.root = prog
    run_policy(prog, st, library or {})
    return st


# ------------------------------------------------------------------ backends
class Live:
    """Executes actions on the real engines; search results are shared between arms with an identical repair memory
    (the same deterministic inputs; reported as shared)."""

    def __init__(self, rts=None):
        self.rts = rts or {"sqlite": W.SQLiteCode(), "spark": W.SparkCode()}
        self.search_cache, self.log = {}, []

    def read(self, project, src):
        return read_claims(project["ws"], src)

    def search(self, project, mem, more=False):
        key = (project["pid"], mem.get("_digest", "empty"), more)
        if key in self.search_cache:
            r = copy.deepcopy(self.search_cache[key])
            r["shared"] = True                         # the arm is attributed the search's measured cost; the ledger
            return r                                   # charged the one real execution
        rt = self.rts[project["runtime"]]
        t0 = time.time()
        rec = L.solve(project, copy.deepcopy(mem.get("de", L.empty_de())), rt, budget_s=BUDGET[project["runtime"]] * (2 if more else 1),
                      M=M_SEARCH, explore=False)
        out = dict(outcome=rec["outcome"], has_candidate=rec["outcome"] in ("submitted", "abstain_ambiguous"), path=rec["edits"] or [], dps=[])
        if out["has_candidate"] and rec["edits"]:      # also re-checks a Phase 4 'unique' verdict with the Phase 5 extension
            inv = L.Investigation(project, rt)
            _, dps = decision_points(inv, [tuple(e) for e in rec["edits"]])
            for dp in dps:
                row, _ = distinguishing_row(inv, dp)
                dp["probe"] = row
                dp["boundary_effect"] = [("kept" if (k := _option_key(inv, s, [row])) != "error" and k[0] else "excluded")
                                         for s in dp["specs"]] if row is not None and dp.get("ref") is not None else None
                dp["option_keys"] = [json.dumps(_option_key(inv, s, [row]), default=str) for s in dp["specs"]] if row is not None else None
            rb = inv.runs
            out["dps"] = [{k: v for k, v in d.items()} for d in dps]
        else:
            rb = {}
        sq = rec["runs_by"].get("sqlite_screen", 0) + (rec["runs_by"].get("engine", 0) if project["runtime"] == "sqlite" else 0) + \
            rb.get("sqlite_screen", 0) + (rb.get("engine", 0) if project["runtime"] == "sqlite" else 0)
        sp = (rec["runs_by"].get("engine", 0) + rb.get("engine", 0)) if project["runtime"] == "spark" else 0
        out["cost"] = dict(sqlite_runs=sq, spark_runs=sp, wall_s=round(time.time() - t0, 3))
        self.search_cache[key] = copy.deepcopy(out)
        out["_rec"] = rec                              # for source-time repair learning only (never copied to another arm)
        return out

    def ask(self, project, dp):
        if dp.get("probe") is None:
            return dict(answer="no_probe", probe=None)
        a = W5.stakeholder_answer(project, [dp["probe"]])
        out = dict(answer=a["answer"], probe=dp["probe"])
        if a["answer"] == "output":
            out["key"], out["option_keys"] = json.dumps(a["output"], default=str), dp["option_keys"]
        return out


def outcome(project, st, rt=None):
    """Score a decision: verified / wrong / justified abstention (the evaluator executes the submitted FILE)."""
    from nexus.de_phase4 import adapter as AD
    d = st.decision
    if d["kind"] != "submit":
        return dict(decision="abstain", reason=d["reason"], verified=False, wrong=False)
    inv = L.Investigation(project, (rt or W.RUNTIMES[project["runtime"]]()))
    spec = spec_for(inv, st.path, [(dp, d["choices"][dp["pos"]]) for dp in st.dps])
    path, _ = AD.write_patch(project["ws"], spec, project["lang"], out_dir="submission5")
    ev = W5.evaluate5(project, path.read_text(), rt)
    return dict(decision="submit", verified=ev["ok"], wrong=not ev["ok"], hidden=ev["fails"], spec=spec)
