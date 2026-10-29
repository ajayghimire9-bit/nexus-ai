"""World B - temporal state (signals and event streams; NOT LOCKED).
Inputs: a signal (tuple of ints; training values 0..6, interface 0..9) or an event stream (rows (kind, value); training
kinds 0..2, interface kinds 0..3, i.e. an unseen event kind). Outputs are per-step state traces.
Verification: bounded exhaustive equivalence on every signal of length <= 3 over 0..9 (event streams: length <= 2 over
kinds 0..3 x values 0..3) plus 30 hidden interface inputs.
  B1 sliding windows & running differences   B2 hysteresis & threshold latches
  B3 guarded session lifecycles & cooldown timers   B4 coupled multi-register updates, delayed emission, conditional reset"""
import itertools

from .base import Mech, Post, exhaustive_lists

WORLD = "B"
FAMILIES = ("B1", "B2", "B3", "B4")
Q_BUDGET = 4


def _sig_tr(r):
    return (tuple(r.randint(0, 6) for _ in range(r.randint(4, 8))),)


def _sig_if(r):
    return (tuple(r.randint(0, 9) for _ in range(r.randint(0, 9))),)


def _ev_tr(r):
    return (tuple((r.randint(0, 2), r.randint(0, 6)) for _ in range(r.randint(4, 7))),)


def _ev_if(r):
    return (tuple((r.randint(0, 3), r.randint(0, 9)) for _ in range(r.randint(0, 8))),)


def _ev_exh():
    ev = [(k, v) for k in range(4) for v in range(4)]
    return [(tuple(p),) for n in range(3) for p in itertools.product(ev, repeat=n)]


def _window(rng):
    v = rng.choice(("runsum", "rundiff", "runmax", "win2"))

    def f(s):
        if v == "runsum":
            return tuple(itertools.accumulate(s))
        if v == "runmax":
            return tuple(itertools.accumulate(s, max))
        if v == "rundiff":
            return tuple(s[t] - (s[t - 1] if t else 0) for t in range(len(s)))
        return tuple(s[t] + (s[t - 1] if t else 0) for t in range(len(s)))
    return f, f"window[{v}]"


def _latch(rng):
    if rng.random() < 0.5:
        c = rng.randint(2, 5)

        def f(s):
            out, st = [], 0
            for x in s:
                st = 1 if x > c else st
                out.append(st)
            return tuple(out)
        return f, f"latch[set>{c}]"
    lo = rng.randint(1, 3)
    hi = lo + rng.randint(2, 3)

    def g(s):
        out, st = [], 0
        for x in s:
            st = 1 if x >= hi else (0 if x <= lo else st)
            out.append(st)
        return tuple(out)
    return g, f"hysteresis[on>={hi},off<={lo}]"


def _session(rng):
    c = rng.randint(1, 5)
    if rng.random() < 0.5:
        def f(s):
            out, n = [], 0
            for x in s:
                n = 0 if x == c else n + 1
                out.append(n)
            return tuple(out)
        return f, f"since[=={c}]"
    k = rng.randint(2, 3)

    def g(s):
        out, cd = [], 0
        for x in s:
            cd = k if (x == c and cd == 0) else max(cd - 1, 0)
            out.append(cd)
        return tuple(out)
    return g, f"cooldown[trig=={c},k={k}]"


def _registers(rng):
    kind = rng.randint(0, 2)
    v = rng.choice(("total", "delayed", "reset"))
    rk = (kind + 1) % 3

    def f(E):
        out, tot, prev = [], 0, 0
        for (k, val) in E:
            if v == "reset" and k == rk:
                tot = 0
            elif k == kind:
                tot += val
            out.append(prev if v == "delayed" else tot)
            prev = tot
        return tuple(out)
    return f, f"registers[{v},kind={kind}{',reset=' + str(rk) if v == 'reset' else ''}]"


GEN = {"B1": _window, "B2": _latch, "B3": _session}


def gen(family, rng, level):
    if family in GEN:
        f, d = GEN[family](rng)
        return Mech(fn=lambda x: f(x[0]), sig=("l",), out="l", descr=d, train=_sig_tr, iface=_sig_if,
                    exhaustive=lambda: exhaustive_lists(3, range(10)), verify_kind="bounded_exhaustive+hidden")
    if family == "B4":
        f, d = _registers(rng)
        return Mech(fn=lambda x: f(x[0]), sig=("L",), out="l", descr=d, train=_ev_tr, iface=_ev_if, exhaustive=_ev_exh,
                    verify_kind="bounded_exhaustive+hidden")
    raise KeyError(family)


def posts(family, rng):
    if family in GEN:
        f, d = GEN[family](rng)
        return [Post(f, "l", "l", d)]
    if family == "B4":
        f, d = _registers(rng)
        return [Post(lambda L: f(tuple((r[0] if r else 0, r[1] if len(r) > 1 else 0) for r in L)), "L", "l", d)]
    return []
