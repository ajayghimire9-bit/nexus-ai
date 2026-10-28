"""Trial 6 - evolving the learner together with a memory translator, with autopsy-compiled search cuts (NOT LOCKED).

L  (old learner): count-cost construction (u5 'count' policy); memory M_old = {verified solved programs, operator counts
   derived from them, tasks recorded unsolved at their budget}.
L' (evolved learner): L + CUTS - construction patterns (node kind, operator, child root kinds) that autopsies of solved
   searches show were built many times in dead branches but never occur in any winning program; a cut is compiled only
   if it prunes NO subtree of any verified stored solution (zero false prune on the evidence).
T_mem: M_old -> M_new. Counts are carried (they are recomputed from the stored verified programs, never fabricated);
   unsolved marks are carried as UNKNOWN (not silently flipped); dead-branch evidence does not exist in M_old, so it is
   either UNKNOWN (no cut) or recovered by CHARGED replay of a few stored tasks.
Preservation contract (checked by `check_contract`, independent of the translator): (1) every stored solution is still
   constructible under the new learner (no cut matches any of its subtrees) and still verifies on its task's examples;
   (2) every task marked unsolved stays unsolved-or-UNKNOWN unless a new verified program exists; (3) every count equals the
   recount from stored verified programs; (4) every cut cites dead-branch evidence from a replayed search."""
from __future__ import annotations

from collections import Counter

from nexus import u5_construct as K


def rootk(n):
    if n[0] == "var":
        return "var"
    if n[0] == "const":
        return "cs" if isinstance(n[1], str) else "cn"
    return n[1]


def pattern(n):
    if n[0] == "u":
        return ("u", n[1], rootk(n[2]))
    if n[0] == "b":
        return ("b", n[1], rootk(n[2]), rootk(n[3]))
    return None


def subtree_patterns(n):
    out = set()

    def walk(x):
        p = pattern(x)
        if p:
            out.add(p)
        if x[0] in ("u", "b"):
            for c in x[2:]:
                walk(c)
        elif x[0] == "fn":
            for a in x[4]:
                walk(a)
    walk(n)
    return out


class CutSearch(K.Search):
    def __init__(self, *a, cuts=frozenset(), **k):
        super().__init__(*a, **k)
        self.cuts, self.n_cut = cuts, 0

    def _add(self, node, vec, syn, level, op):
        if self.cuts and pattern(node) in self.cuts:
            self.n_cut += 1
            return None
        return super()._add(node, vec, syn, level, op)


def solve(task, cfg, cuts, budget):
    s = CutSearch(task.train, task.y_train, cfg, [], budget, cuts=cuts)
    node = s.run()
    return node, s


def autopsy(searches, min_dead=200):
    """Dead patterns: built >= min_dead times across the given solved searches and never in a winning program."""
    built, win = Counter(), set()
    for s, node in searches:
        for e in s.sig.values():
            p = pattern(e[0])
            if p:
                built[p] += 1
        win |= subtree_patterns(node)
    return {p for p, c in built.items() if c >= min_dead and p not in win}, built


def translate(memory, replay_tasks, cfg, budget, solve_fn):
    """T_mem: counts carried; unsolved -> UNKNOWN; cuts from a charged replay of `replay_tasks` stored solved tasks,
    minus anything that would prune a stored verified solution."""
    replays = []
    for t in replay_tasks:
        node, s = solve_fn(t, cfg, frozenset(), budget)
        if node is not None:
            replays.append((s, node))
    cuts, built = autopsy(replays)
    protect = set()
    for prog in memory["programs"].values():
        protect |= subtree_patterns(prog)
    cuts -= protect
    return dict(programs=dict(memory["programs"]), counts=Counter(memory["counts"]),
                unsolved=list(memory["unsolved"]), unknown={t: "UNKNOWN" for t in memory["unsolved"]}, cuts=frozenset(cuts),
                evidence={str(p): built[p] for p in cuts}), len(replays)


def check_contract(mem_old, mem_new, tasks_by_id):
    """Independent machine check of the preservation contract. Returns (ok, violations)."""
    from nexus import u5_construct as K2
    v = []
    for tid, prog in mem_old["programs"].items():
        if tid not in mem_new["programs"]:
            v.append(f"lost {tid}")
            continue
        if subtree_patterns(prog) & set(mem_new["cuts"]):
            v.append(f"cut prunes stored solution {tid}")
        t = tasks_by_id[tid]
        if not all(K2._ok(K2._safe_ev(prog, e), y) for e, y in zip(t.train, t.y_train)):
            v.append(f"stored solution no longer verifies {tid}")
    for tid in mem_old["unsolved"]:
        if tid in mem_new["programs"] and tid not in mem_old["programs"]:
            v.append(f"unsolved {tid} silently marked solved")
    recount = K2.op_counts(list(mem_new["programs"].values()))
    if Counter(mem_new["counts"]) != recount:
        v.append("counts not derivable from stored verified programs")
    if any(str(p) not in mem_new.get("evidence", {}) for p in mem_new["cuts"]):
        v.append("cut without dead-branch evidence")
    return not v, v
