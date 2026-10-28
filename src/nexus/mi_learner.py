"""Learners for the mi track (NOT LOCKED).

Every arm = the SAME established fast path (x7 growth learner: learned ba policy from H0, reset-aware search, bounded acceptance)
followed - only when the fast path does not accept - by a FULL-SPACE stage whose register-hypothesis procedure is the arm's:
  baseline      the existing hard-wired procedure (t7 GRAMMAR5)                 = x7 learn_class_bounded, unchanged behaviour
  lpl:<prog>    the hypothesis space produced by an LPL procedure (invented / random-structural / seed)
  params:<cfg>  the existing procedure with numeric parameters only (closure size bound, register-search seconds)
  direct        equal-budget direct synthesis: the full primitive closure (acc, x, 0..10 under + - * / and conditionals of
                pairs) up to size 5 - no reused invented procedure
The assignment engine (reset-aware backtracking, x7_regsearch), control learning, coverage and bounded acceptance (ba_accept),
the oracle, the evaluator and the meters are identical and outside the editable surface. The fast-path outcome is identical
for every arm and is computed once per episode (cached)."""
from __future__ import annotations

import itertools
import signal
import time

from nexus import ba_accept as BA
from nexus import mi_lpl as LP
from nexus import oop_synthesizer as S
from nexus import t7_repair as TR
from nexus import u5_statesplit as SP
from nexus import x7_regsearch as XR


class EpisodeTimeout(Exception):
    pass


class LearnerMI(XR.Learner2X):
    """Learner2X whose register-update domain comes from a procedure (callable ctx -> ordered list)."""
    domain_fn = None

    def _search_register(self, hist, traces, os, val, max_s):
        obs = [val(o) for o in os]
        ctx = dict(obs=obs, n_trans=len({t for o in os for t in traces[o[0]][:o[1]]}))
        self._mi_dom, st = self.domain_fn(ctx)
        self.mi_stats = getattr(self, "mi_stats", []) + [st]
        rg = super()._search_register(hist, traces, os, val, max_s)
        self.mi_searches = getattr(self, "mi_searches", []) + [rg is not None]     # learner-side evidence, not the evaluator
        return rg

    def _bt(self, i, order, assign, cons, hist, traces, val, f, init, t0, max_s):
        if time.process_time() - t0 > max_s:
            return False
        if not self._check(cons.get(i - 1, []), assign, hist, traces, val, f, init):
            return False
        if i > 0 and not self._x7_early_ok(order[i - 1], assign, hist, traces, val, f, init):
            return False
        if i == len(order):
            return True
        t = order[i]
        lam = self.hyp_lam
        sib = [assign[u] for u in assign if u[1] == t[1] and lam.get(u) == lam.get(t)]
        for g in list(dict.fromkeys(sib + self._mi_dom)):
            assign[t] = g
            if self._bt(i + 1, order, assign, cons, hist, traces, val, f, init, t0, max_s):
                return True
        del assign[t]
        return False


def baseline_domain(ctx):
    return list(TR.GRAMMAR5), dict(size=len(TR.GRAMMAR5))


def params_domain(size_bound):
    """The existing procedure with its numeric parameter changed: closure of {acc, x, 0, 1} under {+, -} to size <= bound."""
    terms = [("var", "acc"), ("var", "x"), ("const", 0), ("const", 1)]
    lv = {1: terms}
    for s in range(3, size_bound + 1, 2):
        lv[s] = []
        for a in range(1, s - 1, 2):
            b = s - 1 - a
            lv[s] += [("b", op, x, y) for op in ("+", "-") for x in lv[a] for y in lv[b]]
    seen, out = set(), []
    for s in sorted(lv):
        for n in lv[s]:
            g = LP._sig(n)
            if g not in seen:
                seen.add(g)
                out.append(n)
    out.remove(("var", "acc"))
    out = [("var", "acc")] + out

    def f(ctx):
        return out, dict(size=len(out))
    return f


def direct_domain():
    terms = [("var", "acc"), ("var", "x")] + [("const", k) for k in LP.LIT]
    lv3 = [("b", op, a, b) for op in LP.OPS for a in terms for b in terms if not (a[0] == "const" and b[0] == "const")]
    lv5 = [("b", op, a, b) for op in LP.OPS for a in lv3 for b in terms] + [("b", op, a, b) for op in LP.OPS for a in terms for b in lv3]
    conds = [("if", ("b", "<", p, q), r, s) for p, q in itertools.permutations(terms[:2] + terms[2:4], 2)
             for r, s in itertools.permutations(terms[:2] + terms[2:4], 2)]
    seen, out = set(), []
    for n in [("var", "acc")] + terms + lv3 + conds + lv5:
        g = LP._sig(n)
        if g in seen or all(v is None for v in g):
            continue
        seen.add(g)
        out.append(n)
    out = out[:LP.POOL_CAP]

    def f(ctx):
        return out, dict(size=len(out))
    return f


def lpl_domain(prog):
    def f(ctx):
        return LP.hypothesis_space(prog, ctx)
    return f


def fast_path(ep, growth, seed):
    """The established fast path alone (growth learner, no fallback). Same for every arm."""
    c0, q0 = time.process_time(), ep.n_queries
    r = XR.learn_class_bounded(ep.train, ep.y_train, ep.query, seed=seed, growth=growth, fix=True, fallback=False)
    return r, dict(cpu_s=round(time.process_time() - c0, 3), queries=ep.n_queries - q0)


def full_space(ep, domain_fn, seed, max_s=60.0, rounds=6, cap_s=None):
    """learn_class_bounded's full-space stage with the arm's register-hypothesis procedure (code path otherwise identical)."""
    t1 = time.process_time()
    q0 = ep.n_queries
    L = LearnerMI(ep.train, ep.y_train, ep.query, seed=seed, max_s=max_s)
    L.domain_fn = domain_fn
    stats = dict(queries=0)
    if cap_s:
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(EpisodeTimeout()))
        signal.setitimer(signal.ITIMER_REAL, cap_s)
    try:
        if L.key is None or L.ctrl is None:
            return None, dict(stats, outcome="no_fields")
        m = L.learn()
        ok, scope = False, None
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
        stats["explained"] = (sum(getattr(L, "mi_searches", [])) / len(L.mi_searches)) if getattr(L, "mi_searches", None) else 0.0
    finally:
        if cap_s:
            signal.setitimer(signal.ITIMER_REAL, 0)
    stats.update(outcome=outcome, cpu_s=round(time.process_time() - t1, 3), queries=ep.n_queries - q0,
                 domain_sizes=[s.get("size") for s in getattr(L, "mi_stats", [])][:6],
                 explained=(sum(getattr(L, "mi_searches", [])) / len(L.mi_searches)) if getattr(L, "mi_searches", None) else 0.0)
    if not ok or m is None:
        return None, stats
    src, name = SP.class_source(m, witnesses=L.witnesses)
    return dict(source=src, name=name, machine=m, scope=scope, learner="full_space"), stats


def score(ep, r):
    if r is None:
        return dict(exact=False, accepted=False, silent=False)
    try:
        cls = SP.compile_class(r["source"], r["name"])
        sc = ep.score(lambda evs: SP.run_class(cls, evs))
    except Exception:                                                # noqa: BLE001
        sc = dict(exact=False)
    return dict(exact=bool(sc["exact"]), accepted=True, silent=not sc["exact"])


def updates_src(r):
    if not r:
        return None
    return [{str(t): S.src(g) for t, g in rg["upd"].items()} for rg in r["machine"]["regs"]]
