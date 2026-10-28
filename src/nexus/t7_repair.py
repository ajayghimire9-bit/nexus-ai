"""Priority A - stronger repair acceptance for the u5 stack (NOT LOCKED). u5 modules are not edited.

1. Transition-plus-consequence coverage (lifecycle classes). After the u5 learner returns a machine, every observed or
   hypothesised (mode, symbol) transition is exercised by membership queries  access(mode) . symbol . w  for every
   continuation w in {empty} + single symbols + the L* continuations, with FRESH values (so registers differ). Any
   disagreement - label or value - is a counterexample; it is added and the machine is relearned (rounds bounded). This
   targets delayed consequences (e.g. PARTIAL then COMMIT), which transition-only coverage misses.
2. Condition-crossing probes (status programs). Records whose oracle label is a quarantine reason are compared with the
   accepted records; their ABNORMAL fields (a non-numeric value where accepted records are numeric, or a categorical value
   never seen in accepted records) are copied pairwise into each other, creating records with two overlapping failure
   conditions; the oracle labels them (counted) before the status program is (re)synthesised. This exposes precedence
   between conditions (e.g. missing AND unknown member).
Both only ADD labelled evidence; acceptance is unchanged (exact agreement with all evidence plus held-out verification)."""
from __future__ import annotations

import itertools
import random

from nexus import u5_statesplit as SP


def update_grammar5():
    """Register updates over (acc, x) from primitives: terminals acc, x, 0, 1; + and -; size <= 5; one representative per
    observational-equivalence class on random probe pairs (u5 used size <= 3, which cannot express acc + x + x)."""
    rnd = random.Random(7)
    probes = [(rnd.uniform(-50, 50), rnd.uniform(-50, 50)) for _ in range(12)]
    terms = [("var", "acc"), ("var", "x"), ("const", 0), ("const", 1)]
    lv = {1: terms}
    lv[3] = [("b", op, a, b) for op in ("+", "-") for a in terms for b in terms]
    lv[5] = [("b", op, a, b) for op in ("+", "-") for a in lv[3] for b in terms] + [("b", op, a, b) for op in ("+", "-") for a in terms for b in lv[3]]
    seen, out = set(), []
    for n in lv[1] + lv[3] + lv[5]:
        sig = tuple(round(SP.S.ev(n, {"acc": a, "x": x}), 9) for a, x in probes)
        if sig not in seen:
            seen.add(sig)
            out.append(n)
    out.remove(("var", "acc"))
    return [("var", "acc")] + out


GRAMMAR5 = update_grammar5()


class Learner2(SP.Learner):
    """u5 Learner with a register search whose variable order makes constraints checkable early: occurrences are sorted
    by the number of distinct transitions in their prefix, and variables are ordered by first appearance in that list
    (the u5 order - by frequency - delayed pruning on long probe histories: 0.1 s -> 8 s -> 20 s timeout)."""

    def _search_register(self, hist, traces, os, val, max_s):
        import time as _t
        from collections import defaultdict as _dd
        t0 = _t.process_time()
        occ = sorted(os, key=lambda o: len(set(traces[o[0]][:o[1]])))
        for f in self.f["numeric"]:
            order = []
            for o in occ:
                for t in traces[o[0]][:o[1]]:
                    if t not in order:
                        order.append(t)
            pos = {t: i for i, t in enumerate(order)}
            cons = _dd(list)
            for o in os:
                last = max((pos[t] for t in set(traces[o[0]][:o[1]])), default=-1)
                cons[last].append(o)
            assign = {}
            if self._bt(0, order, assign, cons, hist, traces, val, f, 0, t0, max_s):
                return dict(field=f, init=0, upd={t: g for t, g in assign.items() if g != SP.GRAMMAR[0]})
        return None

    def _check(self, occs, assign, hist, traces, val, f, init):
        rg = dict(field=f, init=init, upd=assign)
        return all(SP._veq(self._reg_value(rg, hist[o[0]][0], traces[o[0]], o[1]), val(o)) for o in occs)

    def learn_registers(self, hyp, max_s=60.0):
        """COLUMN-level register learning: one source per output column (label, value index), searched jointly over the
        union of all its slots (u5 searched slot by slot, so a register fitted to one emitting transition could take an
        arbitrary update on transitions that only matter for another, then fragment into a second register). Falls back
        to the u5 slot-by-slot procedure when a column has no single consistent source."""
        import time as _t
        from collections import defaultdict as _dd
        t0 = _t.process_time()
        self.hyp_lam = hyp["lam"]
        hist = self.histories() + self.extra_hist
        traces = [self._trace(hyp, evs) for evs, _ in hist]
        occ = _dd(list)
        for hi, ((evs, outs), tr) in enumerate(zip(hist, traces)):
            for p_, rows in enumerate(outs):
                for ri, r in enumerate(rows):
                    for vj in (1, 2):
                        if r[vj] is not None:
                            occ[(tr[p_], ri, vj)].append((hi, p_))
        cols = _dd(list)
        for slot, os in occ.items():
            lab = hist[os[0][0]][1][os[0][1]][slot[1]][0]
            cols[(lab, slot[2])].append(slot)
        regs, sources, reg_vals = [], {}, []
        for col, slots in sorted(cols.items(), key=lambda kv: -sum(len(occ[s]) for s in kv[1])):
            vals = {}
            for sl in slots:
                for hi, p_ in occ[sl]:
                    vals[(hi, p_, col)] = hist[hi][1][p_][sl[1]][sl[2]]       # keyed by column: two columns can share an event
            os = sorted(vals, key=lambda o: (o[0], o[1]))
            val = vals.__getitem__
            src = None
            for f in self.f["numeric"]:
                if all(SP._veq(hist[o[0]][0][o[1]].get(f), val(o)) for o in os):
                    src = ("cur", f)
                    break
            if src is None:
                for i, rg in enumerate(regs):
                    if all(SP._veq(self._reg_value(rg, hist[o[0]][0], traces[o[0]], o[1]), val(o)) for o in os):
                        src = ("reg", i)
                        break
            if src is None:                           # merge: one register re-searched over its old evidence + this column
                for i in range(len(regs)):
                    both = {**reg_vals[i], **vals}
                    keys = sorted(both, key=lambda o: (o[0], o[1]))
                    rg = self._search_register(hist, traces, keys, both.__getitem__, max(1.0, max_s - (_t.process_time() - t0)))
                    if rg is not None:
                        self._occam(rg, hist, traces, keys, both.__getitem__)
                        regs[i], reg_vals[i], src = rg, both, ("reg", i)
                        break
            if src is None:
                rg = self._search_register(hist, traces, os, val, max(1.0, max_s - (_t.process_time() - t0)))
                if rg is None:
                    return super().learn_registers(hyp, max(1.0, max_s - (_t.process_time() - t0)))
                self._occam(rg, hist, traces, os, val)
                regs.append(rg)
                reg_vals.append(dict(vals))
                src = ("reg", len(regs) - 1)
                os2 = [(o[0], o[1]) for o in os]
                w = ("register", f"reg_{len(regs) - 1}", self._register_witness(hist, traces, os2, lambda hp: vals[(hp[0], hp[1], col)]), None)
                if all(x[1] != w[1] for x in self.witnesses if x[0] == "register"):
                    self.witnesses.append(w)
            for sl in slots:
                sources[sl] = src
        self._complete(hyp, regs, sources, occ, hist, traces)
        self.regs, self.sources = regs, sources
        return regs, sources

    def _bt(self, i, order, assign, cons, hist, traces, val, f, init, t0, max_s):
        """u5 backtracking with the size-5 update grammar."""
        import time as _t
        if _t.process_time() - t0 > max_s:
            return False
        if not self._check(cons.get(i - 1, []), assign, hist, traces, val, f, init):
            return False
        if i == len(order):
            return True
        t = order[i]
        lam = self.hyp_lam
        sib = [assign[u] for u in assign if u[1] == t[1] and lam.get(u) == lam.get(t)]
        for g in list(dict.fromkeys(sib + GRAMMAR5)):
            assign[t] = g
            if self._bt(i + 1, order, assign, cons, hist, traces, val, f, init, t0, max_s):
                return True
        del assign[t]
        return False


def coverage_cex(L, max_words=1200, rounds_cap=None):
    """Transition x continuation probes, reached through REGISTER-DIVERSE prefixes: each mode's access path, plus that
    path extended by one and two of the mode's value-changing self-loop symbols (so registers hold non-initial values)."""
    hyp = L.hyp
    alpha = L.alpha
    sufs = [()] + [(a,) for a in alpha] + [e for e in L.E if len(e) <= 3]
    sufs = list(dict.fromkeys(sufs))
    words = []
    for q, acc in sorted(hyp["access"].items()):
        loops = [a for a in alpha if hyp["delta"].get((q, a)) == q and hyp["lam"].get((q, a)) != ("q:invalid",)]
        prefixes = [tuple(acc)] + [tuple(acc) + (a,) for a in loops] + [tuple(acc) + (a, b) for a in loops for b in loops]
        for pre in prefixes:
            for a in alpha:
                for w in sufs:
                    words.append(pre + (a,) + tuple(w))
    words = list(dict.fromkeys(words))[:max_words]
    out = []
    for word in words:
        evs = L.make_events(word, fresh_values=True)
        L.n_mq += 1
        rows = L._query(evs)
        got = SP.run_machine(L.machine, evs)
        if not all(SP._rows_eq(g, w) for g, w in zip(got, rows)):
            out.append((evs, rows, word))
            if len(out) >= 12:
                break
    return out


def learn_class_covered(events, outputs, query, seed=0, max_s=60.0, rounds=6):
    L = Learner2(events, outputs, query, seed=seed, max_s=max_s)
    if L.key is None or L.ctrl is None:
        return None
    m = L.learn()
    cov = dict(rounds=0, cex=0)
    for _ in range(rounds):
        if m is None:
            break
        cex = coverage_cex(L)
        cov["rounds"] += 1
        if not cex:
            break
        cov["cex"] += len(cex)
        relabel = False
        for evs, rows, word in cex:
            if L._run_labels(L.hyp, word) != tuple(SP._labels(r) for r in rows):
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
    if m is None:
        return None
    src, name = SP.class_source(m, witnesses=L.witnesses)
    return dict(source=src, name=name, machine=m, witnesses=L.witnesses, queries=L.n_mq, fields=L.f, coverage=cov)


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def crossing_records(envs, labels, max_pairs=12, seed=0):
    """Hybrid records with two overlapping failure conditions (see module doc)."""
    ok = [e["r"] for e, l in zip(envs, labels) if l == "ok"]
    if not ok:
        return []
    fields = sorted({k for r in ok for k in r})
    numeric = {f for f in fields if all(_isnum(r.get(f)) for r in ok)}
    seen = {f: {repr(r.get(f)) for r in ok} for f in fields if f not in numeric}

    def abnormal(r):
        out = {}
        for f in fields:
            v = r.get(f)
            if f in numeric and not _isnum(v):
                out[f] = v
            elif f not in numeric and f in seen and repr(v) not in seen[f] and len(seen[f]) <= 40:
                out[f] = v
        return out
    byl = {}
    for e, l in zip(envs, labels):
        if l != "ok":
            byl.setdefault(l, []).append(e)
    rnd = random.Random(seed)
    res = []
    for l1, l2 in itertools.combinations(sorted(byl), 2):
        for _ in range(max_pairs // max(1, len(byl))):
            e1, e2 = rnd.choice(byl[l1]), rnd.choice(byl[l2])
            a2 = abnormal(e2["r"])
            if not a2:
                continue
            r = dict(e1["r"], **a2)
            res.append(dict(e1, r=r))
    return res
