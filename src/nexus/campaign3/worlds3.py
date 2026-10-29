"""Phase 3 world registry (NOT LOCKED): Phase 2's worlds (A-F + C5, C6, E5, E6, now Phase-2 comparison families) plus
four WHOLLY UNTOUCHED Phase 3 mechanism families, defined once here before any Phase 3 experiment and used ONLY by the
one-use Phase 3 untouched panel (generator self-checks only before Stage 4):
  C7 column occupancy profile: per-column count of coloured cells, or the column index with the most coloured cells
  C8 border frame: paint the outer border of the board with colour k (inner cells unchanged)
  E7 confounded additive effect: X = do or c0; Z = do or (c0 + 1) mod 4; Y = do or (X + Z) mod 4
  E8 threshold switch: X = do or c1; Y = do or (1 if X >= k else 0)"""
from nexus.campaign2 import worlds2 as W2
from nexus.campaign.worlds.base import Mech, build_task
from nexus.campaign.worlds import world_c_spatial as WC, world_e_causal as WE


def _occupancy(rng):
    v = rng.choice(("counts", "argmax"))

    def counts(g):
        T = WC._T(g)
        return tuple(sum(1 for x in c if x > 0) for c in T)
    if v == "counts":
        return counts, "l", "occupancy[counts]"
    return (lambda g: max(range(len(counts(g))), key=lambda j: (counts(g)[j], -j)) if g and g[0] else 0), "i", "occupancy[argmax]"


def _frame(rng):
    k = rng.randint(1, 4)

    def f(g):
        h = len(g)
        return tuple(tuple(k if (i in (0, h - 1) or j in (0, len(r) - 1)) else x for j, x in enumerate(r)) for i, r in enumerate(g))
    return f, f"frame[{k}]"


class _C3:
    WORLD, FAMILIES, Q_BUDGET = "C", W2.FAMILIES["C"] + ("C7", "C8"), WC.Q_BUDGET

    @staticmethod
    def gen(family, rng, level):
        if family == "C7":
            f, out, d = _occupancy(rng)
            return Mech(fn=lambda x: f(x[0]), sig=("L",), out=out, descr=d, train=WC._tr, iface=WC._if)
        if family == "C8":
            f, d = _frame(rng)
            return Mech(fn=lambda x: f(x[0]), sig=("L",), out="L", descr=d, train=WC._tr, iface=WC._if)
        return W2.WORLDS["C"].gen(family, rng, level)

    @staticmethod
    def posts(family, rng):
        return [] if family in ("C7", "C8") else W2.WORLDS["C"].posts(family, rng)


class _E3:
    WORLD, FAMILIES, Q_BUDGET = "E", W2.FAMILIES["E"] + ("E7", "E8"), WE.Q_BUDGET

    @staticmethod
    def gen(family, rng, level):
        obs = lambda r: ((-1, -1, -1), WE._ctx(r, 3))           # noqa: E731
        itv = lambda r: (WE._do(r, 3), WE._ctx(r, 3))         # noqa: E731
        if family == "E7":
            def f(x):
                d, c = x
                X = WE._co(d[0], c[0])
                Z = WE._co(d[1], (c[0] + 1) % 4)
                return WE._co(d[2], (X + Z) % 4)
            return Mech(fn=f, sig=("l", "l"), out="i", descr="confadd[Y=X+Z]", train=obs, iface=itv, verify_kind="interventional")
        if family == "E8":
            k = rng.randint(1, 3)

            def g(x):
                d, c = x
                X = WE._co(d[0], c[1])
                return WE._co(d[1], 1 if X >= k else 0)
            return Mech(fn=g, sig=("l", "l"), out="i", descr=f"thresh[X>={k}]", train=obs, iface=itv, verify_kind="interventional")
        return W2.WORLDS["E"].gen(family, rng, level)

    @staticmethod
    def posts(family, rng):
        return [] if family in ("E7", "E8") else W2.WORLDS["E"].posts(family, rng)


WORLDS = dict(W2.WORLDS, C=_C3, E=_E3)
FAMILIES = {w: m.FAMILIES for w, m in WORLDS.items()}
UNTOUCHED3 = (("C", "C7"), ("C", "C8"), ("E", "E7"), ("E", "E8"))
PHASE2_COMPARISON = W2.UNTOUCHED


def make_task3(world, family, level, seed, role, partners):
    t = build_task(WORLDS, world, family, level, seed, role, partners, WORLDS[world].Q_BUDGET)
    pure = world == "F" and seed % 2 == 1
    t.meta["pure_synthesis"] = pure
    t.view = lambda t=t, pure=pure: W2.TaskView2(t, pure)
    return t
