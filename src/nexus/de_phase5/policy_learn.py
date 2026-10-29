"""Phase 5 automatic learning of executable investigation procedures (NOT LOCKED).

Source experience of a lineage is recorded once, by REAL execution (Live backend), into per-project caches: the claims of
every source, the repair-search result with its decision points, distinguishing probes and per-option effects, the
stakeholder's answer for each decision point, and the hidden-batch verification of every option combination (source
feedback only). Candidate procedures are then evaluated by REPLAY on those caches (Cached backend): the interpreter is the
same, actions return the recorded observations and measured costs, and only the asked decision point's answer is visible.

Proposal mechanism (simple, automatic; no model): each cycle draws edits of the current program - insert a statement
from the palette, delete, swap neighbours, change a parameter, wrap a statement in a condition, or insert a call to a
stored procedure - with every edit type represented; each edit is evaluated in ITS OWN comparison against the current
program on the validation caches (memory frozen from the training projects), admitted only by admission5.admit, and the
execution-coverage record shows whether the edited statement actually ran. An adopted edit's block is stored as a
library procedure (typed interface State -> State, applicability = observable conditions where it helped, provenance =
source projects and cycle, utility = the admission record) and the program calls it."""
from __future__ import annotations

import copy
import itertools
import json
import random

from nexus.de_phase5 import admission5 as A5, investigate as IV, world5 as W5

SOURCES = W5.SOURCES
CONDS = ["has_candidate", "unresolved", "multi_unresolved", "conflict", "undecided", "asked", "claims_seen", "trust_memory"]
EDIT_TYPES = ("insert", "insert_pair", "delete", "swap", "param", "wrap", "call", "inline")
SEED = [["search"], ["submit_or_abstain"]]          # the minimal starting program: composition must be learned


# typed interfaces of the primitives: what each statement consumes and produces in the investigation state
TYPES = {"read": ((), ("claims",)), "read_all": ((), ("claims",)), "search": ((), ("hypotheses",)), "search_more": (("hypotheses",), ("hypotheses",)),
         "resolve": (("claims", "hypotheses"), ("resolutions",)), "ask": (("hypotheses",), ("resolutions",)),
         "submit_or_abstain": (("resolutions",), ("decision",))}


def typed_pairs():
    """Every (producer, consumer) pair whose consumer reads something the producer writes."""
    out = []
    for a in palette():
        for b in palette():
            if set(TYPES[a[0]][1]) & set(TYPES[b[0]][0]) and a[0] != b[0]:
                out.append((a, b))
    return out


def inline_all(prog, library):
    """The program with every stored-procedure call expanded (proposals refine inside stored procedures too)."""
    out = []
    for s in prog:
        if s[0] == "call" and s[1] in library:
            out += inline_all(copy.deepcopy(library[s[1]]["body"]), library)
        elif s[0] == "if":
            out.append(["if", s[1], inline_all(s[2], library)] + ([inline_all(s[3], library)] if len(s) > 3 else []))
        else:
            out.append(copy.deepcopy(s))
    return out


def enumerate_inserts(prog):
    """Exhaustive top-level single insertions and typed pair insertions (deterministic)."""
    out = []
    for i in range(len(prog) + 1):
        for s in palette():
            new = copy.deepcopy(prog)
            st = copy.deepcopy(s)
            new.insert(i, st)
            out.append(("insert", new, st, f"insert {s} at {i}", [st]))
        for a, b in typed_pairs():
            new = copy.deepcopy(prog)
            a_, b_ = copy.deepcopy(a), copy.deepcopy(b)
            new[i:i] = [a_, b_]
            out.append(("insert_pair", new, a_, f"insert {a} + {b} at {i}", [a_, b_]))
    return out


def palette():
    return ([["read", s] for s in SOURCES] + [["read_all"], ["search"], ["search_more"]] +
            [["resolve", t] for t in ("none", "newest", "learned")] + [["ask", t] for t in ("first", "last", "unclaimed", "conflicted", "lowconf")] +
            [["submit_or_abstain"]])


# ------------------------------------------------------------------ caches (built by real execution) and replay
def build_entry(project, live, mem, rt=None):
    from nexus.de_phase4 import learner as L
    e = dict(pid=project["pid"], reads={s: live.read(project, s) for s in SOURCES})
    s1 = live.search(project, mem)
    e["search"] = {k: v for k, v in s1.items() if k != "_rec"}
    e["_rec"] = s1.get("_rec")
    if not s1["has_candidate"]:
        s2 = live.search(project, mem, more=True)
        e["search_more"] = {k: v for k, v in s2.items() if k != "_rec"}
    e["answers"] = {str(dp["pos"]): live.ask(project, dp) for dp in s1["dps"]}
    combos = {}
    if s1["has_candidate"]:
        inv = L.Investigation(project, live.rts[project["runtime"]])
        dps = s1["dps"]
        for opts in itertools.product(*[dp["options"] for dp in dps]) if dps else [()]:
            st = IV.State(project, live, IV.empty_evidence(), mem)
            st.has_candidate, st.path, st.dps = True, s1["path"], copy.deepcopy(dps)
            st.decision = dict(kind="submit", choices={dp["pos"]: o for dp, o in zip(dps, opts)})
            o = IV.outcome(project, st, live.rts[project["runtime"]])
            combos[json.dumps([str(x) for x in opts])] = dict(verified=o["verified"], wrong=o["wrong"])
    e["combos"] = combos
    e["any_verifiable"] = any(v["verified"] for v in combos.values())
    return e


class Cached:
    def __init__(self, caches):
        self.c = caches

    def read(self, project, src):
        return copy.deepcopy(self.c[project["pid"]]["reads"][src])

    def search(self, project, mem, more=False):
        e = self.c[project["pid"]]
        return copy.deepcopy(e["search_more"] if more and "search_more" in e else e["search"])

    def ask(self, project, dp):
        return copy.deepcopy(self.c[project["pid"]]["answers"].get(str(dp["pos"]), dict(answer="no_probe")))


def replay_row(project, entry, st, q_cost=IV.QUESTION_COST_S):
    d = st.decision
    if d["kind"] == "submit":
        k = json.dumps([str(d["choices"][dp["pos"]]) for dp in st.dps])
        v = entry["combos"].get(k, dict(verified=False, wrong=True))
        correct, completed, wrong = v["verified"], v["verified"], v["wrong"]
    else:
        correct, completed, wrong = not entry["any_verifiable"], False, False
    return dict(correct=correct, completed=completed, wrong=wrong, cost=dict(st.cost), decision=d["kind"],
                questions=st.cost["questions"], executed=st.executed if hasattr(st, "executed") else set())


def score(prog, library, projects, caches, em, mem):
    b = Cached(caches)
    rows = {}
    for p in projects:
        st = IV.investigate(p, b, em, mem, prog, library)
        rows[p["pid"]] = replay_row(p, caches[p["pid"]], st)
    return rows


# ------------------------------------------------------------------ automatic program edits
def _flatten(prog, path=()):
    for i, s in enumerate(prog):
        yield path + (i,), s
        if s[0] == "if":
            yield from _flatten(s[2], path + (i, 2))
            if len(s) > 3:
                yield from _flatten(s[3], path + (i, 3))


def _container(prog, path):
    c = prog
    for k in path[:-1]:
        c = c[k]
    return c, path[-1]


def library_name(prog, path):
    c, i = _container(prog, path)
    return c[i][1] if c[i][0] == "call" else "?"


def propose(prog, library, rng, etype):
    """One edit of type `etype` -> (new program, the new / affected statement, description) or None."""
    new = copy.deepcopy(prog)
    spots = list(_flatten(new))
    if not spots:
        return None
    path, s = rng.choice(spots)
    c, i = _container(new, path)
    if etype == "insert":
        stmt = copy.deepcopy(rng.choice(palette()))
        c.insert(i, stmt)
        return new, stmt, f"insert {stmt} before {path}"
    if etype == "insert_pair":                          # two statements at once (crosses read -> resolve plateaus)
        a, b = copy.deepcopy(rng.choice(palette())), copy.deepcopy(rng.choice(palette()))
        c.insert(i, b)
        c.insert(i, a)
        return new, a, f"insert {a} + {b} before {path}", [a, b]
    if etype == "delete":
        if c[i][0] in ("search",):
            return None
        old = c.pop(i)
        return new, None, f"delete {old} at {path}"
    if etype == "swap":
        if i + 1 >= len(c):
            return None
        c[i], c[i + 1] = c[i + 1], c[i]
        return new, c[i], f"swap {path} with the next statement"
    if etype == "param":
        opts = {"read": list(SOURCES), "resolve": ["none", "newest", "learned"], "ask": ["first", "last", "unclaimed", "conflicted", "lowconf"]}
        if c[i][0] in opts:
            v = rng.choice([o for o in opts[c[i][0]] if o != c[i][1]])
            c[i] = [c[i][0], v]
            return new, c[i], f"set {path} {c[i][0]} -> {v}"
        if c[i][0] == "if":
            cnd = rng.choice(CONDS + [["not", x] for x in CONDS])
            c[i] = ["if", cnd] + c[i][2:]
            return new, c[i], f"set condition at {path} -> {cnd}"
        return None
    if etype == "wrap":
        if c[i][0] == "if":
            return None
        cnd = rng.choice(CONDS + [["not", x] for x in CONDS])
        c[i] = ["if", cnd, [c[i]]]
        return new, c[i], f"wrap {path} in if {cnd}"
    if etype == "inline":                               # expand a stored procedure so later edits can rework its steps
        if c[i][0] != "call" or c[i][1] not in library:
            return None
        body = copy.deepcopy(library[c[i][1]]["body"])
        c[i:i + 1] = body
        return new, body[0], f"inline {library_name(prog, path)}", body
    if etype == "call":
        if not library:
            return None
        name = rng.choice(sorted(library))
        stmt = ["call", name]
        c.insert(i, stmt)
        return new, stmt, f"insert call {name} before {path}"
    return None


def learn_policy(start, projects, caches, em, mem, rng, cycles=8, edits_per_cycle=24, min_saving=0.1, history_pids=None):
    """Cycles of edit -> own comparison -> corrected admission. Returns (program, library, log)."""
    prog, library, log, n_proc = copy.deepcopy(start), {}, [], 0
    base_rows = score(prog, library, projects, caches, em, mem)
    for cyc in range(cycles):
        types = [t for t in EDIT_TYPES if t not in ("insert", "insert_pair")]
        types += [rng.choice(types) for _ in range(max(0, edits_per_cycle - len(types)))]
        rng.shuffle(types)
        flat = inline_all(prog, library)
        proposals = [(t, n, s, d, b) for t, n, s, d, b in enumerate_inserts(flat)]       # exhaustive typed insertions
        for et in types:                                                                 # + sampled edits of every other type
            prop = None
            for _ in range(20):
                prop = propose(flat if et not in ("call", "inline") else prog, library, rng, et)
                if prop is not None:
                    break
            if prop is None:
                log.append(dict(cycle=cyc, type=et, proposed=False))
                continue
            proposals.append((et, prop[0], prop[1], prop[2], prop[3] if len(prop) > 3 else ([prop[1]] if prop[1] is not None else [])))
        cands = []
        for et, new, stmt, desc, block in proposals:
            rows = score(new, library, projects, caches, em, mem)
            ok, why = A5.admit(base_rows, rows, min_saving=min_saving)
            ran = sum(1 for r in rows.values() if stmt is not None and id(stmt) in r["executed"]) if stmt is not None else \
                sum(1 for r in base_rows.values() if r["executed"])
            log.append(dict(cycle=cyc, type=et, edit=desc, admitted=ok, why=why, executed_in_projects=ran,
                            correct=sum(r["correct"] for r in rows.values()), wrong=sum(r["wrong"] for r in rows.values()),
                            questions=sum(r["questions"] for r in rows.values())))
            if ok:
                cands.append((sum(r["correct"] for r in rows.values()), -sum(A5.cost_s(r, IV.QUESTION_COST_S) for r in rows.values()), desc, new, stmt, rows, why, block))
        if not cands:
            continue
        cands.sort(key=lambda t: (t[0], t[1]), reverse=True)
        _, _, desc, new, stmt, rows, why, block = cands[0]
        helped = [p for p in rows if rows[p]["correct"] and not base_rows[p]["correct"]] or \
                 [p for p in rows if rows[p]["completed"] and A5.cost_s(rows[p], 2.0) < A5.cost_s(base_rows[p], 2.0)]
        if stmt is not None and stmt[0] != "call" and not desc.startswith("inline"):
            n_proc += 1
            name = f"proc{n_proc}"
            library[name] = dict(body=copy.deepcopy(block), interface="InvestigationState -> InvestigationState",
                                 applicability="pending",            # filled below: conditions true at entry in every helped project
                                 helped=helped, provenance=dict(cycle=cyc, edit=desc, validation=sorted(rows), source_history=history_pids or []),
                                 utility=why)
            for path_, s_ in list(_flatten(new)):          # the block becomes one call to the stored procedure
                if any(s_ is b_ for b_ in block[1:]):
                    c_, i_ = _container(new, path_)
                    c_.pop(i_)
                    break
            stmt[:] = ["call", name]
        if stmt is not None and stmt[0] == "call" and library.get(stmt[1], {}).get("applicability") == "pending":
            snaps = []
            for p in projects:
                if p["pid"] in helped:
                    st_ = IV.investigate(p, Cached(caches), em, mem, new, library)
                    snaps += [t["obs"]["conditions_at_entry"] for t in st_.trace if t["action"] == "call" and t["obs"]["procedure"] == stmt[1]]
            library[stmt[1]]["applicability"] = {c: snaps[0][c] for c in snaps[0] if all(s_[c] == snaps[0][c] for s_ in snaps)} if snaps else {}
        prog, base_rows = new, score(new, library, projects, caches, em, mem)
        log.append(dict(cycle=cyc, adopted=desc, program=copy.deepcopy(prog)))
    return prog, library, log
