"""Three-level state learning (NOT LOCKED).

Level 1 - the task learner (`Learner3`, built on t7_repair.Learner2): continuation splitting for control modes, column-level
register search, coverage certification, with an explicit, GROWABLE hypothesis space
    H = {max_regs, depth (update size 3 | 5), merge (register merging on/off), max_states}
plus two Part-1 options: grey-box contract filtering (a kind declared not to read the value field may not use x in any update)
and version-space querying (keep up to K competing register programs; query only continuations on which they disagree;
certify on a sample of the coverage words instead of all of them).
Level 2 - growth policies (meta-learned or not): when learning fails, a FAILURE SIGNATURE is computed and a policy picks one
hypothesis-space extension: add_register | add_control_mode | expand_update_depth | merge_registers | add_timer_or_window
(the last has no implementation in this hypothesis space - choosing it is a wasted step, which is honest). Task memory is
reset per episode; only the policy (a table of signature -> action values) persists.
Level 3 - the persistent learning procedure as an editable surface (`SURFACE`, used by oc_evolve): continuation-class weights,
the partition-revision rule, update-proposal order, and query-budget allocation."""
from __future__ import annotations

import random
import time

from nexus import t7_repair as TR
from nexus import u5_statesplit as SP

ACTIONS = ("add_register", "add_control_mode", "expand_update_depth", "merge_registers", "add_timer_or_window")
H0 = dict(max_regs=1, depth=3, merge=False, max_states=3)
H_FULL = dict(max_regs=3, depth=5, merge=True, max_states=14)                  # the f45da4e learner (all grown at once)
G3 = SP.GRAMMAR
G5 = TR.GRAMMAR5


def _uses_x(n):
    return "x" in SP.S._vars(n)


class RegCap(Exception):
    pass


class Learner3(TR.Learner2):
    def __init__(self, events, outputs, query, H, contract=None, seed=0, max_s=20.0, cache=None):
        super().__init__(events, outputs, query, seed=seed, max_s=max_s, max_states=H["max_states"])
        self.H, self.contract = dict(H), contract
        self.grammar = G5 if H["depth"] >= 5 else G3
        if cache is not None:
            self.cache = cache                                   # membership answers are reused across restarts (all arms)
        self.fail = None

    def _domain(self, t):
        g = self.grammar
        if self.contract and self.contract.get(t[1], {}).get("reads_value") is False:
            g = [n for n in g if not _uses_x(n)]
        return g

    def _bt(self, i, order, assign, cons, hist, traces, val, f, init, t0, max_s):
        if time.process_time() - t0 > max_s:
            raise TimeoutError
        if not self._check(cons.get(i - 1, []), assign, hist, traces, val, f, init):
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

    def learn_registers(self, hyp, max_s=10.0):
        try:
            return self._learn_registers_H(hyp, max_s)
        except TimeoutError:
            self.fail = dict(kind="timeout")
            return None
        except RegCap:
            self.fail = dict(kind="reg_cap")
            return None

    def _learn_registers_H(self, hyp, max_s):
        """Learner2's column-level search, honouring H (register cap; merging only when H['merge'])."""
        from collections import defaultdict
        t0 = time.process_time()
        self.hyp_lam = hyp["lam"]
        hist = self.histories() + self.extra_hist
        traces = [self._trace(hyp, evs) for evs, _ in hist]
        occ = defaultdict(list)
        for hi, ((evs, outs), tr) in enumerate(zip(hist, traces)):
            for p_, rows in enumerate(outs):
                for ri, r in enumerate(rows):
                    for vj in (1, 2):
                        if r[vj] is not None:
                            occ[(tr[p_], ri, vj)].append((hi, p_))
        cols = defaultdict(list)
        for slot, os in occ.items():
            cols[(hist[os[0][0]][1][os[0][1]][slot[1]][0], slot[2])].append(slot)
        regs, sources, reg_vals = [], {}, []
        for col, slots in sorted(cols.items(), key=lambda kv: -sum(len(occ[s]) for s in kv[1])):
            vals = {(hi, p_, col): hist[hi][1][p_][sl[1]][sl[2]] for sl in slots for hi, p_ in occ[sl]}
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
            if src is None and self.H["merge"]:
                for i in range(len(regs)):
                    both = {**reg_vals[i], **vals}
                    keys = sorted(both, key=lambda o: (o[0], o[1]))
                    rg = self._search_register(hist, traces, keys, both.__getitem__, max(0.5, max_s - (time.process_time() - t0)))
                    if rg is not None:
                        regs[i], reg_vals[i], src = rg, both, ("reg", i)
                        break
            if src is None:
                if len(regs) >= self.H["max_regs"]:
                    raise RegCap
                rg = self._search_register(hist, traces, os, val, max(0.5, max_s - (time.process_time() - t0)))
                if rg is None:
                    self.fail = dict(kind="unsat", column=col)
                    return None
                self._occam(rg, hist, traces, os, val)
                regs.append(rg)
                reg_vals.append(dict(vals))
                src = ("reg", len(regs) - 1)
            for sl in slots:
                sources[sl] = src
        self._complete(hyp, regs, sources, occ, hist, traces)
        self.regs, self.sources = regs, sources
        return regs, sources


def signature(L, cex):
    """Failure & conflict signature (discrete): what failed, and the shape of the persisting counterexamples."""
    f = (L.fail or {}).get("kind", "cex" if cex else "none")
    label = value = False
    resid = "none"
    for evs, rows, word in cex[:6]:
        got = SP.run_machine(L.machine, evs) if L.machine else []
        for g, w, e in zip(got, rows, evs):
            if [r[0] for r in g] != [r[0] for r in w]:
                label = True
            elif not SP._rows_eq(g, w):
                value = True
                for a, b in zip(g, w):
                    for x, y in zip(a[1:], b[1:]):
                        if x is not None and y is not None and abs(x - y) > 1e-6:
                            v = e.get(L.f["numeric"][0]) if L.f.get("numeric") else None
                            vv = [e.get(n) for n in L.f.get("numeric", [])]
                            if any(isinstance(z, (int, float)) and abs((y - x) - z) < 1e-6 for z in vv):
                                resid = "missing_x"
                            elif any(abs(y - z) < 1e-6 for r in g for z in r[1:] if z is not None):
                                resid = "other_column"
                            else:
                                resid = "other"
                            _ = v
    states_full = L.hyp is not None and L.hyp["n"] >= L.H["max_states"]
    return (f, label, value, resid, states_full, L.H["max_regs"], L.H["depth"], L.H["merge"])


def apply(a, H):
    H = dict(H)
    if a == "add_register" and H["max_regs"] < 3:
        H["max_regs"] += 1
    elif a == "add_control_mode" and H["max_states"] < 16:
        H["max_states"] = min(16, H["max_states"] * 2)
    elif a == "expand_update_depth" and H["depth"] < 5:
        H["depth"] = 5
    elif a == "merge_registers" and not H["merge"]:
        H["merge"] = True
    else:
        return H, False                                           # no-op (already grown, or unsupported)
    return H, True


def available(H):
    return [a for a in ACTIONS if apply(a, H)[1]] + ["add_timer_or_window"]


def attempt(ep, H, contract=None, version_space=False, cache=None, seed=0, cov_sample=1.0):
    """One learning attempt with hypothesis space H. Returns (certified, learner, cex)."""
    L = Learner3(ep.train, ep.y_train, ep.query, H, contract=contract, seed=seed, cache=cache)
    if L.key is None or L.ctrl is None:
        return False, L, []
    hyp = L.learn_control()
    L.hyp = hyp
    if L.learn_registers(hyp) is None:
        L.machine = None
        return False, L, []
    L.machine = L._machine(hyp)
    for _ in range(4):                                            # covered relearning rounds inside the attempt
        cex = TR.coverage_cex(L, max_words=int(1200 * cov_sample)) if not version_space else vs_cex(L, cov_sample)
        if not cex:
            return True, L, []
        relabel = False
        for evs, rows, word in cex:
            if L._run_labels(L.hyp, word) != tuple(SP._labels(r) for r in rows):
                relabel = True
                for i in range(len(word)):
                    if tuple(word[i:]) not in L.E:
                        L.E.append(tuple(word[i:]))
            else:
                L.extra_hist.append((evs, rows))
        if relabel:
            L.hyp = L.learn_control_continue()
        if L.learn_registers(L.hyp) is None:
            L.machine = None
            return False, L, cex
        L.machine = L._machine(L.hyp)
    cex = TR.coverage_cex(L, max_words=int(1200 * cov_sample)) if not version_space else vs_cex(L, cov_sample)
    return not cex, L, cex


def vs_cex(L, sample):
    """Version-space querying: competing explanations = the current machine and its single-update variants (each register
    update on each transition swapped for another grammar element) that still fit ALL evidence; a word is queried only if
    the live candidates disagree on it; then a certification sample of the coverage words."""
    rnd = random.Random(len(L.extra_hist))
    hyp = L.hyp
    hist = L.histories() + L.extra_hist
    traces = [L._trace(hyp, evs) for evs, _ in hist]
    cands = [L.machine]
    for i, rg in enumerate(L.machine["regs"]):
        for t in list(rg["upd"]) + [t for t in hyp["delta"] if t not in rg["upd"]][:6]:
            for g in L._domain(t)[:12]:
                if rg["upd"].get(t) == g:
                    continue
                m2 = dict(L.machine, regs=[dict(r, upd=dict(r["upd"])) for r in L.machine["regs"]])
                m2["regs"][i]["upd"][t] = g
                if all(SP._rows_eq(a, b) for (evs, outs) in hist for a, b in zip(SP.run_machine(m2, evs), outs)):
                    cands.append(m2)
                if len(cands) > 8:
                    break
    words = []
    for q, acc in sorted(hyp["access"].items()):
        loops = [a for a in L.alpha if hyp["delta"].get((q, a)) == q and hyp["lam"].get((q, a)) != ("q:invalid",)]
        for pre in [tuple(acc)] + [tuple(acc) + (a,) for a in loops]:
            for a in L.alpha:
                for w in [()] + [(b,) for b in L.alpha]:
                    words.append(pre + (a,) + w)
    words = list(dict.fromkeys(words))
    out = []
    if len(cands) > 1:
        for word in words:
            evs = L.make_events(word, fresh_values=True)
            outs = [SP.run_machine(m, evs) for m in cands]
            if any(not all(SP._rows_eq(a, b) for a, b in zip(outs[0], o)) for o in outs[1:]):
                L.n_mq += 1
                rows = L._query(evs)
                if not all(SP._rows_eq(g, w) for g, w in zip(outs[0], rows)):
                    out.append((evs, rows, word))
                    if len(out) >= 6:
                        return out
                cands = [m for m, o in zip(cands, outs) if all(SP._rows_eq(a, b) for a, b in zip(o, rows))] or cands[:1]
                if len(cands) <= 1:
                    break
    for word in rnd.sample(words, max(1, int(len(words) * sample))):              # certification sample
        evs = L.make_events(word, fresh_values=True)
        L.n_mq += 1
        rows = L._query(evs)
        if not all(SP._rows_eq(g, w) for g, w in zip(SP.run_machine(L.machine, evs), rows)):
            out.append((evs, rows, word))
            if len(out) >= 6:
                break
    return out


def learn_episode(ep, policy, H0_=None, max_steps=6, contract=False, version_space=False, seed=0, cov_sample=1.0, log=None):
    """Grow the hypothesis space under `policy(signature, H, rnd) -> action` until certified or max_steps.
    Returns dict(certified, exact, key_acc, queries, cpu_s, steps, actions)."""
    t0 = time.process_time()
    rnd = random.Random(seed)
    H = dict(H0_ or H0)
    cache, actions = {}, []
    q0 = ep.n_queries
    L = None
    for step in range(max_steps):
        ok, L, cex = attempt(ep, H, ep.contract if contract else None, version_space, cache, seed, cov_sample)
        if ok:
            break
        sig = signature(L, cex)
        a = policy(sig, H, rnd)
        actions.append((sig, a))
        if log is not None:
            log.append(dict(seed=ep.seed, step=step, sig=list(sig), action=a))
        H, _ = apply(a, H)
    certified = bool(L and L.machine) and ok
    sc = dict(exact=False, key_acc=0.0)
    if L is not None and L.machine:
        src, name = SP.class_source(L.machine, witnesses=L.witnesses)
        cls = SP.compile_class(src, name)
        sc = ep.score(lambda evs: SP.run_class(cls, evs))
    return dict(certified=certified, exact=sc["exact"], key_acc=round(sc["key_acc"], 4), queries=ep.n_queries - q0,
                cpu_s=round(time.process_time() - t0, 3), steps=len(actions), actions=[a for _, a in actions], H=H,
                silent=certified and not sc["exact"])


# ------------------------------------------------------------------------------------------------ growth policies
HAND = ("add_control_mode", "expand_update_depth", "add_register", "merge_registers", "add_register", "add_control_mode")


def hand_policy(sig, H, rnd):
    for a in HAND:
        if apply(a, H)[1]:
            return a
    return "add_timer_or_window"


def random_policy(sig, H, rnd):
    return rnd.choice(available(H))


def sig_key(sig):
    return tuple(sig[:5])


class TablePolicy:
    """Meta-learned growth rule: value table V[signature][action] = mean of (resolved within 2 steps) - 0.02 * steps used,
    estimated on meta-training episodes; ties / unseen signatures fall back to the hand order."""

    def __init__(self, records, prior=1.0):
        from collections import defaultdict
        self.V = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
        for r in records:
            s = self.V[sig_key(r["sig"])][r["action"]]
            s[0] += r["reward"]
            s[1] += 1
        self.prior = prior

    def __call__(self, sig, H, rnd):
        opts = [a for a in available(H)]
        row = self.V.get(sig_key(sig), {})
        best, bv = None, -1e9
        for a in opts:
            tot, n = row.get(a, [0.0, 0.0])
            v = (tot + 0.5 * self.prior) / (n + self.prior) if n else None
            if v is not None and v > bv:
                best, bv = a, v
        return best or hand_policy(sig, H, rnd)
