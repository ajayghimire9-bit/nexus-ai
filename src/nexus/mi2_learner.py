"""MI-2 learner stage (NOT LOCKED; separately versioned; mi_learner stays frozen with MI-1).

Same structure as mi_learner.full_space (the arm's register-hypothesis procedure inside the unchanged x7 learner: reset-aware
backtracking assignment engine, control learning, coverage and bounded acceptance), with two disclosed changes:
  * the per-episode cap counts process CPU time (ITIMER_PROF), not wall time, so outcomes do not depend on machine load;
  * every register search is recorded (solved / unsat / out of time), so a partial-credit signal can be checked against
    independent correctness (it never replaces it).
Witness domains (privileged: the episode's own true updates) exist for the development diagnosis and headroom check only;
mi2_discover refuses them."""
from __future__ import annotations

import signal
import time

from nexus import ba_accept as BA
from nexus import mi_learner as ML
from nexus import mi_lpl as LP
from nexus import t7_repair as TR
from nexus import u5_statesplit as SP


class EpisodeTimeout(Exception):
    pass


class LearnerMI2(ML.LearnerMI):
    def _search_register(self, hist, traces, os, val, max_s):
        c0 = time.process_time()
        rg = super()._search_register(hist, traces, os, val, max_s)
        dt = time.process_time() - c0
        self.mi2_log = getattr(self, "mi2_log", []) + [("solved" if rg is not None else ("time" if dt >= max_s * 0.95 else "unsat"))]
        return rg


def _raise(*_):
    raise EpisodeTimeout()


def full_space(ep, domain_fn, seed, max_s=60.0, rounds=6, cap_s=None):
    t1 = time.process_time()
    q0 = ep.n_queries
    L = LearnerMI2(ep.train, ep.y_train, ep.query, seed=seed, max_s=max_s)
    L.domain_fn = domain_fn
    stats = dict(queries=0)
    if cap_s:
        signal.signal(signal.SIGPROF, _raise)
        signal.setitimer(signal.ITIMER_PROF, cap_s)
    ok, m, scope = False, None, None
    try:
        if L.key is None or L.ctrl is None:
            outcome = "no_fields"
        else:
            m = L.learn()
            for r in range(rounds):
                if m is None or time.process_time() - t1 > 4 * max_s:
                    break
                cex = TR.coverage_cex(L)
                if not cex:
                    cex, scope = BA.bounded_cex(L, seed=seed + r)
                if not cex:
                    ok = True
                    break
                relabel = False
                for evs, rows, word in cex:
                    if L._run_labels(L.hyp, word) != tuple(SP._labels(x) for x in rows):
                        relabel = True
                        for i in range(len(word)):
                            if tuple(word[i:]) not in L.E:
                                L.E.append(tuple(word[i:]))
                    else:
                        L.extra_hist.append((evs, rows))
                hyp = L.learn_control_continue() if relabel else L.hyp
                if L.learn_registers(hyp) is None:
                    m = None
                    break
                L.machine = m = L._machine(hyp)
            outcome = "accepted" if ok and m is not None else ("register_search_failed" if m is None else "acceptance_failed")
    except EpisodeTimeout:
        ok, m, outcome, scope = False, None, "cap_timeout", None
    finally:
        if cap_s:
            signal.setitimer(signal.ITIMER_PROF, 0)
    log = getattr(L, "mi2_log", [])
    stats.update(outcome=outcome, cpu_s=round(time.process_time() - t1, 3), queries=ep.n_queries - q0,
                 domain_sizes=[s.get("size") for s in getattr(L, "mi_stats", [])][:6], searches=log,
                 explained=(log.count("solved") / len(log)) if log else 0.0)
    if not ok or m is None:
        return None, stats
    src, name = SP.class_source(m, witnesses=L.witnesses)
    return dict(source=src, name=name, machine=m, scope=scope, learner="full_space"), stats


# ------------------------------------------------------------------------------------------------ privileged (diagnosis only)
def true_updates(ep):
    out = []
    for d in ep.machine["upd"]:
        for g in d.values():
            if g is not None and g not in out:
                out.append(g)
    return out


def witness_domain(ep, mode):
    """mode: 'end' GRAMMAR5 + the episode's true updates; 'front' the true updates first; 'min' identity + true updates only."""
    truth = [g for g in true_updates(ep) if LP._sig(g) != LP._sig(LP.ACC)]
    g5 = list(TR.GRAMMAR5)
    sig5 = {LP._sig(g) for g in g5}
    new = [g for g in truth if LP._sig(g) not in sig5]
    if mode == "end":
        dom = g5 + new
    elif mode == "front":
        dom = [g5[0]] + truth + [g for g in g5[1:] if g not in truth]
    else:
        dom = [LP.ACC] + truth
    return dom


def witness_fn(ep, mode):
    dom = witness_domain(ep, mode)

    def f(ctx):
        return list(dom), dict(size=len(dom), privileged=True)
    f.privileged = True
    return f


# ------------------------------------------------------------------------------------------------ MI-2 control procedures
# A5: a simple HUMAN-WRITTEN evidence-aware procedure (Claude, frozen in the MI-2 pre-registration before any discovery run;
# never edited afterwards). Same LPL language, same constant miners: terms {acc, x}; constants 0, 1, 2 plus every evidence
# miner; one layer of all four operators (variable-bearing results only); one further additive layer over a variable;
# deduplicated, smallest first. The literal 2 was chosen after the development diagnosis showed SUBH needs a half-term (disclosed).
A5_PROG = dict(main=[
    ("terms", "P0", ("acc", "x")), ("lits", "P1", (0, 1, 2)),
    ("dconsts", "P2", "small_obs"), ("union", "P1", "P1", "P2"), ("dconsts", "P2", "int_diffs"), ("union", "P1", "P1", "P2"),
    ("dconsts", "P2", "int_ratios"), ("union", "P1", "P1", "P2"), ("union", "P1", "P0", "P1"), ("dedupe", "P1", "P1"),
    ("combine", "P2", "P1", "P1", "+"), ("combine", "P3", "P1", "P1", "-"), ("union", "P2", "P2", "P3"),
    ("combine", "P3", "P1", "P1", "*"), ("union", "P2", "P2", "P3"), ("combine", "P3", "P1", "P1", "/"), ("union", "P2", "P2", "P3"),
    ("filter", "P2", "P2", "not_const"), ("dedupe", "P2", "P2"),
    ("combine", "P3", "P2", "P0", "+"), ("combine", "P4", "P2", "P0", "-"), ("union", "P3", "P3", "P4"),
    ("combine", "P4", "P0", "P2", "+"), ("union", "P3", "P3", "P4"), ("combine", "P4", "P0", "P2", "-"), ("union", "P3", "P3", "P4"),
    ("dedupe", "P3", "P3"), ("union", "P5", "P1", "P2"), ("union", "P5", "P5", "P3"), ("dedupe", "P5", "P5"),
    ("sort", "P5", "P5", "size"), ("ret", "P5")], helpers={})


def a6_domain():
    """A6 generic direct synthesis, same operations and evidence: bottom-up enumeration over {acc, x} + LIT (0..10) + every
    evidence-mined constant, all four operators at sizes 3 and 5, conditionals of size-1 terms, one representative per probe
    signature, strictly smallest size first (ties: enumeration order), capped at POOL_CAP. No reused procedure."""
    def f(ctx):
        obs = ctx.get("obs", [])
        mined = [c for m in LP.DMODES for c in LP._derive(m, obs)]
        terms = [LP.ACC, LP.X] + [("const", k) for k in LP.LIT] + [c for c in mined if c[1] not in LP.LIT]
        seen, out = set(), []

        def add(n):
            g = LP._sig(n)
            if g in seen or all(v is None for v in g) or len(out) >= LP.POOL_CAP:
                return
            seen.add(g)
            out.append(n)
        add(LP.ACC)
        for n in terms:
            add(n)
        lv3 = [("b", op, a, b) for op in LP.OPS for a in terms for b in terms if not (a[0] == "const" and b[0] == "const")]
        for n in lv3:
            add(n)
        vars3 = [n for n in out if n[0] == "b"]
        for n in [("if", ("b", "<", p, q), r, s) for p in terms[:4] for q in terms[:4] if p != q for r in terms[:4] for s in terms[:4] if r != s]:
            add(n)
        for op in LP.OPS:
            for a in vars3:
                for b in terms:
                    add(("b", op, a, b))
                    add(("b", op, b, a))
        return out, dict(size=len(out))
    return f


PARAMS_GRID = [(b, k, s) for b in (3, 5, 7) for k in (1, 2, 3, 5, 10) for s in (4.0, 60.0)]


def params_domain(size_bound, max_lit):
    """A4 parameter tuning, RESTRICTED search space: the existing procedure (closure of {acc, x, 0..max_lit} under {+, -} to
    size <= size_bound, deduplicated, smallest first) with three numeric parameters (size bound, largest literal, register-search
    seconds). No new operator, no evidence access, no structural change."""
    terms = [LP.ACC, LP.X] + [("const", k) for k in range(max_lit + 1)]
    lv = {1: terms}
    out, seen = [], set()

    def add(n):
        g = LP._sig(n)
        if g not in seen and len(out) < LP.POOL_CAP:
            seen.add(g)
            out.append(n)
    for n in terms:
        add(n)
    for s in range(3, size_bound + 1, 2):
        lv[s] = []
        for a in range(1, s - 1, 2):
            for op in ("+", "-"):
                for x in lv[a]:
                    for y in lv[s - 1 - a]:
                        lv[s].append(("b", op, x, y))
                        if len(lv[s]) > 4 * LP.POOL_CAP:
                            break
        for n in lv[s]:
            add(n)
    out.remove(LP.ACC)
    out = [LP.ACC] + out

    def f(ctx):
        return list(out), dict(size=len(out))
    return f
