"""Trial 3 - joint failure-constraint tool invention + phantom-state retrodiction (NOT LOCKED).

Families (per-key streams; outputs per event):
  U  undo editor:       ADD v (x += v), SUB v (x -= v), UNDO (revert the last un-undone ADD/SUB), SHOW (emit x)
  T  transactions:      BEGIN, SET v (x = v), COMMIT, ROLLBACK (restore the value at the matching BEGIN), READ (emit x)
  withheld  S savepoint ledger: MARK, INC v, DROP, RESTORE, SHOW;  C composition: ADD, SUB, UNDO, BEGIN, ROLLBACK, SHOW
            (one shared history)
Declared bounded space (the existing learner's): one numeric register with per-symbol updates from the grammar
G = {keep, x+v, x-v, v, 0}. Bounded infeasibility = the complete backtracking search over G^|symbols| returns UNSAT (it is
finite and is run to exhaustion - a timeout never counts); the counterexample histories are then minimised by delta
debugging while UNSAT is preserved.
Representation grammar (for invention and for direct search): state = (x, S) with S a 'stack' | 'queue' | 'none' of
snapshots of x; per symbol an op = (g in G, s in {none, push, pop_restore, pop_discard}, emit?) applied as: push stores x
BEFORE g; pop_restore sets x to the popped snapshot (empty: no-op); emit outputs ('value', x) AFTER the update.
Phantom-state retrodiction: emitted values are the observed boundary of the hidden trajectory; working backwards from each
emit, the value x must have had before the preceding event is abduced, and every op whose g / s cannot produce the abduced
pair is cut from that symbol's domain before the joint backtracking search."""
from __future__ import annotations

import itertools
import random
import time

G = ("keep", "add", "sub", "set", "zero")
SACT = ("none", "push", "pop_restore", "pop_discard")
FAMS = {"U": ["ADD", "SUB", "UNDO", "SHOW"], "T": ["BEGIN", "SET", "COMMIT", "ROLLBACK", "READ"],
        "S": ["MARK", "INC", "DROP", "RESTORE", "SHOW"], "C": ["ADD", "SUB", "UNDO", "BEGIN", "ROLLBACK", "SHOW"]}


def _g(g, x, v):
    return x if g == "keep" else x + v if g == "add" else x - v if g == "sub" else v if g == "set" else 0


def reference(fam, events):
    """Author-written oracle (black box to learners)."""
    out, st = [], {}
    for k, s, v in events:
        x, S = st.get(k, (0, []))
        S = list(S)
        if fam == "U" or fam == "C":
            if s in ("ADD", "SUB"):
                S.append(("u", x))
                x = x + v if s == "ADD" else x - v
            elif s == "UNDO" and S:
                x = S.pop()[1]
            elif s == "BEGIN":
                S.append(("t", x))
            elif s == "ROLLBACK" and S:
                x = S.pop()[1]
        if fam == "T":
            if s == "BEGIN":
                S.append(("t", x))
            elif s == "SET":
                x = v
            elif s == "COMMIT" and S:
                S.pop()
            elif s == "ROLLBACK" and S:
                x = S.pop()[1]
        if fam == "S":
            if s == "MARK":
                S.append(("m", x))
            elif s == "INC":
                x = x + v
            elif s == "DROP" and S:
                S.pop()
            elif s == "RESTORE" and S:
                x = S.pop()[1]
        st[k] = (x, S)
        out.append([("value", x)] if s in ("SHOW", "READ") else [])
    return out


WEIGHTS = {"U": [25, 15, 25, 35], "T": [20, 30, 15, 15, 20], "S": [20, 30, 15, 15, 20], "C": [20, 10, 15, 15, 15, 25]}


def gen(fam, seed, n_keys=30, min_len=6, max_len=20):
    rnd = random.Random(f"t7-jt-{fam}-{seed}")
    per = [[(f"k{i}", rnd.choices(FAMS[fam], WEIGHTS[fam])[0], rnd.randint(1, 9)) for _ in range(rnd.randint(min_len, max_len))]
           for i in range(n_keys)]
    evs, idx = [], [0] * n_keys
    live = list(range(n_keys))
    while live:                                                  # random interleaving; per-key order kept
        i = rnd.choice(live)
        evs.append(per[i][idx[i]])
        idx[i] += 1
        if idx[i] >= len(per[i]):
            live.remove(i)
    return evs


def histories(events, outputs):
    h = {}
    for (k, s, v), o in zip(events, outputs):
        h.setdefault(k, []).append((s, v, o))
    return list(h.values())


# ------------------------------------------------------------------------------------------------ bounded space (UNSAT proof)
def bounded_unsat(hists, symbols):
    """Complete search over one register with per-symbol g in G (emit iff the event emitted). Returns (unsat, nodes)."""
    nodes = 0
    for assign in itertools.product(G, repeat=len(symbols)):
        nodes += 1
        a = dict(zip(symbols, assign))
        if all(_sim_reg(a, h) for h in hists):
            return False, nodes
    return True, nodes


def _sim_reg(a, h):
    x = 0
    for s, v, o in h:
        x = _g(a[s], x, v)
        if o and abs(o[0][1] - x) > 1e-9:
            return False
    return True


def ddmin_unsat(hists, symbols):
    """Delta debugging: a minimal subset of counterexample histories that keeps the bounded space UNSAT."""
    cur = list(hists)
    n = 2
    while len(cur) >= 2:
        chunk = max(1, len(cur) // n)
        reduced = False
        for i in range(0, len(cur), chunk):
            cand = cur[:i] + cur[i + chunk:]
            if cand and bounded_unsat(cand, symbols)[0]:
                cur, n, reduced = cand, max(2, n - 1), True
                break
        if not reduced:
            if n >= len(cur):
                break
            n = min(len(cur), n * 2)
    return cur


# ------------------------------------------------------------------------------------------------ representation search
OPS = [(g, s) for g in G for s in SACT]


def _sim(rep, a, h):
    x, S = 0, []
    for s, v, o in h:
        g, sa = a[s]
        if sa == "push" and rep != "none":
            S.append(x)
        x = _g(g, x, v)
        if sa in ("pop_restore", "pop_discard") and rep != "none" and S:
            y = S.pop() if rep == "stack" else S.pop(0)
            if sa == "pop_restore":
                x = y
        if o and abs(o[0][1] - x) > 1e-9:
            return False
    return True


def retrodict_domains(hists, symbols):
    """Cut per-symbol op domains with abduced phantom states: for every pattern emit -> event(s) -> emit with exactly one
    event between two emits, the op must map the abduced x_before (previous emit) to x_after (next emit) - unless it pops
    (a restore can produce any earlier abduced value)."""
    dom = {s: set(OPS) for s in symbols}
    for h in hists:
        for i in range(1, len(h) - 1):
            if h[i - 1][2] and h[i + 1][2] and not h[i][2]:
                xb, xa = h[i - 1][2][0][1], h[i + 1][2][0][1]
                s, v = h[i][0], h[i][1]
                # the emitting events themselves keep x (if they had an update, x would not be their emitted value)
                ok = set()
                for g, sa in dom[s]:
                    if sa == "pop_restore" or abs(_g(g, xb, v) - xa) < 1e-9:
                        ok.add((g, sa))
                dom[s] = ok or dom[s]
    return dom


def search(hists, symbols, reps, budget_s, dom=None, t0=None):
    """Backtracking over per-symbol ops (symbols ordered by frequency), checking every history whose symbols are all
    assigned. Returns (rep, assignment, nodes, exhausted)."""
    t0 = t0 or time.process_time()
    dom = dom or {s: list(OPS) for s in symbols}
    freq = {s: sum(1 for h in hists for e in h if e[0] == s) for s in symbols}
    order = sorted(symbols, key=lambda s: -freq[s])
    nodes = [0]
    for rep in reps:
        need = [set(e[0] for e in h) for h in hists]

        def bt(i, a):
            nodes[0] += 1
            if time.process_time() - t0 > budget_s:
                raise TimeoutError
            done = set(order[:i])
            if not all(_sim(rep, a, h) for h, nd in zip(hists, need) if nd <= done):
                return None
            if i == len(order):
                return dict(a)
            for op in sorted(dom[order[i]]):
                a[order[i]] = op
                r = bt(i + 1, a)
                if r:
                    return r
            a.pop(order[i], None)
            return None
        try:
            r = bt(0, {})
        except TimeoutError:
            return None, None, nodes[0], False
        if r:
            return rep, r, nodes[0], True
    return None, None, nodes[0], True


def run_program(rep, a, events):
    st, out = {}, []
    for k, s, v in events:
        x, S = st.get(k, (0, []))
        S = list(S)
        if s not in a:
            out.append([("?unknown", None)])
            continue
        g, sa = a[s]
        if sa == "push" and rep != "none":
            S.append(x)
        x = _g(g, x, v)
        if sa in ("pop_restore", "pop_discard") and rep != "none" and S:
            y = S.pop() if rep == "stack" else S.pop(0)
            if sa == "pop_restore":
                x = y
        st[k] = (x, S)
        out.append([("value", x)] if a.get(("emit", s)) else [])
    return out


def emits(events, outputs):
    return {s: bool(o) for (k, s, v), o in zip(events, outputs)}


def class_source(rep, a, fam):
    lines = [f"class Invented_{fam}:", f'    """State = (x, {rep} of snapshots of x), invented jointly from failure constraints."""',
             "", "    def __init__(self):", "        self.x, self.S = {}, {}", "", "    def ingest(self, key, sym, v):",
             "        x, S = self.x.get(key, 0), self.S.setdefault(key, [])"]
    for i, (s, (g, sa)) in enumerate(sorted((k, v) for k, v in a.items() if not isinstance(k, tuple))):
        lines.append(f"        {'if' if i == 0 else 'elif'} sym == {s!r}:")
        if sa == "push":
            lines.append("            S.append(x)")
        gx = {"keep": "x", "add": "x + v", "sub": "x - v", "set": "v", "zero": "0"}[g]
        if gx != "x":
            lines.append(f"            x = {gx}")
        if sa in ("pop_restore", "pop_discard"):
            pop = "S.pop()" if rep == "stack" else "S.pop(0)"
            lines.append(f"            if S:\n                {'x = ' if sa == 'pop_restore' else ''}{pop}")
        if a.get(("emit", s)):
            lines.append("            self.x[key] = x\n            return [('value', x)]")
    lines.append("        self.x[key] = x\n        return []")
    return "\n".join(lines) + "\n"
