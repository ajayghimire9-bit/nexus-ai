"""Register search with reset-aware early pruning (NOT LOCKED; x7 Part 2 general learner fix). No earlier learner file is edited.

Diagnosis (artifacts/x7_dev/diag13327*.json): on sc dev 13327 the control hypothesis was right (3 modes) and the documented
register program was consistent with the learner's own traces (0 / 53 inconsistent slots per register), yet the unchanged
backtracking search timed out (60 s; 128.7 M nodes in 600 s). Cause: an occurrence (history, position) is checked only when
EVERY transition in its whole prefix is assigned, so long keyed histories delay all pruning to the last few variables.

Fix (sound, order-preserving): an assigned update that does not read `acc` (a reset such as 0, x, x + 1) makes the register
value after it independent of everything before it. An occurrence is therefore already DETERMINED as soon as every transition
after the last assigned reset in its prefix is assigned (or the whole prefix is assigned). After each assignment the
determined occurrences that contain the just-assigned transition are evaluated from that reset forward; a mismatch prunes the
subtree. Every completion of a pruned partial assignment gives the same (wrong) value at that occurrence, so no consistent
leaf is ever pruned: the search visits a subset of the old search's nodes in the same order and returns the SAME first
solution, only sooner. The old full checks are kept unchanged. Applies to the full-space learner (t7_repair.Learner2) and the
growth learner (oc_learner.Learner3) through mixins; ba_learn.attempt / ba_platform.learn_class_bounded are copied with only
the learner classes replaced."""
from __future__ import annotations

import time

from nexus import ba_accept as BA
from nexus import oc_learner as OL
from nexus import t7_repair as TR
from nexus import u5_statesplit as SP

STATS = dict(early_checks=0, early_prunes=0)


def _acc_free(g):
    return "acc" not in SP.S._vars(g)


class ResetPrune:
    """Mixin: wraps _search_register to index occurrences by transition; adds the determined-occurrence check to _bt."""

    def _search_register(self, hist, traces, os, val, max_s):
        self._x7_occ = [o[:2] for o in os]
        self._x7_os = list(os)
        self._x7_byt = None
        try:
            return super()._search_register(hist, traces, os, val, max_s)
        finally:
            self._x7_byt = None

    def _x7_index(self, traces):
        byt = {}
        for o in self._x7_os:
            hi, p = o[0], o[1]
            for t in set(traces[hi][:p]):
                byt.setdefault(t, []).append(o)
        self._x7_byt = byt

    def _x7_early_ok(self, t, assign, hist, traces, val, f, init):
        if self._x7_byt is None:
            self._x7_index(traces)
        for o in self._x7_byt.get(t, ()):
            hi, p = o[0], o[1]
            tr = traces[hi]
            start, ok = 0, True
            for j in range(p - 1, -1, -1):
                g = assign.get(tr[j])
                if g is None:
                    ok = False
                    break
                if _acc_free(g):
                    start = j
                    break
            if not ok:
                continue
            STATS["early_checks"] += 1
            evs = hist[hi][0]
            acc = init
            for e, u in zip(evs[start:p], tr[start:p]):
                x = e.get(f)
                acc = SP.S.ev(assign[u], {"acc": acc, "x": x if SP._isnum(x) else 0})
                if acc is SP.S.ERR:
                    acc = None
                    break
            if not SP._veq(acc, val(o)):
                STATS["early_prunes"] += 1
                return False
        return True


class Learner2X(ResetPrune, TR.Learner2):
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
        for g in list(dict.fromkeys(sib + TR.GRAMMAR5)):
            assign[t] = g
            if self._bt(i + 1, order, assign, cons, hist, traces, val, f, init, t0, max_s):
                return True
        del assign[t]
        return False


class Learner3X(ResetPrune, OL.Learner3):
    def _bt(self, i, order, assign, cons, hist, traces, val, f, init, t0, max_s):
        if time.process_time() - t0 > max_s:
            raise TimeoutError
        if not self._check(cons.get(i - 1, []), assign, hist, traces, val, f, init):
            return False
        if i > 0 and not self._x7_early_ok(order[i - 1], assign, hist, traces, val, f, init):
            return False
        if i == len(order):
            return True
        t = order[i]
        lam = self.hyp_lam
        sib = [assign[u] for u in assign if u[1] == t[1] and lam.get(u) == lam.get(t)]
        dom = self._domain(t)
        for g in list(dict.fromkeys([s for s in sib if s in dom] + dom)):
            assign[t] = g
            if self._bt(i + 1, order, assign, cons, hist, traces, val, f, init, t0, max_s):
                return True
        del assign[t]
        return False


def attempt(ep, H, accept="bounded", contract=None, cache=None, seed=0, rounds=4, bounded_rounds=4, cfg=None, learner=Learner3X):
    """ba_learn.attempt with the learner class as a parameter (Learner3X by default; OL.Learner3 reproduces ba_learn)."""
    from nexus import ba_learn as BL
    L = learner(ep.train, ep.y_train, ep.query, H, contract=contract, seed=seed, cache=cache)
    if L.key is None or L.ctrl is None:
        return False, L, [], None
    L.hyp = L.learn_control()
    if L.learn_registers(L.hyp) is None:
        L.machine = None
        return False, L, [], None
    L.machine = L._machine(L.hyp)
    scope = None
    for _ in range(rounds + (bounded_rounds if accept == "bounded" else 0)):
        cex = TR.coverage_cex(L)
        if not cex and accept == "bounded":
            cex, scope = BA.bounded_cex(L, seed=seed + len(L.extra_hist), **(cfg or {}))
        if not cex:
            return True, L, [], scope
        if not BL._feed(L, cex):
            return False, L, cex, scope
    cex = TR.coverage_cex(L)
    if not cex and accept == "bounded":
        cex, scope = BA.bounded_cex(L, seed=seed + 7919, **(cfg or {}))
    return not cex, L, cex, scope


def learn_class_bounded(events, outputs, query, seed=0, max_s=60.0, rounds=6, growth=None, cfg=None, fix=True, fallback=True):
    """ba_platform.learn_class_bounded with the reset-aware learners (fix=True) or the original ones (fix=False, identical
    to ba). Growth first (<= 6 steps from H0), then the full-space learner as the fallback (fallback=True, as in ba / sc)."""
    from nexus import ba_platform as BP
    t0 = time.process_time()
    L3, L2 = (Learner3X, Learner2X) if fix else (OL.Learner3, TR.Learner2)
    if growth is not None:
        ep = BP._Ep(events, outputs, query)
        H, cache, rnd = dict(OL.H0), {}, __import__("random").Random(seed)
        ok = L = scope = None
        steps = 0
        for _ in range(6):
            ok, L, cex, scope = attempt(ep, H, "bounded", None, cache, seed, cfg=cfg, learner=L3)
            steps += 1
            if ok or time.process_time() - t0 > 4 * max_s:
                break
            H, _ = OL.apply(growth(OL.signature(L, cex), H, rnd), H)
        if ok and L is not None and L.machine:
            src, name = SP.class_source(L.machine, witnesses=L.witnesses)
            return dict(source=src, name=name, machine=L.machine, witnesses=L.witnesses, queries=L.n_mq, scope=scope,
                        learner="growth", growth_steps=steps)
        if not fallback:
            return None
    t1 = time.process_time()
    L = L2(events, outputs, query, seed=seed, max_s=max_s)
    if L.key is None or L.ctrl is None:
        return None
    m = L.learn()
    ok, scope = False, None
    for r in range(rounds):
        if m is None or time.process_time() - t1 > 4 * max_s:
            break
        cex = TR.coverage_cex(L)
        if not cex:
            cex, scope = BA.bounded_cex(L, seed=seed + r, **(cfg or {}))
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
    if not ok or m is None:
        return None
    src, name = SP.class_source(m, witnesses=L.witnesses)
    return dict(source=src, name=name, machine=m, witnesses=L.witnesses, queries=L.n_mq, scope=scope, learner="full_space")
