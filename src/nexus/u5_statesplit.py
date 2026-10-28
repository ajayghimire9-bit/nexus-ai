"""Pillar 1 - state-distinction discovery by continuation splitting, and non-dictionary class invention (NOT LOCKED).

Given only an event stream, the oracle's per-event outputs and membership queries (learner-built streams the oracle
labels; every query is counted), NEXUS invents a stateful Python class:

 1. fields  - the entity key is the field for which per-key sub-streams reproduce the oracle's outputs (checked by query);
              the control field is the categorical field with the highest mutual information with the output labels
 2. control states by CONTINUATION SPLITTING (an L*-style observation table for Mealy machines): histories h are rows,
              continuations w are columns, T(h, w) = output labels of w after h. Two histories share a state until a
              continuation w separates them; each separation (h1, h2, w) creates a new control mode and is recorded as the
              witness for that mode. Counterexamples (from the example stream, then random probe words) add their suffixes
              as new continuations (Maler-Pnueli). No state names, counts or transition tables are given.
 3. data registers - when emitted VALUES are not fields of the current event, a register self.reg_i is created; its
              update rule on every observed transition is searched (backtracking with constraint pruning) over update
              expressions enumerated from primitives over (acc, x, 0, 1) with + and - (observationally distinct on probe
              values). Witness: two histories in the same control mode whose same continuation emits different values.
 4. value-level equivalence (CEGIS): random probe words with fresh values are labelled by the oracle; a control mismatch
              refines the table, a value mismatch adds the probe to the examples and repeats the register search.
 5. emission: `class StateMachine_<id>` with __init__ (per-key mode and register dicts), ingest(rec) (if/elif over
              discovered modes and symbols; outputs from the registers BEFORE the update), and an explicit unknown-symbol
              signal ('?unknown') that the operator's monitor turns into an alarm.

Baselines (the Pillar 1 comparison): FlatDict - the flat per-key dictionary template (last record per key; output looked up
by (previous kind, current kind) with values copied from the current or previous record); Stateless - output a function
of the current record only."""
from __future__ import annotations

import hashlib
import itertools
import math
import random
import time
from collections import Counter, defaultdict

from nexus import oop_synthesizer as S

UNKNOWN = ("?unknown", None, None)


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _veq(a, b):
    if a is None or b is None:
        return a is None and b is None
    if _isnum(a) and _isnum(b):
        return abs(a - b) <= 1e-6 * max(1.0, abs(b))
    return a == b


def _labels(rows):
    return tuple(r[0] for r in rows)


# ------------------------------------------------------------------------------------------------ update grammar
def update_grammar():
    """Register update expressions over (acc, x) built from primitives: terminals acc, x, 0, 1; + and -; size <= 3;
    one representative per observational-equivalence class on random probe pairs (smallest first)."""
    rnd = random.Random(7)
    probes = [(rnd.uniform(-50, 50), rnd.uniform(-50, 50)) for _ in range(12)]
    terms = [("var", "acc"), ("var", "x"), ("const", 0), ("const", 1)]
    cand = list(terms) + [("b", op, a, b) for op in ("+", "-") for a in terms for b in terms]
    seen, out = set(), []
    for n in sorted(cand, key=S.size):
        sig = tuple(round(S.ev(n, {"acc": a, "x": x}), 9) for a, x in probes)
        if sig not in seen:
            seen.add(sig)
            out.append(n)
    keep = ("var", "acc")
    out.remove(keep)
    return [keep] + out                                       # 'keep' first: unobserved / invalid transitions keep


GRAMMAR = update_grammar()


# ------------------------------------------------------------------------------------------------ field discovery
def discover_fields(events, outputs, query, max_alpha=12):
    fields = sorted({k for e in events for k in e})
    labels = [_labels(r) for r in outputs]
    cat, keys = [], []
    for f in fields:
        vals = [e.get(f) for e in events]
        d = set(map(repr, vals))
        if all(isinstance(v, str) for v in vals) and 1 < len(d) <= max_alpha:
            cat.append(f)
        if len(d) > max_alpha and len(d) < 0.8 * len(vals) and not _monotone(vals):
            keys.append(f)

    def mi(f):
        a = [e.get(f) for e in events]
        return _mi(a, labels)
    cat.sort(key=mi, reverse=True)
    key = None
    for f in sorted(keys, key=lambda f: -len({e.get(f) for e in events})):
        if _key_ok(f, events, outputs, query):
            key = f
            break
    nums = [f for f in fields if f != key and all(_isnum(e.get(f)) for e in events) and not _monotone([e.get(f) for e in events])]
    return dict(key=key, ctrl=cat[0] if cat else None, ctrl_candidates=cat, numeric=nums)


def _monotone(vals):
    return all(_isnum(v) for v in vals) and all(a < b for a, b in zip(vals, vals[1:]))


def _mi(a, b):
    n = len(a)
    a = [repr(x) for x in a]
    ca, cb, cab = Counter(a), Counter(b), Counter(zip(a, b))
    return sum(c / n * math.log((c / n) / (ca[x] / n * cb[y] / n)) for (x, y), c in cab.items())


def _key_ok(f, events, outputs, query, n_keys=3):
    groups = defaultdict(list)
    for i, e in enumerate(events):
        groups[e.get(f)].append(i)
    big = sorted(groups.values(), key=len, reverse=True)[:n_keys]
    for idx in big:
        sub = [events[i] for i in idx]
        got = query(sub)
        if any(_labels(g) != _labels(outputs[i]) for g, i in zip(got, idx)):
            return False
    return True


# ------------------------------------------------------------------------------------------------ the learner
class Learner:
    def __init__(self, events, outputs, query, fields=None, max_states=14, max_queries=4000, seed=0, max_s=60.0):
        self.t0 = time.process_time()
        self.max_s = max_s
        self.events, self.outputs, self._query = list(events), list(outputs), query
        self.f = fields or discover_fields(events, outputs, query)
        self.key, self.ctrl = self.f["key"], self.f["ctrl"]
        self.rnd = random.Random(seed)
        self.alpha = sorted({e.get(self.ctrl) for e in events})
        self.templates = defaultdict(list)
        for e in events:
            self.templates[e.get(self.ctrl)].append(e)
        self.cache = {}
        self.max_states, self.max_queries = max_states, max_queries
        self.n_mq = 0
        self.witnesses = []                                    # (kind, h1, h2, w) for every state / register created
        self.probe_n = 0
        self.extra_hist = []                                   # value counterexamples (event list, rows list)

    # -------------------------------------------------------------- membership queries
    def _probe_key(self):
        self.probe_n += 1
        k0 = self.events[0].get(self.key)
        return f"probe{self.probe_n:06d}" if isinstance(k0, str) else 10 ** 9 + self.probe_n

    def make_events(self, word, fresh_values=False):
        k = self._probe_key()
        evs = []
        for j, s in enumerate(word):
            src = self.rnd.choice(self.templates[s]) if s in self.templates else dict(self.events[0], **{self.ctrl: s})
            e = dict(src)
            e[self.key] = k
            e[self.ctrl] = s
            if fresh_values:
                for f in self.f["numeric"]:
                    pool = [x.get(f) for x in self.events if _isnum(x.get(f))]
                    if pool:
                        e[f] = round(self.rnd.choice(pool) * self.rnd.uniform(0.5, 1.5), 2)
            evs.append(e)
        return evs

    def mq(self, word):
        word = tuple(word)
        if word not in self.cache:
            evs = self.make_events(word)
            self.n_mq += 1
            rows = self._query(evs)
            self.cache[word] = tuple(_labels(r) for r in rows)
        return self.cache[word]

    def T(self, s, e):
        return self.mq(s + e)[len(s):]

    def row(self, s):
        return tuple(self.T(s, e) for e in self.E)

    # -------------------------------------------------------------- L*-style continuation splitting
    def learn_control(self):
        self.S, self.E = [()], [(a,) for a in self.alpha]
        while True:
            self._close()
            hyp = self._hypothesis()
            cex = self._find_cex(hyp)
            if cex is None or len(self.S) >= self.max_states or self.n_mq >= self.max_queries or self._timeout():
                self.hyp = hyp
                return hyp
            for i in range(len(cex)):
                suf = tuple(cex[i:])
                if suf not in self.E:
                    self.E.append(suf)

    def _timeout(self):
        return time.process_time() - self.t0 > self.max_s

    def _close(self):
        changed = True
        while changed and len(self.S) < self.max_states:
            changed = False
            rows = {self.row(s): s for s in self.S}
            for s in list(self.S):
                for a in self.alpha:
                    r = self.row(s + (a,))
                    if r not in rows:
                        twin = self._closest(r, rows)
                        w = next((e for e, x, y in zip(self.E, r, self.row(twin)) if x != y), None)
                        self.witnesses.append(("mode", s + (a,), twin, w))
                        self.S.append(s + (a,))
                        rows[r] = s + (a,)
                        changed = True

    def _closest(self, r, rows):
        return max(rows.values(), key=lambda s: sum(x == y for x, y in zip(r, self.row(s))))

    def _hypothesis(self):
        rows = {}
        for s in self.S:
            rows.setdefault(self.row(s), len(rows))
        delta, lam = {}, {}
        for s in self.S:
            q = rows[self.row(s)]
            for a in self.alpha:
                delta[(q, a)] = rows.get(self.row(s + (a,)), q)
                lam[(q, a)] = self.T(s, (a,))[0]
        access = {}
        for s in self.S:
            access.setdefault(rows[self.row(s)], s)
        return dict(n=len(rows), delta=delta, lam=lam, access=access, init=rows[self.row(())])

    def _run_labels(self, hyp, word):
        q, out = hyp["init"], []
        for a in word:
            if (q, a) not in hyp["delta"]:
                out.append(("?",))
                continue
            out.append(hyp["lam"][(q, a)])
            q = hyp["delta"][(q, a)]
        return tuple(out)

    def histories(self, events=None, outputs=None):
        events = self.events if events is None else events
        outputs = self.outputs if outputs is None else outputs
        h = defaultdict(lambda: ([], []))
        for e, o in zip(events, outputs):
            w, os = h[e.get(self.key)]
            w.append(e)
            os.append(o)
        return list(h.values())

    def _find_cex(self, hyp, n_random=60, max_len=10):
        for evs, outs in self.histories():
            word = tuple(e.get(self.ctrl) for e in evs)
            if self._run_labels(hyp, word) != tuple(_labels(o) for o in outs):
                return word
        for _ in range(n_random):
            word = tuple(self.rnd.choice(self.alpha) for _ in range(self.rnd.randint(2, max_len)))
            if self._run_labels(hyp, word) != self.mq(word):
                return word
        return None

    # -------------------------------------------------------------- data registers
    def _trace(self, hyp, evs):
        q, tr = hyp["init"], []
        for e in evs:
            a = e.get(self.ctrl)
            tr.append((q, a))
            q = hyp["delta"].get((q, a), q)
        return tr

    def learn_registers(self, hyp, max_s=20.0):
        """Explain every emitted value: a field of the current event, else a register with searched update rules."""
        t0 = time.process_time()
        self.hyp_lam = hyp["lam"]
        hist = self.histories() + self.extra_hist
        occ = defaultdict(list)                       # slot (transition, row index, value index) -> [(hist id, pos)]
        traces = [self._trace(hyp, evs) for evs, _ in hist]
        for hi, ((evs, outs), tr) in enumerate(zip(hist, traces)):
            for p, rows in enumerate(outs):
                for ri, r in enumerate(rows):
                    for vj in (1, 2):
                        if r[vj] is not None:
                            occ[(tr[p], ri, vj)].append((hi, p))
        sources, regs = {}, []
        col_src = {}                                  # output column (label, value index) -> source used first
        for slot, os in sorted(occ.items(), key=lambda kv: -len(kv[1])):
            lab = hist[os[0][0]][1][os[0][1]][slot[1]][0]
            col = (lab, slot[2])
            def val(o):
                hi, p = o
                return hist[hi][1][p][slot[1]][slot[2]]
            src = None
            prior = col_src.get(col)                  # prior: the same output column keeps the same source
            if prior is not None:
                if prior[0] == "cur" and all(_veq(hist[hi][0][p].get(prior[1]), val((hi, p))) for hi, p in os):
                    src = prior
                elif prior[0] == "reg" and all(_veq(self._reg_value(regs[prior[1]], hist[hi][0], traces[hi], p), val((hi, p)))
                                               for hi, p in os):
                    src = prior
            for f in self.f["numeric"] if src is None else ():
                if all(_veq(hist[hi][0][p].get(f), val((hi, p))) for hi, p in os):
                    src = ("cur", f)
                    break
            if src is None:
                for i, rg in enumerate(regs):
                    if all(_veq(self._reg_value(rg, hist[hi][0], traces[hi], p), val((hi, p))) for hi, p in os):
                        src = ("reg", i)
                        break
            if src is None:
                rg = self._search_register(hist, traces, os, val, max(1.0, max_s - (time.process_time() - t0)))
                if rg is None:
                    return None
                self._occam(rg, hist, traces, os, val)
                regs.append(rg)
                src = ("reg", len(regs) - 1)
                w = ("register", f"reg_{len(regs) - 1}", self._register_witness(hist, traces, os, val), None)
                if all(x[1] != w[1] for x in self.witnesses if x[0] == "register"):
                    self.witnesses.append(w)
            sources[slot] = src
            col_src.setdefault(col, src)
        self._complete(hyp, regs, sources, occ, hist, traces)
        self.regs, self.sources = regs, sources
        return regs, sources

    def _complete(self, hyp, regs, sources, occ, hist, traces):
        """Prior: a transition with the same symbol and the same visible output labels as another performs the same
        register update (copied only if every example stays consistent)."""
        for i, rg in enumerate(regs):
            os = [(hi, p, slot) for slot, src in sources.items() if src == ("reg", i) for hi, p in occ[slot]]
            for t in sorted(hyp["delta"], key=str):
                if t in rg["upd"]:
                    continue
                cands = {S.src(g): g for u, g in rg["upd"].items() if u[1] == t[1] and hyp["lam"].get(u) == hyp["lam"].get(t)}
                if len(cands) != 1:
                    continue
                rg["upd"][t] = next(iter(cands.values()))
                if not all(_veq(self._reg_value(rg, hist[hi][0], traces[hi], p), hist[hi][1][p][slot[1]][slot[2]]) for hi, p, slot in os):
                    del rg["upd"][t]

    def _occam(self, rg, hist, traces, os, val):
        """Drop every update the examples do not need (the smallest consistent register program); unbind the field when
        no remaining update reads x."""
        for t in sorted(rg["upd"], key=str):
            if any(u != t and u[1] == t[1] and rg["upd"][u] == rg["upd"][t] and self.hyp_lam.get(u) == self.hyp_lam.get(t)
                   for u in rg["upd"]):
                continue                              # prior: the same symbol does the same update in every mode
            g = rg["upd"].pop(t)
            if not self._check(os, rg["upd"], hist, traces, val, rg["field"], rg["init"]):
                rg["upd"][t] = g
        if not any("x" in S._vars(g) for g in rg["upd"].values()):
            rg["field"] = None

    def _reg_value(self, rg, evs, tr, p):
        acc = rg["init"]
        for e, t in zip(evs[:p], tr[:p]):
            g = rg["upd"].get(t, GRAMMAR[0])
            x = e.get(rg["field"])
            acc = S.ev(g, {"acc": acc, "x": x if _isnum(x) else 0})
            if acc is S.ERR:
                return None
        return acc

    def _register_witness(self, hist, traces, os, val):
        by_state = defaultdict(list)
        for hi, p in os:
            by_state[traces[hi][p]].append((hi, p))
        for t, xs in by_state.items():
            for (h1, p1), (h2, p2) in itertools.combinations(xs, 2):
                if not _veq(val((h1, p1)), val((h2, p2))):
                    w1 = tuple(e.get(self.ctrl) for e in hist[h1][0][:p1])
                    w2 = tuple(e.get(self.ctrl) for e in hist[h2][0][:p2])
                    return dict(mode=t[0], h1=w1, h2=w2, w=(t[1],), v1=val((h1, p1)), v2=val((h2, p2)))
        return None

    def _search_register(self, hist, traces, os, val, max_s):
        t0 = time.process_time()
        need = sorted({hi for hi, _ in os})
        for f in self.f["numeric"]:
            vars_ = Counter(t for hi in need for t in traces[hi])
            order = [t for t, _ in vars_.most_common()]
            cons = defaultdict(list)                       # constraint check index: last variable needed -> occurrences
            pos = {t: i for i, t in enumerate(order)}
            for hi, p in os:
                ts = set(traces[hi][:p])
                last = max((pos[t] for t in ts), default=-1)
                cons[last].append((hi, p))
            for init in (0,):
                assign = {}
                if self._bt(0, order, assign, cons, hist, traces, val, f, init, t0, max_s):
                    upd = {t: g for t, g in assign.items() if g != GRAMMAR[0]}
                    return dict(field=f, init=init, upd=upd)
        return None

    def _bt(self, i, order, assign, cons, hist, traces, val, f, init, t0, max_s):
        if time.process_time() - t0 > max_s:
            return False
        if not self._check(cons.get(i - 1, []), assign, hist, traces, val, f, init):
            return False
        if i == len(order):
            return True
        t = order[i]
        lam = self.hyp_lam
        sib = [assign[u] for u in assign if u[1] == t[1] and lam.get(u) == lam.get(t)]
        opts = list(dict.fromkeys(sib + GRAMMAR))
        for g in opts:
            assign[t] = g
            if self._bt(i + 1, order, assign, cons, hist, traces, val, f, init, t0, max_s):
                return True
        del assign[t]
        return False

    def _check(self, occs, assign, hist, traces, val, f, init):
        rg = dict(field=f, init=init, upd=assign)
        return all(_veq(self._reg_value(rg, hist[hi][0], traces[hi], p), val((hi, p))) for hi, p in occs)

    # -------------------------------------------------------------- assembling and value-level CEGIS
    def learn(self, rounds=10):
        hyp = self.learn_control()
        for _ in range(rounds):
            if self.learn_registers(hyp) is None:
                self.machine = None
                return None
            self.machine = self._machine(hyp)
            cex = self._value_cex()
            if cex is None or self._timeout():
                return self.machine
            evs, rows, word = cex
            if self._run_labels(hyp, word) != tuple(_labels(r) for r in rows):
                for i in range(len(word)):
                    if tuple(word[i:]) not in self.E:
                        self.E.append(tuple(word[i:]))
                hyp = self.learn_control_continue()
            else:
                self.extra_hist.append((evs, rows))
        return self.machine

    def learn_control_continue(self):
        while True:
            self._close()
            hyp = self._hypothesis()
            cex = self._find_cex(hyp)
            if cex is None or len(self.S) >= self.max_states or self.n_mq >= self.max_queries or self._timeout():
                self.hyp = hyp
                return hyp
            for i in range(len(cex)):
                if tuple(cex[i:]) not in self.E:
                    self.E.append(tuple(cex[i:]))

    def _value_cex(self, n=80, max_len=10):
        for _ in range(n):
            word = tuple(self.rnd.choice(self.alpha) for _ in range(self.rnd.randint(2, max_len)))
            evs = self.make_events(word, fresh_values=True)
            self.n_mq += 1
            rows = self._query(evs)
            got = run_machine(self.machine, evs)
            if not all(_rows_eq(g, w) for g, w in zip(got, rows)):
                return evs, rows, word
        return None

    def _machine(self, hyp):
        return dict(key=self.key, ctrl=self.ctrl, n=hyp["n"], init=hyp["init"], delta=dict(hyp["delta"]), lam=dict(hyp["lam"]),
                    regs=[dict(r) for r in self.regs], sources=dict(self.sources), alpha=list(self.alpha))


def _rows_eq(g, w):
    return len(g) == len(w) and all(x[0] == y[0] and _veq(x[1], y[1]) and _veq(x[2], y[2]) for x, y in zip(g, w))


def run_machine(m, events):
    """Interpret a learned machine (used during learning; deployment runs the emitted class source)."""
    mode, regs, out = {}, defaultdict(dict), []
    for e in events:
        k, a = e.get(m["key"]), e.get(m["ctrl"])
        q = mode.get(k, m["init"])
        if (q, a) not in m["delta"]:
            out.append([UNKNOWN])
            continue
        vals = [regs[i].get(k, r["init"]) for i, r in enumerate(m["regs"])]
        rows = []
        for ri, lab in enumerate(m["lam"][(q, a)]):
            v = [None, None]
            for vj in (1, 2):
                src = m["sources"].get(((q, a), ri, vj))
                if src is None:
                    continue
                v[vj - 1] = e.get(src[1]) if src[0] == "cur" else vals[src[1]]
            rows.append((lab, v[0], v[1]))
        for i, r in enumerate(m["regs"]):
            g = r["upd"].get((q, a))
            if g is not None:
                x = e.get(r["field"])
                regs[i][k] = S.ev(g, {"acc": vals[i], "x": x if _isnum(x) else 0})
        mode[k] = m["delta"][(q, a)]
        out.append(rows)
    return out


# ------------------------------------------------------------------------------------------------ source emission
def class_source(m, cid=None, witnesses=()):
    cid = cid or hashlib.sha256(repr(sorted(map(repr, m["delta"].items()))).encode()).hexdigest()[:8]
    nreg = len(m["regs"])
    lines = [f"class StateMachine_{cid}:",
             f'    """Invented by continuation splitting: {m["n"]} control modes (mode_0 = start), {nreg} data register(s).']
    for w in witnesses[:12]:
        if w[0] == "mode":
            lines.append(f"    witness: histories {list(w[1])} vs {list(w[2])} differ after continuation {list(w[3]) if w[3] else []}")
        elif w[2]:
            d = w[2]
            lines.append(f"    witness {w[1]}: in mode_{d['mode']} histories {list(d['h1'])} / {list(d['h2'])} emit {d['v1']} / {d['v2']} after {list(d['w'])}")
    lines.append('    """')
    lines += ["", "    def __init__(self):", "        self.mode = {}"]
    lines += [f"        self.reg_{i} = {{}}" for i in range(nreg)]
    lines += ["", "    def ingest(self, rec):", f"        k, s = rec.get({m['key']!r}), rec.get({m['ctrl']!r})",
              f"        m = self.mode.get(k, {m['init']})"]
    for i, r in enumerate(m["regs"]):
        lines.append(f"        r{i} = self.reg_{i}.get(k, {r['init']!r})")
    for i, r in enumerate(m["regs"]):
        if r["field"] is None:
            continue
        lines.append(f"        x{i} = rec.get({r['field']!r})")
        lines.append(f"        x{i} = x{i} if isinstance(x{i}, (int, float)) and not isinstance(x{i}, bool) else 0")
    by_q = defaultdict(list)
    for (q, a), q2 in sorted(m["delta"].items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        by_q[q].append((a, q2))
    first_q = True
    for q in sorted(by_q):
        lines.append(f"        {'if' if first_q else 'elif'} m == {q}:")
        first_q = False
        first_a = True
        for a, q2 in by_q[q]:
            lines.append(f"            {'if' if first_a else 'elif'} s == {a!r}:")
            first_a = False
            body = []
            rows = []
            for ri, lab in enumerate(m["lam"][(q, a)]):
                v = []
                for vj in (1, 2):
                    src = m["sources"].get(((q, a), ri, vj))
                    v.append("None" if src is None else (f"rec.get({src[1]!r})" if src[0] == "cur" else f"r{src[1]}"))
                rows.append(f"({lab!r}, {v[0]}, {v[1]})")
            body.append(f"out = [{', '.join(rows)}]")
            for i, r in enumerate(m["regs"]):
                g = r["upd"].get((q, a))
                if g is not None:
                    body.append(f"self.reg_{i}[k] = {S.src(g).replace('acc', f'r{i}').replace('x', f'x{i}')}")
            if q2 != q:
                body.append(f"self.mode[k] = {q2}")
            body.append("return out")
            lines += ["                " + b for b in body]
    lines.append("        return [('?unknown', None, None)]   # a symbol never seen: the operator's monitor raises an alarm")
    return "\n".join(lines) + "\n", f"StateMachine_{cid}"


def compile_class(src, name):
    ns = {}
    exec(compile(src, f"<{name}>", "exec"), ns)               # noqa: S102  (NEXUS-generated code)
    return ns[name]


def run_class(cls, events):
    obj = cls()
    return [obj.ingest(e) for e in events]


# ------------------------------------------------------------------------------------------------ baselines
class FlatDict:
    """The flat per-key dictionary template: state = {key: last record}; output looked up by (previous kind, current kind),
    values copied from the current or the previous record (whichever field matches on the examples)."""

    def __init__(self, events, outputs, fields):
        self.key, self.ctrl, self.nums = fields["key"], fields["ctrl"], fields["numeric"]
        last, table = {}, defaultdict(Counter)
        for e, rows in zip(events, outputs):
            p = last.get(e.get(self.key))
            ctx = (p.get(self.ctrl) if p else None, e.get(self.ctrl))
            table[ctx][self._abstract(rows, e, p)] += 1
            last[e.get(self.key)] = e
        self.table = {c: cnt.most_common(1)[0][0] for c, cnt in table.items()}

    def _abstract(self, rows, e, p):
        out = []
        for r in rows:
            vs = []
            for v in r[1:]:
                if v is None:
                    vs.append(None)
                    continue
                src = next((("cur", f) for f in self.nums if _veq(e.get(f), v)), None)
                src = src or next((("prev", f) for f in self.nums if p and _veq(p.get(f), v)), ("const", v))
                vs.append(src)
            out.append((r[0],) + tuple(vs))
        return tuple(out)

    def run(self, events):
        last, out = {}, []
        for e in events:
            p = last.get(e.get(self.key))
            ab = self.table.get((p.get(self.ctrl) if p else None, e.get(self.ctrl)), ())
            rows = []
            for r in ab:
                vs = [None if s is None else (e.get(s[1]) if s[0] == "cur" else (p.get(s[1]) if s[0] == "prev" and p else s[1]))
                      for s in r[1:]]
                rows.append((r[0], vs[0], vs[1]))
            out.append(rows)
            last[e.get(self.key)] = e
        return out


class Stateless(FlatDict):
    def __init__(self, events, outputs, fields):
        self.key, self.ctrl, self.nums = fields["key"], fields["ctrl"], fields["numeric"]
        table = defaultdict(Counter)
        for e, rows in zip(events, outputs):
            table[(None, e.get(self.ctrl))][self._abstract(rows, e, None)] += 1
        self.table = {c: cnt.most_common(1)[0][0] for c, cnt in table.items()}

    def run(self, events):
        out = []
        for e in events:
            ab = self.table.get((None, e.get(self.ctrl)), ())
            out.append([(r[0],) + tuple(None if s is None else (e.get(s[1]) if s[0] == "cur" else s[1]) for s in r[1:]) for r in ab])
        return out


def markov_witness(events, outputs, fields):
    """Two events with identical current records (ignoring key / sequence) but different outputs: proof that no function
    of the current record suffices (the trigger for state invention)."""
    seen = {}
    ign = {fields["key"]}
    for e, rows in zip(events, outputs):
        sig = (e.get(fields["ctrl"]),)
        lab = _labels(rows)
        if sig in seen and seen[sig][1] != lab:
            return dict(record_kind=sig[0], outputs=(seen[sig][1], lab))
        seen.setdefault(sig, (e, lab))
    _ = ign
    return None


def learn_class(task_events, task_outputs, query, seed=0, max_s=60.0):
    """Full Pillar 1 pipeline. Returns dict(source, name, machine, witnesses, queries, cpu_s) or None."""
    t0 = time.process_time()
    L = Learner(task_events, task_outputs, query, seed=seed, max_s=max_s)
    if L.key is None or L.ctrl is None:
        return None
    mw = markov_witness(task_events, task_outputs, L.f)
    m = L.learn()
    if m is None:
        return dict(source=None, name=None, machine=None, witnesses=L.witnesses, queries=L.n_mq, cpu_s=time.process_time() - t0,
                    fields=L.f, markov=mw)
    src, name = class_source(m, witnesses=L.witnesses)
    return dict(source=src, name=name, machine=m, witnesses=L.witnesses, queries=L.n_mq, cpu_s=round(time.process_time() - t0, 3),
                fields=L.f, markov=mw, learner=L)
