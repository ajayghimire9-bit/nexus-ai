"""Phase 6 investigation procedures: a typed executable language, its interpreter, and AUTOMATIC procedure composition
(NOT LOCKED; the Phase 5 design - investigate.py / policy_learn.py - carried to multi-stage, multi-engine pipelines).

Statements
  ["read", src] ["read_all"]                    requirement claims with provenance
  ["search", mode, skills]                      mode whole | decompose (stage-wise); skills on | off (invented skills, chained)
  ["resolve", trust]                            trust none | calibrated (trust6: provenance-only, abstention-aware)
  ["ask", target]                               ONE clarification (1 probe row): first | unclaimed | conflicted
  ["submit_or_abstain"]   ["if", cond, [..], [..]]   ["repeat", n, [..]]   ["call", name]
  conditions: has_candidate unresolved multi_unresolved conflict undecided asked claims_seen trust_memory, ["not", c]
Human engineering: the primitives, this interpreter, F0. Learned: memory (pi weights, invented skills, calibrated trust)
and the COMPOSITION of procedures (learn_policy, from SEED), evaluated by replay of recorded source experience.
Prescreening (SQLite before DuckDB / Spark) is a fixed part of `search` in every arm (disclosed)."""
from __future__ import annotations

import copy
import itertools
import json
import time

from nexus.de_phase5 import admission5 as A5
from nexus.de_phase6 import ir6, pipeline6 as P6, skills6 as SK, trust6 as T6, world6 as W6

QUESTION_COST_S = 2.0
MAX_STEPS = 40
SOURCES = W6.SOURCES
F0 = [["read_all"], ["search", "whole", "on"], ["resolve", "calibrated"], ["if", "unresolved", [["ask", "first"]]], ["submit_or_abstain"]]
SEED = [["search", "whole", "off"], ["submit_or_abstain"]]
COND_NAMES = ("has_candidate", "unresolved", "multi_unresolved", "conflict", "undecided", "asked", "claims_seen", "trust_memory")
TYPES = {"read": ((), ("claims",)), "read_all": ((), ("claims",)), "search": ((), ("hypotheses",)), "resolve": (("claims", "hypotheses"), ("resolutions",)),
         "ask": (("hypotheses",), ("resolutions",)), "submit_or_abstain": (("resolutions",), ("decision",))}


def palette():
    return ([["read", s] for s in SOURCES] + [["read_all"]] + [["search", m, k] for m in ("whole", "decompose") for k in ("on", "off")] +
            [["resolve", t] for t in ("none", "calibrated")] + [["ask", t] for t in ("first", "unclaimed", "conflicted")] + [["submit_or_abstain"]])


def read_claims(ws, source):
    from pathlib import Path
    p = Path(ws) / source
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    cl = d.get("requirements", []) if source == "contract.json" else d.get("claims", [])
    return [dict(c, provenance=dict(file=source, claim_id=c.get("id"))) for c in cl if "state_ref" in c.get("subject", {})]


class State:
    def __init__(self, project, backend, mem):
        self.p, self.b, self.mem = project, backend, mem
        self.claims, self.read_sources = [], set()
        self.has_candidate, self.cand, self.dps = None, None, []
        self.asked, self.decision, self.trace, self.steps, self.executed = False, None, [], 0, set()
        self.cost = dict(sqlite_runs=0, duckdb_runs=0, spark_runs=0, wall_s=0.0, questions=0, reads=0, searches=0)

    def unresolved(self):
        return [d for d in self.dps if d["resolved"] is None]

    def log(self, action, obs, decision=None):
        self.trace.append(dict(action=action, obs=obs, decision=decision))


def cond(st, c):
    if isinstance(c, list) and c[0] == "not":
        return not cond(st, c[1])
    return {"has_candidate": bool(st.has_candidate), "unresolved": bool(st.unresolved()), "multi_unresolved": len(st.unresolved()) > 1,
            "conflict": any(d["conflict"] and d["resolved"] is None for d in st.dps), "undecided": any(d["undecided"] for d in st.dps),
            "asked": st.asked, "claims_seen": bool(st.claims), "trust_memory": bool(st.mem.get("trust", {}).get("records"))}[c]


def run(prog, st, library, root=True):
    for s in prog:
        if st.decision is not None or st.steps >= MAX_STEPS:
            break
        st.steps += 1
        st.executed.add(id(s))
        op = s[0]
        if op == "if":
            run(s[2] if cond(st, s[1]) else (s[3] if len(s) > 3 else []), st, library, False)
        elif op == "repeat":
            for _ in range(min(int(s[1]), 3)):
                before = (len(st.unresolved()), st.asked, len(st.claims))
                run(s[2], st, library, False)
                if (len(st.unresolved()), st.asked, len(st.claims)) == before:
                    break
        elif op == "call":
            st.log("call", dict(procedure=s[1], conditions_at_entry={c: cond(st, c) for c in COND_NAMES}))
            run(library[s[1]]["body"], st, library, False)
        else:
            ACTIONS[op](st, *s[1:])
    if root and st.decision is None:
        a_submit(st)


def a_read(st, src):
    if src in st.read_sources:
        return
    st.read_sources.add(src)
    st.cost["reads"] += 1
    new = st.b.read(st.p, src)
    st.claims += new
    st.log("read", dict(source=src, claims=[c["provenance"]["claim_id"] for c in new]))
    _attach(st)


def a_read_all(st):
    for s in SOURCES:
        a_read(st, s)


def _attach(st):
    for dp in st.dps:
        if dp.get("ref") is not None:
            dp["claims"] = [c for c in st.claims if c["subject"]["state_ref"] == dp["ref"]]


def a_search(st, mode, skills):
    if st.has_candidate:
        return
    r = st.b.search(st.p, st.mem, mode, skills)
    for k in ("sqlite_runs", "duckdb_runs", "spark_runs", "wall_s"):
        st.cost[k] += r["cost"].get(k, 0)
    st.cost["searches"] += 1
    st.has_candidate = r["has_candidate"]
    st.cand = r
    st.dps = copy.deepcopy(r["dps"])
    st.log("search", dict(mode=mode, skills=skills, outcome=r["outcome"], edits=r["path"], shared=r.get("shared", False),
                          decision_points=[dict(stage=d["stage"], op=d["op"], options=d["options"], ref=d.get("ref"), column=d.get("col")) for d in st.dps]))
    _attach(st)


def a_resolve(st, trust):
    tm = st.mem.get("trust", T6.empty())
    for dp in st.unresolved():
        if not dp["claims"] or not dp.get("effects"):
            continue
        effects = {c["effect_at_boundary"] for c in dp["claims"]}
        if len(effects) > 1:
            dp["conflict"] = True
            if trust != "calibrated":
                st.log("resolve", dict(stage=dp["stage"], conflict=True, trust=trust), "unresolved: conflicting claims")
                continue
            pick, why = T6.decide(tm, dp["claims"], margin=st.mem.get("M", {}).get("trust_margin", 1.0),
                                  min_support=st.mem.get("M", {}).get("trust_support", 2))
            if pick is None:
                st.log("resolve", dict(stage=dp["stage"], conflict=True, trust="calibrated"), f"unresolved: {why}")
                continue
            via = "trust:calibrated"
        else:
            pick, why, via = dp["claims"][0], "all claims agree", "claim"
        opt = next((o for o, e in zip(dp["options"], dp["effects"]) if e == pick["effect_at_boundary"]), None)
        if opt is None:
            continue
        dp["resolved"], dp["via"] = opt, via
        st.log("resolve", dict(stage=dp["stage"], claims=[c["provenance"] for c in dp["claims"]], via=via, why=why), f"option {opt}")


def a_ask(st, target):
    if st.asked or not st.unresolved():
        return
    un = st.unresolved()
    pick = {"first": lambda: un[0], "unclaimed": lambda: next((d for d in un if not d["claims"]), un[0]),
            "conflicted": lambda: next((d for d in un if d["conflict"] or len({c["effect_at_boundary"] for c in d["claims"]}) > 1), un[0])}[target]()
    st.asked = True
    st.cost["questions"] += 1
    ans = st.b.ask(st.p, pick)
    st.log("ask", dict(stage=pick["stage"], target=target, probe=pick.get("probe"), answer=ans["answer"]))
    if ans["answer"] == "undetermined":
        pick["undecided"] = True
    elif ans["answer"] == "output":
        ok = [o for o, k in zip(pick["options"], pick["option_keys"]) if k == ans["key"]]
        if len(ok) == 1:
            pick["resolved"], pick["via"] = ok[0], "clarification"
            st.log("revise", dict(stage=pick["stage"], refuted=[o for o in pick["options"] if o != ok[0]]), f"option {ok[0]}")


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
        st.decision = dict(kind="submit", choices={f"{d['stage']}:{d['pos']}": d["resolved"] for d in st.dps})
    st.log("decide", None, st.decision)


ACTIONS = {"read": a_read, "read_all": a_read_all, "search": a_search, "resolve": a_resolve, "ask": a_ask, "submit_or_abstain": a_submit}


def investigate(project, backend, mem, prog, library=None):
    st = State(project, backend, mem)
    run(prog, st, library or {})
    return st


def chosen_specs(st):
    """Rebind the decision: replay the repair path on THIS project with each decision point's chosen option."""
    c = st.cand
    if not st.dps:
        return c["specs"]
    inv = P6.Inv6(st.p)
    path = [tuple(e) for e in c["path"]]
    tail = []
    for dp in st.dps:
        o = st.decision["choices"][f"{dp['stage']}:{dp['pos']}"]
        if dp["pos"] < len(path):
            path[dp["pos"]] = (dp["stage"], dp["op"], o) if o is not None else None
        elif o is not None:
            tail.append((dp["stage"], dp["op"], o))
    return P6.replay(inv, [e for e in path if e is not None] + tail)


# ------------------------------------------------------------------ backends
class Live:
    def __init__(self, budget):
        self.budget, self.cache = budget, {}
        self.proposer = SK.SkillProposer()

    def read(self, project, src):
        return read_claims(project["ws"], src)

    def search(self, project, mem, mode, skills):
        key = (project["pid"], mem.get("_digest", "empty"), mode, skills)
        if key in self.cache:
            r = copy.deepcopy(self.cache[key])
            r["shared"] = True
            return r
        t0 = time.time()
        try:
            inv = P6.Inv6(project)
        except Exception as e:                           # noqa: BLE001  (Unsupported legacy)
            out = dict(outcome="unsupported", has_candidate=False, path=None, specs=None, dps=[], cost=dict(wall_s=0.0), note=str(e)[:80])
            self.cache[key] = out
            return copy.deepcopy(out)
        budget = self.budget(project)
        r = P6.search(inv, mem.get("de", {}), budget, mode=mode, use_skills=skills == "on", skills_mod=self.proposer,
                      stall_frac=mem.get("M", {}).get("stall_frac", 0.25))
        out = dict(outcome=r["outcome"], has_candidate=r["outcome"] in ("submitted", "ambiguous"), path=r["path"], specs=r["specs"], dps=r["dps"],
                   cost=dict(sqlite_runs=inv.runs["sqlite"], duckdb_runs=inv.runs["duckdb"], spark_runs=inv.runs["spark"], wall_s=round(time.time() - t0, 3)),
                   partials=r["partials"][:20], refutations=r["refutations"][:40], start_features=r["start_features"])
        out["_inv"] = inv
        self.cache[key] = {k: v for k, v in out.items() if k != "_inv"}
        return out

    def ask(self, project, dp):
        if dp.get("probe") is None:
            return dict(answer="no_probe")
        a = W6.stakeholder_answer(project, [dp["probe"]])
        out = dict(answer=a["answer"])
        if a["answer"] == "output":
            out["key"] = json.dumps(a["output"], default=str)
            # option keys were computed on the prescreen engine with the pipeline's key format: compare like with like
            out["key"] = _norm_key(out["key"])
            dp["option_keys"] = [_norm_key(k) for k in dp["option_keys"]]
        return out


def _norm_key(k):
    try:
        v = json.loads(k)
        return json.dumps([[list(map(lambda x: x if not isinstance(x, float) else round(x, 6), r)) for r in v[0]], v[1] or []], default=str)
    except Exception:                                    # noqa: BLE001
        return k


def outcome(project, st):
    d = st.decision
    if d["kind"] != "submit":
        return dict(decision="abstain", reason=d["reason"], verified=False, wrong=False)
    specs = chosen_specs(st)
    files = [ir6.lower(s, stg["target_lang"]) for s, stg in zip(specs, project["stages"])]
    ev = W6.evaluate6(project, files)
    return dict(decision="submit", verified=ev["ok"], wrong=not ev["ok"], hidden=ev["fails"], files=files)


# ------------------------------------------------------------------ cached replay + automatic composition (Phase 5 design)
class Cached:
    def __init__(self, caches):
        self.c = caches

    def read(self, project, src):
        return copy.deepcopy(self.c[project["pid"]]["reads"][src])

    def search(self, project, mem, mode, skills):
        return copy.deepcopy(self.c[project["pid"]]["search"][f"{mode}|{skills}"])

    def ask(self, project, dp):
        a = copy.deepcopy(self.c[project["pid"]]["answers"].get(f"{mode_key(dp)}", dict(answer="no_probe")))
        if a.get("answer") == "output":
            dp["option_keys"] = a["option_keys"]
        return a


def mode_key(dp):
    return f"{dp['stage']}:{dp['pos']}:{dp['op']}"


def build_entry(project, live, mem, configs=(("whole", "off"), ("whole", "on"), ("decompose", "off"), ("decompose", "on"))):
    e = dict(pid=project["pid"], reads={s: live.read(project, s) for s in SOURCES}, search={}, answers={}, combos={})
    single = len(project["stages"]) == 1
    no_sk = not mem.get("de", {}).get("skills")
    for mode, sk in configs:
        same = (("whole" if single else mode), ("off" if no_sk else sk))
        if same != (mode, sk) and f"{same[0]}|{same[1]}" in e["search"]:     # identical inputs: reuse the executed search
            e["search"][f"{mode}|{sk}"] = dict(e["search"][f"{same[0]}|{same[1]}"], reused_from=f"{same[0]}|{same[1]}")
            for k_, v_ in list(e["combos"].items()):
                if k_.startswith(f"{same[0]}|{same[1]}|"):
                    e["combos"][f"{mode}|{sk}|" + k_.split("|", 2)[2]] = v_
            continue
        r = live.search(project, mem, mode, sk)
        e["search"][f"{mode}|{sk}"] = {k: v for k, v in r.items() if k != "_inv"}
        for dp in r["dps"]:
            if mode_key(dp) not in e["answers"]:
                a = live.ask(project, dp)
                a["option_keys"] = dp["option_keys"]
                e["answers"][mode_key(dp)] = a
        if r["has_candidate"]:
            for opts in itertools.product(*[dp["options"] for dp in r["dps"]]) if r["dps"] else [()]:
                st = State(project, live, mem)
                st.has_candidate, st.cand, st.dps = True, r, copy.deepcopy(r["dps"])
                st.decision = dict(kind="submit", choices={f"{dp['stage']}:{dp['pos']}": o for dp, o in zip(r["dps"], opts)})
                o = outcome(project, st)
                e["combos"][f"{mode}|{sk}|" + json.dumps([str(x) for x in opts])] = dict(verified=o["verified"], wrong=o["wrong"])
    e["any_verifiable"] = any(v["verified"] for v in e["combos"].values())
    return e


def replay_row(entry, st):
    d = st.decision
    if d["kind"] == "submit":
        cfg = next((t["obs"] for t in st.trace if t["action"] == "search"), {})
        k = f"{cfg.get('mode')}|{cfg.get('skills')}|" + json.dumps([str(d["choices"][f"{dp['stage']}:{dp['pos']}"]) for dp in st.dps])
        v = entry["combos"].get(k, dict(verified=False, wrong=True))
        correct, completed, wrong = v["verified"], v["verified"], v["wrong"]
    else:
        correct, completed, wrong = not entry["any_verifiable"], False, False
    return dict(correct=correct, completed=completed, wrong=wrong, cost=dict(st.cost, questions=st.cost["questions"]), decision=d["kind"],
                questions=st.cost["questions"], executed=st.executed)


def score(prog, library, projects, caches, mem):
    b = Cached(caches)
    rows = {}
    for p in projects:
        st = investigate(p, b, mem, prog, library)
        rows[p["pid"]] = replay_row(caches[p["pid"]], st)
    return rows


def _flatten(prog, path=()):
    for i, s in enumerate(prog):
        yield path + (i,), s
        if s[0] == "if":
            yield from _flatten(s[2], path + (i, 2))


def inline_all(prog, library):
    out = []
    for s in prog:
        if s[0] == "call" and s[1] in library:
            out += inline_all(copy.deepcopy(library[s[1]]["body"]), library)
        elif s[0] == "if":
            out.append(["if", s[1], inline_all(s[2], library)] + ([inline_all(s[3], library)] if len(s) > 3 else []))
        else:
            out.append(copy.deepcopy(s))
    return out


def proposals(prog, library, rng, n_sampled=16, typed_pairs=True):
    flat = inline_all(prog, library)
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
    for _ in range(n_sampled):                           # sampled delete / swap / parameter / wrap / call edits
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
        elif et == "wrap" and new[i][0] != "if":
            c = rng.choice(list(COND_NAMES) + [["not", x] for x in COND_NAMES])
            new[i] = ["if", c, [new[i]]]
            out.append(("wrap", new, [new[i]], f"wrap {i} in if {c}"))
        elif et == "call" and library:
            name = rng.choice(sorted(library))
            stmt = ["call", name]
            new.insert(i, stmt)
            out.append(("call", new, [stmt], f"insert call {name} at {i}"))
    return out


def learn_policy(start, projects, caches, mem, rng, cycles=4, typed_pairs=True, history=None):
    prog, library, log, n = copy.deepcopy(start), {}, [], 0
    base = score(prog, library, projects, caches, mem)
    for cyc in range(cycles):
        best = None
        for et, new, block, desc in proposals(prog, library, rng, typed_pairs=typed_pairs):
            rows = score(new, library, projects, caches, mem)
            ok, why = A5.admit(base, rows, min_saving=0.1, q_cost=QUESTION_COST_S)
            ran = sum(1 for r in rows.values() if block and id(block[0]) in r["executed"])
            log.append(dict(cycle=cyc, type=et, edit=desc, admitted=ok, executed_in_projects=ran, correct=sum(r["correct"] for r in rows.values()),
                            wrong=sum(r["wrong"] for r in rows.values())))
            if ok:
                key = (sum(r["correct"] for r in rows.values()), -sum(A5.cost_s(r, QUESTION_COST_S) for r in rows.values()))
                if best is None or key > best[0]:
                    best = (key, new, block, desc, rows, why)
        if best is None:
            break
        _, new, block, desc, rows, why = best
        if len(block) >= 2 or (block and block[0][0] in ("search", "resolve", "ask")):
            n += 1
            name = f"proc{n}"
            helped = [p for p in rows if rows[p]["correct"] and not base[p]["correct"]] or \
                     [p for p in rows if rows[p]["completed"] and A5.cost_s(rows[p], 2) < A5.cost_s(base[p], 2)]
            library[name] = dict(body=copy.deepcopy(block), interface="InvestigationState -> InvestigationState", helped=helped,
                                 provenance=dict(cycle=cyc, edit=desc, validation=sorted(rows), source_history=history or []), utility=why)
            first = block[0]
            for path_, s_ in list(_flatten(new)):
                if any(s_ is b_ for b_ in block[1:]):
                    c_ = new
                    for k_ in path_[:-1]:
                        c_ = c_[k_]
                    c_.pop(path_[-1])
                    break
            first[:] = ["call", name]
        prog, base = new, score(new, library, projects, caches, mem)
        log.append(dict(cycle=cyc, adopted=desc, program=copy.deepcopy(prog)))
    return prog, library, log
